import random
import copy
import math

from settings_io import normalize_settings, get_active_population_names
from event_stream import EventStream
from entity_state_snapshot import EntityStateSnapshot, collect_entity_state_snapshot
from social_lifecycle import (
    apply_health_after_survival,
    company_resilience_score,
    company_strategy_bonus,
    education_capital_from_child,
    government_policy_pressure_score,
    health_sickness_multiplier,
    labor_health_education_adjustment,
    medical_recovery_chance,
    reproductive_chance_with_security,
    reproductive_security_score,
)

GOOD_FIELDS = ["food", "medical_goods", "education_goods", "reproduction_goods", "tools"]
TRADED_GOODS = ["food", "medical_goods", "education_goods", "reproduction_goods"]
GOOD_DISPLAY = {
    "food": "Food",
    "medical_goods": "MedicalGoods",
    "education_goods": "EducationGoods",
    "reproduction_goods": "ReproductionGoods",
    "tools": "Tools",
}


# dev40：订单簿购买需求类型。
# 刚需和储备需求使用不同的预算释放规则：刚需优先释放现金，储备继续保持价格敏感和意愿敏感。
NEED_FOOD_HARD = "food_hard"
NEED_MEDICAL_HARD = "medical_hard"
NEED_REPRODUCTION_HARD = "reproduction_hard"
NEED_REPRODUCTION_RESERVE = "reproduction_reserve"
NEED_FOOD_RESERVE = "food_reserve"
NEED_MEDICAL_RESERVE = "medical_reserve"
NEED_EDUCATION = "education"
NEED_TOOLS = "tools"
HARD_NEED_KINDS = {NEED_FOOD_HARD, NEED_MEDICAL_HARD, NEED_REPRODUCTION_HARD}
RESERVE_NEED_KINDS = {NEED_REPRODUCTION_RESERVE, NEED_FOOD_RESERVE, NEED_MEDICAL_RESERVE}


def parse_round_list(value):
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        text = str(value).replace("，", ",").replace("；", ",").replace(";", ",").replace(" ", ",")
        raw_items = text.split(",")

    rounds = set()
    for item in raw_items:
        item = str(item).strip()
        if not item:
            continue
        try:
            number = int(item)
        except ValueError:
            continue
        if number >= 1:
            rounds.add(number)
    return rounds


class Individual:
    NEXT_ID = 0

    def __init__(self, cfg, parent=None, pop_config=None, birth_turn=0):
        self.cfg = cfg
        self.id = Individual.NEXT_ID
        Individual.NEXT_ID += 1
        self.birth_turn = birth_turn
        # dev21：唯一代号与祖先追踪。实际 code 会在 Environment 生成个体后统一赋值。
        self.code = ""
        self.ancestor_code = ""
        self.ancestor_index = 0
        self.lineage_sequence = 0
        self.employer_branch = ""
        self.wage_received = 0
        self.dividend_received = 0
        self.produced_goods_value = 0
        self.rich_tax_paid = 0

        if parent is None:
            self.morality = self.initial_fluctuate(pop_config["morality"], 0, 100, cfg["mutation"]["morality"])
            self.strength = self.initial_fluctuate(pop_config["strength"], cfg["base"]["min_strength"], cfg["base"]["max_strength"], cfg["mutation"]["strength"])
            self.enforce_ability_balance()
            self.reproduce = pop_config["reproduce"]
            self.labor = self.initial_fluctuate(pop_config["labor"], 0, 100, cfg["mutation"]["labor"])
        else:
            self.morality = self.mutate(parent.morality, 0, 100, cfg["mutation"]["morality"])
            self.strength = self.mutate(parent.strength, cfg["base"]["min_strength"], cfg["base"]["max_strength"], cfg["mutation"]["strength"])
            self.enforce_ability_balance()
            self.reproduce = self.mutate(parent.reproduce, cfg["base"]["min_reproduce"], cfg["base"]["max_reproduce"], cfg["mutation"]["reproduce"])
            self.labor = self.mutate(parent.labor, 0, 100, cfg["mutation"]["labor"])

        # BOT8 2.4.0：临时智慧来自教育机制，伴随个体一生。
        # 临时智慧不遗传，不计入智慧值和总能力限制，只在生产效率等需要“有效智慧”的地方参与计算。
        self.temp_intelligence = 0
        self.education_temp_intelligence_received = 0
        self.education_temp_intelligence_given = 0
        # CivitasLab M6A：生命周期科学化扩展（不包含工具机制）。
        # health_index 是 0-100 的健康资本；education_capital 是教育积累代理，
        # 二者会影响疾病风险、劳动参与、繁殖安全评分和演化适应度。
        self.health_index = 100
        self.education_capital = 0
        self.reproductive_security_score = 0
        self.reproductive_security_bonus = 0

        self.balance = cfg["base"]["initial_balance"]
        # BOT8 dev8：多商品库存。balance 暂时继续代表货币 money，生产阶段不再创造货币。
        # 食物用于生存；医疗用品用于生病后的生存回合；教育用品用于下一代临时智慧；生育用品用于繁殖；工具仅加入库存和输出，暂不实装效果。
        # dev11：只有初始个体获得基础商品库存；新生个体的商品必须来自父代、政府、市场或后续生产，避免出生凭空创造商品。
        if parent is None:
            self.food = int(cfg["base"].get("survival_cost", 100) * 3)
        else:
            self.food = 0
        # dev12：初始个体不再拥有医疗用品、教育用品和生育用品。
        # 这些物资必须通过生产、市场、政府库存或后续机制获得，避免开局隐性赠予过多功能商品。
        self.medical_goods = 0
        self.education_goods = 0
        self.reproduction_goods = 0
        self.tools = 0
        # BOT8 dev6：阶层与社会流动机制。初始个体记录出生阶层；子代会在繁殖阶段记录母代阶层。
        if parent is None:
            self.parent_class = "Initial"
            _, self.birth_class = self.class_rank_and_label(self.balance, cfg, pop_config)
        else:
            self.parent_class = ""
            self.birth_class = ""
        self.current_class = self.birth_class
        self.class_change = 0
        self.is_upward_mobile = 0
        self.is_downward_mobile = 0
        # BOT8 中的寿命不是现实年龄，而是可参与生存阶段的抽象生命周期。
        # dev29：初始族群不应被隐式视为同一批“刚出生个体”。当开启初始年龄分布时，
        # 初始个体会拥有不同的已生存回合数，并相应减少剩余 life；出生子代仍从 0 岁开始。
        base_life = random.randint(cfg["base"]["min_life"], cfg["base"]["max_life"])
        initial_age_rounds = 0
        if parent is None and bool(cfg["base"].get("enable_initial_age_distribution", True)):
            ratio = max(0, min(100, int(cfg["base"].get("initial_age_distribution_ratio", 60))))
            max_initial_age = int(round(cfg["base"]["min_life"] * ratio / 100))
            initial_age_rounds = random.randint(0, max(0, max_initial_age))
        self.life = max(1, int(base_life - initial_age_rounds))
        self.initial_age_rounds = int(initial_age_rounds)
        self.role = "normal"
        self.critical = False
        self.used_critical_chance = False
        self.charity_banned = False
        self.survival_rounds = int(initial_age_rounds)
        # dev36：劳动权益分红诊断。last_labor_turn / last_labor_good 是跨回合状态，
        # 用于“近期劳动者”分红实验；不改变劳动参与或生产逻辑。
        self.last_labor_turn = 0
        self.last_labor_good = ""

        self.reset_turn_detail()

    @classmethod
    def clone_from(cls, other):
        obj = cls.__new__(cls)
        for k, v in other.__dict__.items():
            setattr(obj, k, copy.deepcopy(v) if k not in {"cfg"} else v)
        obj.id = cls.NEXT_ID
        cls.NEXT_ID += 1
        return obj

    def enforce_ability_balance(self):
        b = self.cfg["base"]
        total = b["total_ability"]
        min_s = max(b["min_strength"], total - b["max_intelligence"])
        max_s = min(b["max_strength"], total - b["min_intelligence"])
        self.strength = int(max(min_s, min(max_s, self.strength)))
        self.intelligence = int(total - self.strength)

    def effective_intelligence(self):
        # 有效智慧 = 基础智慧 + 临时智慧。临时智慧不改变基因/遗传智慧，只影响个体一生中的生产表现。
        return int(self.intelligence + getattr(self, "temp_intelligence", 0))

    def initial_fluctuate(self, value, minv, maxv, delta):
        amount = random.randint(0, delta)
        direction = random.choice([-1, 1])
        return int(max(minv, min(maxv, value + amount * direction)))

    def mutate(self, value, minv, maxv, delta):
        return int(max(minv, min(maxv, value + random.randint(-delta, delta))))

    @staticmethod
    def class_rank_and_label(balance, cfg, pop_config):
        # BOT8 dev6：阶层由个人存款划分，并复用现有生存成本、财富税免税线和财富税高档阈值。
        # 这样不新增阶层阈值参数，且能直接观察税收、教育、救助对阶层流动的影响。
        survival_cost = int(cfg["base"].get("survival_cost", 100))
        exempt_threshold = int(pop_config.get("wealth_tax_exempt_threshold", 600))
        high_threshold = int(pop_config.get("wealth_tax_threshold", 1500))
        value = int(balance)
        if value < survival_cost:
            return 0, "Poor"
        if value < exempt_threshold:
            return 1, "Lower"
        if value < high_threshold:
            return 2, "Middle"
        return 3, "Rich"


    def reset_turn_detail(self):
        self.turn_start_balance = self.balance
        self.after_labor_balance = self.balance
        self.after_tax_balance = self.balance
        self.after_plunder_balance = self.balance
        self.after_invasion_balance = self.balance
        self.after_government_aid_balance = self.balance
        self.after_rescue_balance = self.balance
        self.after_reproduce_balance = self.balance
        self.pre_survival_balance = self.balance
        self.end_balance = self.balance
        self.turn_income = 0
        self.turn_labor_income = 0
        self.employer_branch = ""
        self.wage_received = 0
        self.dividend_received = 0
        self.produced_goods_value = 0
        self.rich_tax_paid = 0

        self.labor_participation_chance = 0
        self.resource_access_score = 0
        self.requested_resource = 0
        self.allocated_resource = 0
        self.population_resource_claim = 0
        self.population_resource_quota = 0
        self.shared_resource_enabled = 0
        self.tribe_trust = 0

        self.did_labor = 0
        self.primary_production_good = ""
        self.production_price_response = 0
        self.total_market_need = 0
        self.total_market_unmet_need = 0
        for good in TRADED_GOODS:
            setattr(self, f"market_{good}_need", 0)
            setattr(self, f"market_{good}_spending_limit", 0)
        self.labor_gross_production = 0
        self.labor_net_production = 0
        self.labor_tax_paid = 0
        self.labor_income_after_tax = 0
        self.env_consumed_by_labor = 0
        self.wealth_tax_paid = 0
        self.total_tax_paid = 0
        # BOT8 dev17：跨部族贸易记录。税收由买方支付，进入对应部族政府存款。
        self.market_import_value = 0
        self.market_export_value = 0
        self.market_tax_paid = 0
        self.trade_tax_paid = 0
        self.import_tax_paid = 0
        self.trade_tax_generated = 0
        self.import_tax_generated = 0

        self.did_internal_plunder = 0
        self.internal_plunder_gain = 0
        self.internal_plunder_victim_loss_caused = 0
        self.internal_plunder_system_loss_caused = 0
        self.was_internal_plunder_victim = 0
        self.internal_plunder_loss = 0
        self.was_sanctioned = 0
        self.sanction_loss = 0

        self.did_invasion = 0
        self.invasion_success = 0
        self.invasion_gain = 0
        self.invasion_victim_loss_caused = 0
        self.invasion_system_loss_caused = 0
        self.was_invasion_victim = 0
        self.invasion_loss = 0
        self.invasion_fail_life_loss = 0

        self.government_aid_received = 0
        self.individual_rescue_given = 0
        self.individual_rescue_received = 0
        # BOT8 dev16：道德施舍机制记录。默认机制关闭，仅用于高级调试。
        self.moral_donation_given = 0
        self.moral_donation_received = 0


        self.did_reproduce = 0
        self.child_count = 0
        self.reproduction_goods_consumed_for_child = 0
        self.reproduction_money_transferred_to_child = 0
        self.birth_food_transferred_to_child = 0
        self.birth_food_received = 0
        self.inheritance_given = 0
        self.inheritance_received = 0
        self.education_temp_intelligence_received = getattr(self, "education_temp_intelligence_received", 0)
        self.education_temp_intelligence_given = 0
        self.government_education_investment_received = 0
        self.government_education_temp_intelligence_received = 0

        self.survival_cost_paid = 0
        # BOT8 dev8：本回合商品库存、生产、消耗和生病记录。
        self.money = self.balance
        self.food_consumed = 0
        self.medical_goods_consumed = 0
        self.education_goods_consumed = 0
        self.reproduction_goods_consumed = 0
        self.tools_consumed = 0
        self.food_produced = 0
        self.medical_goods_produced = 0
        self.education_goods_produced = 0
        self.reproduction_goods_produced = 0
        self.tools_produced = 0
        self.food_tax_paid = 0
        self.medical_goods_tax_paid = 0
        self.education_goods_tax_paid = 0
        self.reproduction_goods_tax_paid = 0
        self.tools_tax_paid = 0
        self.food_aid_received = 0
        self.medical_aid_received = 0
        self.is_sick = 0
        self.became_sick_this_turn = 0
        self.sickness_risk = 0
        self.health_delta_this_turn = 0
        self.health_deteriorated_this_turn = 0
        self.medical_recovery_this_turn = 0
        self.reproductive_security_score = getattr(self, "reproductive_security_score", 0)
        self.reproductive_security_bonus = 0
        self.medical_goods_needed = 0
        self.medical_goods_shortage = 0
        self.food_shortage = 0
        self.education_goods_used_for_child = 0
        self.reproduction_goods_used = 0
        self.money_used_for_reproduction = 0
        self.entered_critical_this_turn = 0
        self.recovered_from_critical_this_turn = 0
        self.died_this_turn = 0
        self.death_reason = ""
        self.deposit_to_government_on_death = 0

        # BOT8 dev7：灾害个体记录。灾害是外部冲击，用于观察部族系统韧性。
        self.affected_by_disaster = 0
        self.disaster_balance_loss = 0
        self.disaster_life_loss = 0

        # BOT8 dev10：基础商品市场与政府采购记录。
        # 市场交易位于生产之后、掠夺/侵略之前；当前商品按本部族动态价格指数结算。
        self.did_market_trade = 0
        self.market_money_spent = 0
        self.market_money_earned = 0
        self.government_purchase_sold = 0
        self.market_partner_class = ""
        self.market_goods_bought_value = 0
        self.market_goods_sold_value = 0
        for good in TRADED_GOODS:
            setattr(self, f"market_unmet_{good}_need", 0)
        for good in GOOD_FIELDS:
            setattr(self, f"market_{good}_bought", 0)
            setattr(self, f"market_{good}_sold", 0)

        # BOT8 dev9：全库存掠夺/侵略记录。
        # 货币按 1:1 转移不损耗；食物、医疗用品、教育用品、生育用品和工具按 plunder_gain_rate 转移，剩余作为商品损耗。
        for good in GOOD_FIELDS:
            display = GOOD_DISPLAY[good]
            setattr(self, f"internal_plunder_{good}_gain", 0)
            setattr(self, f"internal_plunder_{good}_loss", 0)
            setattr(self, f"invasion_{good}_gain", 0)
            setattr(self, f"invasion_{good}_loss", 0)
        self.internal_plunder_goods_gain = 0
        self.internal_plunder_goods_loss = 0
        self.internal_plunder_goods_system_loss = 0
        self.internal_plunder_total_value_gain = 0
        self.internal_plunder_total_value_loss = 0
        self.invasion_goods_gain = 0
        self.invasion_goods_loss = 0
        self.invasion_goods_system_loss = 0
        self.invasion_total_value_gain = 0
        self.invasion_total_value_loss = 0


class Environment:
    def __init__(self, cfg):
        self.cfg = normalize_settings(copy.deepcopy(cfg))
        self.population_names = get_active_population_names(self.cfg)
        self.state = {
            "population_config": {p: copy.deepcopy(self.cfg["population"][p]) for p in self.population_names}
        }
        self.turn = 0
        Individual.NEXT_ID = 0

        self.populations = {
            p: [Individual(self.cfg, pop_config=self.state["population_config"][p], birth_turn=0) for _ in range(self.cfg["base"]["initial_population"])]
            for p in self.population_names
        }
        # dev21：每个个体获得唯一代号。格式：部族1位 + 祖先编号3位 + 出生回合4位 + 血系序号5位。
        self.ancestor_counters = {p: 0 for p in self.population_names}
        self.lineage_counters = {p: {} for p in self.population_names}
        for p, pop in self.populations.items():
            for ind in pop:
                self.assign_initial_code(p, ind)

        # dev31：小族群正常初始条件预设。该预设只改变开局禀赋，不在运行中强制恢复人口、
        # 不增加出生率、不创造后续补贴。目的在于避免 5 人小族群被初始化成“无医疗、无生育用品、
        # 仅少量食物”的裸初始状态。
        self.apply_small_group_initial_conditions()

        self.env_resource = {p: self.state["population_config"][p].get("initial_env_resource", self.cfg["base"]["initial_env_resource"]) for p in self.population_names}
        # BOT8 2.1.0：生态承载力与环境退化运行态。
        # env_capacity 表示资源上限 K；env_health 使用 0-100，控制实际再生效率；resource_pressure 表示本回合消耗/实际再生。
        self.env_capacity = {p: self.state["population_config"][p].get("env_capacity", 50000) for p in self.population_names}
        self.env_health = {p: self.state["population_config"][p].get("env_health", 100) for p in self.population_names}
        self.resource_pressure = {p: 0.0 for p in self.population_names}
        # BOT8 2.2.0：环境退化缓冲池。小幅超采不会立即扣 EnvHealth，而是累积到 1 后再扣除。
        self.env_damage_buffer = {p: 0.0 for p in self.population_names}
        self.env_recovery_buffer = {p: 0.0 for p in self.population_names}

        # BOT8 2.3.0：种群间共用环境资源运行态。
        # 该机制参考公共池资源研究：资源具有“使用会减少他人可用量”的共同池属性。
        self.shared_env_resource = sum(self.env_resource.values())
        self.shared_env_capacity = sum(self.env_capacity.values())
        self.shared_env_health = int(round(sum(self.env_health.values()) / max(1, len(self.env_health))))
        self.shared_resource_pressure = 0.0
        self.shared_env_damage_buffer = 0.0
        self.shared_env_recovery_buffer = 0.0

        self.government_deposit = {p: 0 for p in self.population_names}
        # BOT8 dev8：政府商品库存。政府救助阶段优先发放食物和医疗用品，不再直接资助货币。
        self.government_food = {p: 0 for p in self.population_names}
        self.government_medical_goods = {p: 0 for p in self.population_names}
        self.government_education_goods = {p: 0 for p in self.population_names}
        self.government_reproduction_goods = {p: 0 for p in self.population_names}
        self.government_tools = {p: 0 for p in self.population_names}
        # dev42：按族群规模生成默认政府初始财政/公共库存。只在初始化运行，不属于运行中补贴。
        self.apply_population_scaled_government_initials()
        # dev21：公司化劳动。每个部族有一个公司主体，按商品种类拆分为分公司。
        self.companies = self.initialize_companies()
        self.event_logs = []
        self.max_event_logs = 800
        # CivitasLab system-stage step8: structured event stream for future high-refresh runtime UI.
        self.event_stream = EventStream(max_events=5000)
        # CivitasLab system-stage step9: compact per-turn entity snapshots for runtime detail windows.
        self.entity_state_snapshots = EntityStateSnapshot(max_turns=200)
        self.last_company_branch_choice = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        self.turn_branch_workers = {p: {good: [] for good in GOOD_FIELDS} for p in self.population_names}
        self.last_company_sales_volume = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        self.government_production_resource = self.env_resource
        self.last_goods_consumption = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        for p in self.population_names:
            survival_cost_seed = int(self.cfg["base"].get("survival_cost", 100))
            reproduction_units_seed = self.reproduction_goods_required_per_birth()
            self.last_goods_consumption[p]["food"] = survival_cost_seed * max(1, self.cfg["base"].get("initial_population", 50))
            self.last_goods_consumption[p]["medical_goods"] = max(1, survival_cost_seed // 10)
            self.last_goods_consumption[p]["education_goods"] = max(1, reproduction_units_seed)
            self.last_goods_consumption[p]["reproduction_goods"] = max(1, reproduction_units_seed)
        self.current_goods_consumption = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        self.turn_goods_production = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        self.turn_goods_tax = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        # BOT8 dev13：部族内商品价格指数。100 表示 1 货币/单位；价格根据供需、未满足需求和未售出供给动态变化。
        self.market_price_index = {p: {good: 100 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_market_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_market_supply = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_market_volume_by_good = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_market_unmet_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_market_unsold_supply = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        # BOT8 dev17：跨部族贸易与税制运行态。
        self.turn_market_local_volume = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_market_import_volume = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_market_export_volume = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_trade_tax_income = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_import_tax_income = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_import_spending = {p: 0 for p in self.population_names}
        self.turn_export_income = {p: 0 for p in self.population_names}
        # BOT8 dev18：政府宏观调控运行态。公共机构通过低价收储、高价投放和民生折价释放缓冲商品市场。
        self.turn_government_stockpile_food = {p: 0 for p in self.population_names}
        self.turn_government_stockpile_medical_goods = {p: 0 for p in self.population_names}
        self.turn_government_stockpile_spending = {p: 0 for p in self.population_names}
        self.turn_government_release_food = {p: 0 for p in self.population_names}
        self.turn_government_release_medical_goods = {p: 0 for p in self.population_names}
        self.turn_government_release_income = {p: 0 for p in self.population_names}
        self.turn_government_subsidy_value = {p: 0 for p in self.population_names}
        self.turn_market_stability_index = {p: 0 for p in self.population_names}
        # dev27：订单簿式市场统计。成交均价将反向形成市场价格；政府作为最后买方吸收剩余卖单。
        self.turn_market_trade_money_by_good = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_market_trade_amount_by_good = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_government_orderbook_purchase = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_government_orderbook_purchase_spending = {p: 0 for p in self.population_names}
        self.turn_government_surplus_deleted = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        self.turn_government_surplus_value = {p: 0 for p in self.population_names}
        # dev31：公共生育用品释放统计。政府通过订单簿买入的生育用品必须有进入繁殖链路的路径，
        # 否则公共库存只会留存或被剩余价值删除。
        self.turn_government_reproduction_goods_released = {p: 0 for p in self.population_names}
        self.turn_government_reproduction_goods_release_targets = {p: 0 for p in self.population_names}
        # dev34：资源/财富分布、救助释放、医疗链路与工资闭环诊断。只记录，不改变机制。
        self.turn_food_aid_eligible_count = {p: 0 for p in self.population_names}
        self.turn_food_aid_received_count = {p: 0 for p in self.population_names}
        self.turn_food_aid_unmet_count = {p: 0 for p in self.population_names}
        self.turn_government_food_before_aid = {p: 0 for p in self.population_names}
        self.turn_government_food_after_aid = {p: 0 for p in self.population_names}
        self.turn_food_shortage_with_government_food_count = {p: 0 for p in self.population_names}
        self.turn_medical_aid_eligible_count = {p: 0 for p in self.population_names}
        self.turn_medical_aid_received_count = {p: 0 for p in self.population_names}
        self.turn_medical_aid_unmet_count = {p: 0 for p in self.population_names}
        self.turn_government_medical_goods_before_aid = {p: 0 for p in self.population_names}
        self.turn_government_medical_goods_after_aid = {p: 0 for p in self.population_names}
        self.turn_medical_shortage_with_government_medical_goods_count = {p: 0 for p in self.population_names}
        self.turn_critical_medical_need_count = {p: 0 for p in self.population_names}
        self.turn_critical_medical_aid_received_count = {p: 0 for p in self.population_names}
        self.turn_critical_medical_aid_unmet_count = {p: 0 for p in self.population_names}
        self.turn_medical_goods_bought_by_critical = {p: 0 for p in self.population_names}
        self.turn_medical_goods_bought_by_healthy = {p: 0 for p in self.population_names}
        self.turn_total_wages_paid = {p: 0 for p in self.population_names}
        self.turn_company_cash_before_wages = {p: 0 for p in self.population_names}
        self.turn_company_cash_after_wages = {p: 0 for p in self.population_names}
        self.turn_company_cash_after_resource_purchase = {p: 0 for p in self.population_names}
        self.turn_company_unable_to_pay_full_wages_count = {p: 0 for p in self.population_names}
        self.turn_company_production_stopped_by_cash_count = {p: 0 for p in self.population_names}
        self.turn_company_production_stopped_by_stock_count = {p: 0 for p in self.population_names}
        # dev39：工资响应消费诊断。工资提高会先提高个体余额；若启用工资响应消费，也会提高当回合有效买入意愿。
        self.turn_effective_buy_willingness_sum = {p: 0 for p in self.population_names}
        self.turn_effective_buy_willingness_count = {p: 0 for p in self.population_names}
        self.turn_wage_consumption_bonus_sum = {p: 0 for p in self.population_names}
        self.turn_wage_responsive_buyer_count = {p: 0 for p in self.population_names}
        self.turn_wage_responsive_extra_cap_total = {p: 0 for p in self.population_names}
        self.turn_wage_funded_market_spending = {p: 0 for p in self.population_names}
        self.turn_worker_market_spending = {p: 0 for p in self.population_names}
        self.turn_worker_market_spending_to_company = {p: 0 for p in self.population_names}
        # dev40：刚性需求预算释放诊断。
        self.turn_food_hard_need_count = {p: 0 for p in self.population_names}
        self.turn_food_hard_need_amount = {p: 0 for p in self.population_names}
        self.turn_food_hard_spending_cap = {p: 0 for p in self.population_names}
        self.turn_food_hard_actual_spending = {p: 0 for p in self.population_names}
        self.turn_food_hard_satisfied_amount = {p: 0 for p in self.population_names}
        self.turn_food_hard_unsatisfied_amount = {p: 0 for p in self.population_names}
        self.turn_medical_hard_need_count = {p: 0 for p in self.population_names}
        self.turn_medical_hard_need_amount = {p: 0 for p in self.population_names}
        self.turn_medical_hard_spending_cap = {p: 0 for p in self.population_names}
        self.turn_medical_hard_actual_spending = {p: 0 for p in self.population_names}
        self.turn_medical_hard_satisfied_amount = {p: 0 for p in self.population_names}
        self.turn_medical_hard_unsatisfied_amount = {p: 0 for p in self.population_names}
        self.turn_reproduction_hard_need_count = {p: 0 for p in self.population_names}
        self.turn_reproduction_hard_need_amount = {p: 0 for p in self.population_names}
        self.turn_reproduction_hard_spending_cap = {p: 0 for p in self.population_names}
        self.turn_reproduction_hard_actual_spending = {p: 0 for p in self.population_names}
        self.turn_reproduction_hard_satisfied_amount = {p: 0 for p in self.population_names}
        self.turn_reproduction_hard_unsatisfied_amount = {p: 0 for p in self.population_names}
        self.turn_hard_need_spending_total = {p: 0 for p in self.population_names}
        self.turn_reserve_need_spending_total = {p: 0 for p in self.population_names}
        self.turn_hard_need_blocked_by_no_cash = {p: 0 for p in self.population_names}
        self.turn_hard_need_blocked_by_no_market_stock = {p: 0 for p in self.population_names}
        self.turn_hard_need_blocked_by_high_price = {p: 0 for p in self.population_names}
        self.turn_hard_need_blocked_by_budget_cap = {p: 0 for p in self.population_names}
        # dev41：公司硬刚需库存释放诊断。记录已有公司库存因生存/医疗/生育刚需而突破初始库存目标进入订单簿的情况。
        self.turn_company_hard_need_release_pressure = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_company_hard_need_release_listed = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_company_sellable_stock = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_company_hard_need_release_enabled_count = {p: 0 for p in self.population_names}
        # dev42：生育用品/教育用品库存韧性诊断。
        self.turn_repro_education_resilience_gap = {p: {"education_goods": 0, "reproduction_goods": 0} for p in self.population_names}
        self.turn_repro_education_resilience_weight_added = {p: {"education_goods": 0, "reproduction_goods": 0} for p in self.population_names}
        # dev44：硬刚需生产响应诊断。只影响生产权重，不创造资源、不直接影响出生率。
        self.last_resource_use_to_regen_ratio = {p: 0.0 for p in self.population_names}
        self.turn_hard_need_production_bonus = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_hard_need_unmet_for_production = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_inventory_sales_dividend_paid = {p: 0 for p in self.population_names}
        self.turn_inventory_sales_dividend_recipients = {p: 0 for p in self.population_names}
        # dev35：库存销售收入回流校准。区分历史库存清算收入，并记录现金保护拦截情况。
        self.turn_historical_inventory_sales_income = {p: 0 for p in self.population_names}
        self.turn_inventory_sales_dividend_eligible_branches = {p: 0 for p in self.population_names}
        self.turn_inventory_sales_dividend_blocked_by_cash_protection = {p: 0 for p in self.population_names}
        self.turn_inventory_sales_dividend_blocked_by_no_historical_income = {p: 0 for p in self.population_names}
        self.turn_inventory_sales_dividend_cash_floor = {p: 0 for p in self.population_names}
        # dev28：公司库存流通统计。生产决策和销售决策分离后，停产分公司也能把历史库存挂到订单簿。
        self.turn_company_inventory_listed = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_company_inventory_sold_to_individuals = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_company_inventory_sold_to_government = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_company_inventory_unsold = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_company_inventory_listing_ratio = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_company_orderbook_ask_count = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.trade_flow_rows = []
        # BOT8 dev14：上一回合未满足需求会参与下一回合生产结构，避免生产比例只追随历史消费导致关键商品长期短缺。
        self.last_market_unmet_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        # BOT8 dev19：上一回合出生失败原因参与下一回合生产信号，尤其是生育用品刚性短缺。
        self.last_birth_blocked_no_reproduction_goods = {p: 0 for p in self.population_names}
        # BOT8 dev20：刚性需求与储备需求分离。上一回合的刚性需求直接驱动下一回合生产结构。
        self.last_hard_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.last_reserve_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_hard_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        self.turn_reserve_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        # BOT8 dev5：部族社会信任运行态.
        # trust 是部族级状态变量，初始值来自部族参数；运行中由救助、教育、掠夺、侵略、基尼系数和濒死比例动态更新。
        self.tribe_trust = {p: float(self.state["population_config"][p].get("trust", 60)) for p in self.population_names}
        self.total_social_wealth = 0
        self.summary_output_rows = []
        self.individual_output_rows = []
        self.current_summary_rows = []
        self.dead_individuals_this_turn = []
        self.newborns_this_turn = []
        self.turn_branch_workers = {p: {good: [] for good in GOOD_FIELDS} for p in self.population_names}
        # CivitasLab system-stage step10: turn-local production-ratio cache.
        # Production ratios are a turn-level signal; caching avoids repeated random jitter and redundant recomputation
        # while keeping the cache reset at every turn boundary.
        self._goods_production_ratios_cache = {}
        if hasattr(self, "companies"):
            for comp in self.companies.values():
                for branch in comp.values():
                    branch["last_sales_volume"] = branch.get("sales_volume", 0)
                    branch["wages_paid"] = 0
                    branch["sales_income"] = 0
                    branch["historical_inventory_sales_income"] = 0
                    branch["goods_produced"] = 0
                    branch["sales_volume"] = 0
        if hasattr(self, "current_goods_consumption"):
            self.current_goods_consumption = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        if hasattr(self, "turn_goods_production"):
            self.turn_goods_production = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        if hasattr(self, "turn_goods_tax"):
            self.turn_goods_tax = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        if hasattr(self, "turn_market_demand"):
            self.turn_market_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_supply"):
            self.turn_market_supply = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_volume_by_good"):
            self.turn_market_volume_by_good = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_unmet_demand"):
            self.turn_market_unmet_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_unsold_supply"):
            self.turn_market_unsold_supply = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_local_volume"):
            self.turn_market_local_volume = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_import_volume"):
            self.turn_market_import_volume = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_export_volume"):
            self.turn_market_export_volume = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_hard_demand"):
            self.turn_hard_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_reserve_demand"):
            self.turn_reserve_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_hard_demand"):
            self.turn_hard_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_reserve_demand"):
            self.turn_reserve_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_trade_tax_income"):
            self.turn_trade_tax_income = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_import_tax_income"):
            self.turn_import_tax_income = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_import_spending"):
            self.turn_import_spending = {p: 0 for p in self.population_names}
        if hasattr(self, "turn_export_income"):
            self.turn_export_income = {p: 0 for p in self.population_names}
        for macro_attr in [
            "turn_government_stockpile_food", "turn_government_stockpile_medical_goods", "turn_government_stockpile_spending",
            "turn_government_release_food", "turn_government_release_medical_goods", "turn_government_release_income",
            "turn_government_subsidy_value", "turn_market_stability_index", "turn_government_orderbook_purchase_spending", "turn_government_surplus_value",
            "turn_reproduction_goods_hard_buyer_count", "turn_reproduction_goods_hard_demand_total",
            "turn_reproduction_goods_hard_demand_satisfied", "turn_reproduction_goods_hard_demand_unsatisfied",
            "turn_reproduction_goods_blocked_no_company_stock", "turn_reproduction_goods_blocked_no_money",
            "turn_reproduction_goods_company_sales_volume", "turn_reproduction_goods_individual_sales_volume",
            "turn_food_aid_eligible_count", "turn_food_aid_received_count", "turn_food_aid_unmet_count",
            "turn_government_food_before_aid", "turn_government_food_after_aid", "turn_food_shortage_with_government_food_count",
            "turn_medical_aid_eligible_count", "turn_medical_aid_received_count", "turn_medical_aid_unmet_count",
            "turn_government_medical_goods_before_aid", "turn_government_medical_goods_after_aid", "turn_medical_shortage_with_government_medical_goods_count",
            "turn_critical_medical_need_count", "turn_critical_medical_aid_received_count", "turn_critical_medical_aid_unmet_count",
            "turn_medical_goods_bought_by_critical", "turn_medical_goods_bought_by_healthy",
            "turn_total_wages_paid", "turn_company_cash_before_wages", "turn_company_cash_after_wages", "turn_company_cash_after_resource_purchase",
            "turn_company_unable_to_pay_full_wages_count", "turn_company_production_stopped_by_cash_count", "turn_company_production_stopped_by_stock_count",
            "turn_effective_buy_willingness_sum", "turn_effective_buy_willingness_count", "turn_wage_consumption_bonus_sum",
            "turn_wage_responsive_buyer_count", "turn_wage_responsive_extra_cap_total", "turn_wage_funded_market_spending",
            "turn_worker_market_spending", "turn_worker_market_spending_to_company",
            "turn_company_hard_need_release_enabled_count",
            "turn_inventory_sales_dividend_paid", "turn_inventory_sales_dividend_recipients",
            "turn_historical_inventory_sales_income", "turn_inventory_sales_dividend_eligible_branches",
            "turn_inventory_sales_dividend_blocked_by_cash_protection", "turn_inventory_sales_dividend_blocked_by_no_historical_income",
            "turn_inventory_sales_dividend_cash_floor",
            "turn_excess_cash_dividend_paid", "turn_excess_cash_dividend_recipients", "turn_excess_cash_dividend_pool",
            "turn_excess_cash_dividend_eligible_branches", "turn_excess_cash_dividend_blocked_by_no_excess_cash",
            "turn_excess_cash_dividend_blocked_by_no_recipients",
            "turn_death_life_end_with_reproduction_goods", "turn_death_life_end_with_food_for_birth",
            # dev37：低人口劳动空窗与寿命尾部诊断。仅记录，不改变劳动、繁殖或死亡行为。
            "turn_pop_below5_flag", "turn_pop_below3_flag",
            "turn_labor_eligible_count_when_pop_below5", "turn_labor_eligible_count_when_pop_below3",
            "turn_labor_willing_count_when_pop_below5", "turn_labor_willing_count_when_pop_below3",
            "turn_actual_worker_count_when_pop_below5", "turn_actual_worker_count_when_pop_below3",
            "turn_no_worker_reason_sick_count", "turn_no_worker_reason_critical_count",
            "turn_no_worker_reason_low_labor_count", "turn_no_worker_reason_no_company_demand_count",
            "turn_no_worker_reason_no_expected_profit_count", "turn_no_worker_reason_no_resource_count",
            "turn_company_demand_for_workers_when_pop_below5", "turn_company_demand_for_workers_when_pop_below3",
            "turn_branches_with_positive_expected_profit_when_pop_below5", "turn_branches_with_positive_expected_profit_when_pop_below3",
            "turn_branches_stopped_by_stock_when_pop_below5", "turn_branches_stopped_by_cash_when_pop_below5",
            "turn_branches_stopped_by_resource_when_pop_below5",
            "turn_government_production_resource_when_pop_below5", "turn_company_total_stock_when_pop_below5",
            "turn_company_total_money_when_pop_below5",
            "turn_low_pop_snapshot_count",
            "turn_last_individuals_avg_money", "turn_last_individuals_avg_food",
            "turn_last_individuals_avg_medical_goods", "turn_last_individuals_avg_reproduction_goods",
            "turn_last_individuals_avg_labor", "turn_last_individuals_avg_reproduce",
            "turn_last_individuals_avg_life_remaining", "turn_last_individuals_avg_age",
            "turn_last_individuals_sick_count", "turn_last_individuals_critical_count",
            "turn_last_individuals_can_work_count", "turn_last_individuals_can_reproduce_count",
            "turn_last_individuals_has_food_for_birth_count", "turn_last_individuals_has_reproduction_goods_count",
            "turn_life_end_with_can_reproduce", "turn_life_end_with_can_work",
            "turn_life_end_with_food_and_reproduction_goods",
            "turn_last_death_life_remaining", "turn_last_death_had_food_for_birth",
            "turn_last_death_had_reproduction_goods", "turn_last_death_was_sick",
            "turn_last_death_was_critical", "turn_last_death_could_work", "turn_last_death_could_reproduce",
            # dev38：继续核查低人口劳动转化与父代食物安全线。只记录，不参与决策。
            "turn_labor_candidate_raw_count", "turn_labor_candidates_trimmed_by_tendency",
            "turn_labor_allocated_candidate_count", "turn_labor_candidates_without_allocation",
            "turn_labor_positive_profit_but_no_worker_when_pop_below5",
            "turn_parent_food_requirement", "turn_potential_parent_count_when_pop_below5",
            "turn_potential_parent_with_reproduction_goods_when_pop_below5",
            "turn_potential_parent_food_ready_when_pop_below5",
            "turn_parent_food_gap_when_pop_below5", "turn_parent_food_gap_when_pop_below3",
            "turn_last_individuals_parent_food_gap_avg",
            "turn_food_bought_by_potential_parent", "turn_food_aid_to_potential_parent",
            "turn_birth_blocked_food_safety_with_reproduction_goods",
            # M6A：医疗/教育/生育安全/政策压力/公司韧性观测字段。
            "turn_medical_recovery_count", "turn_health_deterioration_count",
            "turn_reproductive_security_bonus_sum", "turn_reproductive_security_count",
            "turn_company_resilience_score", "turn_government_policy_pressure_score",
            # 系统级第七阶段：进化方向加权算法与周期性诊断。只记录定向进化偏置，不影响自然遗传变异。
            "turn_evolution_sample_count", "turn_evolution_direction_change_count",
            "turn_evolution_fitness_avg", "turn_evolution_fitness_gap_morality",
            "turn_evolution_fitness_gap_strength", "turn_evolution_fitness_gap_reproduce",
            "turn_evolution_fitness_gap_labor", "turn_evolution_signal_morality",
            "turn_evolution_signal_strength", "turn_evolution_signal_reproduce", "turn_evolution_signal_labor",
        ]:
            if hasattr(self, macro_attr):
                setattr(self, macro_attr, {p: 0 for p in self.population_names})
        if hasattr(self, "turn_market_trade_money_by_good"):
            self.turn_market_trade_money_by_good = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_trade_amount_by_good"):
            self.turn_market_trade_amount_by_good = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_government_orderbook_purchase"):
            self.turn_government_orderbook_purchase = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_government_surplus_deleted"):
            self.turn_government_surplus_deleted = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        for company_inventory_attr in [
            "turn_company_inventory_listed",
            "turn_company_inventory_sold_to_individuals",
            "turn_company_inventory_sold_to_government",
            "turn_company_inventory_unsold",
            "turn_company_inventory_listing_ratio",
            "turn_company_orderbook_ask_count",
            "turn_company_hard_need_release_pressure",
            "turn_company_hard_need_release_listed",
            "turn_company_sellable_stock",
        ]:
            if hasattr(self, company_inventory_attr):
                setattr(self, company_inventory_attr, {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names})
        for resilience_attr in ["turn_repro_education_resilience_gap", "turn_repro_education_resilience_weight_added"]:
            if hasattr(self, resilience_attr):
                setattr(self, resilience_attr, {p: {"education_goods": 0, "reproduction_goods": 0} for p in self.population_names})
        for dev44_attr in ["turn_hard_need_production_bonus", "turn_hard_need_unmet_for_production"]:
            if hasattr(self, dev44_attr):
                setattr(self, dev44_attr, {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names})
        if hasattr(self, "turn_disaster_type"):
            for p in self.turn_disaster_type:
                self.turn_disaster_type[p] = ""
        self.turn_history = []

        self.population_history = {p: [] for p in self.population_names}
        self.total_balance_history = {p: [] for p in self.population_names}
        self.gini_history = {p: [] for p in self.population_names}
        self.str_total_ratio_history = {p: [] for p in self.population_names}
        self.production_history = {p: [] for p in self.population_names}
        self.invasion_gain_history = {p: [] for p in self.population_names}
        self.env_health_history = {p: [] for p in self.population_names}
        self.resource_pressure_history = {p: [] for p in self.population_names}

        for name in [
            "turn_production_total", "turn_labor_gross_total",
            "turn_labor_candidate_count", "turn_labor_request_total", "turn_labor_allocated_total", "turn_labor_unmet_demand",
            "turn_population_resource_claim", "turn_population_resource_quota", "turn_population_resource_used", "turn_population_resource_shortage",
            "turn_env_consumption_total", "turn_resource_regen_total", "turn_env_health_change",
            "turn_invasion_gain_total", "turn_invasion_victim_loss_total", "turn_invasion_system_loss_total",
            "turn_invasion_goods_gain_total", "turn_invasion_goods_loss_total", "turn_invasion_goods_system_loss_total", "turn_invasion_total_value_gain", "turn_invasion_total_value_loss",
            "turn_internal_plunder_gain_total", "turn_internal_plunder_victim_loss_total", "turn_internal_plunder_system_loss_total",
            "turn_internal_plunder_goods_gain_total", "turn_internal_plunder_goods_loss_total", "turn_internal_plunder_goods_system_loss_total", "turn_internal_plunder_total_value_gain", "turn_internal_plunder_total_value_loss",
            "turn_government_aid_total", "turn_gov_aid_budget_used", "turn_gov_aid_budget_remaining",
            "turn_government_education_total",
            "turn_trust_change", "turn_trust_gain_from_aid", "turn_trust_gain_from_rescue", "turn_trust_gain_from_education",
            "turn_trust_loss_from_plunder", "turn_trust_loss_from_invasion", "turn_trust_loss_from_gini", "turn_trust_loss_from_critical",
            "turn_labor_tax_total", "turn_wealth_tax_total", "turn_individual_rescue_total", "turn_moral_donation_total", "turn_moral_donation_count",
            "turn_survival_cost_total", "turn_reproduce_cost_total", "turn_child_initial_wealth_total", "turn_inheritance_transfer_total",
            "turn_labor_worker_count", "turn_workers_paid_count", "turn_workers_paid_enough_for_food_count", "turn_workers_paid_enough_for_reproduction_count", "turn_government_purchase_to_company",
            "turn_company_resource_purchased", "turn_company_resource_cost", "turn_company_expected_profit", "turn_company_actual_revenue", "turn_company_wage_paid", "turn_company_dividend_paid", "turn_rich_tax_income",
            "turn_internal_plunder_count", "turn_sanction_count",
            "turn_invasion_attempt_count", "turn_invasion_success_count", "turn_birth_count", "turn_death_count",
            "turn_entered_critical_count", "turn_recovered_critical_count",
            "turn_entered_critical_when_pop_below5", "turn_recovered_critical_when_pop_below5",
            "turn_deaths_life_end_when_pop_below3", "turn_deaths_life_end_when_pop_below5",
            "turn_deaths_food_shortage_when_pop_below5", "turn_deaths_medical_shortage_when_pop_below5",
            "turn_deaths_critical_goods_shortage_when_pop_below5",
            "turn_disaster_occurred", "turn_disaster_strength", "turn_disaster_wealth_loss",
            "turn_disaster_life_loss", "turn_disaster_env_regen_loss", "turn_disaster_trust_loss",
            "turn_disaster_plunder_bonus",
            "turn_food_shortage_count", "turn_medical_shortage_count", "turn_sick_count", "turn_new_sick_count",
            "turn_market_trade_count", "turn_market_trade_volume", "turn_market_food_volume", "turn_market_medical_goods_volume",
            "turn_market_education_goods_volume", "turn_market_reproduction_goods_volume",
            "turn_reproduction_eligible_count", "turn_reproduction_attempt_count", "turn_birth_blocked_critical",
            "turn_birth_blocked_sick", "turn_birth_blocked_no_money", "turn_birth_blocked_no_reproduction_goods",
            "turn_birth_blocked_no_food_safety", "turn_birth_blocked_low_reproduce_chance", "turn_birth_blocked_other",
            "turn_birth_food_transfer_total", "turn_newborn_survival_skipped_count",
            "turn_secondary_birth_eligible_count", "turn_secondary_birth_condition_ready_count", "turn_secondary_birth_attempt_count",
            "turn_secondary_birth_success_count", "turn_secondary_birth_blocked_sick_or_critical",
            "turn_secondary_birth_blocked_no_reproduction_goods", "turn_secondary_birth_blocked_no_food_safety",
            "turn_secondary_birth_blocked_low_reproduce_chance",
            "turn_reproduction_goods_demand_count", "turn_reproduction_goods_demand_blocked_by_poor_old_logic", "turn_reproduction_goods_demand_blocked_by_food",
            "turn_reproduction_goods_demand_blocked_by_sick_or_critical", "turn_reproduction_goods_spending_blocked_by_poor_old_logic",
            "turn_food_hard_shortage_count", "turn_medical_hard_shortage_count",
            "turn_education_goods_shortage_count", "turn_reproduction_goods_shortage_count",
            "turn_import_spending", "turn_export_income",
            "turn_government_purchase_food", "turn_government_purchase_medical_goods", "turn_government_purchase_spending",
            "turn_government_stockpile_food", "turn_government_stockpile_medical_goods", "turn_government_stockpile_spending",
            "turn_government_release_food", "turn_government_release_medical_goods", "turn_government_release_income",
            "turn_government_subsidy_value", "turn_market_stability_index", "turn_government_orderbook_purchase_spending", "turn_government_surplus_value",
            "turn_reproduction_goods_hard_buyer_count", "turn_reproduction_goods_hard_demand_total",
            "turn_reproduction_goods_hard_demand_satisfied", "turn_reproduction_goods_hard_demand_unsatisfied",
            "turn_reproduction_goods_blocked_no_company_stock", "turn_reproduction_goods_blocked_no_money",
            "turn_reproduction_goods_company_sales_volume", "turn_reproduction_goods_individual_sales_volume",
            "turn_food_aid_eligible_count", "turn_food_aid_received_count", "turn_food_aid_unmet_count",
            "turn_government_food_before_aid", "turn_government_food_after_aid", "turn_food_shortage_with_government_food_count",
            "turn_medical_aid_eligible_count", "turn_medical_aid_received_count", "turn_medical_aid_unmet_count",
            "turn_government_medical_goods_before_aid", "turn_government_medical_goods_after_aid", "turn_medical_shortage_with_government_medical_goods_count",
            "turn_critical_medical_need_count", "turn_critical_medical_aid_received_count", "turn_critical_medical_aid_unmet_count",
            "turn_medical_goods_bought_by_critical", "turn_medical_goods_bought_by_healthy",
            "turn_total_wages_paid", "turn_company_cash_before_wages", "turn_company_cash_after_wages", "turn_company_cash_after_resource_purchase",
            "turn_company_unable_to_pay_full_wages_count", "turn_company_production_stopped_by_cash_count", "turn_company_production_stopped_by_stock_count",
            "turn_effective_buy_willingness_sum", "turn_effective_buy_willingness_count", "turn_wage_consumption_bonus_sum",
            "turn_wage_responsive_buyer_count", "turn_wage_responsive_extra_cap_total", "turn_wage_funded_market_spending",
            "turn_worker_market_spending", "turn_worker_market_spending_to_company",
            "turn_inventory_sales_dividend_paid", "turn_inventory_sales_dividend_recipients",
            "turn_historical_inventory_sales_income", "turn_inventory_sales_dividend_eligible_branches",
            "turn_inventory_sales_dividend_blocked_by_cash_protection", "turn_inventory_sales_dividend_blocked_by_no_historical_income",
            "turn_inventory_sales_dividend_cash_floor",
            "turn_excess_cash_dividend_paid", "turn_excess_cash_dividend_recipients", "turn_excess_cash_dividend_pool",
            "turn_excess_cash_dividend_eligible_branches", "turn_excess_cash_dividend_blocked_by_no_excess_cash",
            "turn_excess_cash_dividend_blocked_by_no_recipients",
            "turn_death_life_end_with_reproduction_goods", "turn_death_life_end_with_food_for_birth",
            # dev37：低人口劳动空窗与寿命尾部诊断。仅记录，不改变劳动、繁殖或死亡行为。
            "turn_pop_below5_flag", "turn_pop_below3_flag",
            "turn_labor_eligible_count_when_pop_below5", "turn_labor_eligible_count_when_pop_below3",
            "turn_labor_willing_count_when_pop_below5", "turn_labor_willing_count_when_pop_below3",
            "turn_actual_worker_count_when_pop_below5", "turn_actual_worker_count_when_pop_below3",
            "turn_no_worker_reason_sick_count", "turn_no_worker_reason_critical_count",
            "turn_no_worker_reason_low_labor_count", "turn_no_worker_reason_no_company_demand_count",
            "turn_no_worker_reason_no_expected_profit_count", "turn_no_worker_reason_no_resource_count",
            "turn_company_demand_for_workers_when_pop_below5", "turn_company_demand_for_workers_when_pop_below3",
            "turn_branches_with_positive_expected_profit_when_pop_below5", "turn_branches_with_positive_expected_profit_when_pop_below3",
            "turn_branches_stopped_by_stock_when_pop_below5", "turn_branches_stopped_by_cash_when_pop_below5",
            "turn_branches_stopped_by_resource_when_pop_below5",
            "turn_government_production_resource_when_pop_below5", "turn_company_total_stock_when_pop_below5",
            "turn_company_total_money_when_pop_below5",
            "turn_low_pop_snapshot_count",
            "turn_last_individuals_avg_money", "turn_last_individuals_avg_food",
            "turn_last_individuals_avg_medical_goods", "turn_last_individuals_avg_reproduction_goods",
            "turn_last_individuals_avg_labor", "turn_last_individuals_avg_reproduce",
            "turn_last_individuals_avg_life_remaining", "turn_last_individuals_avg_age",
            "turn_last_individuals_sick_count", "turn_last_individuals_critical_count",
            "turn_last_individuals_can_work_count", "turn_last_individuals_can_reproduce_count",
            "turn_last_individuals_has_food_for_birth_count", "turn_last_individuals_has_reproduction_goods_count",
            "turn_life_end_with_can_reproduce", "turn_life_end_with_can_work",
            "turn_life_end_with_food_and_reproduction_goods",
            "turn_last_death_life_remaining", "turn_last_death_had_food_for_birth",
            "turn_last_death_had_reproduction_goods", "turn_last_death_was_sick",
            "turn_last_death_was_critical", "turn_last_death_could_work", "turn_last_death_could_reproduce",
            # dev38：继续核查低人口劳动转化与父代食物安全线。只记录，不参与决策。
            "turn_labor_candidate_raw_count", "turn_labor_candidates_trimmed_by_tendency",
            "turn_labor_allocated_candidate_count", "turn_labor_candidates_without_allocation",
            "turn_labor_positive_profit_but_no_worker_when_pop_below5",
            "turn_parent_food_requirement", "turn_potential_parent_count_when_pop_below5",
            "turn_potential_parent_with_reproduction_goods_when_pop_below5",
            "turn_potential_parent_food_ready_when_pop_below5",
            "turn_parent_food_gap_when_pop_below5", "turn_parent_food_gap_when_pop_below3",
            "turn_last_individuals_parent_food_gap_avg",
            "turn_food_bought_by_potential_parent", "turn_food_aid_to_potential_parent",
            "turn_birth_blocked_food_safety_with_reproduction_goods",
            # M6A：医疗/教育/生育安全/政策压力/公司韧性观测字段。
            "turn_medical_recovery_count", "turn_health_deterioration_count",
            "turn_reproductive_security_bonus_sum", "turn_reproductive_security_count",
            "turn_company_resilience_score", "turn_government_policy_pressure_score",
            # 系统级第七阶段：进化方向加权算法与周期性诊断。只记录定向进化偏置，不影响自然遗传变异。
            "turn_evolution_sample_count", "turn_evolution_direction_change_count",
            "turn_evolution_fitness_avg", "turn_evolution_fitness_gap_morality",
            "turn_evolution_fitness_gap_strength", "turn_evolution_fitness_gap_reproduce",
            "turn_evolution_fitness_gap_labor", "turn_evolution_signal_morality",
            "turn_evolution_signal_strength", "turn_evolution_signal_reproduce", "turn_evolution_signal_labor",
        ]:
            setattr(self, name, {p: 0 for p in self.population_names})

        # dev24：累计出生/死亡与阻断诊断。不同于 turn_* 字段，累计字段不会在每回合开始时清零。
        self.cumulative_birth_count = {p: 0 for p in self.population_names}
        self.cumulative_death_count = {p: 0 for p in self.population_names}
        self.cumulative_birth_blocked_critical = {p: 0 for p in self.population_names}
        self.cumulative_birth_blocked_sick = {p: 0 for p in self.population_names}
        self.cumulative_birth_blocked_no_money = {p: 0 for p in self.population_names}
        self.cumulative_birth_blocked_no_reproduction_goods = {p: 0 for p in self.population_names}
        self.cumulative_birth_blocked_no_food_safety = {p: 0 for p in self.population_names}
        self.cumulative_birth_blocked_low_reproduce_chance = {p: 0 for p in self.population_names}
        self.cumulative_birth_blocked_other = {p: 0 for p in self.population_names}

        # dev31：单人断代诊断。只记录状态，不改变人口、生育或死亡逻辑。
        self.single_survivor_turn_count = {p: 0 for p in self.population_names}
        self.turns_at_population_below3 = {p: 0 for p in self.population_names}
        self.last_survivor_death_reason = {p: "" for p in self.population_names}
        self.last_survivor_reproduce_chance_failed = {p: 0 for p in self.population_names}
        self.last_survivor_had_reproduction_goods = {p: 0 for p in self.population_names}
        self.last_survivor_had_food_for_birth = {p: 0 for p in self.population_names}
        # dev36：低人口劳动者空窗与寿命断代累计诊断。只记录，不改变人口或公司行为。
        self.turns_with_no_workers_when_pop_below5 = {p: 0 for p in self.population_names}
        self.turns_with_no_wages_when_pop_below5 = {p: 0 for p in self.population_names}
        self.company_has_cash_but_no_workers_count = {p: 0 for p in self.population_names}
        self.company_has_stock_but_no_workers_count = {p: 0 for p in self.population_names}
        self.death_life_end_with_reproduction_goods = {p: 0 for p in self.population_names}
        self.death_life_end_with_food_for_birth = {p: 0 for p in self.population_names}

        # dev37：低人口诊断累计项。只记录低人口阶段出现频率，不作为任何机制输入。
        self.pop_below5_turn_count = {p: 0 for p in self.population_names}
        self.pop_below3_turn_count = {p: 0 for p in self.population_names}

        # BOT8 dev7：每回合灾害类型记录。空字符串表示本回合该部族未受到灾害。
        self.turn_disaster_type = {p: "" for p in self.population_names}

        self.death_survival_rounds = {p: [] for p in self.population_names}
        self.evolution_ready = {p: False for p in self.population_names}
        self.evolution_direction = {p: {"morality": 0, "strength": 0, "reproduce": 0, "labor": 0} for p in self.population_names}
        # 系统级第七阶段：定向进化平滑分数和方向历史。自然变异仍独立存在。
        self.evolution_direction_score = {p: {"morality": 0.0, "strength": 0.0, "reproduce": 0.0, "labor": 0.0} for p in self.population_names}
        self.evolution_direction_history = {p: [] for p in self.population_names}
        self.evolution_samples = {p: [] for p in self.population_names}
        self.avg_stat = {p: {"intelligence": [], "strength": [], "balance": [], "dead_lifespan": [], "labor": [], "morality": [], "reproduce": [], "critical": []} for p in self.population_names}

        # 机制调度运行态：
        # 1. cfg["switches"] 是总开关。总开关关闭时，调度永远不生效。
        # 2. effective_switches 是运行中的实际开关状态，会被启用/禁用回合持续修改。
        # 3. switch_schedule_events 会把设置界面里的字符串转换成整数回合集合。
        self.effective_switches = copy.deepcopy(self.cfg.get("switches", {}))
        self.switch_schedule_events = self.prepare_switch_schedule_events()

        self.update_total_wealth()

    def apply_small_group_initial_conditions(self):
        """dev31：小族群正常初始条件预设。

        该函数只在初始化时运行，且只在 initial_population 不高于阈值时生效。
        它不是人口恢复机制，不会在运行过程中补发资源、提高出生率或阻止死亡。
        """
        base = self.cfg.get("base", {})
        if not bool(base.get("enable_small_group_initial_conditions", False)):
            return
        initial_population = int(base.get("initial_population", 0))
        threshold = int(base.get("small_group_initial_population_threshold", 5))
        if initial_population <= 0 or initial_population > threshold:
            return
        survival_cost = max(0, int(base.get("survival_cost", 100)))
        child_units = max(0, self.reproduction_goods_required_per_birth())
        food_rounds = max(0, int(base.get("small_group_initial_food_rounds", 5)))
        medical_ratio = max(0, int(base.get("small_group_initial_medical_goods_ratio", 50)))
        reproduction_ratio = max(0, int(base.get("small_group_initial_reproduction_goods_ratio", 100)))
        target_food = int(survival_cost * food_rounds)
        target_medical = int(survival_cost * medical_ratio / 100)
        target_reproduction = int(child_units * reproduction_ratio / 100)
        for p, pop in self.populations.items():
            for ind in pop:
                ind.food = max(int(getattr(ind, "food", 0)), target_food)
                ind.medical_goods = max(int(getattr(ind, "medical_goods", 0)), target_medical)
                if int(getattr(ind, "reproduce", 0)) >= 10:
                    ind.reproduction_goods = max(int(getattr(ind, "reproduction_goods", 0)), target_reproduction)

    def class_rank_label(self, p, balance):
        return Individual.class_rank_and_label(balance, self.cfg, self.state["population_config"][p])

    def update_individual_class(self, p, ind):
        current_rank, current_label = self.class_rank_label(p, ind.balance)
        ind.current_class = current_label
        birth_label = getattr(ind, "birth_class", "")
        label_to_rank = {"Poor": 0, "Lower": 1, "Middle": 2, "Rich": 3}
        birth_rank = label_to_rank.get(birth_label, current_rank)
        ind.class_change = int(current_rank - birth_rank)
        ind.is_upward_mobile = int(ind.class_change > 0)
        ind.is_downward_mobile = int(ind.class_change < 0)
        return current_rank, current_label

    def get_class_summary(self, p, pop):
        counts = {"Poor": 0, "Lower": 0, "Middle": 0, "Rich": 0}
        upward = 0
        downward = 0
        same = 0
        for ind in pop:
            self.update_individual_class(p, ind)
            counts[ind.current_class] = counts.get(ind.current_class, 0) + 1
            if ind.class_change > 0:
                upward += 1
            elif ind.class_change < 0:
                downward += 1
            else:
                same += 1
        total = max(1, len(pop))
        return {
            "PoorCount": counts["Poor"],
            "LowerCount": counts["Lower"],
            "MiddleCount": counts["Middle"],
            "RichCount": counts["Rich"],
            "UpwardMobilityCount": upward,
            "DownwardMobilityCount": downward,
            "SameClassCount": same,
            "UpwardMobilityRate": round(upward / total * 100, 4),
            "DownwardMobilityRate": round(downward / total * 100, 4),
        }

    def prepare_switch_schedule_events(self):
        events = {}
        schedules = self.cfg.get("switch_schedules", {})
        for switch_key in self.cfg.get("switches", {}):
            data = schedules.get(switch_key, {})
            events[switch_key] = {
                "enable": parse_round_list(data.get("enable_rounds", "")),
                "disable": parse_round_list(data.get("disable_rounds", "")),
            }
        return events

    def apply_switch_schedules(self):
        for switch_key, base_enabled in self.cfg.get("switches", {}).items():
            if not base_enabled:
                self.effective_switches[switch_key] = False
                continue
            events = self.switch_schedule_events.get(switch_key, {})
            if self.turn in events.get("disable", set()):
                self.effective_switches[switch_key] = False
            if self.turn in events.get("enable", set()):
                self.effective_switches[switch_key] = True

    def is_feature_enabled(self, switch_key):
        return bool(self.cfg.get("switches", {}).get(switch_key, False)) and bool(self.effective_switches.get(switch_key, False))

    def reproduction_goods_required_per_birth(self):
        # dev29：显式生育用品需求，避免继续把 child_initial_balance 同时当作货币、食物和生育用品。
        return max(0, int(self.cfg["base"].get(
            "reproduction_goods_required_per_birth",
            self.cfg["base"].get("child_initial_balance", 100),
        )))

    def child_initial_money_amount(self):
        # dev29：子代初始货币是独立语义；旧设置缺失时才回退到 child_initial_balance 以保持兼容。
        return max(0, int(self.cfg["base"].get(
            "child_initial_money",
            self.cfg["base"].get("child_initial_balance", 0),
        )))

    def child_initial_food_amount(self):
        # dev29：子代初始食物是由父代转移的实物，且不应在出生当回合被 survival_phase 消耗。
        return max(0, int(self.cfg["base"].get(
            "child_initial_food",
            self.cfg["base"].get("survival_cost", 100),
        )))

    def parent_food_required_for_birth(self):
        survival_cost = max(0, int(self.cfg["base"].get("survival_cost", 100)))
        multiplier = max(0, int(self.cfg["base"].get("parent_food_required_for_birth_multiplier", 3)))
        return int(survival_cost * multiplier)

    def reset_turn_records(self):
        for attr in [a for a in self.__dict__ if a.startswith("turn_") and isinstance(getattr(self, a), dict)]:
            for p in getattr(self, attr):
                getattr(self, attr)[p] = 0
        self.dead_individuals_this_turn = []
        self.newborns_this_turn = []
        self.turn_branch_workers = {p: {good: [] for good in GOOD_FIELDS} for p in self.population_names}
        if hasattr(self, "companies"):
            for comp in self.companies.values():
                for branch in comp.values():
                    branch["last_sales_volume"] = branch.get("sales_volume", 0)
                    branch["wages_paid"] = 0
                    branch["sales_income"] = 0
                    branch["historical_inventory_sales_income"] = 0
                    branch["goods_produced"] = 0
                    branch["sales_volume"] = 0
        if hasattr(self, "current_goods_consumption"):
            self.current_goods_consumption = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        if hasattr(self, "turn_goods_production"):
            self.turn_goods_production = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        if hasattr(self, "turn_goods_tax"):
            self.turn_goods_tax = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        if hasattr(self, "turn_market_demand"):
            self.turn_market_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_supply"):
            self.turn_market_supply = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_volume_by_good"):
            self.turn_market_volume_by_good = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_unmet_demand"):
            self.turn_market_unmet_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_unsold_supply"):
            self.turn_market_unsold_supply = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_local_volume"):
            self.turn_market_local_volume = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_import_volume"):
            self.turn_market_import_volume = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_export_volume"):
            self.turn_market_export_volume = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_hard_demand"):
            self.turn_hard_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_reserve_demand"):
            self.turn_reserve_demand = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_trade_tax_income"):
            self.turn_trade_tax_income = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_import_tax_income"):
            self.turn_import_tax_income = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_import_spending"):
            self.turn_import_spending = {p: 0 for p in self.population_names}
        if hasattr(self, "turn_export_income"):
            self.turn_export_income = {p: 0 for p in self.population_names}
        for macro_attr in [
            "turn_government_stockpile_food", "turn_government_stockpile_medical_goods", "turn_government_stockpile_spending",
            "turn_government_release_food", "turn_government_release_medical_goods", "turn_government_release_income",
            "turn_government_subsidy_value", "turn_market_stability_index", "turn_government_orderbook_purchase_spending", "turn_government_surplus_value",
            "turn_reproduction_goods_hard_buyer_count", "turn_reproduction_goods_hard_demand_total",
            "turn_reproduction_goods_hard_demand_satisfied", "turn_reproduction_goods_hard_demand_unsatisfied",
            "turn_reproduction_goods_blocked_no_company_stock", "turn_reproduction_goods_blocked_no_money",
            "turn_reproduction_goods_company_sales_volume", "turn_reproduction_goods_individual_sales_volume",
        ]:
            if hasattr(self, macro_attr):
                setattr(self, macro_attr, {p: 0 for p in self.population_names})
        if hasattr(self, "turn_market_trade_money_by_good"):
            self.turn_market_trade_money_by_good = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_market_trade_amount_by_good"):
            self.turn_market_trade_amount_by_good = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_government_orderbook_purchase"):
            self.turn_government_orderbook_purchase = {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names}
        if hasattr(self, "turn_government_surplus_deleted"):
            self.turn_government_surplus_deleted = {p: {good: 0 for good in GOOD_FIELDS} for p in self.population_names}
        for company_inventory_attr in [
            "turn_company_inventory_listed",
            "turn_company_inventory_sold_to_individuals",
            "turn_company_inventory_sold_to_government",
            "turn_company_inventory_unsold",
            "turn_company_inventory_listing_ratio",
            "turn_company_orderbook_ask_count",
            "turn_company_hard_need_release_pressure",
            "turn_company_hard_need_release_listed",
            "turn_company_sellable_stock",
        ]:
            if hasattr(self, company_inventory_attr):
                setattr(self, company_inventory_attr, {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names})
        for resilience_attr in ["turn_repro_education_resilience_gap", "turn_repro_education_resilience_weight_added"]:
            if hasattr(self, resilience_attr):
                setattr(self, resilience_attr, {p: {"education_goods": 0, "reproduction_goods": 0} for p in self.population_names})
        for dev44_attr in ["turn_hard_need_production_bonus", "turn_hard_need_unmet_for_production"]:
            if hasattr(self, dev44_attr):
                setattr(self, dev44_attr, {p: {good: 0 for good in TRADED_GOODS} for p in self.population_names})
        if hasattr(self, "turn_disaster_type"):
            for p in self.turn_disaster_type:
                self.turn_disaster_type[p] = ""

    def reset_individual_turn_records(self):
        for p, pop in self.populations.items():
            for ind in pop:
                ind.reset_turn_detail()
                # BOT8 dev16：进化机制改为按“货币 + 商品按当前价格折算”的总市场价值变化判断。
                # 回合开始价值使用本回合开始时价格，回合后价值使用进化采样时价格，因此价格变化也会影响适应度。
                ind.turn_start_market_value = self.inventory_total_value(ind, p)
                ind.pre_survival_market_value = ind.turn_start_market_value

    def snapshot_balances(self, field_name):
        for pop in self.populations.values():
            for ind in pop:
                setattr(ind, field_name, ind.balance)

    def update_total_wealth(self):
        # dev21：公司货币进入货币守恒统计。商品价值另行在汇总字段中输出。
        company_money = 0
        if hasattr(self, "companies"):
            company_money = sum(branch.get("money", 0) for comp in self.companies.values() for branch in comp.values())
        self.total_social_wealth = int(sum(i.balance for pop in self.populations.values() for i in pop) + sum(self.government_deposit.values()) + company_money)

    def log_event(self, phase, message, entity_type="unknown", entity_id="", population="", event_type="text_log", data=None):
        # 运行 GUI 实时日志：按阶段记录关键行为，避免只看汇总数字无法定位机制问题。
        entry = f"第{self.turn}回合｜{phase}｜{message}"
        self.event_logs.append(entry)
        if len(self.event_logs) > getattr(self, "max_event_logs", 800):
            self.event_logs = self.event_logs[-self.max_event_logs:]
        # 系统级开发：同步写入结构化事件流。旧调用仍只传 phase/message，不改变模型行为。
        if hasattr(self, "event_stream"):
            inferred_entity_type = entity_type
            if inferred_entity_type == "unknown":
                phase_text = str(phase)
                if "政府" in phase_text or "剩余价值" in phase_text:
                    inferred_entity_type = "government"
                elif "公司" in phase_text or "劳动" in phase_text or "分红" in phase_text:
                    inferred_entity_type = "company"
                elif "购买" in phase_text or "市场" in phase_text or "订单" in phase_text:
                    inferred_entity_type = "market"
                elif "生育" in phase_text or "死亡" in phase_text or "救助" in phase_text:
                    inferred_entity_type = "individual"
            self.event_stream.append(
                turn=self.turn,
                phase=phase,
                message=message,
                entity_type=inferred_entity_type,
                entity_id=entity_id,
                population=population,
                event_type=event_type,
                data=data or {},
            )

    def log_structured_event(self, phase, message, entity_type="unknown", entity_id="", population="", event_type="text_log", data=None):
        """Explicit structured-event helper for future GUI/event-stream integrations."""
        self.log_event(phase, message, entity_type=entity_type, entity_id=entity_id, population=population, event_type=event_type, data=data)

    def make_individual_code(self, population_name, ancestor_index, birth_turn, lineage_sequence):
        return f"{population_name}{int(ancestor_index):03d}{int(birth_turn):04d}{int(lineage_sequence):05d}"

    def assign_initial_code(self, population_name, ind):
        self.ancestor_counters[population_name] += 1
        ancestor = self.ancestor_counters[population_name]
        self.lineage_counters[population_name][ancestor] = 1
        ind.ancestor_index = ancestor
        ind.lineage_sequence = 1
        ind.code = self.make_individual_code(population_name, ancestor, 0, 1)
        ind.ancestor_code = ind.code
        ind.population_name = population_name

    def assign_child_code(self, population_name, child, parent):
        ancestor = int(getattr(parent, "ancestor_index", 0) or 0)
        if ancestor <= 0:
            self.assign_initial_code(population_name, child)
            return
        self.lineage_counters.setdefault(population_name, {}).setdefault(ancestor, 1)
        self.lineage_counters[population_name][ancestor] += 1
        seq = self.lineage_counters[population_name][ancestor]
        child.ancestor_index = ancestor
        child.lineage_sequence = seq
        child.code = self.make_individual_code(population_name, ancestor, self.turn, seq)
        child.ancestor_code = getattr(parent, "ancestor_code", "") or self.make_individual_code(population_name, ancestor, 0, 1)
        child.population_name = population_name

    def initial_population_reference(self, p=None):
        """dev42：初始资产规模默认与族群规模关联。当前模型各部族使用 base.initial_population。
        单独封装，便于后续支持每部族不同初始人口。"""
        return max(0, int(self.cfg.get("base", {}).get("initial_population", 0)))

    def use_population_scaled_initials(self, p):
        cfg = self.state.get("population_config", {}).get(p, {})
        return bool(int(cfg.get("use_population_scaled_initials", 1)))

    def scaled_or_manual_company_initial_money(self, p):
        cfg = self.state.get("population_config", {}).get(p, {})
        if self.use_population_scaled_initials(p):
            per_capita = max(0, int(cfg.get("company_initial_money_per_capita", 400)))
            return int(self.initial_population_reference(p) * per_capita)
        return max(0, int(cfg.get("company_initial_money", 2000)))

    def scaled_company_initial_stock_target(self, p, good):
        cfg = self.state.get("population_config", {}).get(p, {})
        pop_ref = self.initial_population_reference(p)
        survival_cost = max(1, int(self.cfg.get("base", {}).get("survival_cost", 100)))
        child_units = max(1, self.reproduction_goods_required_per_birth())
        if good == "food":
            rounds = max(0, int(cfg.get("company_initial_food_rounds", 3)))
            return int(pop_ref * survival_cost * rounds)
        if good == "medical_goods":
            ratio = max(0, int(cfg.get("company_initial_medical_goods_ratio", 50)))
            return int(round(pop_ref * survival_cost * ratio / 100))
        if good == "education_goods":
            ratio = max(0, int(cfg.get("company_initial_education_goods_ratio", 100)))
            return int(round(pop_ref * child_units * ratio / 100))
        if good == "reproduction_goods":
            ratio = max(0, int(cfg.get("company_initial_reproduction_goods_ratio", 100)))
            return int(round(pop_ref * child_units * ratio / 100))
        return 0

    def company_operating_stock_target(self, p, good):
        """dev43：公司运行期库存目标。

        dev42 已把初始库存按族群规模关联，但旧的生产收益评估仍长期使用
        branch.initial_stock 作为库存过剩惩罚基准。人口增长后，如果仍用开局目标，
        公司会在环境资源尚未接近上限、刚需仍未完全满足时误判为“库存过剩”而压制生产。

        该函数只用于生产/定价/库存压力判断，不创造资源、不改变出生率；
        它让公司库存目标随当前人口和已有商品机制需求自然变化。
        """
        cfg = self.state.get("population_config", {}).get(p, {})
        current_pop = max(1, len(self.populations.get(p, [])))
        survival_cost = max(1, int(self.cfg.get("base", {}).get("survival_cost", 100)))
        child_units = max(1, self.reproduction_goods_required_per_birth())
        if good == "food":
            rounds = max(0, int(cfg.get("company_initial_food_rounds", 3)))
            return max(1, int(current_pop * survival_cost * rounds))
        if good == "medical_goods":
            ratio = max(0, int(cfg.get("company_initial_medical_goods_ratio", 50)))
            return max(1, int(round(current_pop * survival_cost * ratio / 100)))
        if good == "education_goods":
            ratio = max(0, int(cfg.get("company_initial_education_goods_ratio", 100)))
            if int(cfg.get("enable_repro_education_inventory_resilience", 1)):
                ratio = max(ratio, max(0, int(cfg.get("education_inventory_target_births_ratio", 100))))
            return max(1, int(round(current_pop * child_units * ratio / 100)))
        if good == "reproduction_goods":
            ratio = max(0, int(cfg.get("company_initial_reproduction_goods_ratio", 100)))
            if int(cfg.get("enable_repro_education_inventory_resilience", 1)):
                ratio = max(ratio, max(0, int(cfg.get("repro_inventory_target_births_ratio", 150))))
            return max(1, int(round(current_pop * child_units * ratio / 100)))
        return max(1, int(self.companies.get(p, {}).get(good, {}).get("initial_stock", 1)))

    def apply_population_scaled_government_initials(self):
        """dev42：政府初始财政/公共库存可按族群规模生成。
        这是初始化条件，不是运行中补贴；关闭 use_population_scaled_initials 后保持手动/旧逻辑。"""
        for p in self.population_names:
            cfg = self.state.get("population_config", {}).get(p, {})
            if not self.use_population_scaled_initials(p):
                continue
            pop_ref = self.initial_population_reference(p)
            survival_cost = max(1, int(self.cfg.get("base", {}).get("survival_cost", 100)))
            child_units = max(1, self.reproduction_goods_required_per_birth())
            self.government_deposit[p] = max(0, int(cfg.get("government_initial_money_per_capita", 20))) * pop_ref
            self.government_food[p] = int(pop_ref * survival_cost * max(0, int(cfg.get("government_initial_food_rounds", 1))))
            self.government_medical_goods[p] = int(round(pop_ref * survival_cost * max(0, int(cfg.get("government_initial_medical_goods_ratio", 25))) / 100))
            self.government_education_goods[p] = int(round(pop_ref * child_units * max(0, int(cfg.get("government_initial_education_goods_ratio", 25))) / 100))
            self.government_reproduction_goods[p] = int(round(pop_ref * child_units * max(0, int(cfg.get("government_initial_reproduction_goods_ratio", 25))) / 100))
            self.government_tools[p] = 0

    def initialize_companies(self):
        # 公司总初始货币由部族参数决定，按固定比例分配给各商品分公司。工具分公司保留但暂不实装生产用途。
        # dev22：分公司拥有“初始库存目标”和同量初始库存，用于形成真实的库存目标，而不是以 0 作为销售目标。
        companies = {}
        money_ratios = {"food": 55, "medical_goods": 15, "education_goods": 10, "reproduction_goods": 20, "tools": 0}
        for p in self.population_names:
            cfg = self.state["population_config"].get(p, {})
            total = self.scaled_or_manual_company_initial_money(p)
            companies[p] = {}
            stock_targets = {good: self.scaled_company_initial_stock_target(p, good) for good in GOOD_FIELDS}
            allocated = 0
            for idx, good in enumerate(GOOD_FIELDS):
                if idx == len(GOOD_FIELDS) - 1:
                    money = max(0, total - allocated)
                else:
                    money = int(round(total * money_ratios.get(good, 0) / 100))
                    allocated += money
                initial_stock = max(0, int(stock_targets.get(good, 0)))
                companies[p][good] = {
                    "money": money,
                    "initial_money": money,
                    "stock": initial_stock,
                    "initial_stock": initial_stock,
                    "wages_paid": 0,
                    "sales_income": 0,
                    "goods_produced": 0,
                    "sales_volume": 0,
                }
        return companies

    def company_totals(self, p):
        comp = self.companies.get(p, {}) if hasattr(self, "companies") else {}
        return {
            "money": int(sum(b.get("money", 0) for b in comp.values())),
            "stock": int(sum(b.get("stock", 0) for b in comp.values())),
            "wages": int(sum(b.get("wages_paid", 0) for b in comp.values())),
            "sales": int(sum(b.get("sales_income", 0) for b in comp.values())),
            "produced": int(sum(b.get("goods_produced", 0) for b in comp.values())),
        }

    def company_transfer_money_to_branch(self, p, target_good, needed):
        # dev24：回调 dev23 的“分公司之间自动调剂货币”。
        # 分公司继续保持独立货币账户；某分公司资金不足时，不再从其他分公司自动调入资金。
        return 0

    def is_tax_enabled(self):
        return self.is_feature_enabled("enable_tax_system")

    def good_value(self, obj, population=None):
        # BOT8 dev14：商品价值统计使用当前部族价格指数换算。
        # 这只影响统计价值，不改变实际商品数量。工具未进入市场时仍按 1:1 估值。
        total = 0
        for good in GOOD_FIELDS:
            amount = max(0, int(getattr(obj, good, 0)))
            if population is not None and good in TRADED_GOODS:
                total += int(round(amount * self.goods_price_index(population, good) / 100))
            else:
                total += amount
        return int(total)

    def government_good_stock(self, p, good):
        return getattr(self, f"government_{good}")[p]

    def add_government_good(self, p, good, amount):
        amount = int(max(0, amount))
        if amount <= 0:
            return 0
        getattr(self, f"government_{good}")[p] += amount
        return amount

    def remove_government_good(self, p, good, amount):
        stock = getattr(self, f"government_{good}")
        take = min(max(0, int(amount)), stock[p])
        stock[p] -= take
        return take

    def consume_individual_good(self, p, ind, good, amount):
        amount = int(max(0, amount))
        have = int(max(0, getattr(ind, good, 0)))
        take = min(have, amount)
        setattr(ind, good, have - take)
        if take > 0:
            self.current_goods_consumption[p][good] += take
            setattr(ind, f"{good}_consumed", getattr(ind, f"{good}_consumed", 0) + take)
        return take

    def transfer_all_goods_to_government(self, p, ind):
        for good in GOOD_FIELDS:
            amount = int(max(0, getattr(ind, good, 0)))
            if amount > 0:
                self.add_government_good(p, good, amount)
                setattr(ind, good, 0)

    def inventory_total_value(self, ind, population=None):
        # BOT8 dev14：全库存价值 = 货币 + 按当前价格指数折算的商品价值。
        return int(max(0, getattr(ind, "balance", 0)) + self.good_value(ind, population))

    def plunder_inventory_by_ratio(self, attacker, target, ratio, prefix, loss_population=None, gain_population=None):
        # BOT8 dev9：全库存掠夺/侵略通用函数。
        # 货币只转移不损耗，以保持货币总量守恒；商品按 plunder_gain_rate 转移，剩余作为商品损耗。
        ratio = max(0, min(100, int(ratio)))
        retain_rate = max(0, min(100, int(self.cfg["behavior"].get("plunder_gain_rate", 50))))

        money_loss = min(target.balance, int(round(target.balance * ratio / 100)))
        if money_loss > 0:
            target.balance -= money_loss
            attacker.balance += money_loss

        goods_loss_total = 0
        goods_gain_total = 0
        goods_system_loss_total = 0
        goods_loss_value_total = 0
        goods_gain_value_total = 0
        per_good = {}
        for good in GOOD_FIELDS:
            have = int(max(0, getattr(target, good, 0)))
            loss = min(have, int(round(have * ratio / 100)))
            gain = int(round(loss * retain_rate / 100))
            system_loss = max(0, loss - gain)
            if loss > 0:
                setattr(target, good, have - loss)
                setattr(attacker, good, int(getattr(attacker, good, 0)) + gain)
            goods_loss_total += loss
            goods_gain_total += gain
            goods_system_loss_total += system_loss
            loss_price = self.goods_price_index(loss_population, good) if loss_population is not None and good in TRADED_GOODS else 100
            gain_price = self.goods_price_index(gain_population, good) if gain_population is not None and good in TRADED_GOODS else 100
            loss_value = int(round(loss * loss_price / 100))
            gain_value = int(round(gain * gain_price / 100))
            goods_loss_value_total += loss_value
            goods_gain_value_total += gain_value
            per_good[good] = {"loss": loss, "gain": gain, "system_loss": system_loss, "loss_value": loss_value, "gain_value": gain_value}

            setattr(attacker, f"{prefix}_{good}_gain", getattr(attacker, f"{prefix}_{good}_gain", 0) + gain)
            setattr(target, f"{prefix}_{good}_loss", getattr(target, f"{prefix}_{good}_loss", 0) + loss)

        total_value_loss = money_loss + goods_loss_value_total
        total_value_gain = money_loss + goods_gain_value_total
        return {
            "money_loss": money_loss,
            "money_gain": money_loss,
            "goods_loss": goods_loss_total,
            "goods_gain": goods_gain_total,
            "goods_system_loss": goods_system_loss_total,
            "goods_loss_value": goods_loss_value_total,
            "goods_gain_value": goods_gain_value_total,
            "total_value_loss": total_value_loss,
            "total_value_gain": total_value_gain,
            "per_good": per_good,
        }

    def calculate_gini(self, values):
        values = sorted(max(0, int(v)) for v in values)
        n, total = len(values), sum(values)
        if n == 0 or total <= 0:
            return 0.0
        weighted = sum(idx * v for idx, v in enumerate(values, start=1))
        return round(max(0.0, min(1.0, (2 * weighted) / (n * total) - (n + 1) / n)), 4)

    def median_value(self, values):
        if not values:
            return 0
        values = sorted(values)
        mid = len(values) // 2
        if len(values) % 2:
            return values[mid]
        return int(round((values[mid - 1] + values[mid]) / 2))
    def bottom_percent_average(self, values, percent=20):
        values = sorted(int(v) for v in values)
        if not values:
            return 0
        n = max(1, int(math.ceil(len(values) * max(0, min(100, percent)) / 100)))
        return int(round(sum(values[:n]) / max(1, n)))

    def age_round_of(self, ind):
        return int(self.turn - int(getattr(ind, "birth_turn", 0)) + int(getattr(ind, "initial_age_rounds", 0)))

    def cohort_stats(self, pop, predicate):
        members = [i for i in pop if predicate(i)]
        if not members:
            return {
                "count": 0,
                "food": 0,
                "money": 0,
                "medical": 0,
                "reproduction": 0,
                "critical": 0,
            }
        count = len(members)
        return {
            "count": count,
            "food": int(round(sum(int(getattr(i, "food", 0)) for i in members) / count)),
            "money": int(round(sum(int(getattr(i, "balance", 0)) for i in members) / count)),
            "medical": int(round(sum(int(getattr(i, "medical_goods", 0)) for i in members) / count)),
            "reproduction": int(round(sum(int(getattr(i, "reproduction_goods", 0)) for i in members) / count)),
            "critical": sum(1 for i in members if getattr(i, "critical", False)),
        }


    def morality_check(self, morality, trust=50, unrest_bonus=0):
        # BOT8 dev5：道德检定加入部族社会信任修正。
        # 基础概率仍为 BOT8 2.2.0 的平滑线性函数；信任越高，掠夺越少、救助越多。
        morality = max(0, min(100, int(morality)))
        trust = max(0, min(100, float(trust)))
        base_plunder = 40 * (100 - morality) / 100
        base_rescue = 40 * morality / 100
        plunder = int(round(base_plunder * (1 - trust / 200) + unrest_bonus))
        rescue = int(round(base_rescue * (0.75 + trust / 200)))
        plunder = max(0, min(100, plunder))
        rescue = max(0, min(100 - plunder, rescue))
        roll = random.randint(1, 100)
        return "plunder" if roll <= plunder else ("rescue" if roll <= plunder + rescue else "normal")

    def plunder_gain_after_loss(self, loss_amount):
        return int(round(loss_amount * self.cfg["behavior"]["plunder_gain_rate"] / 100))

    def invasion_probability(self, ind):
        b, beh = self.cfg["base"], self.cfg["behavior"]
        strength_score = int(round((ind.strength - b["min_strength"]) / max(1, b["max_strength"] - b["min_strength"]) * 100))
        strength_score = max(0, min(100, strength_score))
        balance_score = 100 - int(round(min(ind.balance, 1000) / 1000 * 100))
        balance_score = max(0, min(100, balance_score))
        raw_probability = max(0, min(100, int(round(strength_score * beh["invasion_strength_weight"] / 100 + balance_score * beh["invasion_poverty_weight"] / 100))))
        # BOT8 2.2.0：基础侵略风险用于降低普通回合中的侵略频率，避免侵略成为过强主导机制。
        return max(0, min(100, int(round(raw_probability * beh.get("invasion_base_risk", 20) / 100))))

    def invasion_success_probability(self, attacker_strength, target_strength):
        sigma = max(1, self.cfg["behavior"]["invasion_success_sigma"])
        z = (attacker_strength - target_strength) / (math.sqrt(2) * sigma)
        return int(round(max(5, min(95, 50 + 45 * math.erf(z)))))


    def disaster_phase(self):
        # BOT8 dev7：灾害与系统韧性机制。
        # 灾害被设计为低频外部冲击，用于检验环境健康、政府存款、教育、信任和阶层结构的抗冲击能力。
        # 四类灾害对应社会—生态系统中的常见冲击：干旱、疫病、经济危机、社会动荡。
        if not self.is_feature_enabled("enable_disaster"):
            return

        probability = max(0, min(100, int(self.cfg["base"].get("disaster_probability", 3))))
        if random.randint(1, 100) > probability:
            return

        strength = max(0, min(100, int(self.cfg["base"].get("disaster_strength", 20))))
        disaster_type = random.choice(["Drought", "Epidemic", "EconomicCrisis", "SocialUnrest"])

        for p in self.population_names:
            self.turn_disaster_occurred[p] = 1
            self.turn_disaster_type[p] = disaster_type
            self.turn_disaster_strength[p] = strength

        if disaster_type == "Epidemic":
            # 疫病：按强度比例随机影响个体，受影响者寿命 -1。
            for p, pop in self.populations.items():
                if not pop:
                    continue
                affected_count = max(1, int(round(len(pop) * strength / 100)))
                affected = random.sample(pop, min(len(pop), affected_count))
                for ind in affected:
                    ind.life -= 1
                    ind.affected_by_disaster = 1
                    ind.disaster_life_loss += 1
                    self.turn_disaster_life_loss[p] += 1

        elif disaster_type == "EconomicCrisis":
            # 经济危机：为保持“无政府发行时货币总量守恒”，危机不再销毁货币。
            # 受影响货币转入政府存款，可解释为危机强制回收、债务清算或紧急财政接管。
            for p, pop in self.populations.items():
                for ind in pop:
                    loss = int(round(ind.balance * strength / 100))
                    if loss <= 0:
                        continue
                    loss = min(loss, ind.balance)
                    ind.balance -= loss
                    self.government_deposit[p] += loss
                    ind.affected_by_disaster = 1
                    ind.disaster_balance_loss += loss
                    self.turn_disaster_wealth_loss[p] += loss

        elif disaster_type == "SocialUnrest":
            # 社会动荡：降低本回合部族信任，并临时提高道德检定中的掠夺概率。
            # 信任损失和掠夺加成都由 disaster_strength 推导，避免引入更多参数。
            trust_loss = max(1, int(round(strength / 5)))
            plunder_bonus = max(1, int(round(strength / 5)))
            for p in self.population_names:
                old = self.tribe_trust.get(p, 50)
                self.tribe_trust[p] = max(0, old - trust_loss)
                actual_loss = old - self.tribe_trust[p]
                self.turn_disaster_trust_loss[p] += round(actual_loss, 4)
                self.turn_disaster_plunder_bonus[p] = plunder_bonus

        # Drought 不在这里直接扣资源，而是在 start_phase 的资源再生计算中降低本回合实际再生。

    def start_phase(self):
        self.reset_turn_records()
        self.reset_individual_turn_records()
        self.disaster_phase()

        # BOT8 2.1.0：环境再生受环境健康影响，并受到生态承载力上限限制。
        # 实际再生 = 基础再生 × EnvHealth / 100；再生后资源不能超过 EnvCapacity。
        if self.is_feature_enabled("enable_shared_environment_resource"):
            total_base_regen = sum(self.state["population_config"][p].get("resource_regen", self.cfg["base"]["resource_regen"]) for p in self.population_names)
            raw_regen_total = int(round(total_base_regen * max(0, min(100, self.shared_env_health)) / 100))
            drought_factor = (100 - max(self.turn_disaster_strength.values())) / 100 if any(t == "Drought" for t in self.turn_disaster_type.values()) else 1
            actual_regen_total = int(round(raw_regen_total * max(0, drought_factor)))
            regen_loss = max(0, raw_regen_total - actual_regen_total)
            self.shared_env_resource = min(self.shared_env_capacity, self.shared_env_resource + actual_regen_total)
            for p in self.population_names:
                share = actual_regen_total // max(1, len(self.population_names))
                self.turn_resource_regen_total[p] += share
                if self.turn_disaster_type[p] == "Drought":
                    self.turn_disaster_env_regen_loss[p] += regen_loss // max(1, len(self.population_names))
                self.env_resource[p] = self.shared_env_resource
                self.env_capacity[p] = self.shared_env_capacity
                self.env_health[p] = self.shared_env_health
                self.resource_pressure[p] = 0.0
        else:
            for p in self.env_resource:
                cfg = self.state["population_config"][p]
                base_regen = cfg.get("resource_regen", self.cfg["base"]["resource_regen"])
                raw_regen = int(round(base_regen * max(0, min(100, self.env_health[p])) / 100))
                drought_factor = (100 - self.turn_disaster_strength[p]) / 100 if self.turn_disaster_type[p] == "Drought" else 1
                actual_regen = int(round(raw_regen * max(0, drought_factor)))
                if self.turn_disaster_type[p] == "Drought":
                    self.turn_disaster_env_regen_loss[p] += max(0, raw_regen - actual_regen)
                self.env_resource[p] = min(self.env_capacity[p], self.env_resource[p] + actual_regen)
                self.turn_resource_regen_total[p] += actual_regen
                self.resource_pressure[p] = 0.0

        for p in self.evolution_samples:
            self.evolution_samples[p] = []
        for p, pop in self.populations.items():
            for ind in pop:
                ind.role = "normal"
                ind.charity_banned = False
                self.sickness_phase_for_individual(p, ind)
                if not ind.critical:
                    ind.role = self.morality_check(ind.morality, self.tribe_trust.get(p, 50), self.turn_disaster_plunder_bonus.get(p, 0))

    def sickness_risk_percent(self, population_name, ind):
        # BOT8 dev8：生病风险由个体力量和部族医疗水平共同降低。
        # 固定基础风险为 10%，避免新增参数；力量和医疗水平越高，风险越低。
        max_strength = max(1, self.cfg["base"].get("max_strength", 500))
        strength_resistance = max(0, min(1, ind.strength / max_strength))
        medical_level = max(0, min(100, self.state["population_config"][population_name].get("medical_level", 50)))
        medical_resistance = medical_level / 100
        risk = 10 * (1 - 0.5 * strength_resistance) * (1 - 0.5 * medical_resistance)
        risk *= health_sickness_multiplier(getattr(ind, "health_index", 100))
        return max(0, min(100, round(risk, 4)))

    def sickness_phase_for_individual(self, population_name, ind):
        if ind.critical:
            return
        risk = self.sickness_risk_percent(population_name, ind)
        ind.sickness_risk = risk
        if random.random() * 100 <= risk:
            ind.is_sick = 1
            ind.became_sick_this_turn = 1
            self.turn_sick_count[population_name] += 1
            self.turn_new_sick_count[population_name] += 1

    def enter_critical_or_die(self, p, ind, reason):
        # 统一濒死入口：所有食物不足、医疗不足等原因都必须消耗同一个濒死机会。
        if not ind.used_critical_chance:
            ind.critical = True
            ind.used_critical_chance = True
            ind.entered_critical_this_turn = 1
            ind.death_reason = reason
            self.turn_entered_critical_count[p] += 1
            # dev32：低人口濒死诊断。只记录，不改变濒死/死亡逻辑。
            if len(self.populations.get(p, [])) < 5:
                self.turn_entered_critical_when_pop_below5[p] += 1
            return True
        self.mark_death(p, ind, reason)
        return False

    def sustainable_labor_budget(self, resource, actual_regen):
        # BOT8 2.3.0：可持续采收约束。
        # 参考可持续产出思想，默认劳动阶段最多消耗本回合实际再生量，避免稳定观察型社会长期透支存量。
        ratio = max(0, self.cfg["base"].get("environment_safe_harvest_ratio", 100))
        sustainable_cap = int(round(actual_regen * ratio / 100))
        return max(0, min(resource, sustainable_cap))

    def is_potential_parent_for_dev38(self, ind):
        """dev38：潜在父代诊断口径。只用于统计，不改变繁殖判定。"""
        return (
            not getattr(ind, "critical", False)
            and not getattr(ind, "is_sick", 0)
            and int(getattr(ind, "reproduce", 0)) >= 10
        )

    def is_potential_parent_with_goods_for_dev38(self, ind):
        """dev38：已有生育用品的潜在父代，用于追踪父代食物安全线缺口。"""
        return self.is_potential_parent_for_dev38(ind) and int(getattr(ind, "reproduction_goods", 0)) >= self.reproduction_goods_required_per_birth()

    def labor_participation_probability(self, ind, population_name=None):
        # BOT8 2.4.0：劳动参与概率 = 基础劳动意愿 + 存款压力/惰性修正。
        # 该算法只使用已有经济参数：生存消耗与财富税阈值。
        # 存款越接近生存压力，劳动概率越高；存款明显超过财富税阈值后，劳动概率逐步下降。
        base = int(ind.labor)
        survival_cost = max(1, self.cfg["base"].get("survival_cost", 100))
        gov_cfg = self.state["population_config"].get(population_name, {}) if population_name is not None else {}
        wealth_threshold = max(survival_cost * 2, gov_cfg.get("wealth_tax_threshold", 1500))

        if ind.balance < survival_cost * 2:
            pressure_bonus = int(round((survival_cost * 2 - ind.balance) / (survival_cost * 2) * 40))
        else:
            pressure_bonus = 0

        if ind.balance > wealth_threshold:
            idle_penalty = int(round(min(30, (ind.balance - wealth_threshold) / max(1, wealth_threshold) * 30)))
        else:
            idle_penalty = 0

        trust_bonus = 0
        if population_name is not None:
            trust_bonus = int(round((self.tribe_trust.get(population_name, 50) - 50) / 5))

        lifecycle_bonus = labor_health_education_adjustment(
            getattr(ind, "health_index", 100),
            getattr(ind, "education_capital", getattr(ind, "temp_intelligence", 0)),
        )
        return max(0, min(100, base + pressure_bonus - idle_penalty + trust_bonus + lifecycle_bonus))

    def resource_access_score(self, ind):
        # 资源获取优先级用于“能力优先”和“混合分配”模式。
        # 有效智慧仍然最重要，但劳动意愿和贫困程度也会提高获得资源的机会，避免资源完全被高智慧个体垄断。
        survival_cost = max(1, self.cfg["base"].get("survival_cost", 100))
        poverty_score = max(0, min(100, int(round((survival_cost * 3 - ind.balance) / max(1, survival_cost * 3) * 100))))
        score = (
            ind.effective_intelligence() * 0.55
            + ind.labor * 1.20
            + poverty_score * 0.80
            + random.randint(0, 20)
        )
        return int(round(max(0, score)))

    def collect_labor_candidates(self):
        candidates_by_pop = {p: [] for p in self.population_names}
        standard_share = max(1, self.cfg["base"].get("labor_env_cost", 100))
        for p, pop in self.populations.items():
            for ind in pop:
                if ind.critical:
                    continue
                chance = self.labor_participation_probability(ind, p)
                ind.labor_participation_chance = chance
                if random.randint(1, 100) <= chance:
                    score = self.resource_access_score(ind)
                    ind.resource_access_score = score
                    ind.requested_resource = standard_share
                    candidates_by_pop[p].append({
                        "population": p,
                        "individual": ind,
                        "score": score,
                        "requested": standard_share,
                    })
                    self.turn_labor_candidate_count[p] += 1
                    if hasattr(self, "turn_labor_candidate_raw_count"):
                        self.turn_labor_candidate_raw_count[p] += 1
                    self.turn_labor_request_total[p] += standard_share
        return candidates_by_pop

    def allocate_worker_resources(self, workers, available_resource):
        # dev11：精简资源分配参数，只保留固定“混合分配”。
        # 一半资源保证最低劳动机会，一半资源按 ResourceAccessScore 分配，必要时后续再重新引入可调模式。
        if not workers or available_resource <= 0:
            return []
        standard = max(1, self.cfg["base"].get("labor_env_cost", 100))
        min_share = max(1, standard // 2)
        max_share = max(min_share, int(round(standard * 1.5)))
        available = int(max(0, available_resource))
        allocations = {id(w["individual"]): 0 for w in workers}
        equal_budget = int(round(available * 0.5))
        ability_budget = max(0, available - equal_budget)
        equal_per_worker = min(min_share, equal_budget // len(workers)) if workers else 0
        for w in workers:
            allocations[id(w["individual"])] += equal_per_worker
        ability_budget += max(0, equal_budget - equal_per_worker * len(workers))
        for w in sorted(workers, key=lambda x: x["score"], reverse=True):
            if ability_budget <= 0:
                break
            current = allocations[id(w["individual"])]
            room = max(0, max_share - current)
            give = min(room, ability_budget)
            allocations[id(w["individual"])] += give
            ability_budget -= give
        result = []
        for w in workers:
            ind = w["individual"]
            allocated = int(max(0, allocations.get(id(ind), 0)))
            if allocated <= 0:
                continue
            result.append((w["population"], ind, allocated, w["requested"], w["score"]))
        return result

    def allocate_shared_population_quotas(self, candidates_by_pop, shared_budget):
        # BOT8 2.4.0：共用资源先分配种群配额，再由种群内部二次分配给个体。
        # 该设计来自公共池资源的“配额/规则”思路：共享资源不是简单让所有个体按智慧混排抢占。
        active_pops = [p for p in self.population_names]
        if not active_pops or shared_budget <= 0:
            return {p: 0 for p in self.population_names}

        # dev11：共用资源配额比例固定为 40/40/20，减少市场机制前的可调参数数量。
        equal_ratio, need_ratio, ability_ratio = 40, 40, 20
        ratio_sum = equal_ratio + need_ratio + ability_ratio

        claims = {p: sum(w["requested"] for w in candidates_by_pop[p]) for p in self.population_names}
        total_claim = sum(claims.values())
        ability_scores = {
            p: ((sum(w["score"] for w in candidates_by_pop[p]) / len(candidates_by_pop[p])) + self.tribe_trust.get(p, 50) * 0.2 if candidates_by_pop[p] else self.tribe_trust.get(p, 50) * 0.2)
            for p in self.population_names
        }
        total_ability = sum(ability_scores.values())

        quotas = {}
        for p in self.population_names:
            equal_part = (shared_budget * equal_ratio / ratio_sum) / len(active_pops)
            need_part = (shared_budget * need_ratio / ratio_sum) * (claims[p] / total_claim) if total_claim > 0 else 0
            ability_part = (shared_budget * ability_ratio / ratio_sum) * (ability_scores[p] / total_ability) if total_ability > 0 else 0
            quotas[p] = int(round(equal_part + need_part + ability_part))

        total_quota = sum(quotas.values())
        if total_quota > shared_budget and total_quota > 0:
            scale = shared_budget / total_quota
            quotas = {p: int(quotas[p] * scale) for p in quotas}

        # 余数按劳动需求从高到低补足，保证不超过总预算。
        remaining = max(0, shared_budget - sum(quotas.values()))
        for p in sorted(self.population_names, key=lambda x: claims[x], reverse=True):
            if remaining <= 0:
                break
            quotas[p] += 1
            remaining -= 1

        for p in self.population_names:
            self.turn_population_resource_claim[p] += claims[p]
            self.turn_population_resource_quota[p] += quotas[p]
            self.turn_population_resource_shortage[p] += max(0, claims[p] - quotas[p])
        return quotas

    def labor_phase(self):
        candidates_by_pop = self.collect_labor_candidates()
        for _p in self.population_names:
            raw_count = len(candidates_by_pop[_p])
            tendency = max(0, min(100, int(self.state["population_config"].get(_p, {}).get("company_production_tendency", 60))))
            kept_count = int(round(raw_count * tendency / 100))
            candidates_by_pop[_p] = sorted(candidates_by_pop[_p], key=lambda w: w["score"], reverse=True)[:kept_count]
            if hasattr(self, "turn_labor_candidates_trimmed_by_tendency"):
                self.turn_labor_candidates_trimmed_by_tendency[_p] += max(0, raw_count - len(candidates_by_pop[_p]))

        if self.is_feature_enabled("enable_shared_environment_resource"):
            shared_budget = self.sustainable_labor_budget(self.shared_env_resource, sum(self.turn_resource_regen_total.values()))
            quotas = self.allocate_shared_population_quotas(candidates_by_pop, shared_budget)
            total_used = 0
            for p in self.population_names:
                allocated_workers = self.allocate_worker_resources(candidates_by_pop[p], quotas.get(p, 0))
                if hasattr(self, "turn_labor_allocated_candidate_count"):
                    self.turn_labor_allocated_candidate_count[p] += len(allocated_workers)
                    self.turn_labor_candidates_without_allocation[p] += max(0, len(candidates_by_pop[p]) - len(allocated_workers))
                used = 0
                for _, ind, allocated, requested, score in allocated_workers:
                    actual_used = self.process_labor_worker(p, ind, allocated, requested, score, shared=True, population_quota=quotas.get(p, 0))
                    used += actual_used
                self.turn_population_resource_used[p] += used
                total_used += used
            self.shared_env_resource = max(0, self.shared_env_resource - total_used)
            for p in self.population_names:
                self.env_resource[p] = self.shared_env_resource
            self.distribute_company_dividends()
            return

        for p in self.population_names:
            budget = self.sustainable_labor_budget(self.env_resource[p], self.turn_resource_regen_total[p])
            allocated_workers = self.allocate_worker_resources(candidates_by_pop[p], budget)
            if hasattr(self, "turn_labor_allocated_candidate_count"):
                self.turn_labor_allocated_candidate_count[p] += len(allocated_workers)
                self.turn_labor_candidates_without_allocation[p] += max(0, len(candidates_by_pop[p]) - len(allocated_workers))
            used = 0
            for _, ind, allocated, requested, score in allocated_workers:
                actual_used = self.process_labor_worker(p, ind, allocated, requested, score, shared=False, population_quota=budget)
                used += actual_used
            self.env_resource[p] = max(0, self.env_resource[p] - used)
            self.turn_population_resource_claim[p] += sum(w["requested"] for w in candidates_by_pop[p])
            self.turn_population_resource_quota[p] += budget
            self.turn_population_resource_used[p] += used
            self.turn_population_resource_shortage[p] += max(0, sum(w["requested"] for w in candidates_by_pop[p]) - budget)
        self.distribute_company_dividends()

    def get_hard_need_unmet_for_production(self, p, good):
        """dev44：把上一回合硬刚需未满足量转化为本回合生产信号。

        生产发生在市场之前，因此不能使用本回合尚未完成的成交结果。这里使用上一回合
        保存下来的 last_hard_demand / last_market_unmet_demand / 出生阻断等信号。
        """
        unmet = 0
        if good == "food":
            unmet += max(0, int(self.last_hard_demand.get(p, {}).get("food", 0)))
            unmet += max(0, int(self.last_market_unmet_demand.get(p, {}).get("food", 0)))
        elif good == "medical_goods":
            unmet += max(0, int(self.last_hard_demand.get(p, {}).get("medical_goods", 0)))
            unmet += max(0, int(self.last_market_unmet_demand.get(p, {}).get("medical_goods", 0)))
        elif good == "reproduction_goods":
            child_cost = max(1, self.reproduction_goods_required_per_birth())
            unmet += max(0, int(getattr(self, "last_reproduction_goods_hard_demand_unsatisfied", {}).get(p, 0)))
            unmet += max(0, int(getattr(self, "last_birth_blocked_no_reproduction_goods", {}).get(p, 0))) * child_cost
            unmet += max(0, int(self.last_hard_demand.get(p, {}).get("reproduction_goods", 0)))
            unmet += max(0, int(self.last_market_unmet_demand.get(p, {}).get("reproduction_goods", 0)))
        elif good == "education_goods":
            unmet += max(0, int(self.last_market_unmet_demand.get(p, {}).get("education_goods", 0)))
        return max(0, int(unmet))

    def get_hard_need_production_bonus(self, p, good):
        """dev44：环境资源未接近极限且刚需未满足时，提高对应商品生产权重。

        注意：这是生产结构响应，不是人口恢复机制。它不创造资源，不降低出生条件，
        也不改变消费预算，只让公司在资源仍闲置时更重视上一回合未满足的硬需求。
        """
        cfg = self.state.get("population_config", {}).get(p, {})
        if not int(cfg.get("enable_hard_need_production_response", 1)):
            return 0.0
        if good not in TRADED_GOODS:
            return 0.0
        threshold = max(0, int(cfg.get("hard_need_resource_use_threshold", 80))) / 100.0
        last_use_ratio = float(getattr(self, "last_resource_use_to_regen_ratio", {}).get(p, 0.0))
        if last_use_ratio >= threshold:
            return 0.0
        unmet = self.get_hard_need_unmet_for_production(p, good)
        if unmet <= 0:
            return 0.0
        base_weight = max(0, int(cfg.get("hard_need_production_response_weight", 80)))
        good_key = {
            "food": "food_hard_need_production_weight",
            "medical_goods": "medical_hard_need_production_weight",
            "reproduction_goods": "reproduction_hard_need_production_weight",
            "education_goods": "education_need_production_weight",
        }.get(good, "hard_need_production_response_weight")
        good_weight = max(0, int(cfg.get(good_key, 100)))
        population = max(1, len(self.populations.get(p, [])))
        survival_cost = max(1, int(self.cfg.get("base", {}).get("survival_cost", 100)))
        normalized_unmet = unmet / population / survival_cost
        bonus = base_weight * good_weight / 100.0 * normalized_unmet

        # 如果该商品库存已经远高于运行期库存目标，则降低额外生产响应，避免库存越积越多。
        stock = max(0, int(self.companies.get(p, {}).get(good, {}).get("stock", 0))) if hasattr(self, "companies") else 0
        target = max(1, int(self.company_operating_stock_target(p, good))) if hasattr(self, "company_operating_stock_target") else 1
        if stock > target * 3:
            bonus *= 0.3
        cap = max(0, int(cfg.get("hard_need_production_weight_cap", 300)))
        bonus = min(cap, max(0.0, bonus))
        if hasattr(self, "turn_hard_need_production_bonus"):
            self.turn_hard_need_production_bonus[p][good] = max(self.turn_hard_need_production_bonus[p].get(good, 0), int(round(bonus)))
        if hasattr(self, "turn_hard_need_unmet_for_production"):
            self.turn_hard_need_unmet_for_production[p][good] = max(self.turn_hard_need_unmet_for_production[p].get(good, 0), int(unmet))
        return bonus

    def goods_production_ratios(self, p):
        # BOT8 dev20：商品生产结构改为“刚性需求优先”。
        # CivitasLab system-stage step10: the ratio is cached per population per turn.
        # This also prevents the small random production jitter from changing multiple times inside one turn.
        cache = getattr(self, "_goods_production_ratios_cache", None)
        if isinstance(cache, dict) and p in cache:
            return cache[p].copy()
        # 设计原则：刚性需求 > 机制阻断 > 未满足市场需求 > 历史消耗 > 储备需求 > 价格信号。
        # 刚性需求包括食物生存缺口、生病医疗缺口，以及阻断繁殖的生育用品缺口；储备需求只弱影响生产。
        last = self.last_goods_consumption.get(p, {})
        unmet = self.last_market_unmet_demand.get(p, {})
        hard = self.last_hard_demand.get(p, {})
        reserve = self.last_reserve_demand.get(p, {})
        survival_cost = max(1, int(self.cfg["base"].get("survival_cost", 100)))
        child_cost = max(1, self.reproduction_goods_required_per_birth())
        blocked_reproduction_goods = int(getattr(self, "last_birth_blocked_no_reproduction_goods", {}).get(p, 0))

        weights = {good: 0 for good in GOOD_FIELDS}

        # 食物：刚性生存缺口权重显著高于储备需求；价格只作为弱信号。
        weights["food"] = (
            max(0, int(last.get("food", 0))) * 1
            + max(0, int(hard.get("food", 0))) * 6
            + max(0, int(reserve.get("food", 0))) * 1
            + max(0, int(unmet.get("food", 0))) * 2
            + max(0, self.goods_price_index(p, "food") - 100) / 5
        )

        # 医疗用品：生病医疗缺口直接决定濒死风险，因此刚性权重最高。
        weights["medical_goods"] = (
            max(0, int(last.get("medical_goods", 0))) * 1
            + max(0, int(hard.get("medical_goods", 0))) * 8
            + max(0, int(reserve.get("medical_goods", 0))) * 0.5
            + max(0, int(unmet.get("medical_goods", 0))) * 2
            + max(0, self.goods_price_index(p, "medical_goods") - 100) / 5
        )

        # 生育用品：不由政府免费救助，而由繁殖阻断与市场需求强烈推动生产。
        weights["reproduction_goods"] = (
            max(0, int(last.get("reproduction_goods", 0))) * 1
            + blocked_reproduction_goods * child_cost * 8
            + int(getattr(self, "last_reproduction_goods_hard_demand_unsatisfied", {}).get(p, 0)) * 8
            + max(0, int(hard.get("reproduction_goods", 0))) * 5
            + max(0, int(reserve.get("reproduction_goods", 0))) * 1
            + max(0, int(unmet.get("reproduction_goods", 0))) * 2
            + max(0, self.goods_price_index(p, "reproduction_goods") - 100) / 5
        )

        # 教育用品：重要但不应挤占生存、医疗、生育的刚性产能。
        weights["education_goods"] = (
            max(0, int(last.get("education_goods", 0))) * 1
            + max(0, int(hard.get("education_goods", 0))) * 2
            + max(0, int(reserve.get("education_goods", 0))) * 1
            + max(0, int(unmet.get("education_goods", 0))) * 1
            + max(0, self.goods_price_index(p, "education_goods") - 100) / 5
        )

        # 工具仍然仅加入库存和输出，不实装生产用途；没有历史消耗时不主动生产。
        weights["tools"] = max(0, int(last.get("tools", 0))) if int(last.get("tools", 0)) > 0 else 0

        if sum(weights.values()) <= 0:
            weights = {"food": 70, "medical_goods": 10, "education_goods": 10, "reproduction_goods": 10, "tools": 0}
        else:
            for good in GOOD_FIELDS:
                if good == "tools" and int(last.get("tools", 0)) <= 0:
                    continue
                weights[good] = max(0, weights.get(good, 0) + random.randint(-5, 5))

        # dev42：生育用品/教育用品库存韧性。
        # 当公司库存低于按当前人口计算的目标储备时，把缺口转化为生产权重。
        # 它不直接改变出生条件，也不凭空增加库存，只影响公司生产结构。
        cfg = self.state["population_config"].get(p, {})
        if int(cfg.get("enable_repro_education_inventory_resilience", 1)):
            current_pop = max(1, len(self.populations.get(p, [])))
            child_units = max(1, self.reproduction_goods_required_per_birth())
            weight_scale = max(0, int(cfg.get("repro_education_inventory_resilience_weight", 50))) / 100
            reserve_specs = {
                "reproduction_goods": max(0, int(cfg.get("repro_inventory_target_births_ratio", 150))),
                "education_goods": max(0, int(cfg.get("education_inventory_target_births_ratio", 100))),
            }
            for reserve_good, reserve_ratio in reserve_specs.items():
                target_stock = int(round(current_pop * child_units * reserve_ratio / 100))
                company_stock = int(self.companies.get(p, {}).get(reserve_good, {}).get("stock", 0)) if hasattr(self, "companies") else 0
                gap = max(0, target_stock - company_stock)
                add_weight = gap * weight_scale
                if add_weight > 0:
                    weights[reserve_good] = weights.get(reserve_good, 0) + add_weight
                if hasattr(self, "turn_repro_education_resilience_gap"):
                    self.turn_repro_education_resilience_gap[p][reserve_good] = max(self.turn_repro_education_resilience_gap[p].get(reserve_good, 0), int(gap))
                    self.turn_repro_education_resilience_weight_added[p][reserve_good] = max(self.turn_repro_education_resilience_weight_added[p].get(reserve_good, 0), int(round(add_weight)))

        # dev44：硬刚需生产响应。上一回合硬刚需未满足且环境资源仍未接近上限时，
        # 将未满足的食物/医疗/生育/教育需求追加为生产权重。
        for hard_good in TRADED_GOODS:
            hard_bonus = self.get_hard_need_production_bonus(p, hard_good)
            if hard_bonus > 0:
                weights[hard_good] = weights.get(hard_good, 0) + hard_bonus

        # 权重底线不是固定比例；最终会归一化。底线只避免关键商品长期归零。
        weights["food"] = max(40, weights.get("food", 0))
        weights["medical_goods"] = max(10, weights.get("medical_goods", 0))
        weights["education_goods"] = max(5, weights.get("education_goods", 0))
        weights["reproduction_goods"] = max(10, weights.get("reproduction_goods", 0))
        if int(last.get("tools", 0)) <= 0:
            weights["tools"] = 0
        total_weight = sum(weights.values()) or 1
        ratios = {good: weights.get(good, 0) / total_weight for good in GOOD_FIELDS}
        cache = getattr(self, "_goods_production_ratios_cache", None)
        if isinstance(cache, dict):
            cache[p] = ratios.copy()
        return ratios

    def market_goods_target_stock(self, ind, good):
        # BOT8 dev15：目标库存用于购买、囤积和生产偏好。
        # 贫困者只维持刚性生存需求；富裕者会保持更高安全库存，形成自然囤积行为。
        b = self.cfg["base"]
        survival_cost = int(b.get("survival_cost", 100))
        child_cost = self.reproduction_goods_required_per_birth()
        pop_cfg = self.state["population_config"].get(getattr(ind, "population_name", "A"), {})
        exempt = int(pop_cfg.get("wealth_tax_exempt_threshold", 600))
        high = int(pop_cfg.get("wealth_tax_threshold", 1500))
        balance = int(getattr(ind, "balance", 0))
        rich = balance >= high
        poor = balance < survival_cost

        if good == "food":
            target = survival_cost if poor else survival_cost * 3
            if rich:
                target = int(round(target * 1.5))
            return max(0, target)
        if good == "medical_goods":
            if getattr(ind, "is_sick", 0):
                target = survival_cost
            else:
                target = 0 if poor else int(round(survival_cost * 0.3))
            if rich:
                target = int(round(target * 1.5))
            return max(0, target)
        if good == "reproduction_goods":
            # dev29：贫穷不再让生育用品“需求”归零。货币余额只影响后续买得起多少，
            # 不应和是否需要生育用品混在一起；否则会与“繁殖不再要求旧货币门槛”的逻辑冲突。
            if ind.reproduce < 10 or getattr(ind, "is_sick", 0) or getattr(ind, "critical", False):
                return 0
            if int(getattr(ind, "food", 0)) < survival_cost:
                return 0
            target = child_cost
            if rich:
                target = int(round(target * 1.5))
            return max(0, target)
        if good == "education_goods":
            if poor or ind.reproduce < 10 or ind.balance <= child_cost + survival_cost:
                return 0
            target = child_cost
            if rich:
                target = int(round(target * 2))
            return max(0, target)
        return 0

    def personal_shortage_signal(self, ind, good):
        survival_cost = max(1, int(self.cfg["base"].get("survival_cost", 100)))
        target = self.market_goods_target_stock(ind, good)
        current = int(getattr(ind, good, 0))
        shortage = max(0, target - current)
        return (shortage / survival_cost) * 20

    def individual_production_weights(self, p, ind):
        # BOT8 dev15：劳动者不再完全按部族统一比例生产。
        # 个体生产权重 = 部族基础权重 + 市场价格信号 + 自身库存缺口 + 财富策略 + 智慧响应。
        base_ratios = self.goods_production_ratios(p)
        weights = {good: base_ratios.get(good, 0) * 100 for good in GOOD_FIELDS}
        b = self.cfg["base"]
        survival_cost = int(b.get("survival_cost", 100))
        pop_cfg = self.state["population_config"].get(p, {})
        exempt = int(pop_cfg.get("wealth_tax_exempt_threshold", 600))
        high = int(pop_cfg.get("wealth_tax_threshold", 1500))
        balance = int(getattr(ind, "balance", 0))
        effective_int = max(0, ind.effective_intelligence())
        price_response_multiplier = 0.5 + effective_int / max(1, int(b.get("max_intelligence", 500)))
        total_price_response = 0

        for good in TRADED_GOODS:
            price_signal = max(0, self.goods_price_index(p, good) - 100) / 5
            price_signal *= price_response_multiplier
            shortage_signal = self.personal_shortage_signal(ind, good)
            weights[good] = weights.get(good, 0) + price_signal + shortage_signal
            total_price_response += price_signal

        # 财富策略：贫困者优先生存和医疗；富裕者更偏向教育、生育和高价商品。
        if balance < survival_cost:
            weights["food"] += 20
            if getattr(ind, "is_sick", 0):
                weights["medical_goods"] += 10
            weights["education_goods"] *= 0.25
            weights["reproduction_goods"] *= 0.5
        elif balance < exempt:
            weights["food"] += 10
            weights["reproduction_goods"] += 5
        elif balance >= high:
            weights["education_goods"] += 10
            weights["reproduction_goods"] += 10
            high_price_good = max(TRADED_GOODS, key=lambda g: self.goods_price_index(p, g))
            weights[high_price_good] += 10

        # 工具仍然仅加入库存和输出，不实装生产/市场用途；没有工具消耗时不主动生产工具。
        if self.last_goods_consumption.get(p, {}).get("tools", 0) <= 0:
            weights["tools"] = 0
        weights = {good: max(0, weight) for good, weight in weights.items()}
        if sum(weights.values()) <= 0:
            weights = {"food": 70, "medical_goods": 10, "education_goods": 10, "reproduction_goods": 10, "tools": 0}
        ind.production_price_response = int(round(total_price_response))
        primary = max(weights, key=lambda g: weights[g])
        ind.primary_production_good = GOOD_DISPLAY.get(primary, primary)
        return weights

    def distribute_product_budget(self, p, ind, production_budget):
        # dev22：旧的“个体直接生产并获得商品”逻辑已停用。
        # 公司化劳动后，个体只向公司提供劳动并获得工资，商品进入公司分公司库存。
        # 如果后续代码误调用此函数，应立即暴露为结构性错误，而不是悄悄恢复旧机制。
        raise RuntimeError("distribute_product_budget 已废弃：公司化劳动机制下不得让个体直接获得生产商品。")

    def branch_expected_profit_score(self, p, good, ind=None, allocated_resource=None):
        # dev26：公司为纯营收驱动主体。分公司只有在预期收益为正时才招工/生产。
        branch = self.companies.get(p, {}).get(good, {})
        price_index = max(1, self.goods_price_index(p, good)) if good in TRADED_GOODS else 100
        b = self.cfg.get("base", {})
        max_prod = max(0, int(b.get("max_production", 800)))
        max_int = max(1, int(b.get("max_intelligence", 500)))
        survival_cost = max(1, int(b.get("survival_cost", 100)))
        effective_int = ind.effective_intelligence() if ind is not None else max_int
        standard = max(1, int(b.get("labor_env_cost", 100)))
        resource = standard if allocated_resource is None else max(0, int(allocated_resource))
        expected_output = max(0, int(round(max_prod * (effective_int / max_int) * (resource / standard))))
        expected_revenue = expected_output * price_index / 100
        reward_ratio = max(0, min(100, int(self.state["population_config"].get(p, {}).get("labor_reward_ratio", 50))))
        expected_wage = expected_revenue * reward_ratio / 100
        resource_price = max(0, int(self.state["population_config"].get(p, {}).get("production_resource_price", 1)))
        resource_cost = resource * resource_price
        stock = max(0, int(branch.get("stock", 0)))
        target = max(1, int(branch.get("initial_stock", 1)))
        overstock_ratio = stock / target
        overstock_penalty = max(0, overstock_ratio - 1) * 50
        sales_volume = max(0, int(branch.get("last_sales_volume", branch.get("sales_volume", 0))))
        produced = max(1, int(branch.get("goods_produced", 0)) or int(branch.get("stock", 1)))
        sold_ratio_bonus = min(50, (sales_volume / produced) * 50)
        demand_ratio = self.goods_production_ratios(p).get(good, 0)
        demand_bonus = demand_ratio * 20
        unmet_for_good = int(self.last_market_unmet_demand.get(p, {}).get(good, 0)) if hasattr(self, "last_market_unmet_demand") and good in TRADED_GOODS else 0
        strategy_bonus = company_strategy_bonus(
            good=good,
            stock=stock,
            target=target,
            unmet_demand=unmet_for_good,
            survival_cost=survival_cost,
        )
        # dev44：硬刚需未满足且环境资源仍有闲置时，不能只在归一化生产比例中体现，
        # 还需要进入分公司预期收益评分，否则低人口/库存惩罚场景下公司可能仍判定“不值得招工”。
        hard_need_profit_bonus = self.get_hard_need_production_bonus(p, good) if good in TRADED_GOODS else 0
        score = expected_revenue - resource_cost - expected_wage - overstock_penalty + sold_ratio_bonus + demand_bonus + hard_need_profit_bonus + strategy_bonus
        return max(0, score)

    def choose_company_branch_for_worker(self, p, ind=None, allocated_resource=None):
        weights = {good: self.branch_expected_profit_score(p, good, ind, allocated_resource) for good in GOOD_FIELDS}
        # 工具仍保留但不实装；除非后续出现工具需求，否则不进入生产。
        weights["tools"] = 0
        total = sum(max(0, v) for v in weights.values())
        if total <= 0:
            return None
        roll = random.random() * total
        acc = 0
        for good in GOOD_FIELDS:
            acc += max(0, weights.get(good, 0))
            if roll <= acc:
                self.last_company_branch_choice[p][good] += 1
                self.turn_company_expected_profit[p] += int(round(weights.get(good, 0)))
                return good
        return None

    def process_labor_worker(self, p, ind, allocated_resource, requested_resource=None, access_score=None, shared=False, population_quota=0):
        b = self.cfg["base"]
        standard = max(1, b.get("labor_env_cost", 100))
        requested_resource = standard if requested_resource is None else requested_resource
        access_score = ind.resource_access_score if access_score is None else access_score

        branch_good = self.choose_company_branch_for_worker(p, ind, allocated_resource)
        if branch_good is None:
            # dev26：公司纯营收驱动；当所有分公司预期收益为非正时，公司可以 0 招工、0 生产。
            # dev37：记录候选劳动者未被录用的直接原因，用于低人口劳动空窗诊断。
            if hasattr(self, "turn_no_worker_reason_no_expected_profit_count"):
                self.turn_no_worker_reason_no_expected_profit_count[p] += 1
                self.turn_no_worker_reason_no_company_demand_count[p] += 1
            self.log_event("劳动", f"{getattr(ind, 'code', ind.id)} 未被录用：本回合无正收益分公司岗位", entity_type="individual", entity_id=str(getattr(ind, "code", ind.id)), population=p, event_type="labor_not_hired", data={"reason": "no_positive_profit_branch", "labor": int(getattr(ind, "labor", 0)), "critical": int(bool(getattr(ind, "critical", False))), "sick": int(bool(getattr(ind, "is_sick", False)))})
            return 0

        branch = self.companies[p][branch_good]
        resource_price = max(0, int(self.state["population_config"].get(p, {}).get("production_resource_price", 1)))
        resource_affordable = allocated_resource if resource_price <= 0 else int(branch.get("money", 0)) // max(1, resource_price)
        actual_resource = min(max(0, int(allocated_resource)), max(0, int(resource_affordable)))
        if actual_resource <= 0:
            self.turn_company_production_stopped_by_cash_count[p] += 1
            if hasattr(self, "turn_no_worker_reason_no_resource_count"):
                self.turn_no_worker_reason_no_resource_count[p] += 1
            self.log_event("劳动", f"{getattr(ind, 'code', ind.id)} 未生产：{p}部族{GOOD_DISPLAY.get(branch_good, branch_good)}分公司无力向政府购买生产资源", entity_type="individual", entity_id=str(getattr(ind, "code", ind.id)), population=p, event_type="labor_no_resource", data={"branch_good": branch_good, "allocated_resource": int(allocated_resource), "resource_affordable": int(resource_affordable), "branch_money": int(branch.get("money", 0)), "resource_price": int(resource_price)})
            return 0

        resource_cost = actual_resource * resource_price
        if resource_cost > 0:
            branch["money"] -= resource_cost
            self.government_deposit[p] += resource_cost
            self.turn_company_resource_purchased[p] += actual_resource
            self.turn_company_resource_cost[p] += resource_cost
        self.turn_company_cash_after_resource_purchase[p] += int(branch.get("money", 0))

        self.turn_env_consumption_total[p] += actual_resource
        effective_int = ind.effective_intelligence()
        gross = int(round(b["max_production"] * (effective_int / max(1, b["max_intelligence"])) * (actual_resource / standard)))
        prod = max(0, gross)
        branch["stock"] += prod
        branch["goods_produced"] += prod
        self.turn_branch_workers.setdefault(p, {}).setdefault(branch_good, []).append(ind)

        market_value = int(round(prod * self.goods_price_index(p, branch_good) / 100)) if branch_good in TRADED_GOODS else int(prod)
        reward_ratio = max(0, min(100, int(self.state["population_config"].get(p, {}).get("labor_reward_ratio", 50))))
        planned_wage = int(round(market_value * reward_ratio / 100))
        self.turn_company_cash_before_wages[p] += int(branch.get("money", 0))
        wage = min(planned_wage, int(branch.get("money", 0)))
        if planned_wage > 0 and wage < planned_wage:
            self.turn_company_unable_to_pay_full_wages_count[p] += 1
        if wage > 0:
            branch["money"] -= wage
            branch["wages_paid"] += wage
            ind.balance += wage
            ind.wage_received += wage
            ind.turn_labor_income += wage
            self.turn_workers_paid_count[p] += 1
            self.turn_company_wage_paid[p] += wage
            self.turn_total_wages_paid[p] += wage
            survival_cost_for_stat = int(self.cfg["base"].get("survival_cost", 100))
            child_cost_for_stat = self.reproduction_goods_required_per_birth()
            if int(getattr(ind, "food", 0)) + int(getattr(ind, "balance", 0)) >= survival_cost_for_stat:
                self.turn_workers_paid_enough_for_food_count[p] += 1
            missing_rep_goods = max(0, child_cost_for_stat - int(getattr(ind, "reproduction_goods", 0)))
            can_cover_rep_goods = missing_rep_goods <= 0 or int(getattr(ind, "balance", 0)) >= self.goods_cost(p, "reproduction_goods", missing_rep_goods)
            if (not getattr(ind, "critical", False)
                    and not getattr(ind, "is_sick", 0)
                    and can_cover_rep_goods):
                self.turn_workers_paid_enough_for_reproduction_count[p] += 1
        self.turn_company_cash_after_wages[p] += int(branch.get("money", 0))
        ind.did_labor = 1
        # dev36：记录最近劳动分公司，用于“近期劳动者”劳动权益分红实验。
        ind.last_labor_turn = self.turn
        ind.last_labor_good = branch_good
        ind.employer_branch = GOOD_DISPLAY.get(branch_good, branch_good)
        ind.primary_production_good = ind.employer_branch
        ind.produced_goods_value += market_value
        ind.labor_gross_production += gross
        ind.labor_net_production += prod
        ind.labor_tax_paid += 0
        ind.total_tax_paid += 0
        ind.env_consumed_by_labor += actual_resource
        ind.allocated_resource += actual_resource
        ind.requested_resource += requested_resource
        ind.resource_access_score = access_score
        ind.shared_resource_enabled = int(shared)
        ind.population_resource_quota = population_quota
        ind.population_resource_claim = self.turn_population_resource_claim.get(p, 0)
        setattr(ind, f"{branch_good}_produced", getattr(ind, f"{branch_good}_produced", 0) + prod)
        self.turn_labor_worker_count[p] += 1
        self.turn_labor_gross_total[p] += gross
        self.turn_labor_tax_total[p] += 0
        self.turn_production_total[p] += prod
        self.turn_goods_production[p][branch_good] += prod
        self.turn_labor_allocated_total[p] += actual_resource
        self.turn_labor_unmet_demand[p] += max(0, requested_resource - actual_resource)
        self.log_event("劳动", f"{getattr(ind, 'code', ind.id)} 在{p}部族{GOOD_DISPLAY.get(branch_good, branch_good)}分公司工作，产出{prod}，产值{market_value}，获得工资{wage}", entity_type="individual", entity_id=str(getattr(ind, "code", ind.id)), population=p, event_type="labor_work", data={"branch_good": branch_good, "produced": int(prod), "market_value": int(market_value), "wage": int(wage), "actual_resource": int(actual_resource), "resource_cost": int(resource_cost)})
        return actual_resource

    def distribute_company_dividends(self):
        # dev26：生产回合劳动报酬结算后，分公司将超过初始资金的资金按本回合劳动者有效智慧比例全部分红。
        for p in self.population_names:
            for good, workers in self.turn_branch_workers.get(p, {}).items():
                if not workers:
                    continue
                branch = self.companies.get(p, {}).get(good, {})
                excess = int(branch.get("money", 0)) - int(branch.get("initial_money", 0))
                if excess <= 0:
                    continue
                total_int = sum(max(1, w.effective_intelligence()) for w in workers)
                paid_total = 0
                for idx, worker in enumerate(workers):
                    if idx == len(workers) - 1:
                        div = max(0, excess - paid_total)
                    else:
                        div = int(round(excess * max(1, worker.effective_intelligence()) / max(1, total_int)))
                        div = min(div, max(0, excess - paid_total))
                    if div <= 0:
                        continue
                    worker.balance += div
                    worker.dividend_received += div
                    paid_total += div
                branch["money"] -= paid_total
                self.turn_company_dividend_paid[p] += paid_total
                self.log_event("分红", f"{p}部族{GOOD_DISPLAY.get(good, good)}分公司向{len(workers)}名劳动者按智慧比例分红{paid_total}", entity_type="company", entity_id=f"Company:{p}:{good}", population=p, event_type="company_dividend", data={"branch_good": good, "recipient_count": int(len(workers)), "paid_total": int(paid_total), "mode": "intelligence_weighted"})

    def distribute_inventory_sales_dividends(self):
        # dev35：库存销售收入分红实验。默认关闭，只用于比较工资提升与库存清算收益回流。
        # 资金来源是公司真实销售收入，不创造货币，不提高生育概率。
        # 本版加入两项保护：
        # 1) 默认只从历史库存清算收入分红，不抽走本回合新生产销售收入；
        # 2) 默认启用公司现金保护，避免分红后分公司低于初始运营资金。
        base = self.cfg.get("base", {})
        if not bool(base.get("enable_inventory_sales_dividend", False)):
            return
        ratio = max(0, min(100, int(base.get("inventory_sales_dividend_ratio", 10))))
        if ratio <= 0:
            return
        historical_only = bool(base.get("inventory_sales_dividend_historical_only", True))
        cash_protection = bool(base.get("inventory_sales_dividend_cash_protection", True))
        min_cash_ratio = max(0, int(base.get("inventory_sales_dividend_min_cash_ratio", 120)))
        floor_ratio = max(0, int(base.get("inventory_sales_dividend_cash_floor_ratio", 100)))

        for p, pop in self.populations.items():
            recipients = [i for i in pop if not getattr(i, "critical", False)]
            if not recipients:
                continue
            for good, branch in self.companies.get(p, {}).items():
                sales_income = max(0, int(branch.get("sales_income", 0)))
                historical_income = max(0, int(branch.get("historical_inventory_sales_income", 0)))
                source_income = historical_income if historical_only else sales_income
                if source_income <= 0:
                    self.turn_inventory_sales_dividend_blocked_by_no_historical_income[p] += 1
                    continue

                branch_money = max(0, int(branch.get("money", 0)))
                initial_money = max(0, int(branch.get("initial_money", 0)))
                min_cash = int(round(initial_money * min_cash_ratio / 100))
                cash_floor = int(round(initial_money * floor_ratio / 100))
                self.turn_inventory_sales_dividend_cash_floor[p] += cash_floor

                if cash_protection and branch_money <= min_cash:
                    self.turn_inventory_sales_dividend_blocked_by_cash_protection[p] += 1
                    continue

                requested_pool = int(round(source_income * ratio / 100))
                available_by_cash = max(0, branch_money - cash_floor) if cash_protection else branch_money
                pool = min(branch_money, requested_pool, available_by_cash)
                if pool <= 0:
                    self.turn_inventory_sales_dividend_blocked_by_cash_protection[p] += 1
                    continue

                self.turn_inventory_sales_dividend_eligible_branches[p] += 1
                per_capita = pool // len(recipients)
                remainder = pool % len(recipients)
                if per_capita <= 0 and remainder <= 0:
                    continue
                paid_total = 0
                for idx, ind in enumerate(recipients):
                    pay = per_capita + (1 if idx < remainder else 0)
                    if pay <= 0:
                        continue
                    ind.balance += pay
                    ind.dividend_received += pay
                    paid_total += pay
                if paid_total > 0:
                    branch["money"] -= paid_total
                    self.turn_inventory_sales_dividend_paid[p] += paid_total
                    self.turn_inventory_sales_dividend_recipients[p] += len(recipients)
                    self.turn_company_dividend_paid[p] += paid_total
                    self.log_event("库存销售分红", f"{p}部族{GOOD_DISPLAY.get(good, good)}分公司按历史库存清算收入分红{paid_total}", entity_type="company", entity_id=f"Company:{p}:{good}", population=p, event_type="inventory_sales_dividend", data={"branch_good": good, "recipient_count": int(len(recipients)), "paid_total": int(paid_total), "historical_only": int(bool(historical_only)), "source_income": int(source_income)})

    def excess_cash_dividend_recipients(self, p, good, mode, recent_turns):
        """dev36：为超额现金分红选择对象。

        mode=0：所有非濒死个体；mode=1：本回合本分公司劳动者；mode=2：近期本分公司劳动者。
        这只是分红对象选择，不改变劳动、生育或生存逻辑。
        """
        pop = self.populations.get(p, [])
        if mode <= 0:
            return [i for i in pop if not getattr(i, "critical", False)]
        if mode == 1:
            return [i for i in self.turn_branch_workers.get(p, {}).get(good, []) if not getattr(i, "critical", False)]
        window = max(0, int(recent_turns))
        return [
            i for i in pop
            if not getattr(i, "critical", False)
            and getattr(i, "last_labor_good", "") == good
            and getattr(i, "last_labor_turn", 0) > 0
            and self.turn - int(getattr(i, "last_labor_turn", 0)) <= window
        ]

    def distribute_excess_cash_dividends(self):
        # dev36：超额现金分层分红实验。默认关闭。
        # 与 dev35 的“销售额比例分红”不同，本函数只从分公司超过运营现金阈值的真实盈余中提取分红池。
        # 资金来自公司已有货币，不创造货币；默认只分给本回合本分公司劳动者，模拟劳动权益/利润分享。
        base = self.cfg.get("base", {})
        if not bool(base.get("enable_excess_cash_dividend", False)):
            return
        ratio = max(0, min(100, int(base.get("excess_cash_dividend_ratio", 20))))
        if ratio <= 0:
            return
        min_cash_ratio = max(0, int(base.get("excess_cash_dividend_min_cash_ratio", 120)))
        mode = max(0, min(2, int(base.get("excess_cash_dividend_recipient_mode", 1))))
        recent_turns = max(0, int(base.get("excess_cash_dividend_recent_turns", 5)))

        for p in self.population_names:
            for good, branch in self.companies.get(p, {}).items():
                branch_money = max(0, int(branch.get("money", 0)))
                initial_money = max(0, int(branch.get("initial_money", 0)))
                threshold = int(round(initial_money * min_cash_ratio / 100))
                excess_cash = max(0, branch_money - threshold)
                if excess_cash <= 0:
                    self.turn_excess_cash_dividend_blocked_by_no_excess_cash[p] += 1
                    continue
                recipients = self.excess_cash_dividend_recipients(p, good, mode, recent_turns)
                if not recipients:
                    self.turn_excess_cash_dividend_blocked_by_no_recipients[p] += 1
                    continue
                pool = min(branch_money, int(round(excess_cash * ratio / 100)))
                if pool <= 0:
                    self.turn_excess_cash_dividend_blocked_by_no_excess_cash[p] += 1
                    continue
                self.turn_excess_cash_dividend_eligible_branches[p] += 1
                self.turn_excess_cash_dividend_pool[p] += pool
                total_weight = sum(max(1, int(w.effective_intelligence())) for w in recipients)
                paid_total = 0
                for idx, worker in enumerate(recipients):
                    if idx == len(recipients) - 1:
                        pay = max(0, pool - paid_total)
                    else:
                        pay = int(round(pool * max(1, int(worker.effective_intelligence())) / max(1, total_weight)))
                        pay = min(pay, max(0, pool - paid_total))
                    if pay <= 0:
                        continue
                    worker.balance += pay
                    worker.dividend_received += pay
                    paid_total += pay
                if paid_total > 0:
                    branch["money"] = max(0, int(branch.get("money", 0)) - paid_total)
                    self.turn_excess_cash_dividend_paid[p] += paid_total
                    self.turn_excess_cash_dividend_recipients[p] += len(recipients)
                    self.turn_company_dividend_paid[p] += paid_total
                    self.log_event("超额现金分红", f"{p}部族{GOOD_DISPLAY.get(good, good)}分公司从超额现金中向{len(recipients)}名劳动者分红{paid_total}", entity_type="company", entity_id=f"Company:{p}:{good}", population=p, event_type="excess_cash_dividend", data={"branch_good": good, "recipient_count": int(len(recipients)), "paid_total": int(paid_total), "excess_cash": int(excess_cash), "ratio": int(ratio)})

    def environment_update_phase(self):
        # BOT8 2.2.0：环境健康根据资源压力变化，并加入 env_damage_buffer。
        # 小幅超采会先进入缓冲池，累计满 1 才减少 EnvHealth，使环境退化更平滑。
        # ResourcePressure 在实际再生为 0 时不再用 1 强行替代：有消耗则记为 999，无消耗则为 0。
        if self.is_feature_enabled("enable_shared_environment_resource"):
            total_consumption = sum(self.turn_env_consumption_total.values())
            total_regen = sum(self.turn_resource_regen_total.values())
            pressure = 999 if total_regen <= 0 and total_consumption > 0 else (0 if total_regen <= 0 else round(total_consumption / total_regen, 4))
            self.shared_resource_pressure = pressure
            old_health = self.shared_env_health
            degradation_rate = max(0, int(round(sum(self.state["population_config"][p].get("env_degradation_rate", 10) for p in self.population_names) / max(1, len(self.population_names)))))
            recovery_rate = max(0, int(round(sum(self.state["population_config"][p].get("env_recovery_rate", 3) for p in self.population_names) / max(1, len(self.population_names)))))
            change = self.calculate_env_health_change(pressure, degradation_rate, recovery_rate, shared=True)
            self.shared_env_health = max(0, min(100, old_health + change))
            for p in self.population_names:
                self.env_health[p] = self.shared_env_health
                self.resource_pressure[p] = pressure
                self.turn_env_health_change[p] = self.shared_env_health - old_health
                self.env_resource[p] = self.shared_env_resource
            return

        for p in self.population_names:
            cfg = self.state["population_config"][p]
            consumption = self.turn_env_consumption_total[p]
            actual_regen = self.turn_resource_regen_total[p]
            pressure = 999 if actual_regen <= 0 and consumption > 0 else (0 if actual_regen <= 0 else round(consumption / actual_regen, 4))
            self.resource_pressure[p] = pressure
            old_health = self.env_health[p]
            change = self.calculate_env_health_change(pressure, cfg.get("env_degradation_rate", 10), cfg.get("env_recovery_rate", 3), p=p)
            self.env_health[p] = max(0, min(100, old_health + change))
            self.turn_env_health_change[p] = self.env_health[p] - old_health

    def calculate_env_health_change(self, pressure, degradation_rate, recovery_rate, p=None, shared=False):
        change = 0
        if shared:
            damage_buffer_name = "shared_env_damage_buffer"
            recovery_buffer_name = "shared_env_recovery_buffer"
        else:
            damage_buffer_name = recovery_buffer_name = None

        if pressure > 1:
            damage = (pressure - 1) * degradation_rate
            if shared:
                self.shared_env_damage_buffer += damage
                drop = min(15, int(self.shared_env_damage_buffer))
                if drop > 0:
                    change = -drop
                    self.shared_env_damage_buffer -= drop
                    self.shared_env_recovery_buffer = 0.0
            else:
                self.env_damage_buffer[p] += damage
                drop = min(15, int(self.env_damage_buffer[p]))
                if drop > 0:
                    change = -drop
                    self.env_damage_buffer[p] -= drop
                    self.env_recovery_buffer[p] = 0.0
        elif pressure < 0.6:
            if shared:
                self.shared_env_recovery_buffer += recovery_rate
                recover = int(self.shared_env_recovery_buffer)
                if recover > 0:
                    change = recover
                    self.shared_env_recovery_buffer -= recover
                    self.shared_env_damage_buffer = 0.0
            else:
                self.env_recovery_buffer[p] += recovery_rate
                recover = int(self.env_recovery_buffer[p])
                if recover > 0:
                    change = recover
                    self.env_recovery_buffer[p] -= recover
                    self.env_damage_buffer[p] = 0.0
        elif pressure < 0.9:
            if shared:
                self.shared_env_recovery_buffer += recovery_rate / 2
                recover = int(self.shared_env_recovery_buffer)
                if recover > 0:
                    change = recover
                    self.shared_env_recovery_buffer -= recover
                    self.shared_env_damage_buffer = 0.0
            else:
                self.env_recovery_buffer[p] += recovery_rate / 2
                recover = int(self.env_recovery_buffer[p])
                if recover > 0:
                    change = recover
                    self.env_recovery_buffer[p] -= recover
                    self.env_damage_buffer[p] = 0.0
        return change

    def is_reproduction_hard_buyer(self, ind, p=None):
        """dev25：真正接近繁殖、且只缺生育用品的刚性买方。
        不再要求旧版 child_initial_balance 货币门槛；货币只影响能买多少。"""
        if ind is None or getattr(ind, "critical", False) or getattr(ind, "is_sick", 0):
            return False
        if p is None:
            p = getattr(ind, "population_name", "A")
        survival_cost = int(self.cfg["base"].get("survival_cost", 100))
        child_cost = self.reproduction_goods_required_per_birth()
        # dev29：购买准备条件和真正出生条件分离。接近繁殖者可以提前购买生育用品；
        # 真正出生仍在 reproduce_phase 中要求 parent_food_required_for_birth()。
        if int(getattr(ind, "food", 0)) < survival_cost:
            return False
        if int(getattr(ind, "reproduction_goods", 0)) >= child_cost:
            return False
        return int(getattr(ind, "reproduce", 0)) >= 30

    def reproduction_goods_hard_need(self, ind):
        child_cost = self.reproduction_goods_required_per_birth()
        return max(0, child_cost - int(getattr(ind, "reproduction_goods", 0)))

    def has_reproduction_hard_buyer(self, p):
        return any(self.is_reproduction_hard_buyer(ind, p) for ind in self.populations.get(p, []))

    def market_goods_safety_stock(self, good, ind=None):
        # BOT8 dev20：卖方安全库存按个体真实用途计算，使无相关需求者释放商品。
        survival_cost = int(self.cfg["base"].get("survival_cost", 100))
        child_cost = self.reproduction_goods_required_per_birth()
        if good == "food":
            if ind is not None:
                pop_cfg = self.state["population_config"].get(getattr(ind, "population_name", "A"), {})
                high = int(pop_cfg.get("wealth_tax_threshold", 1500))
                return survival_cost * (3 if getattr(ind, "balance", 0) >= high else 2)
            return survival_cost * 2
        if good == "medical_goods":
            return survival_cost if ind is not None and getattr(ind, "is_sick", 0) else 0
        if good == "reproduction_goods":
            if ind is not None and getattr(ind, "reproduce", 0) >= 10 and not getattr(ind, "is_sick", 0) and not getattr(ind, "critical", False):
                return child_cost
            return 0
        if good == "education_goods":
            if ind is not None:
                pop_cfg = self.state["population_config"].get(getattr(ind, "population_name", "A"), {})
                exempt = int(pop_cfg.get("wealth_tax_exempt_threshold", 600))
                if getattr(ind, "reproduce", 0) >= 10 and getattr(ind, "balance", 0) >= exempt:
                    return child_cost
            return 0
        return 10**12

    def market_goods_hard_reserve_need(self, ind, good):
        # BOT8 dev20：市场需求拆分为刚性需求和储备需求。
        # 刚性需求会直接影响生存、治疗或繁殖；储备需求只代表安全库存和未来计划。
        survival_cost = int(self.cfg["base"].get("survival_cost", 100))
        child_cost = self.reproduction_goods_required_per_birth()
        current = int(getattr(ind, good, 0))
        hard = 0
        if good == "food":
            hard = max(0, survival_cost - current)
        elif good == "medical_goods":
            hard = max(0, survival_cost - current) if getattr(ind, "is_sick", 0) else 0
        elif good == "reproduction_goods":
            # dev29：满足状态与最低食物安全条件却缺生育用品时，生育用品属于刚性繁殖需求。
            # 这里不再包含旧式货币门槛；货币只影响实际购买量。
            food_req = survival_cost
            if (not getattr(ind, "critical", False)
                    and not getattr(ind, "is_sick", 0)
                    and getattr(ind, "food", 0) >= food_req
                    and getattr(ind, "reproduce", 0) >= 10):
                hard = max(0, child_cost - current)
        elif good == "education_goods":
            # 教育不足不会阻断生存或出生，因此只给弱刚性权重。
            if getattr(ind, "reproduce", 0) >= 10 and getattr(ind, "balance", 0) >= child_cost + survival_cost:
                hard = max(0, int(round(child_cost * 0.25)) - current)

        target = self.market_goods_target_stock(ind, good)
        total_need = max(0, target - current)
        reserve = max(0, total_need - hard)
        return int(hard), int(reserve)

    def market_goods_need(self, ind, good):
        # BOT8 dev15/dev23：市场需求改为目标库存缺口，并确保刚性需求不会被储备目标低估。
        # 食物/医疗/生育用品的刚性需求必须优先进入市场购买，否则会出现“库存很多但不能繁殖/生存”。
        target = self.market_goods_target_stock(ind, good)
        current = int(getattr(ind, good, 0))
        hard, _ = self.market_goods_hard_reserve_need(ind, good)
        need = max(0, target - current, hard)
        setattr(ind, f"market_{good}_need", int(need))
        return int(need)

    def record_reproduction_goods_demand_diagnostic(self, p, ind):
        # dev29：诊断生育用品需求链路。这里不改变行为，只记录旧逻辑会误判的位置。
        if getattr(ind, "critical", False) or getattr(ind, "is_sick", 0):
            self.turn_reproduction_goods_demand_blocked_by_sick_or_critical[p] += 1
            return
        if int(getattr(ind, "reproduce", 0)) < 10:
            return
        survival_cost = int(self.cfg["base"].get("survival_cost", 100))
        if int(getattr(ind, "food", 0)) < survival_cost:
            self.turn_reproduction_goods_demand_blocked_by_food[p] += 1
            return
        required = self.reproduction_goods_required_per_birth()
        if int(getattr(ind, "reproduction_goods", 0)) >= required:
            return
        self.turn_reproduction_goods_demand_count[p] += 1
        if int(getattr(ind, "balance", 0)) < survival_cost:
            self.turn_reproduction_goods_demand_blocked_by_poor_old_logic[p] += 1
        if int(getattr(ind, "balance", 0)) > 0 and int(self.market_spending_limit(ind, "reproduction_goods")) <= 0:
            self.turn_reproduction_goods_spending_blocked_by_poor_old_logic[p] += 1

    def market_goods_base_surplus(self, ind, good):
        return max(0, int(getattr(ind, good, 0)) - self.market_goods_safety_stock(good, ind))

    def market_goods_sell_ratio(self, p, good):
        # 高价提高出售意愿，低信任降低出售意愿。
        price_index = self.goods_price_index(p, good)
        base_sell_ratio = 0.3
        price_bonus = max(0, price_index - 100) / 500
        trust_factor = 0.5 + max(0, min(100, self.tribe_trust.get(p, 50))) / 100
        return max(0.0, min(1.0, (base_sell_ratio + price_bonus) * trust_factor))

    def market_goods_surplus(self, ind, good, p=None):
        # 返回“本回合愿意出售的库存”，不是全部安全库存以上库存。
        base_surplus = self.market_goods_base_surplus(ind, good)
        if base_surplus <= 0:
            return 0
        if p is None:
            p = getattr(ind, "population_name", None)
        if p is None or good not in TRADED_GOODS:
            return base_surplus
        ratio = self.market_goods_sell_ratio(p, good)
        sellable = int(math.floor(base_surplus * ratio))
        if sellable <= 0 and base_surplus > 0 and self.goods_price_index(p, good) > 100:
            sellable = 1
        return max(0, min(base_surplus, sellable))

    def goods_price_index(self, p, good):
        return int(max(1, self.market_price_index.get(p, {}).get(good, 100)))

    def goods_cost(self, p, good, amount):
        # BOT8 dev13：价格指数 100=1 货币/单位。向上取整避免低价商品出现 0 成本交易。
        amount = int(max(0, amount))
        if amount <= 0:
            return 0
        price_index = self.goods_price_index(p, good)
        return int(math.ceil(amount * price_index / 100))

    def market_spending_ratio(self, ind, good):
        # BOT8 dev15：购买行为加入价格承受能力。
        # 刚性需求可花更多货币，非刚性生育/教育需求受预算约束更强。
        survival_cost = int(self.cfg["base"].get("survival_cost", 100))
        if good == "food":
            return 0.8
        if good == "medical_goods":
            return 0.7 if getattr(ind, "is_sick", 0) else 0.2
        if good == "reproduction_goods":
            # dev29：贫穷不再直接取消生育用品购买意愿。实际购买仍受 balance 和 spending_limit 限制。
            if ind.balance <= 0:
                return 0.0
            return 0.4
        if good == "education_goods":
            if ind.balance < survival_cost * 2:
                return 0.0
            return 0.3
        return 0.0

    def market_spending_limit(self, ind, good):
        # BOT8 dev20：购买预算必须保留后续机制所需的刚性货币。
        # dev29：生育用品购买预算不再保留旧版子代货币门槛；只保留本回合食物紧急预算。
        survival_cost = int(self.cfg["base"].get("survival_cost", 100))
        child_cost = self.reproduction_goods_required_per_birth()
        balance = int(max(0, getattr(ind, "balance", 0)))
        if good == "reproduction_goods":
            # dev25：刚性生育用品买方不再保留旧版子代初始货币门槛。
            # 只保留本回合食物紧急购买预算，避免为了生育用品牺牲生存刚需。
            if self.is_reproduction_hard_buyer(ind, getattr(ind, "population_name", "A")):
                food_shortage = max(0, survival_cost - int(getattr(ind, "food", 0)))
                food_price = self.goods_price_index(getattr(ind, "population_name", "A"), "food")
                food_emergency_reserve = int(math.ceil(food_shortage * food_price / 100)) if food_shortage > 0 else 0
                return max(0, balance - food_emergency_reserve)
            return int(balance * self.market_spending_ratio(ind, good))
        if good == "education_goods":
            return max(0, balance - child_cost - survival_cost)
        return int(balance * self.market_spending_ratio(ind, good))

    def affordable_goods_amount(self, p, buyer, good):
        price_index = self.goods_price_index(p, good)
        spending_limit = self.market_spending_limit(buyer, good)
        return int(spending_limit * 100 // price_index)

    def record_market_volume(self, p, good, amount, money_value):
        # 本函数保留给政府本地采购使用，按本地成交记录市场量。
        amount = int(max(0, amount))
        money_value = int(max(0, money_value))
        if amount <= 0 and money_value <= 0:
            return
        self.turn_market_trade_count[p] += 1
        self.turn_market_trade_volume[p] += money_value
        self.turn_market_volume_by_good[p][good] += amount
        self.turn_market_local_volume[p][good] += amount
        if good == "food":
            self.turn_market_food_volume[p] += amount
        elif good == "medical_goods":
            self.turn_market_medical_goods_volume[p] += amount
        elif good == "education_goods":
            self.turn_market_education_goods_volume[p] += amount
        elif good == "reproduction_goods":
            self.turn_market_reproduction_goods_volume[p] += amount

    def market_trade_costs(self, buyer_pop, seller_pop, good, amount):
        # BOT8 dev17：跨部族交易按卖方部族价格成交。
        # 买方支付 = 商品价款 + 卖方政府交易税 + 买方政府进口税。
        amount = int(max(0, amount))
        if amount <= 0:
            return 0, 0, 0, 0
        goods_value = self.goods_cost(seller_pop, good, amount)
        # dev26：恢复税收系统后，只启用富人资产税；交易税和进口税暂不生效。
        trade_tax_rate = 0
        import_tax_rate = 0
        trade_tax = 0
        import_tax = 0
        total_paid = goods_value + trade_tax + import_tax
        return goods_value, trade_tax, import_tax, total_paid

    def affordable_market_trade_amount(self, buyer_pop, seller_pop, buyer, good):
        spending_limit = self.market_spending_limit(buyer, good)
        if spending_limit <= 0:
            return 0
        price_index = max(1, self.goods_price_index(seller_pop, good))
        seller_cfg = self.state["population_config"].get(seller_pop, {})
        buyer_cfg = self.state["population_config"].get(buyer_pop, {})
        if not self.is_tax_enabled():
            trade_tax_rate = 0
            import_tax_rate = 0
        else:
            trade_tax_rate = max(0, int(seller_cfg.get("trade_tax_rate", 0)))
            import_tax_rate = max(0, int(buyer_cfg.get("import_tax_rate", 0))) if buyer_pop != seller_pop else 0
        unit_total = (price_index / 100) * (1 + trade_tax_rate / 100 + import_tax_rate / 100)
        if unit_total <= 0:
            return 0
        return int(spending_limit // unit_total)

    def record_market_trade(self, buyer_pop, seller_pop, good, amount, goods_value, trade_tax, import_tax, total_paid):
        is_import = buyer_pop != seller_pop
        if is_import:
            self.turn_market_import_volume[buyer_pop][good] += amount
            self.turn_market_export_volume[seller_pop][good] += amount
            self.turn_market_volume_by_good[buyer_pop][good] += amount
            self.turn_market_trade_count[buyer_pop] += 1
            self.turn_market_trade_count[seller_pop] += 1
            self.turn_market_trade_volume[buyer_pop] += total_paid
            self.turn_market_trade_volume[seller_pop] += goods_value
            self.turn_import_spending[buyer_pop] += total_paid
            self.turn_export_income[seller_pop] += goods_value
        else:
            self.turn_market_local_volume[buyer_pop][good] += amount
            self.turn_market_volume_by_good[buyer_pop][good] += amount
            self.turn_market_trade_count[buyer_pop] += 1
            self.turn_market_trade_volume[buyer_pop] += total_paid
        self.turn_trade_tax_income[seller_pop][good] += trade_tax
        self.turn_import_tax_income[buyer_pop][good] += import_tax
        if good == "food":
            self.turn_market_food_volume[buyer_pop] += amount
            if hasattr(self, "turn_food_bought_by_potential_parent") and self.is_potential_parent_with_goods_for_dev38(buyer):
                self.turn_food_bought_by_potential_parent[buyer_pop] += amount
        elif good == "medical_goods":
            self.turn_market_medical_goods_volume[buyer_pop] += amount
            if getattr(buyer, "critical", False):
                self.turn_medical_goods_bought_by_critical[buyer_pop] += amount
            else:
                self.turn_medical_goods_bought_by_healthy[buyer_pop] += amount
        elif good == "education_goods":
            self.turn_market_education_goods_volume[buyer_pop] += amount
        elif good == "reproduction_goods":
            self.turn_market_reproduction_goods_volume[buyer_pop] += amount

    def append_trade_flow(self, buyer_pop, seller_pop, buyer, seller, good, amount, goods_value, trade_tax, import_tax, total_paid):
        if buyer_pop == seller_pop:
            return
        self.trade_flow_rows.append({
            "Turn": self.turn,
            "Goods": GOOD_DISPLAY.get(good, good),
            "BuyerTribe": buyer_pop,
            "SellerTribe": seller_pop,
            "Amount": int(amount),
            "SellerPriceIndex": self.goods_price_index(seller_pop, good),
            "GoodsValue": int(goods_value),
            "TradeTax": int(trade_tax),
            "ImportTax": int(import_tax),
            "TotalPaid": int(total_paid),
            "BuyerID": getattr(buyer, "id", ""),
            "SellerID": getattr(seller, "id", seller),
        })

    def population_current_hard_need(self, p, good):
        """dev41：扫描当前个体的刚性需求，供公司上架决策使用。

        这不是人口恢复机制，也不改变需求本身；它只让公司在已经存在真实刚需时，
        知道不能继续把可销售库存全部锁在“初始库存目标”内。
        """
        if good not in ("food", "medical_goods"):
            return 0
        total = 0
        for ind in self.populations.get(p, []):
            if getattr(ind, "critical", False):
                continue
            try:
                hard, _ = self.market_goods_hard_reserve_need(ind, good)
            except Exception:
                hard = 0
            if hard > 0:
                total += int(hard)
        return max(0, int(total))

    def company_hard_need_release_pressure(self, p, good):
        """dev41：公司库存释放压力。

        取当前刚需与上一回合未满足需求的较大值。这样公司不会因为本回合订单簿尚未成交，
        或上一回合已经暴露短缺，却仍只按普通库存比例少量上架。
        """
        if good not in ("food", "medical_goods"):
            return 0
        current_hard = self.population_current_hard_need(p, good)
        last_unmet = 0
        try:
            last_unmet = int(self.last_market_unmet_demand.get(p, {}).get(good, 0))
        except Exception:
            last_unmet = 0
        return max(0, int(current_hard), int(last_unmet))

    def company_hard_need_inventory_release_enabled(self, p, good):
        cfg = self.state["population_config"].get(p, {})
        if not int(cfg.get("enable_company_hard_need_inventory_release", 1)):
            return False
        return self.company_hard_need_release_pressure(p, good) > 0

    def company_sellable_amount(self, seller_pop, good):
        branch = self.companies.get(seller_pop, {}).get(good)
        if not branch:
            return 0
        stock = max(0, int(branch.get("stock", 0)))
        surplus = max(0, stock - int(branch.get("initial_stock", 0)))
        # dev41：食物/医疗/生育用品存在刚性缺口时，公司已有库存必须能进入订单簿销售，
        # 不再被“恢复初始库存目标”完全锁住。公司仍获得货币收入，不创造资源。
        if good in ("food", "medical_goods") and self.company_hard_need_inventory_release_enabled(seller_pop, good):
            return stock
        # dev25：存在真正的生育用品刚性买方时，生育用品分公司可动用全部库存，
        # 不再因“恢复初始库存目标”阻断生育用品流通。
        if good == "reproduction_goods" and self.has_reproduction_hard_buyer(seller_pop):
            return stock
        if surplus <= 0:
            return 0
        # 公司目标：分公司货币倾向于恢复到初始货币，库存倾向于恢复到初始库存。
        # dev24：当存在生育用品刚性需求或未满足需求时，公司优先释放生育用品库存，
        # 避免公司库存积压而有繁殖条件的个体无法获得生育用品。
        if good == "reproduction_goods":
            hard = 0
            unmet = 0
            try:
                hard = int(self.turn_hard_demand.get(seller_pop, {}).get(good, 0))
                unmet = int(self.turn_market_unmet_demand.get(seller_pop, {}).get(good, 0))
            except Exception:
                pass
            if hard > 0 or unmet > 0:
                return surplus
        if branch.get("money", 0) < branch.get("initial_money", 0):
            return surplus
        return max(0, int(round(surplus * 0.5)))

    def execute_company_market_trade(self, buyer_pop, seller_pop, buyer, good, amount):
        amount = int(max(0, amount))
        if amount <= 0:
            return 0
        branch = self.companies.get(seller_pop, {}).get(good)
        if not branch:
            return 0
        sellable = self.company_sellable_amount(seller_pop, good)
        affordable = self.affordable_market_trade_amount(buyer_pop, seller_pop, buyer, good)
        trade_amount = min(amount, sellable, affordable)
        while trade_amount > 0:
            goods_value, trade_tax, import_tax, total_paid = self.market_trade_costs(buyer_pop, seller_pop, good, trade_amount)
            if total_paid <= buyer.balance:
                break
            trade_amount -= 1
        if trade_amount <= 0:
            return 0
        goods_value, trade_tax, import_tax, total_paid = self.market_trade_costs(buyer_pop, seller_pop, good, trade_amount)
        if total_paid <= 0 or total_paid > buyer.balance:
            return 0
        buyer.balance -= total_paid
        branch["money"] += goods_value
        branch["sales_income"] += goods_value
        branch["sales_volume"] = branch.get("sales_volume", 0) + trade_amount
        self.turn_company_actual_revenue[seller_pop] += goods_value
        self.government_deposit[seller_pop] += trade_tax
        self.government_deposit[buyer_pop] += import_tax
        branch["stock"] -= trade_amount
        setattr(buyer, good, int(getattr(buyer, good, 0)) + trade_amount)
        setattr(buyer, f"market_{good}_bought", getattr(buyer, f"market_{good}_bought", 0) + trade_amount)
        buyer.market_money_spent += total_paid
        buyer.market_goods_bought_value += goods_value
        buyer.market_tax_paid += trade_tax + import_tax
        buyer.trade_tax_paid += trade_tax
        buyer.import_tax_paid += import_tax
        buyer.did_market_trade = 1
        if buyer_pop != seller_pop:
            buyer.market_import_value += total_paid
        self.record_market_trade(buyer_pop, seller_pop, good, trade_amount, goods_value, trade_tax, import_tax, total_paid)
        if buyer_pop != seller_pop:
            self.append_trade_flow(buyer_pop, seller_pop, buyer, f"Company:{seller_pop}:{good}", good, trade_amount, goods_value, trade_tax, import_tax, total_paid)
        phase_name = "生育用品优先销售" if good == "reproduction_goods" and self.is_reproduction_hard_buyer(buyer, buyer_pop) else "市场"
        self.log_event(phase_name, f"{getattr(buyer, 'code', buyer.id)} 从{seller_pop}部族公司购买{trade_amount}{GOOD_DISPLAY.get(good, good)}，支付{total_paid}", entity_type="individual", entity_id=str(getattr(buyer, "code", buyer.id)), population=buyer_pop, event_type="company_market_purchase", data={"seller_population": seller_pop, "good": good, "amount": int(trade_amount), "goods_value": int(goods_value), "trade_tax": int(trade_tax), "import_tax": int(import_tax), "total_paid": int(total_paid)})
        return trade_amount

    def execute_market_trade(self, buyer_pop, seller_pop, buyer, seller, good, amount):
        # 统一执行本地/跨部族交易。货币守恒：买方扣款 = 卖方收入 + 两类政府税收。
        amount = int(max(0, amount))
        if amount <= 0 or buyer.id == seller.id:
            return 0
        seller_surplus = self.market_goods_surplus(seller, good, seller_pop)
        affordable = self.affordable_market_trade_amount(buyer_pop, seller_pop, buyer, good)
        trade_amount = min(amount, seller_surplus, affordable)
        while trade_amount > 0:
            goods_value, trade_tax, import_tax, total_paid = self.market_trade_costs(buyer_pop, seller_pop, good, trade_amount)
            if total_paid <= buyer.balance:
                break
            trade_amount -= 1
        if trade_amount <= 0:
            return 0
        goods_value, trade_tax, import_tax, total_paid = self.market_trade_costs(buyer_pop, seller_pop, good, trade_amount)
        if total_paid <= 0 or total_paid > buyer.balance:
            return 0

        buyer.balance -= total_paid
        seller.balance += goods_value
        self.government_deposit[seller_pop] += trade_tax
        self.government_deposit[buyer_pop] += import_tax

        setattr(buyer, good, int(getattr(buyer, good, 0)) + trade_amount)
        setattr(seller, good, int(getattr(seller, good, 0)) - trade_amount)
        setattr(buyer, f"market_{good}_bought", getattr(buyer, f"market_{good}_bought", 0) + trade_amount)
        setattr(seller, f"market_{good}_sold", getattr(seller, f"market_{good}_sold", 0) + trade_amount)
        buyer.market_money_spent += total_paid
        seller.market_money_earned += goods_value
        buyer.market_goods_bought_value += goods_value
        seller.market_goods_sold_value += goods_value
        buyer.market_tax_paid += trade_tax + import_tax
        buyer.trade_tax_paid += trade_tax
        buyer.import_tax_paid += import_tax
        seller.trade_tax_generated += trade_tax
        if import_tax > 0:
            buyer.import_tax_generated += import_tax
        if buyer_pop != seller_pop:
            buyer.market_import_value += goods_value
            seller.market_export_value += goods_value
        if good == "reproduction_goods":
            self.turn_reproduction_goods_individual_sales_volume[buyer_pop] += trade_amount
        buyer.did_market_trade = 1
        seller.did_market_trade = 1
        buyer.market_partner_class = getattr(seller, "current_class", "")
        seller.market_partner_class = getattr(buyer, "current_class", "")
        self.record_market_trade(buyer_pop, seller_pop, good, trade_amount, goods_value, trade_tax, import_tax, total_paid)
        self.append_trade_flow(buyer_pop, seller_pop, buyer, seller, good, trade_amount, goods_value, trade_tax, import_tax, total_paid)
        return trade_amount

    def execute_individual_trade(self, p, buyer, seller, good, amount):
        return self.execute_market_trade(p, p, buyer, seller, good, amount)

    def calculate_initial_market_demand_supply(self, p, pop, traded_goods):
        for good in traded_goods:
            demand = 0
            hard = 0
            reserve = 0
            for ind in pop:
                if ind.critical or ind.balance <= 0:
                    continue
                need = self.market_goods_need(ind, good)
                h, r = self.market_goods_hard_reserve_need(ind, good)
                demand += need
                hard += h
                reserve += r
            self.turn_market_demand[p][good] = int(demand)
            self.turn_hard_demand[p][good] = int(hard)
            self.turn_reserve_demand[p][good] = int(reserve)
            self.turn_market_supply[p][good] = sum(
                self.market_goods_surplus(ind, good, p)
                for ind in pop
                if not ind.critical
            ) + self.company_sellable_amount(p, good)

    def build_global_seller_pools(self, traded_goods):
        pools = {good: [] for good in traded_goods}
        for seller_pop, pop in self.populations.items():
            for good in traded_goods:
                for seller in pop:
                    if seller.critical:
                        continue
                    surplus = self.market_goods_surplus(seller, good, seller_pop)
                    if surplus > 0:
                        pools[good].append((seller_pop, seller))
                pools[good].sort(
                    key=lambda item, g=good: (self.goods_price_index(item[0], g), -self.market_goods_surplus(item[1], g, item[0]))
                )
        return pools

    def reproduction_goods_priority_sale_phase(self):
        """dev25：普通市场前，生育用品分公司优先服务真正接近繁殖的刚性买方。"""
        good = "reproduction_goods"
        child_cost = self.reproduction_goods_required_per_birth()
        for p in self.population_names:
            buyers = [ind for ind in self.populations.get(p, []) if self.is_reproduction_hard_buyer(ind, p)]
            if not buyers:
                continue
            buyers.sort(key=lambda ind: (
                int(getattr(ind, "reproduction_goods", 0)),
                -int(getattr(ind, "reproduce", 0)),
                -int(getattr(ind, "survival_rounds", 0)),
                self.inventory_total_value(ind, p),
            ))
            for buyer in buyers:
                need = self.reproduction_goods_hard_need(buyer)
                if need <= 0:
                    continue
                self.turn_reproduction_goods_hard_buyer_count[p] += 1
                self.turn_reproduction_goods_hard_demand_total[p] += need
                sellable_before = self.company_sellable_amount(p, good)
                if sellable_before <= 0:
                    self.turn_reproduction_goods_blocked_no_company_stock[p] += need
                    self.turn_reproduction_goods_hard_demand_unsatisfied[p] += need
                    self.log_event("生育用品优先销售", f"{getattr(buyer, 'code', buyer.id)} 需求{need}生育用品，但公司无可售库存", entity_type="individual", entity_id=str(getattr(buyer, "code", buyer.id)), population=buyer_pop, event_type="reproduction_goods_blocked_no_company_stock", data={"need": int(need), "good": "reproduction_goods"})
                    continue
                affordable_before = self.affordable_market_trade_amount(p, p, buyer, good)
                if affordable_before <= 0:
                    self.turn_reproduction_goods_blocked_no_money[p] += need
                    self.turn_reproduction_goods_hard_demand_unsatisfied[p] += need
                    self.log_event("生育用品优先销售", f"{getattr(buyer, 'code', buyer.id)} 需求{need}生育用品，但余额不足，未成交", entity_type="individual", entity_id=str(getattr(buyer, "code", buyer.id)), population=buyer_pop, event_type="reproduction_goods_blocked_no_money", data={"need": int(need), "balance": int(getattr(buyer, "balance", 0)), "good": "reproduction_goods"})
                    continue
                before = int(getattr(buyer, good, 0))
                bought = self.execute_company_market_trade(p, p, buyer, good, need)
                after = int(getattr(buyer, good, 0))
                gained = max(0, after - before)
                self.turn_reproduction_goods_company_sales_volume[p] += gained
                self.turn_reproduction_goods_hard_demand_satisfied[p] += gained
                remain = max(0, need - gained)
                if remain > 0:
                    self.turn_reproduction_goods_hard_demand_unsatisfied[p] += remain
                    if self.company_sellable_amount(p, good) <= 0:
                        self.turn_reproduction_goods_blocked_no_company_stock[p] += remain
                    elif self.affordable_market_trade_amount(p, p, buyer, good) <= 0:
                        self.turn_reproduction_goods_blocked_no_money[p] += remain

    def individual_market_trade_phase(self):
        # BOT8 dev17：个体市场分为“本地优先”和“跨部族补缺”。
        # 本地市场先满足需求；若开启跨部族自由交易，剩余需求再按卖方部族价格从其他部族购买。
        traded_goods = TRADED_GOODS
        # BOT8 dev20：购买优先级区分刚性需求和储备需求。先活下来，再治疗，再繁殖，再储备/教育。
        hard_priority = {"food": 0, "medical_goods": 1, "reproduction_goods": 2, "education_goods": 5}
        # dev24：储备购买中也提高生育用品优先级，避免小群体繁殖闭环因生育用品流通不足而断裂。
        reserve_priority = {"reproduction_goods": 3, "food": 4, "medical_goods": 5, "education_goods": 6}
        all_buyers = []
        local_seller_pools = {}
        for p, pop in self.populations.items():
            self.calculate_initial_market_demand_supply(p, pop, traded_goods)
            local_seller_pools[p] = {}
            for good in traded_goods:
                local_seller_pools[p][good] = [
                    seller for seller in pop
                    if not seller.critical and self.market_goods_surplus(seller, good, p) > 0
                ]
                local_seller_pools[p][good].sort(key=lambda seller, g=good, pp=p: self.market_goods_surplus(seller, g, pp), reverse=True)

            for ind in pop:
                if ind.critical:
                    continue
                for good in traded_goods:
                    need = self.market_goods_need(ind, good)
                    if need > 0:
                        ind.total_market_need += need
                        setattr(ind, f"market_{good}_spending_limit", self.market_spending_limit(ind, good))
                    if need > 0 and ind.balance > 0:
                        hard_need, reserve_need = self.market_goods_hard_reserve_need(ind, good)
                        priority_value = hard_priority.get(good, 9) if hard_need > 0 else reserve_priority.get(good, 9)
                        all_buyers.append((priority_value, p, good, need, ind))
        all_buyers.sort(key=lambda item: (item[0], -item[3], item[4].balance))

        # dev25：普通市场前，先处理真正接近繁殖者的生育用品刚性需求。
        self.reproduction_goods_priority_sale_phase()

        # 第一段：本地市场。
        for _, p, good, _, buyer in all_buyers:
            need = self.market_goods_need(buyer, good)
            if need <= 0 or buyer.balance <= 0:
                continue
            bought_company = self.execute_company_market_trade(p, p, buyer, good, need)
            need -= bought_company
            for seller in local_seller_pools.get(p, {}).get(good, []):
                if need <= 0 or buyer.balance <= 0:
                    break
                if seller.id == buyer.id:
                    continue
                if self.market_goods_surplus(seller, good, p) <= 0:
                    continue
                bought = self.execute_market_trade(p, p, buyer, seller, good, need)
                need -= bought

        # 第二段：跨部族自由交易。不开启时，剩余需求直接记录为未满足需求。
        if self.is_feature_enabled("enable_global_trade"):
            global_seller_pools = self.build_global_seller_pools(traded_goods)
            for _, buyer_pop, good, _, buyer in all_buyers:
                need = self.market_goods_need(buyer, good)
                if need <= 0 or buyer.balance <= 0:
                    continue
                company_sellers = [
                    op for op in self.population_names
                    if op != buyer_pop and self.company_sellable_amount(op, good) > 0
                ]
                company_sellers.sort(key=lambda op, g=good: (self.goods_price_index(op, g), -self.company_sellable_amount(op, g)))
                for other_pop in company_sellers:
                    if need <= 0 or buyer.balance <= 0:
                        break
                    bought_company = self.execute_company_market_trade(buyer_pop, other_pop, buyer, good, need)
                    need -= bought_company
                for seller_pop, seller in global_seller_pools.get(good, []):
                    if need <= 0 or buyer.balance <= 0:
                        break
                    if seller_pop == buyer_pop or seller.id == buyer.id:
                        continue
                    if self.market_goods_surplus(seller, good, seller_pop) <= 0:
                        continue
                    bought = self.execute_market_trade(buyer_pop, seller_pop, buyer, seller, good, need)
                    need -= bought

        for _, p, good, _, buyer in all_buyers:
            remaining = self.market_goods_need(buyer, good)
            if remaining > 0:
                setattr(buyer, f"market_unmet_{good}_need", remaining)
                buyer.total_market_unmet_need += remaining

    def government_target_stock_ratios(self, p):
        # BOT8 dev10：政府意向库存比例由上回合物资消耗比例决定，使政府采购行为可解释、可控。
        consumption = self.last_goods_consumption.get(p, {})
        goods = ["food", "medical_goods", "education_goods", "reproduction_goods"]
        total = sum(max(0, int(consumption.get(good, 0))) for good in goods)
        if total <= 0:
            return {"food": 0.7, "medical_goods": 0.1, "education_goods": 0.1, "reproduction_goods": 0.1}
        return {good: max(0, int(consumption.get(good, 0))) / total for good in goods}

    def execute_government_purchase_from_company(self, p, good, amount):
        amount = int(max(0, amount))
        if amount <= 0 or self.government_deposit[p] <= 0:
            return 0
        branch = self.companies.get(p, {}).get(good)
        if not branch:
            return 0
        sellable = self.company_sellable_amount(p, good)
        if sellable <= 0:
            return 0
        price_index = max(1, self.goods_price_index(p, good))
        max_affordable = int(self.government_deposit[p] * 100 // price_index)
        buy = min(amount, sellable, max_affordable)
        if buy <= 0:
            return 0
        cost = self.goods_cost(p, good, buy)
        if cost <= 0 or cost > self.government_deposit[p]:
            return 0
        self.government_deposit[p] -= cost
        branch["money"] += cost
        branch["sales_income"] += cost
        branch["sales_volume"] = branch.get("sales_volume", 0) + buy
        self.turn_company_actual_revenue[p] += cost
        self.turn_government_purchase_to_company[p] += cost
        branch["stock"] -= buy
        self.add_government_good(p, good, buy)
        self.record_market_volume(p, good, buy, cost)
        self.log_event("政府采购", f"{p}部族政府从公司购买{buy}{GOOD_DISPLAY.get(good, good)}，支付{cost}", entity_type="government", entity_id=f"Government:{p}", population=p, event_type="government_purchase_from_company", data={"good": good, "amount": int(buy), "cost": int(cost), "seller": f"Company:{p}:{good}"})
        return buy

    def execute_government_purchase(self, p, seller, good, amount):
        amount = int(max(0, amount))
        if amount <= 0 or self.government_deposit[p] <= 0:
            return 0
        seller_surplus = self.market_goods_surplus(seller, good, p)
        affordable = int(max(0, self.government_deposit[p]) * 100 // self.goods_price_index(p, good))
        buy_amount = min(amount, seller_surplus, affordable)
        if buy_amount <= 0:
            return 0
        money = self.goods_cost(p, good, buy_amount)
        if money > self.government_deposit[p]:
            buy_amount = int(self.government_deposit[p] * 100 // self.goods_price_index(p, good))
            money = self.goods_cost(p, good, buy_amount)
        if buy_amount <= 0 or money <= 0:
            return 0
        setattr(seller, good, int(getattr(seller, good, 0)) - buy_amount)
        seller.balance += money
        seller.market_money_earned += money
        seller.market_goods_sold_value += money
        seller.government_purchase_sold += money
        seller.did_market_trade = 1
        setattr(seller, f"market_{good}_sold", getattr(seller, f"market_{good}_sold", 0) + buy_amount)
        self.government_deposit[p] -= money
        self.add_government_good(p, good, buy_amount)
        self.turn_government_purchase_spending[p] += money
        self.record_market_volume(p, good, buy_amount, money)
        if good == "food":
            self.turn_government_purchase_food[p] += buy_amount
        elif good == "medical_goods":
            self.turn_government_purchase_medical_goods[p] += buy_amount
        return buy_amount


    def government_target_stock_amount(self, p, good):
        # BOT8 dev18：政府目标库存继续复用人口、基础生存需求和救助预算比例，避免引入过多新参数。
        survival_cost = int(self.cfg["base"].get("survival_cost", 100))
        pop = self.populations.get(p, [])
        ratio = max(0, min(100, int(self.state["population_config"].get(p, {}).get("gov_aid_budget_ratio", 50))))
        target_total_stock = int(round(len(pop) * survival_cost * ratio / 100))
        target_ratios = self.government_target_stock_ratios(p)
        return int(round(target_total_stock * target_ratios.get(good, 0)))

    def execute_government_release(self, p, buyer, good, requested_amount, subsidy_rate):
        # BOT8 dev18：政府高价投放。政府以低于市场价的有效价格向短缺个体出售公共库存。
        # 货币仍然守恒：买方支付的货币进入政府存款；折价部分作为调控让利记录，不创造货币。
        requested_amount = int(max(0, requested_amount))
        if requested_amount <= 0 or buyer.balance <= 0:
            return 0
        stock = self.government_good_stock(p, good)
        if stock <= 0:
            return 0
        market_price_index = self.goods_price_index(p, good)
        effective_price_index = max(1, int(round(market_price_index * max(0, 100 - subsidy_rate) / 100)))
        affordable = int(max(0, buyer.balance) * 100 // effective_price_index)
        amount = min(requested_amount, stock, affordable)
        if amount <= 0:
            return 0
        paid = int(math.ceil(amount * effective_price_index / 100))
        if paid > buyer.balance:
            amount = int(buyer.balance * 100 // effective_price_index)
            paid = int(math.ceil(amount * effective_price_index / 100))
        if amount <= 0 or paid <= 0:
            return 0
        market_value = self.goods_cost(p, good, amount)
        self.remove_government_good(p, good, amount)
        setattr(buyer, good, int(getattr(buyer, good, 0)) + amount)
        buyer.balance -= paid
        self.government_deposit[p] += paid
        buyer.market_money_spent += paid
        buyer.did_market_trade = 1
        setattr(buyer, f"market_{good}_bought", getattr(buyer, f"market_{good}_bought", 0) + amount)
        self.turn_government_release_income[p] += paid
        self.turn_government_subsidy_value[p] += max(0, market_value - paid)
        if good == "food":
            self.turn_government_release_food[p] += amount
        elif good == "medical_goods":
            self.turn_government_release_medical_goods[p] += amount
        self.turn_market_trade_count[p] += 1
        self.turn_market_trade_volume[p] += paid
        self.turn_market_volume_by_good[p][good] += amount
        self.turn_market_local_volume[p][good] += amount
        return amount

    def government_macro_control_phase(self):
        # BOT8 dev18：政府宏观调控。参考缓冲库存和公共收储思路：低价时收储，高价时投放，优先调控食物与医疗物资。
        if not self.is_feature_enabled("enable_government_macro_control"):
            return
        base = self.cfg["base"]
        low_price = int(base.get("market_control_low_price_index", 80))
        high_price = int(base.get("market_control_high_price_index", 150))
        for p, pop in self.populations.items():
            pop_cfg = self.state["population_config"].get(p, {})
            budget_ratio = max(0, min(100, int(pop_cfg.get("market_control_budget_ratio", 20))))
            budget_left = int(max(0, self.government_deposit[p]) * budget_ratio / 100)
            for good in ["food", "medical_goods"]:
                price = self.goods_price_index(p, good)
                target_stock = self.government_target_stock_amount(p, good)
                # 高价投放：只释放目标库存以上的公共库存，防止政府把应急库存全部卖空。
                if price >= high_price:
                    releasable = max(0, self.government_good_stock(p, good) - target_stock)
                    if releasable > 0:
                        subsidy_rate = int(pop_cfg.get("food_subsidy_rate" if good == "food" else "medical_subsidy_rate", 20))
                        buyers = [ind for ind in pop if not ind.critical and ind.balance > 0 and self.market_goods_need(ind, good) > 0]
                        buyers.sort(key=lambda ind, g=good: (-self.market_goods_need(ind, g), ind.balance))
                        for buyer in buyers:
                            if releasable <= 0:
                                break
                            need = self.market_goods_need(buyer, good)
                            sold = self.execute_government_release(p, buyer, good, min(need, releasable), subsidy_rate)
                            releasable -= sold
                # 低价收储：政府在价格较低时买入目标库存以上的一层缓冲库存，避免未来短缺时无物可投放。
                if price <= low_price and budget_left > 0:
                    extended_target = max(target_stock, int(round(target_stock * 2)))
                    need = max(0, extended_target - self.government_good_stock(p, good))
                    if need <= 0:
                        continue
                    sellers = [seller for seller in pop if not seller.critical and self.market_goods_surplus(seller, good, p) > 0]
                    sellers.sort(key=lambda seller, g=good: self.market_goods_surplus(seller, g, p), reverse=True)
                    for seller in sellers:
                        if need <= 0 or budget_left <= 0 or self.government_deposit[p] <= 0:
                            break
                        before_deposit = self.government_deposit[p]
                        max_affordable = int(budget_left * 100 // max(1, self.goods_price_index(p, good)))
                        bought = self.execute_government_purchase(p, seller, good, min(need, max_affordable))
                        spent = max(0, before_deposit - self.government_deposit[p])
                        budget_left -= spent
                        need -= bought
                        if good == "food":
                            self.turn_government_stockpile_food[p] += bought
                        elif good == "medical_goods":
                            self.turn_government_stockpile_medical_goods[p] += bought
                        self.turn_government_stockpile_spending[p] += spent

    def calculate_market_stability_index(self):
        # BOT8 dev18：市场稳定指标。综合价格偏离与未满足需求，用于快速观察市场是否失衡。
        for p in self.population_names:
            price_dev = 0
            unmet = 0
            demand = 0
            for good in TRADED_GOODS:
                price_dev += abs(self.goods_price_index(p, good) - 100) / 100
                unmet += max(0, int(self.turn_market_unmet_demand[p].get(good, 0)))
                demand += max(0, int(self.turn_market_demand[p].get(good, 0)))
            avg_price_dev = price_dev / max(1, len(TRADED_GOODS))
            unmet_ratio = unmet / max(1, demand)
            score = 100 - avg_price_dev * 25 - unmet_ratio * 50
            self.turn_market_stability_index[p] = int(max(0, min(100, round(score))))

    def government_purchase_phase(self):
        # BOT8 dev13：政府按动态价格从本部族库存过剩个体处采购食物和医疗用品。
        # 政府采购位于个体市场之后、政府救助之前，不凭空产生商品。
        survival_cost = int(self.cfg["base"].get("survival_cost", 100))
        for p, pop in self.populations.items():
            if self.government_deposit[p] <= 0 or not pop:
                continue
            ratio = max(0, min(100, self.state["population_config"].get(p, {}).get("gov_aid_budget_ratio", 50)))
            target_total_stock = int(round(len(pop) * survival_cost * ratio / 100))
            target_ratios = self.government_target_stock_ratios(p)
            for good in ["food", "medical_goods"]:
                # dev20：政府采购只补到目标库存，不再在个体仍有刚性缺口时无限吸收市场物资。
                if good == "food":
                    target_stock = len(pop) * survival_cost * 2
                elif good == "medical_goods":
                    sick_count = sum(1 for i in pop if getattr(i, "is_sick", 0))
                    target_stock = sick_count * survival_cost * 2
                else:
                    target_stock = int(round(target_total_stock * target_ratios.get(good, 0)))
                current_amount = self.government_good_stock(p, good)
                need = max(0, target_stock - current_amount)
                if need <= 0:
                    continue
                # dev21：政府优先从本部族公司分公司采购关键商品，再从个体购买。
                if need > 0 and self.government_deposit[p] > 0:
                    before = self.government_deposit[p]
                    bought_company = self.execute_government_purchase_from_company(p, good, need)
                    spent_company = max(0, before - self.government_deposit[p])
                    need -= bought_company
                    if good == "food":
                        self.turn_government_purchase_food[p] += bought_company
                    elif good == "medical_goods":
                        self.turn_government_purchase_medical_goods[p] += bought_company
                    self.turn_government_purchase_spending[p] += spent_company
                sellers = [seller for seller in pop if not seller.critical and self.market_goods_surplus(seller, good, p) > 0]
                sellers.sort(key=lambda seller: self.market_goods_surplus(seller, good, p), reverse=True)
                for seller in sellers:
                    if need <= 0 or self.government_deposit[p] <= 0:
                        break
                    bought = self.execute_government_purchase(p, seller, good, need)
                    need -= bought

    def orderbook_individual_sellable_amount(self, ind, good, p):
        """dev27：个体卖方每 100 可售实物形成一个价格梯度。"""
        return max(0, int(self.market_goods_surplus(ind, good, p)))

    def company_inventory_listing_ratio(self, p, good):
        """dev28：根据库存压力决定公司历史库存上架比例。

        生产决策仍可因预期收益为 0 而停产；销售决策不再依赖本回合生产量。
        当库存超过初始库存目标 3 倍时，分公司以更高比例和更低价格清库存。
        """
        branch = self.companies.get(p, {}).get(good)
        if not branch:
            return 0.0
        stock = max(0, int(branch.get("stock", 0)))
        if stock <= 0:
            return 0.0
        cfg = self.state["population_config"].get(p, {})
        if self.company_hard_need_inventory_release_enabled(p, good):
            min_ratio = max(0, min(100, int(cfg.get("company_hard_need_min_listing_ratio", 80)))) / 100
            return max(0.20, min_ratio)
        raw_initial_stock = int(branch.get("initial_stock", 0))
        initial_stock = max(1, raw_initial_stock)
        if raw_initial_stock <= 0 or stock > initial_stock * 3:
            return 0.50
        return 0.20

    def orderbook_company_listing_amount(self, p, good):
        """dev28：公司按“本回合生产量 + 历史可售库存”综合生成最多 20 档卖单。"""
        branch = self.companies.get(p, {}).get(good)
        if not branch:
            return 0
        stock = max(0, int(branch.get("stock", 0)))
        if stock <= 0:
            return 0
        sellable = max(0, int(self.company_sellable_amount(p, good)))
        if sellable <= 0:
            return 0
        produced = max(0, int(branch.get("goods_produced", 0)))
        listing_ratio = self.company_inventory_listing_ratio(p, good)
        inventory_based = int(math.ceil(sellable * listing_ratio))
        hard_pressure = self.company_hard_need_release_pressure(p, good)
        hard_based = 0
        if hard_pressure > 0 and self.company_hard_need_inventory_release_enabled(p, good):
            cfg = self.state["population_config"].get(p, {})
            multiplier = max(0, int(cfg.get("company_hard_need_listing_multiplier", 120)))
            hard_based = int(math.ceil(hard_pressure * multiplier / 100))
            if hasattr(self, "turn_company_hard_need_release_pressure"):
                self.turn_company_hard_need_release_pressure[p][good] = max(self.turn_company_hard_need_release_pressure[p].get(good, 0), int(hard_pressure))
                self.turn_company_hard_need_release_enabled_count[p] += 1
        listing_amount = min(sellable, max(produced, inventory_based, hard_based))
        if sellable > 0 and listing_amount <= 0:
            listing_amount = min(1, sellable)
        if hasattr(self, "turn_company_sellable_stock"):
            self.turn_company_sellable_stock[p][good] = max(self.turn_company_sellable_stock[p].get(good, 0), int(sellable))
            if hard_based > 0:
                self.turn_company_hard_need_release_listed[p][good] = max(self.turn_company_hard_need_release_listed[p].get(good, 0), int(listing_amount))
        return max(0, int(listing_amount))

    def individual_ask_price_index(self, p, good, level_index):
        base = max(1, self.goods_price_index(p, good))
        # 个体库存少，价格梯度较粗：每档逐步抬价。
        multiplier = 0.90 + 0.10 * max(0, level_index)
        return max(1, int(round(base * multiplier)))

    def company_ask_price_index(self, p, good, level_index, total_levels):
        base = max(1, self.goods_price_index(p, good))
        branch = self.companies.get(p, {}).get(good, {})
        stock = max(0, int(branch.get("stock", 0)))
        raw_initial_stock = int(branch.get("initial_stock", 0))
        initial_stock = max(1, raw_initial_stock)
        overstock = raw_initial_stock <= 0 or stock > initial_stock * 3
        # dev28：库存严重过剩时，价格梯度改为清库存型：0.3 - 1.0 × 当前价格。
        # 普通库存仍沿用较平滑的公司供给曲线：0.7 - 1.8 × 当前价格。
        if overstock:
            min_mult, max_mult = 0.30, 1.00
        else:
            min_mult, max_mult = 0.70, 1.80
        if total_levels <= 1:
            gradient = min_mult
        else:
            gradient = min_mult + ((max_mult - min_mult) * level_index / max(1, total_levels - 1))
        return max(1, int(round(base * gradient)))

    def build_orderbook_sell_orders(self):
        """dev28：生成订单簿卖单。个体按每100可售商品一档，公司按可售库存最多20档。"""
        orders = {good: [] for good in TRADED_GOODS}
        for p in self.population_names:
            # 个体卖单
            for seller in self.populations.get(p, []):
                if seller.critical:
                    continue
                for good in TRADED_GOODS:
                    sellable = self.orderbook_individual_sellable_amount(seller, good, p)
                    if sellable <= 0:
                        continue
                    remaining = sellable
                    level = 0
                    while remaining > 0:
                        amount = min(100, remaining)
                        orders[good].append({
                            "seller_type": "individual",
                            "seller_pop": p,
                            "seller": seller,
                            "good": good,
                            "amount": int(amount),
                            "price_index": self.individual_ask_price_index(p, good, level),
                            "seller_id": getattr(seller, "code", getattr(seller, "id", "")),
                        })
                        remaining -= amount
                        level += 1
            # 公司卖单
            for good in TRADED_GOODS:
                amount_total = self.orderbook_company_listing_amount(p, good)
                if amount_total <= 0:
                    continue
                levels = min(20, max(1, int(math.ceil(amount_total / 100))))
                base_chunk = max(1, int(math.ceil(amount_total / levels)))
                remaining = amount_total
                self.turn_company_inventory_listed[p][good] += int(amount_total)
                self.turn_company_inventory_listing_ratio[p][good] = int(round(self.company_inventory_listing_ratio(p, good) * 100))
                self.turn_company_orderbook_ask_count[p][good] += int(levels)
                self.log_event(
                    "公司库存上架",
                    f"{p}部族{GOOD_DISPLAY.get(good, good)}分公司上架{int(amount_total)}库存，{int(levels)}档，"
                    f"上架比例{self.turn_company_inventory_listing_ratio[p][good]}%",
                    entity_type="company",
                    entity_id=f"Company:{p}:{good}",
                    population=p,
                    event_type="company_inventory_listing",
                    data={"good": good, "amount_total": int(amount_total), "levels": int(levels), "listing_ratio_percent": int(self.turn_company_inventory_listing_ratio[p][good]), "sellable_stock": int(self.company_sellable_amount(p, good))}
                )
                # dev35：区分本回合新生产上架与历史库存清算上架。
                # produced_quota 代表本回合生产量中可能进入订单簿的数量；超过该额度的卖单视为历史库存清算。
                produced_quota = max(0, min(int(self.companies.get(p, {}).get(good, {}).get("goods_produced", 0)), int(amount_total)))
                for level in range(levels):
                    if remaining <= 0:
                        break
                    amount = min(base_chunk, remaining)
                    new_production_part = min(int(amount), produced_quota)
                    historical_part = max(0, int(amount) - int(new_production_part))
                    produced_quota -= new_production_part
                    orders[good].append({
                        "seller_type": "company",
                        "seller_pop": p,
                        "seller": None,
                        "good": good,
                        "amount": int(amount),
                        "price_index": self.company_ask_price_index(p, good, level, levels),
                        "seller_id": f"Company:{p}:{good}",
                        "historical_amount": int(historical_part),
                    })
                    remaining -= amount
        for good in TRADED_GOODS:
            orders[good].sort(key=lambda o: (o["price_index"], -o["amount"]))
        return orders

    def orderbook_goods_cost(self, amount, price_index):
        amount = int(max(0, amount))
        if amount <= 0:
            return 0
        return max(1, int(math.ceil(amount * max(1, int(price_index)) / 100)))

    def individual_effective_buy_willingness(self, buyer, good=None, need_kind=None):
        """dev40：按需求类型计算有效买入意愿。

        刚性需求不再用普通买入意愿压缩；储备和教育等非刚性需求继续使用 dev39 的工资响应消费。
        """
        p = getattr(buyer, "population_name", "A")
        cfg = self.state["population_config"].get(p, {})
        base = max(0, min(100, int(cfg.get("individual_buy_willingness", 80))))
        if need_kind in HARD_NEED_KINDS:
            return base, 100, 0
        bonus = 0
        if int(cfg.get("enable_wage_responsive_consumption", 1)):
            survival_cost = max(1, int(self.cfg.get("base", {}).get("survival_cost", 100)))
            per_survival = max(0, int(cfg.get("wage_consumption_bonus_per_survival", 10)))
            cap = max(0, int(cfg.get("wage_consumption_bonus_cap", 20)))
            wage = max(0, int(getattr(buyer, "wage_received", 0)))
            bonus = min(cap, int((wage / survival_cost) * per_survival))
        effective = max(0, min(100, base + bonus))
        return base, effective, bonus

    def hard_need_prefix(self, good, need_kind):
        if need_kind == NEED_FOOD_HARD or (need_kind == "hard" and good == "food"):
            return "food"
        if need_kind == NEED_MEDICAL_HARD or (need_kind == "hard" and good == "medical_goods"):
            return "medical"
        if need_kind == NEED_REPRODUCTION_HARD or (need_kind == "hard" and good == "reproduction_goods"):
            return "reproduction"
        return ""

    def is_hard_need_kind(self, good, need_kind):
        return self.hard_need_prefix(good, need_kind) != ""

    def individual_orderbook_spending_cap(self, buyer, good, price_index, need_kind=None, need_amount=0):
        """兼容旧调用；dev40 起内部转到按需求类型的预算函数。"""
        return self.individual_orderbook_spending_cap_by_need(buyer, good, price_index, need_kind, need_amount)

    def individual_orderbook_spending_cap_by_need(self, buyer, good, price_index, need_kind=None, need_amount=0):
        """dev40：按需求类型释放购买预算。

        - 食物刚需：仅限刚性缺口，允许使用当前全部现金，不受价格折扣/普通买入意愿压缩。
        - 医疗刚需：生病个体在食物刚需之后可使用当前剩余现金购买医疗刚需。
        - 生育用品刚需：在食物/医疗刚需之后，可使用 90% 当前剩余现金购买生育用品刚需。
        - 储备/教育：保留 dev39 普通消费意愿、工资响应消费和价格敏感规则。
        """
        p = getattr(buyer, "population_name", "A")
        balance = int(max(0, getattr(buyer, "balance", 0)))
        need_amount = int(max(0, need_amount))
        price_index = max(1, int(price_index))
        prefix = self.hard_need_prefix(good, need_kind)
        if prefix:
            if balance <= 0 or need_amount <= 0:
                return 0
            if prefix == "medical" and not getattr(buyer, "is_sick", 0):
                return 0
            if prefix == "reproduction":
                if getattr(buyer, "critical", False) or getattr(buyer, "is_sick", 0):
                    return 0
                survival_cost = int(self.cfg.get("base", {}).get("survival_cost", 100))
                if int(getattr(buyer, "food", 0)) < survival_cost:
                    return 0
                return max(0, min(balance, int(balance * 0.9)))
            return balance

        base_willingness, willingness, bonus = self.individual_effective_buy_willingness(buyer, good, need_kind)
        base_limit = max(0, int(self.market_spending_limit(buyer, good)))
        price_factor = min(1.5, max(0.25, 100 / max(1, int(price_index))))
        base_cap = int(balance * base_willingness / 100 * price_factor)
        cap = int(balance * willingness / 100 * price_factor)
        final_cap = max(0, min(base_limit, cap, balance))
        base_final_cap = max(0, min(base_limit, base_cap, balance))
        if hasattr(self, "turn_effective_buy_willingness_sum"):
            self.turn_effective_buy_willingness_sum[p] += willingness
            self.turn_effective_buy_willingness_count[p] += 1
            self.turn_wage_consumption_bonus_sum[p] += bonus
            if bonus > 0:
                self.turn_wage_responsive_buyer_count[p] += 1
                self.turn_wage_responsive_extra_cap_total[p] += max(0, final_cap - base_final_cap)
        return final_cap

    def execute_orderbook_trade(self, buyer_pop, buyer, order, requested_amount, need_kind=None):
        """dev27：按订单价格成交。买方扣款=卖方收入；交易税/进口税暂保持 dev26 逻辑不生效。"""
        amount = int(max(0, min(requested_amount, order.get("amount", 0))))
        if amount <= 0 or buyer.balance <= 0:
            return 0
        good = order["good"]
        price_index = max(1, int(order["price_index"]))
        cap = self.individual_orderbook_spending_cap_by_need(buyer, good, price_index, need_kind, amount)
        if cap <= 0:
            return 0
        affordable = int(cap * 100 // price_index)
        amount = min(amount, affordable)
        while amount > 0 and self.orderbook_goods_cost(amount, price_index) > buyer.balance:
            amount -= 1
        if amount <= 0:
            return 0
        cost = self.orderbook_goods_cost(amount, price_index)
        if cost <= 0 or cost > buyer.balance:
            return 0
        seller_pop = order["seller_pop"]
        if order["seller_type"] == "company":
            branch = self.companies.get(seller_pop, {}).get(good)
            if not branch or branch.get("stock", 0) < amount:
                return 0
            buyer.balance -= cost
            branch["stock"] -= amount
            branch["money"] += cost
            branch["sales_income"] += cost
            # dev35：只把订单中标记为历史库存清算的部分计入库存清算收入。
            historical_amount = min(int(amount), max(0, int(order.get("historical_amount", 0))))
            historical_income = int(round(cost * historical_amount / max(1, int(amount)))) if historical_amount > 0 else 0
            if historical_income > 0:
                branch["historical_inventory_sales_income"] = branch.get("historical_inventory_sales_income", 0) + historical_income
                self.turn_historical_inventory_sales_income[seller_pop] += historical_income
            order["historical_amount"] = max(0, int(order.get("historical_amount", 0)) - historical_amount)
            branch["sales_volume"] = branch.get("sales_volume", 0) + amount
            self.turn_company_actual_revenue[seller_pop] += cost
            self.turn_company_inventory_sold_to_individuals[seller_pop][good] += amount
        else:
            seller = order["seller"]
            if seller is None or int(getattr(seller, good, 0)) < amount:
                return 0
            buyer.balance -= cost
            setattr(seller, good, int(getattr(seller, good, 0)) - amount)
            seller.balance += cost
            seller.market_money_earned += cost
            seller.market_goods_sold_value += cost
            setattr(seller, f"market_{good}_sold", getattr(seller, f"market_{good}_sold", 0) + amount)
            if buyer_pop != seller_pop:
                seller.market_export_value += cost
            seller.did_market_trade = 1
        setattr(buyer, good, int(getattr(buyer, good, 0)) + amount)
        setattr(buyer, f"market_{good}_bought", getattr(buyer, f"market_{good}_bought", 0) + amount)
        hard_prefix = self.hard_need_prefix(good, need_kind)
        if hard_prefix:
            actual_attr = f"turn_{hard_prefix}_hard_actual_spending"
            satisfied_attr = f"turn_{hard_prefix}_hard_satisfied_amount"
            getattr(self, actual_attr)[buyer_pop] += cost
            getattr(self, satisfied_attr)[buyer_pop] += amount
            self.turn_hard_need_spending_total[buyer_pop] += cost
        elif need_kind in RESERVE_NEED_KINDS or need_kind in ("reserve", NEED_EDUCATION, NEED_TOOLS, "total"):
            self.turn_reserve_need_spending_total[buyer_pop] += cost
        buyer.market_money_spent += cost
        buyer.market_goods_bought_value += cost
        if hasattr(self, "turn_worker_market_spending") and int(getattr(buyer, "wage_received", 0)) > 0:
            self.turn_worker_market_spending[buyer_pop] += cost
            self.turn_wage_funded_market_spending[buyer_pop] += min(cost, int(getattr(buyer, "wage_received", 0)))
            if order.get("seller_type") == "company":
                self.turn_worker_market_spending_to_company[buyer_pop] += cost
        buyer.did_market_trade = 1
        if buyer_pop != seller_pop:
            buyer.market_import_value += cost
        self.turn_market_trade_count[buyer_pop] += 1
        self.turn_market_trade_volume[buyer_pop] += cost
        self.turn_market_volume_by_good[buyer_pop][good] += amount
        self.turn_market_trade_money_by_good[buyer_pop][good] += cost
        self.turn_market_trade_amount_by_good[buyer_pop][good] += amount
        if buyer_pop == seller_pop:
            self.turn_market_local_volume[buyer_pop][good] += amount
        else:
            self.turn_market_import_volume[buyer_pop][good] += amount
            self.turn_market_export_volume[seller_pop][good] += amount
            self.turn_import_spending[buyer_pop] += cost
            self.turn_export_income[seller_pop] += cost
            self.append_trade_flow(buyer_pop, seller_pop, buyer, order.get("seller_id", ""), good, amount, cost, 0, 0, cost)
        if good == "food":
            self.turn_market_food_volume[buyer_pop] += amount
            if hasattr(self, "turn_food_bought_by_potential_parent") and self.is_potential_parent_with_goods_for_dev38(buyer):
                self.turn_food_bought_by_potential_parent[buyer_pop] += amount
        elif good == "medical_goods":
            self.turn_market_medical_goods_volume[buyer_pop] += amount
            if getattr(buyer, "critical", False):
                self.turn_medical_goods_bought_by_critical[buyer_pop] += amount
            else:
                self.turn_medical_goods_bought_by_healthy[buyer_pop] += amount
        elif good == "education_goods":
            self.turn_market_education_goods_volume[buyer_pop] += amount
        elif good == "reproduction_goods":
            self.turn_market_reproduction_goods_volume[buyer_pop] += amount
            if order["seller_type"] == "company":
                self.turn_reproduction_goods_company_sales_volume[buyer_pop] += amount
            else:
                self.turn_reproduction_goods_individual_sales_volume[buyer_pop] += amount
        order["amount"] -= amount
        phase = "订单簿市场"
        if good == "reproduction_goods" and self.is_reproduction_hard_buyer(buyer, buyer_pop):
            phase = "生育用品优先销售"
        self.log_event(phase, f"{getattr(buyer, 'code', buyer.id)} 按价格{price_index}购买{amount}{GOOD_DISPLAY.get(good, good)}，支付{cost}", entity_type="individual", entity_id=str(getattr(buyer, "code", buyer.id)), population=buyer_pop, event_type="orderbook_purchase", data={"buyer_id": str(getattr(buyer, "code", buyer.id)), "seller_id": str(order.get("seller_id", "")), "seller_type": str(order.get("seller_type", "")), "seller_population": str(order.get("seller_pop", "")), "good": good, "amount": int(amount), "price_index": int(price_index), "cost": int(cost), "need_kind": str(need_kind or "")})
        return amount

    def orderbook_buyer_need_amount(self, buyer, good, need_kind):
        """dev40：按具体需求类型重新计算当前需求量，避免刚性阶段提前买入储备量。"""
        hard, reserve = self.market_goods_hard_reserve_need(buyer, good)
        if need_kind in ("hard", NEED_FOOD_HARD, NEED_MEDICAL_HARD, NEED_REPRODUCTION_HARD):
            return max(0, int(hard))
        if need_kind in ("reserve", NEED_REPRODUCTION_RESERVE, NEED_FOOD_RESERVE, NEED_MEDICAL_RESERVE):
            return max(0, int(reserve))
        return max(0, int(self.market_goods_need(buyer, good)))

    def orderbook_buyer_demand_plan(self, buyer):
        """dev30：生成单个买方内部购买计划。

        关键点：食物刚性缺口优先，但只购买刚性缺口本身；食物储备排在生育用品之后。
        这修复了简单“食物优先”会把储备食物也提前买走、挤出生育用品预算的问题。
        """
        plan = []
        # 1 食物刚性需求：仅补到本回合基础生存线。
        hard, reserve = self.market_goods_hard_reserve_need(buyer, "food")
        if hard > 0:
            plan.append((1, "food", NEED_FOOD_HARD))
        # 2 生病个体医疗刚性需求。
        hard, reserve = self.market_goods_hard_reserve_need(buyer, "medical_goods")
        if hard > 0:
            plan.append((2, "medical_goods", NEED_MEDICAL_HARD))
        # 3 生育用品刚性需求。
        hard, reserve = self.market_goods_hard_reserve_need(buyer, "reproduction_goods")
        if hard > 0:
            plan.append((3, "reproduction_goods", NEED_REPRODUCTION_HARD))
        if reserve > 0:
            plan.append((4, "reproduction_goods", NEED_REPRODUCTION_RESERVE))
        # 5 食物储备需求：在生育用品之后，避免把繁殖预算提前消耗在非刚性食物库存上。
        hard, reserve = self.market_goods_hard_reserve_need(buyer, "food")
        if reserve > 0:
            plan.append((5, "food", NEED_FOOD_RESERVE))
        # 6 医疗储备需求。
        hard, reserve = self.market_goods_hard_reserve_need(buyer, "medical_goods")
        if reserve > 0:
            plan.append((6, "medical_goods", NEED_MEDICAL_RESERVE))
        # 7 教育用品需求。
        need = int(self.market_goods_need(buyer, "education_goods"))
        if need > 0:
            plan.append((7, "education_goods", NEED_EDUCATION))
        plan.sort(key=lambda item: item[0])
        return plan

    def orderbook_available_amount_for_buyer(self, orders, buyer_pop, buyer, good):
        """返回当前订单簿中该买方可购买的指定商品数量，用于诊断未满足原因。"""
        total = 0
        for order in orders.get(good, []):
            amount = int(order.get("amount", 0))
            if amount <= 0:
                continue
            if order.get("seller_type") == "individual" and order.get("seller") is buyer:
                continue
            if order.get("seller_pop") != buyer_pop and not self.is_feature_enabled("enable_global_trade"):
                continue
            total += amount
        return max(0, total)

    def orderbook_purchase_one_good(self, p, buyer, good, need, orders, need_kind=None):
        """dev30：让单个买方按当前订单簿购买一种商品，供买方内部优先级流程复用。"""
        bought_total = 0
        order_list = orders.get(good, [])
        idx = 0
        while need > 0 and buyer.balance > 0 and idx < len(order_list):
            order = order_list[idx]
            if order.get("amount", 0) <= 0:
                idx += 1
                continue
            if order["seller_type"] == "individual" and order.get("seller") is buyer:
                idx += 1
                continue
            # 关闭跨部族自由交易时，只购买本部族卖单。
            if order["seller_pop"] != p and not self.is_feature_enabled("enable_global_trade"):
                idx += 1
                continue
            bought = self.execute_orderbook_trade(p, buyer, order, need, need_kind)
            if bought <= 0:
                idx += 1
                continue
            bought_total += bought
            need -= bought
        return bought_total

    def orderbook_individual_purchase_phase(self, orders):
        # dev30：买方之间保持随机，买方内部按刚性/储备需求优先级购买。
        # 这不是强制干预，不创造资源、不提高出生率，只修复 dev27 订单簿把同一个体不同需求完全随机化的问题。
        buyers = []
        for p, pop in self.populations.items():
            self.calculate_initial_market_demand_supply(p, pop, TRADED_GOODS)
            for ind in pop:
                if ind.critical:
                    continue
                # 生育用品需求诊断每个体每回合记录一次，避免按商品循环重复计数。
                self.record_reproduction_goods_demand_diagnostic(p, ind)
                total_need = 0
                for good in TRADED_GOODS:
                    total_need += int(self.market_goods_need(ind, good))
                if total_need > 0:
                    ind.total_market_need += total_need
                    buyers.append((p, ind, self.orderbook_buyer_demand_plan(ind)))

        random.shuffle(buyers)
        for p, buyer, demand_items in buyers:
            if buyer.balance <= 0 or buyer.critical:
                continue
            for _, good, need_kind in demand_items:
                if buyer.balance <= 0 or buyer.critical:
                    break
                need = int(self.orderbook_buyer_need_amount(buyer, good, need_kind))
                if need <= 0:
                    continue

                hard_prefix = self.hard_need_prefix(good, need_kind)
                hard_need_amount = 0
                if hard_prefix:
                    hard_need_amount = int(need)
                    getattr(self, f"turn_{hard_prefix}_hard_need_count")[p] += 1
                    getattr(self, f"turn_{hard_prefix}_hard_need_amount")[p] += hard_need_amount
                    cap_for_diag = self.individual_orderbook_spending_cap_by_need(buyer, good, self.goods_price_index(p, good), need_kind, hard_need_amount)
                    getattr(self, f"turn_{hard_prefix}_hard_spending_cap")[p] += int(max(0, cap_for_diag))

                hard_reproduction_need = 0
                tracked_reproduction_hard = False
                if good == "reproduction_goods" and need_kind == NEED_REPRODUCTION_HARD:
                    hard_reproduction_need = min(need, int(self.reproduction_goods_hard_need(buyer)))
                    if hard_reproduction_need > 0:
                        tracked_reproduction_hard = True
                        self.turn_reproduction_goods_hard_buyer_count[p] += 1
                        self.turn_reproduction_goods_hard_demand_total[p] += hard_reproduction_need

                bought = self.orderbook_purchase_one_good(p, buyer, good, need, orders, need_kind)

                if hard_prefix:
                    unsatisfied_hard = max(0, hard_need_amount - int(bought))
                    getattr(self, f"turn_{hard_prefix}_hard_unsatisfied_amount")[p] += unsatisfied_hard
                    if unsatisfied_hard > 0:
                        available = self.orderbook_available_amount_for_buyer(orders, p, buyer, good)
                        if available <= 0:
                            self.turn_hard_need_blocked_by_no_market_stock[p] += unsatisfied_hard
                        elif buyer.balance <= 0:
                            self.turn_hard_need_blocked_by_no_cash[p] += unsatisfied_hard
                        else:
                            cap_left = self.individual_orderbook_spending_cap_by_need(buyer, good, self.goods_price_index(p, good), need_kind, unsatisfied_hard)
                            if cap_left <= 0:
                                self.turn_hard_need_blocked_by_budget_cap[p] += unsatisfied_hard
                            else:
                                self.turn_hard_need_blocked_by_high_price[p] += unsatisfied_hard

                if tracked_reproduction_hard:
                    satisfied = min(hard_reproduction_need, bought)
                    unsatisfied = max(0, hard_reproduction_need - satisfied)
                    self.turn_reproduction_goods_hard_demand_satisfied[p] += satisfied
                    self.turn_reproduction_goods_hard_demand_unsatisfied[p] += unsatisfied
                    if unsatisfied > 0:
                        available = self.orderbook_available_amount_for_buyer(orders, p, buyer, good)
                        if available <= 0:
                            self.turn_reproduction_goods_blocked_no_company_stock[p] += unsatisfied
                        elif buyer.balance <= 0 or self.individual_orderbook_spending_cap_by_need(buyer, good, self.goods_price_index(p, good), need_kind, unsatisfied) <= 0:
                            self.turn_reproduction_goods_blocked_no_money[p] += unsatisfied

        for p, pop in self.populations.items():
            for ind in pop:
                if ind.critical:
                    continue
                for good in TRADED_GOODS:
                    remaining = self.market_goods_need(ind, good)
                    if remaining > 0:
                        setattr(ind, f"market_unmet_{good}_need", remaining)
                        ind.total_market_unmet_need += remaining

    def government_orderbook_spending_cap(self, p, good, price_index):
        cfg = self.state["population_config"].get(p, {})
        willingness = max(0, min(100, int(cfg.get("government_buy_willingness", 60))))
        deposit = max(0, int(self.government_deposit.get(p, 0)))
        if deposit <= 0 or willingness <= 0:
            return 0
        reserve = int(deposit * (100 - willingness) / 100)
        available = max(0, deposit - reserve)
        price_factor = min(1.0, max(0.05, 100 / max(1, int(price_index))))
        return int(available * price_factor)

    def execute_government_orderbook_purchase(self, buyer_pop, order, requested_amount):
        good = order["good"]
        price_index = max(1, int(order["price_index"]))
        cap = self.government_orderbook_spending_cap(buyer_pop, good, price_index)
        if cap <= 0:
            return 0
        amount = min(int(requested_amount), int(order.get("amount", 0)))
        affordable = int(cap * 100 // price_index)
        amount = min(amount, affordable)
        while amount > 0 and self.orderbook_goods_cost(amount, price_index) > self.government_deposit[buyer_pop]:
            amount -= 1
        if amount <= 0:
            return 0
        cost = self.orderbook_goods_cost(amount, price_index)
        if cost <= 0 or cost > self.government_deposit[buyer_pop]:
            return 0
        seller_pop = order["seller_pop"]
        if order["seller_type"] == "company":
            branch = self.companies.get(seller_pop, {}).get(good)
            if not branch or branch.get("stock", 0) < amount:
                return 0
            self.government_deposit[buyer_pop] -= cost
            branch["stock"] -= amount
            branch["money"] += cost
            branch["sales_income"] += cost
            # dev35：政府购买公司订单时，同样只把历史库存清算部分计入可分红来源。
            historical_amount = min(int(amount), max(0, int(order.get("historical_amount", 0))))
            historical_income = int(round(cost * historical_amount / max(1, int(amount)))) if historical_amount > 0 else 0
            if historical_income > 0:
                branch["historical_inventory_sales_income"] = branch.get("historical_inventory_sales_income", 0) + historical_income
                self.turn_historical_inventory_sales_income[seller_pop] += historical_income
            order["historical_amount"] = max(0, int(order.get("historical_amount", 0)) - historical_amount)
            branch["sales_volume"] = branch.get("sales_volume", 0) + amount
            self.turn_company_actual_revenue[seller_pop] += cost
            self.turn_government_purchase_to_company[buyer_pop] += cost
            self.turn_company_inventory_sold_to_government[seller_pop][good] += amount
        else:
            seller = order.get("seller")
            if seller is None or int(getattr(seller, good, 0)) < amount:
                return 0
            self.government_deposit[buyer_pop] -= cost
            setattr(seller, good, int(getattr(seller, good, 0)) - amount)
            seller.balance += cost
            seller.market_money_earned += cost
            seller.government_purchase_sold += cost
            seller.did_market_trade = 1
        self.add_government_good(buyer_pop, good, amount)
        self.turn_government_orderbook_purchase[buyer_pop][good] += amount
        self.turn_government_orderbook_purchase_spending[buyer_pop] += cost
        self.turn_government_purchase_spending[buyer_pop] += cost
        order["amount"] -= amount
        self.turn_market_trade_count[buyer_pop] += 1
        self.turn_market_trade_volume[buyer_pop] += cost
        self.turn_market_volume_by_good[buyer_pop][good] += amount
        self.turn_market_trade_money_by_good[buyer_pop][good] += cost
        self.turn_market_trade_amount_by_good[buyer_pop][good] += amount
        self.log_event("政府剩余购买", f"{buyer_pop}部族政府按价格{price_index}购买{amount}{GOOD_DISPLAY.get(good, good)}，支付{cost}", entity_type="government", entity_id=f"Government:{buyer_pop}", population=buyer_pop, event_type="government_orderbook_purchase", data={"buyer_id": f"Government:{buyer_pop}", "seller_id": str(order.get("seller_id", "")), "seller_type": str(order.get("seller_type", "")), "seller_population": str(order.get("seller_pop", "")), "good": good, "amount": int(amount), "price_index": int(price_index), "cost": int(cost), "need_kind": "government_last_buyer"})
        return amount

    def government_orderbook_purchase_phase(self, orders):
        # dev27：个体购买优先；政府作为最后买方按低价优先吸收剩余卖单，但不会耗尽全部财政。
        for p in self.population_names:
            for good in TRADED_GOODS:
                order_list = [o for o in orders.get(good, []) if o.get("amount", 0) > 0]
                order_list.sort(key=lambda o: (o["price_index"], -o["amount"]))
                for order in order_list:
                    if self.government_deposit[p] <= 0:
                        break
                    self.execute_government_orderbook_purchase(p, order, order.get("amount", 0))

    def government_stock_limit(self, p, good):
        pop_count = len(self.populations.get(p, []))
        survival_cost = int(self.cfg["base"].get("survival_cost", 100))
        child_units = self.reproduction_goods_required_per_birth()
        if pop_count <= 0:
            return 0
        if good == "food":
            return pop_count * survival_cost * 3
        if good == "medical_goods":
            sick_count = sum(1 for i in self.populations.get(p, []) if getattr(i, "is_sick", 0))
            return sick_count * survival_cost * 3 + int(pop_count * survival_cost * 0.5)
        if good == "education_goods":
            return max(0, self.turn_birth_count.get(p, 0)) * child_units * 3
        if good == "reproduction_goods":
            # dev31：公共生育用品在繁殖前会释放给刚性买方，因此剩余价值删除上限必须
            # 至少覆盖当前刚性缺口和上一回合因缺生育用品失败的信号。否则政府刚买入的
            # 生育用品会在尚未形成下一轮繁殖准备前被删除。
            hard_need = sum(self.reproduction_goods_hard_need(i) for i in self.populations.get(p, []) if self.is_reproduction_hard_buyer(i, p))
            blocked_need = int(getattr(self, "last_birth_blocked_no_reproduction_goods", {}).get(p, 0)) * child_units
            baseline = int(pop_count * child_units)
            return max(baseline, int(hard_need + blocked_need))
        if good == "tools":
            return 0
        return 0

    def government_surplus_value_cleanup_phase(self):
        # dev27：政府超过目标保留量的实物被移除并记录为“剩余价值”。
        for p in self.population_names:
            for good in GOOD_FIELDS:
                stock = self.government_good_stock(p, good)
                limit = self.government_stock_limit(p, good)
                excess = max(0, int(stock) - int(limit))
                if excess <= 0:
                    continue
                self.remove_government_good(p, good, excess)
                self.turn_government_surplus_deleted[p][good] += excess
                value_index = self.goods_price_index(p, good) if good in TRADED_GOODS else 100
                value = int(math.ceil(excess * value_index / 100))
                self.turn_government_surplus_value[p] += value
                self.log_event("剩余价值", f"{p}部族政府移除超过保留上限的{excess}{GOOD_DISPLAY.get(good, good)}，剩余价值{value}", entity_type="government", entity_id=f"Government:{p}", population=p, event_type="government_surplus_cleanup", data={"good": good, "amount": int(excess), "surplus_value": int(value), "stock_limit": int(limit)})

    def finalize_market_statistics_and_prices(self):
        # dev27：市场价格优先由本回合订单簿成交均价形成；无成交时才沿用供需压力微调。
        b = self.cfg["base"]
        speed = max(0, int(b.get("price_adjust_speed", 10))) / 100
        min_price = int(b.get("min_price_index", 1))
        max_price = max(min_price, int(b.get("max_price_index", 500)))
        for p, pop in self.populations.items():
            for good in TRADED_GOODS:
                raw_unmet = sum(self.market_goods_need(ind, good) for ind in pop if not ind.critical and ind.balance > 0)
                raw_unsold = sum(self.market_goods_surplus(ind, good, p) for ind in pop if not ind.critical) + self.company_sellable_amount(p, good)
                unmet = max(0, int(raw_unmet))
                unsold = max(0, int(raw_unsold))
                self.turn_market_unmet_demand[p][good] = unmet
                self.turn_market_unsold_supply[p][good] = unsold
                amount = self.turn_market_trade_amount_by_good[p][good]
                money = self.turn_market_trade_money_by_good[p][good]
                if amount > 0:
                    avg_price = int(round(money * 100 / max(1, amount)))
                    self.market_price_index[p][good] = int(max(min_price, min(max_price, avg_price)))
                    continue
                old_price = self.goods_price_index(p, good)
                supply_base = max(1, self.turn_market_supply[p][good])
                demand_base = max(1, self.turn_market_demand[p][good])
                shortage_pressure = unmet / supply_base
                surplus_pressure = unsold / demand_base
                if shortage_pressure > 0:
                    new_price = old_price * (1 + speed * shortage_pressure)
                elif surplus_pressure > 0:
                    new_price = old_price * (1 - speed * surplus_pressure)
                else:
                    new_price = old_price
                self.market_price_index[p][good] = int(max(min_price, min(max_price, round(new_price))))

    def finalize_company_inventory_orderbook_stats(self, orders):
        """dev28：政府购买结束后统计公司订单簿剩余未成交库存。"""
        for good, order_list in orders.items():
            for order in order_list:
                if order.get("seller_type") != "company":
                    continue
                seller_pop = order.get("seller_pop")
                if seller_pop not in self.turn_company_inventory_unsold:
                    continue
                remaining = max(0, int(order.get("amount", 0)))
                self.turn_company_inventory_unsold[seller_pop][good] += remaining

    def market_phase(self):
        if not self.is_feature_enabled("enable_market"):
            return
        orders = self.build_orderbook_sell_orders()
        self.orderbook_individual_purchase_phase(orders)
        # dev31：政府订单簿最后买方拆分为独立开关。它是市场流动性闭环；旧宏观调控开关
        # 只负责低价收储、高价投放等宏观调控语义，二者不再混用。
        if self.is_feature_enabled("enable_government_orderbook_buyer"):
            self.government_orderbook_purchase_phase(orders)
        self.finalize_company_inventory_orderbook_stats(orders)
        # dev29：剩余价值清理不再位于市场阶段内部。政府刚购买的公共库存必须先经过
        # 政府救助、政府教育和本回合生存/繁殖等既有用途，再在回合末清理超额库存。
        self.finalize_market_statistics_and_prices()
        self.calculate_market_stability_index()

    def internal_plunder_phase(self):
        if not self.is_feature_enabled("enable_internal_plunder"):
            return
        beh = self.cfg["behavior"]
        for p, pop in self.populations.items():
            actual = set()
            for attacker in [i for i in pop if i.role == "plunder" and not i.critical and self.inventory_total_value(i, p) > 0]:
                targets = [
                    t for t in pop
                    if t.id != attacker.id
                    and not t.critical
                    and t.strength < attacker.strength
                    and self.inventory_total_value(t, p) > 0
                ]
                if not targets:
                    continue
                target = random.choice(targets)
                ratio = random.randint(beh["internal_plunder_min"], beh["internal_plunder_max"])

                # BOT8 2.2.0：最低掠夺需求只在掠夺者濒死边缘、且目标余额足够时触发。
                # BOT8 dev9：最低需求只提升货币掠夺比例，不改变商品库存按比例被掠夺的原则。
                if attacker.balance < self.cfg["base"]["survival_cost"] and target.balance >= self.cfg["base"]["survival_cost"]:
                    minimum_money_need = max(0, self.cfg["base"]["survival_cost"] - attacker.balance)
                    if target.balance > 0:
                        ratio = max(ratio, int(math.ceil(minimum_money_need / max(1, target.balance) * 100)))
                        ratio = min(100, ratio)

                result = self.plunder_inventory_by_ratio(attacker, target, ratio, "internal_plunder", loss_population=p, gain_population=p)
                money_loss = result["money_loss"]
                money_gain = result["money_gain"]
                goods_loss = result["goods_loss"]
                goods_gain = result["goods_gain"]
                goods_system_loss = result["goods_system_loss"]
                total_value_loss = result["total_value_loss"]
                total_value_gain = result["total_value_gain"]

                attacker.did_internal_plunder = 1
                attacker.internal_plunder_gain += money_gain
                attacker.internal_plunder_goods_gain += goods_gain
                attacker.internal_plunder_goods_loss += 0
                attacker.internal_plunder_goods_system_loss += goods_system_loss
                attacker.internal_plunder_total_value_gain += total_value_gain
                attacker.internal_plunder_total_value_loss += 0
                attacker.internal_plunder_victim_loss_caused += money_loss
                attacker.internal_plunder_system_loss_caused += 0

                target.was_internal_plunder_victim = 1
                target.internal_plunder_loss += money_loss
                target.internal_plunder_goods_loss += goods_loss
                target.internal_plunder_total_value_loss += total_value_loss

                self.turn_internal_plunder_count[p] += 1
                self.turn_internal_plunder_victim_loss_total[p] += money_loss
                self.turn_internal_plunder_gain_total[p] += money_gain
                self.turn_internal_plunder_system_loss_total[p] += 0
                self.turn_internal_plunder_goods_loss_total[p] += goods_loss
                self.turn_internal_plunder_goods_gain_total[p] += goods_gain
                self.turn_internal_plunder_goods_system_loss_total[p] += goods_system_loss
                self.turn_internal_plunder_total_value_loss[p] += total_value_loss
                self.turn_internal_plunder_total_value_gain[p] += total_value_gain
                actual.add(attacker.id)
            sec = self.state["population_config"][p]["security"]
            for ind in pop:
                if ind.id in actual and self.inventory_total_value(ind, p) > 0 and random.randint(1, 100) <= sec:
                    ind.was_sanctioned = 1
                    ind.sanction_loss += self.inventory_total_value(ind, p)
                    self.turn_sanction_count[p] += 1
                    self.government_deposit[p] += ind.balance
                    ind.balance = 0
                    # 制裁没收货币与全部商品库存，商品进入政府库存。
                    self.transfer_all_goods_to_government(p, ind)
                    ind.charity_banned = True

    def invasion_phase(self):
        if not self.is_feature_enabled("enable_invasion"):
            return
        for ap in self.population_names:
            for attacker in list(self.populations[ap]):
                if attacker.critical or random.randint(1, 100) > self.invasion_probability(attacker):
                    continue
                attacker.did_invasion = 1
                self.turn_invasion_attempt_count[ap] += 1
                targets = [
                    (vp, t)
                    for vp in self.population_names
                    if vp != ap
                    for t in self.populations[vp]
                    if not t.critical
                    and t.strength < attacker.strength
                    and self.inventory_total_value(t, vp) > 0
                ]
                if not targets:
                    continue
                vp, target = random.choice(targets)
                if random.randint(1, 100) <= self.invasion_success_probability(attacker.strength, target.strength):
                    loot_min = self.cfg["behavior"].get("invasion_loot_min", 30)
                    loot_max = self.cfg["behavior"].get("invasion_loot_max", 70)
                    if loot_min > loot_max:
                        loot_min, loot_max = loot_max, loot_min
                    loot_ratio = random.randint(loot_min, loot_max)

                    result = self.plunder_inventory_by_ratio(attacker, target, loot_ratio, "invasion", loss_population=vp, gain_population=ap)
                    money_loss = result["money_loss"]
                    money_gain = result["money_gain"]
                    goods_loss = result["goods_loss"]
                    goods_gain = result["goods_gain"]
                    goods_system_loss = result["goods_system_loss"]
                    total_value_loss = result["total_value_loss"]
                    total_value_gain = result["total_value_gain"]

                    attacker.invasion_success = 1
                    attacker.invasion_gain += money_gain
                    attacker.invasion_goods_gain += goods_gain
                    attacker.invasion_goods_system_loss += goods_system_loss
                    attacker.invasion_total_value_gain += total_value_gain
                    attacker.invasion_victim_loss_caused += money_loss
                    attacker.invasion_system_loss_caused += 0
                    target.was_invasion_victim = 1
                    target.invasion_loss += money_loss
                    target.invasion_goods_loss += goods_loss
                    target.invasion_total_value_loss += total_value_loss

                    self.turn_invasion_success_count[ap] += 1
                    self.turn_invasion_gain_total[ap] += money_gain
                    self.turn_invasion_victim_loss_total[vp] += money_loss
                    self.turn_invasion_system_loss_total[ap] += 0
                    self.turn_invasion_goods_loss_total[vp] += goods_loss
                    self.turn_invasion_goods_gain_total[ap] += goods_gain
                    self.turn_invasion_goods_system_loss_total[ap] += goods_system_loss
                    self.turn_invasion_total_value_loss[vp] += total_value_loss
                    self.turn_invasion_total_value_gain[ap] += total_value_gain

                    # dev11：政府采购在掠夺/侵略前发生，形成公共仓储。为避免政府库存绝对安全，
                    # 成功侵略有 25% 概率袭击被侵略部族的政府商品库存；货币仍不被袭击。
                    if random.randint(1, 100) <= 25:
                        retain_rate = max(0, min(100, int(self.cfg["behavior"].get("plunder_gain_rate", 50))))
                        for good in GOOD_FIELDS:
                            stock = getattr(self, f"government_{good}")[vp]
                            gov_loss = int(round(stock * loot_ratio / 100))
                            if gov_loss <= 0:
                                continue
                            gov_gain = int(round(gov_loss * retain_rate / 100))
                            getattr(self, f"government_{good}")[vp] -= gov_loss
                            setattr(attacker, good, int(getattr(attacker, good, 0)) + gov_gain)
                            gov_system_loss = max(0, gov_loss - gov_gain)
                            attacker.invasion_goods_gain += gov_gain
                            attacker.invasion_goods_system_loss += gov_system_loss
                            gain_value = int(round(gov_gain * (self.goods_price_index(ap, good) if good in TRADED_GOODS else 100) / 100))
                            loss_value = int(round(gov_loss * (self.goods_price_index(vp, good) if good in TRADED_GOODS else 100) / 100))
                            attacker.invasion_total_value_gain += gain_value
                            self.turn_invasion_goods_loss_total[vp] += gov_loss
                            self.turn_invasion_goods_gain_total[ap] += gov_gain
                            self.turn_invasion_goods_system_loss_total[ap] += gov_system_loss
                            self.turn_invasion_total_value_loss[vp] += loss_value
                            self.turn_invasion_total_value_gain[ap] += gain_value
                else:
                    loss_life = self.cfg["behavior"]["invasion_fail_life_loss"]
                    attacker.life -= loss_life
                    attacker.invasion_fail_life_loss += loss_life

    def tax_phase(self):
        if not self.is_tax_enabled():
            return
        # dev26：税收系统只保留富人资产税。
        # 征税对象是“货币 + 商品按当前市场价折算”的大量剩余价值者，避免压低普通个体购买力。
        for p, pop in self.populations.items():
            cfg = self.state["population_config"][p]
            threshold = int(cfg.get("wealth_tax_threshold", 1500))
            rate = max(0, int(cfg.get("wealth_tax_rate", 2)))
            wealth_collected = 0
            for ind in pop:
                market_value = self.inventory_total_value(ind, p)
                if market_value <= threshold or ind.balance <= 0:
                    continue
                taxable = market_value - threshold
                tax = int(round(taxable * rate / 100))
                tax = min(ind.balance, tax)
                if tax <= 0:
                    continue
                ind.balance -= tax
                ind.wealth_tax_paid += tax
                ind.rich_tax_paid += tax
                ind.total_tax_paid += tax
                wealth_collected += tax
            self.turn_wealth_tax_total[p] += wealth_collected
            self.turn_rich_tax_income[p] += wealth_collected
            self.government_deposit[p] += wealth_collected

    def government_aid_phase(self):
        # BOT8 dev20：政府救助改为“刚性救助优先，储备救助受预算约束”。
        # 如果政府已有库存，就必须优先满足会导致濒死/死亡的食物和医疗刚性缺口；否则会出现政府库存高而个体死亡的结构性错误。
        if not self.is_feature_enabled("enable_government_aid"):
            return
        cost = int(self.cfg["base"].get("survival_cost", 100))
        for p, pop in self.populations.items():
            initial_food = int(self.government_food[p])
            initial_medical = int(self.government_medical_goods[p])
            self.turn_government_food_before_aid[p] = initial_food
            self.turn_government_medical_goods_before_aid[p] = initial_medical
            self.turn_food_aid_eligible_count[p] = sum(1 for i in pop if i.food < cost and not i.charity_banned)
            self.turn_medical_aid_eligible_count[p] = sum(1 for i in pop if i.is_sick and i.medical_goods < cost and not i.charity_banned)
            self.turn_critical_medical_need_count[p] = sum(1 for i in pop if i.critical and i.is_sick and i.medical_goods < cost and not i.charity_banned)
            aid_value = 0

            # 1) 食物刚性救助：food < survival_cost。该部分不受 gov_aid_budget_ratio 限制。
            food_needy = sorted(
                [i for i in pop if i.food < cost and not i.charity_banned],
                key=lambda x: (0 if x.critical else 1, x.food, self.inventory_total_value(x, p))
            )
            for ind in food_needy:
                need = max(0, cost - int(ind.food))
                give = min(need, int(self.government_food[p]))
                if give <= 0:
                    break
                self.government_food[p] -= give
                ind.food += give
                if hasattr(self, "turn_food_aid_to_potential_parent") and self.is_potential_parent_with_goods_for_dev38(ind):
                    self.turn_food_aid_to_potential_parent[p] += give
                ind.food_aid_received += give
                ind.government_aid_received += give
                aid_value += give
                self.log_event("政府救助", f"{p}部族政府向{getattr(ind, 'code', ind.id)} 发放食物{give}", entity_type="government", entity_id=f"Government:{p}", population=p, event_type="government_food_aid", data={"recipient": str(getattr(ind, "code", ind.id)), "good": "food", "amount": int(give), "recipient_food_after": int(getattr(ind, "food", 0)), "government_food_after": int(self.government_food[p])})

            # 2) 医疗刚性救助：sick 且 medical_goods < survival_cost。该部分不受 gov_aid_budget_ratio 限制。
            medical_needy = sorted(
                [i for i in pop if i.is_sick and i.medical_goods < cost and not i.charity_banned],
                key=lambda x: (0 if x.critical else 1, x.medical_goods, x.food, self.inventory_total_value(x, p))
            )
            for ind in medical_needy:
                need = max(0, cost - int(ind.medical_goods))
                give = min(need, int(self.government_medical_goods[p]))
                if give <= 0:
                    break
                self.government_medical_goods[p] -= give
                ind.medical_goods += give
                ind.medical_aid_received += give
                ind.government_aid_received += give
                aid_value += give
                self.log_event("政府救助", f"{p}部族政府向{getattr(ind, 'code', ind.id)} 发放医疗用品{give}", entity_type="government", entity_id=f"Government:{p}", population=p, event_type="government_medical_aid", data={"recipient": str(getattr(ind, "code", ind.id)), "good": "medical_goods", "amount": int(give), "recipient_medical_goods_after": int(getattr(ind, "medical_goods", 0)), "government_medical_goods_after": int(self.government_medical_goods[p])})

            # 3) 储备救助：只在政府仍有库存时，把极低食物者补到最多 2 回合需求；受预算比例约束。
            ratio = max(0, min(100, self.state["population_config"].get(p, {}).get("gov_aid_budget_ratio", 50)))
            reserve_food_budget = int(round(max(0, self.government_food[p]) * ratio / 100))
            reserve_targets = sorted(
                [i for i in pop if cost <= i.food < cost * 2 and not i.charity_banned],
                key=lambda x: (x.food, self.inventory_total_value(x, p))
            )
            for ind in reserve_targets:
                if reserve_food_budget <= 0:
                    break
                need = max(0, cost * 2 - int(ind.food))
                give = min(need, reserve_food_budget, int(self.government_food[p]))
                if give <= 0:
                    continue
                self.government_food[p] -= give
                reserve_food_budget -= give
                ind.food += give
                if hasattr(self, "turn_food_aid_to_potential_parent") and self.is_potential_parent_with_goods_for_dev38(ind):
                    self.turn_food_aid_to_potential_parent[p] += give
                ind.food_aid_received += give
                ind.government_aid_received += give
                aid_value += give

            # dev23：刚性救助闭环复查。若政府仍有库存且仍有刚性缺口，继续补足；
            # 该段用于捕捉前序排序或中途状态变化导致的遗漏，避免“政府有粮而个体饿死”。
            for ind in sorted([i for i in pop if i.food < cost and not i.charity_banned], key=lambda x: (x.food, self.inventory_total_value(x, p))):
                if self.government_food[p] <= 0:
                    break
                need = max(0, cost - int(ind.food))
                give = min(need, int(self.government_food[p]))
                if give <= 0:
                    continue
                self.government_food[p] -= give
                ind.food += give
                if hasattr(self, "turn_food_aid_to_potential_parent") and self.is_potential_parent_with_goods_for_dev38(ind):
                    self.turn_food_aid_to_potential_parent[p] += give
                ind.food_aid_received += give
                ind.government_aid_received += give
                aid_value += give
                self.log_event("政府救助", f"{p}部族政府复查补发食物{give}给{getattr(ind, 'code', ind.id)}", entity_type="government", entity_id=f"Government:{p}", population=p, event_type="government_food_aid_recheck", data={"recipient": str(getattr(ind, "code", ind.id)), "good": "food", "amount": int(give), "recipient_food_after": int(getattr(ind, "food", 0)), "government_food_after": int(self.government_food[p])})
            for ind in sorted([i for i in pop if i.is_sick and i.medical_goods < cost and not i.charity_banned], key=lambda x: (x.medical_goods, x.food, self.inventory_total_value(x, p))):
                if self.government_medical_goods[p] <= 0:
                    break
                need = max(0, cost - int(ind.medical_goods))
                give = min(need, int(self.government_medical_goods[p]))
                if give <= 0:
                    continue
                self.government_medical_goods[p] -= give
                ind.medical_goods += give
                ind.medical_aid_received += give
                ind.government_aid_received += give
                aid_value += give
                self.log_event("政府救助", f"{p}部族政府复查补发医疗用品{give}给{getattr(ind, 'code', ind.id)}", entity_type="government", entity_id=f"Government:{p}", population=p, event_type="government_medical_aid_recheck", data={"recipient": str(getattr(ind, "code", ind.id)), "good": "medical_goods", "amount": int(give), "recipient_medical_goods_after": int(getattr(ind, "medical_goods", 0)), "government_medical_goods_after": int(self.government_medical_goods[p])})

            self.turn_government_aid_total[p] += aid_value
            self.turn_gov_aid_budget_used[p] += aid_value
            # 刚性救助不受预算限制，因此这里记录的是本回合剩余的公共食物/医疗库存价值，而非旧式预算余额。
            self.turn_gov_aid_budget_remaining[p] += max(0, self.government_food[p] + self.government_medical_goods[p])
            self.turn_government_food_after_aid[p] = int(self.government_food[p])
            self.turn_government_medical_goods_after_aid[p] = int(self.government_medical_goods[p])
            self.turn_food_aid_received_count[p] = sum(1 for i in pop if int(getattr(i, "food_aid_received", 0)) > 0)
            self.turn_food_aid_unmet_count[p] = sum(1 for i in pop if i.food < cost and not i.charity_banned)
            self.turn_food_shortage_with_government_food_count[p] = self.turn_food_aid_unmet_count[p] if initial_food > 0 else 0
            self.turn_medical_aid_received_count[p] = sum(1 for i in pop if int(getattr(i, "medical_aid_received", 0)) > 0)
            self.turn_medical_aid_unmet_count[p] = sum(1 for i in pop if i.is_sick and i.medical_goods < cost and not i.charity_banned)
            self.turn_medical_shortage_with_government_medical_goods_count[p] = self.turn_medical_aid_unmet_count[p] if initial_medical > 0 else 0
            self.turn_critical_medical_aid_received_count[p] = sum(1 for i in pop if i.critical and int(getattr(i, "medical_aid_received", 0)) > 0)
            self.turn_critical_medical_aid_unmet_count[p] = sum(1 for i in pop if i.critical and i.is_sick and i.medical_goods < cost and not i.charity_banned)

    def individual_rescue_phase(self):
        if not self.is_feature_enabled("enable_rescue"):
            return
        beh = self.cfg["behavior"]
        cost = int(self.cfg["base"].get("survival_cost", 100))
        for p, pop in self.populations.items():
            rescuers = [i for i in pop if i.role == "rescue" and not i.critical]
            needy = sorted(
                [i for i in pop if (i.critical or i.food < cost or (i.is_sick and i.medical_goods < cost)) and not i.charity_banned],
                key=lambda x: (0 if x.critical else 1, x.food + x.medical_goods)
            )
            helped = set()
            for rescuer in rescuers:
                avail = [n for n in needy if n.id != rescuer.id and n.id not in helped]
                if not avail:
                    break
                target = avail[0]
                given_value = 0
                # 个体救助实物化：优先转移食物，其次转移医疗用品。money 不再作为本阶段主要救助物。
                for good, needed in [("food", max(0, cost - target.food)), ("medical_goods", max(0, cost - target.medical_goods) if target.is_sick else 0)]:
                    if needed <= 0:
                        continue
                    surplus = self.market_goods_surplus(rescuer, good)
                    give = min(needed, surplus)
                    if give <= 0:
                        continue
                    setattr(rescuer, good, getattr(rescuer, good) - give)
                    setattr(target, good, getattr(target, good) + give)
                    if good == "food":
                        target.food_aid_received += give
                    elif good == "medical_goods":
                        target.medical_aid_received += give
                    given_value += give
                if given_value <= 0:
                    continue
                rescuer.individual_rescue_given += given_value
                target.individual_rescue_received += given_value
                self.turn_individual_rescue_total[p] += given_value
                helped.add(target.id)

    def moral_donation_phase(self):
        # BOT8 dev16：道德施舍机制。
        # 该机制默认关闭，并放入高级调试入口。它不同于“个体救助”：
        # 个体救助面向濒死/短缺者，道德施舍则让高道德且拥有剩余库存的个体，
        # 按少量比例把货币或商品转移给同部族总市场价值最低的个体。
        # 施舍不创造或销毁货币/商品，只改变分配结构。
        if not self.is_feature_enabled("enable_moral_donation"):
            return
        cost = int(self.cfg["base"].get("survival_cost", 100))
        for p, pop in self.populations.items():
            if len(pop) < 2:
                continue
            values = {ind.id: self.inventory_total_value(ind, p) for ind in pop}
            median_value = self.median_value(list(values.values()))
            donors = sorted(
                [i for i in pop if not i.critical and i.morality >= 70 and values.get(i.id, 0) > median_value],
                key=lambda i: (-i.morality, -values.get(i.id, 0))
            )
            targets = sorted(
                [i for i in pop if not i.critical and not i.charity_banned],
                key=lambda i: (values.get(i.id, 0), i.food + i.medical_goods)
            )
            helped = set()
            for donor in donors:
                available_targets = [t for t in targets if t.id != donor.id and t.id not in helped and values.get(t.id, 0) < values.get(donor.id, 0)]
                if not available_targets:
                    continue
                target = available_targets[0]
                # 每回合施舍规模随道德值上升，但保持温和，避免覆盖市场和政府救助机制。
                max_value_budget = max(1, int(round((donor.morality - 60) / 100 * cost)))
                donated_value = 0

                # 优先施舍目标最接近刚性需求的食物和医疗用品。
                for good in ["food", "medical_goods", "education_goods", "reproduction_goods"]:
                    if donated_value >= max_value_budget:
                        break
                    if good == "food":
                        need = max(0, cost - target.food)
                    elif good == "medical_goods":
                        need = max(0, cost - target.medical_goods) if target.is_sick else 0
                    else:
                        need = max(0, self.market_goods_target_stock(target, good) - int(getattr(target, good, 0)))
                    if need <= 0:
                        continue
                    surplus = self.market_goods_base_surplus(donor, good)
                    if surplus <= 0:
                        continue
                    price = self.goods_price_index(p, good) if good in TRADED_GOODS else 100
                    affordable_by_budget = max(0, int((max_value_budget - donated_value) * 100 // price))
                    give = min(need, surplus, affordable_by_budget)
                    if give <= 0:
                        continue
                    setattr(donor, good, int(getattr(donor, good, 0)) - give)
                    setattr(target, good, int(getattr(target, good, 0)) + give)
                    value = int(round(give * price / 100))
                    donated_value += value

                # 如果目标没有直接商品缺口，允许高道德者小额施舍货币。
                if donated_value <= 0 and donor.balance > self.state["population_config"][p].get("wealth_tax_exempt_threshold", 600) and target.balance < cost:
                    give_money = min(max_value_budget, donor.balance - self.state["population_config"][p].get("wealth_tax_exempt_threshold", 600), cost - target.balance)
                    if give_money > 0:
                        donor.balance -= give_money
                        target.balance += give_money
                        donated_value += give_money

                if donated_value <= 0:
                    continue
                donor.moral_donation_given += donated_value
                target.moral_donation_received += donated_value
                self.turn_moral_donation_total[p] += donated_value
                self.turn_moral_donation_count[p] += 1
                helped.add(target.id)

    def government_reproduction_goods_release_phase(self):
        """dev31：释放已有公共生育用品库存。

        政府会通过订单簿最后买方买入生育用品；如果不在繁殖前释放，这些库存只能留存或被剩余价值删除。
        本阶段只转移政府已经持有的实物给接近繁殖、缺少生育用品的个体，不创造资源，
        不提高出生概率，也不绕过 reproduce_phase 的食物安全线和随机繁殖判断。
        """
        if not self.is_feature_enabled("enable_government_aid"):
            return
        if not bool(self.cfg.get("base", {}).get("enable_government_reproduction_goods_release", False)):
            return
        child_cost = self.reproduction_goods_required_per_birth()
        if child_cost <= 0:
            return
        for p, pop in self.populations.items():
            if self.government_reproduction_goods[p] <= 0:
                continue
            parent_food_req = self.parent_food_required_for_birth()
            targets = sorted(
                [
                    i for i in pop
                    if self.is_reproduction_hard_buyer(i, p)
                    and int(getattr(i, "food", 0)) >= parent_food_req
                ],
                key=lambda i: (-int(getattr(i, "reproduce", 0)), -int(getattr(i, "food", 0)), self.inventory_total_value(i, p))
            )
            for ind in targets:
                if self.government_reproduction_goods[p] <= 0:
                    break
                need = max(0, child_cost - int(getattr(ind, "reproduction_goods", 0)))
                give = min(need, int(self.government_reproduction_goods[p]))
                if give <= 0:
                    continue
                self.government_reproduction_goods[p] -= give
                ind.reproduction_goods += give
                ind.government_aid_received += give
                self.turn_government_reproduction_goods_released[p] += give
                self.turn_government_reproduction_goods_release_targets[p] += 1
                self.log_event("政府生育用品释放", f"{p}部族政府向{getattr(ind, 'code', ind.id)} 发放生育用品{give}", entity_type="government", entity_id=f"Government:{p}", population=p, event_type="government_reproduction_goods_release", data={"recipient": str(getattr(ind, "code", ind.id)), "good": "reproduction_goods", "amount": int(give), "recipient_reproduction_goods_after": int(getattr(ind, "reproduction_goods", 0)), "government_reproduction_goods_after": int(self.government_reproduction_goods[p])})

    def effective_reproduction_chance(self, p, ind):
        """M6A：繁殖安全评分。

        不强制恢复人口、不绕过食物/生育用品/健康条件，只在原始 reproduce
        值附近给出 -5 到 +5 的温和修正，让健康、食物缓冲、公共信任和家庭资源
        对出生概率有可解释影响。
        """
        score = reproductive_security_score(
            ind,
            survival_cost=max(1, int(self.cfg["base"].get("survival_cost", 100))),
            parent_food_required=self.parent_food_required_for_birth(),
            reproduction_goods_required=self.reproduction_goods_required_per_birth(),
            tribe_trust=self.tribe_trust.get(p, 50),
        )
        effective, bonus = reproductive_chance_with_security(int(getattr(ind, "reproduce", 0)), score)
        ind.reproductive_security_score = score
        ind.reproductive_security_bonus = bonus
        self.turn_reproductive_security_bonus_sum[p] += int(bonus)
        self.turn_reproductive_security_count[p] += 1
        return effective

    def apply_evolution_to_child(self, p, child):
        if not self.is_feature_enabled("enable_evolution") or not self.evolution_ready[p]:
            return
        d = self.evolution_direction[p]
        if d["morality"]:
            child.morality = max(0, min(100, child.morality + random.randint(0, self.cfg["mutation"]["morality"]) * d["morality"]))
        if d["strength"]:
            child.strength += random.randint(0, self.cfg["mutation"]["strength"]) * d["strength"]
            child.enforce_ability_balance()
        if d["reproduce"]:
            child.reproduce = max(self.cfg["base"]["min_reproduce"], min(self.cfg["base"]["max_reproduce"], child.reproduce + random.randint(0, self.cfg["mutation"]["reproduce"]) * d["reproduce"]))
        if d["labor"]:
            child.labor = max(0, min(100, child.labor + random.randint(0, self.cfg["mutation"]["labor"]) * d["labor"]))

    def reproduce_phase(self):
        b = self.cfg["base"]
        money_cost = self.child_initial_money_amount()
        goods_cost = self.reproduction_goods_required_per_birth()
        survival_cost = int(b.get("survival_cost", 100))
        child_food = self.child_initial_food_amount()
        # dev29：父代食物安全线显式化，避免继续把 child_initial_balance 与食物需求混用。
        required_parent_food_for_birth = self.parent_food_required_for_birth()
        edu_unit = 100
        # dev33：二次减概率生育判定。它不读取人口数量、不提供强制恢复；第一轮生育后，
        # 仍具备完整生育资源的既有个体可进入第二轮较低概率判定，从现有资源富余自然转化为更高出生数。
        secondary_birth_enabled = bool(int(b.get("enable_secondary_birth_check", 1)))
        secondary_birth_ratio = max(0, min(100, int(b.get("secondary_birth_chance_ratio", 50))))

        for p, pop in self.populations.items():
            newborns = []
            pop_cfg = self.state["population_config"][p]

            # BOT8 dev8：政府教育不再消耗政府货币，而是消耗 government_education_goods。
            gov_education_enabled = bool(int(pop_cfg.get("gov_education_enabled", 1)))
            gov_education_budget_ratio = max(0, min(100, int(pop_cfg.get("gov_education_budget_ratio", 20))))
            gov_education_remaining = 0
            if gov_education_enabled:
                gov_education_remaining = int(round(self.government_education_goods[p] * gov_education_budget_ratio / 100))

            def create_child_for_parent(ind, secondary=False):
                nonlocal gov_education_remaining
                parent_class_before_reproduce = self.class_rank_label(p, ind.balance)[1]
                # dev23/dev29：繁殖不再因旧版“子代初始货币”而被硬性阻断。
                # 父代有多少可转移货币就转移多少，货币仍然不被销毁。
                money_transfer = min(int(ind.balance), money_cost)

                # dev29：生育消耗语义拆分。生育用品、子代货币、子代食物分别由独立参数控制。
                # 食物转移不是凭空生成，用于保证新生个体至少具备下一回合基础生存物资。
                ind.balance -= money_transfer
                self.consume_individual_good(p, ind, "reproduction_goods", goods_cost)
                self.consume_individual_good(p, ind, "food", child_food)
                ind.did_reproduce = 1
                ind.child_count += 1
                ind.reproduction_goods_consumed_for_child += goods_cost
                ind.reproduction_money_transferred_to_child += money_transfer
                ind.money_used_for_reproduction += money_transfer
                ind.reproduction_goods_used += goods_cost
                ind.birth_food_transferred_to_child = getattr(ind, "birth_food_transferred_to_child", 0) + child_food
                self.turn_birth_food_transfer_total[p] += child_food
                self.turn_reproduce_cost_total[p] += goods_cost

                child = Individual(self.cfg, parent=ind, birth_turn=self.turn)
                self.assign_child_code(p, child, ind)
                child.balance = money_transfer
                child.food = child_food
                event_name = "二次生育" if secondary else "生育"
                self.log_event(event_name, f"{getattr(ind, 'code', ind.id)} 消耗{goods_cost}生育用品、转移{child_food}食物和{money_transfer}货币，生育 {getattr(child, 'code', child.id)}", entity_type="individual", entity_id=str(getattr(ind, "code", ind.id)), population=p, event_type="secondary_birth" if secondary else "birth", data={"child_code": str(getattr(child, "code", child.id)), "reproduction_goods_cost": int(goods_cost), "child_food": int(child_food), "money_transfer": int(money_transfer), "parent_food_after": int(getattr(ind, "food", 0)), "parent_reproduction_goods_after": int(getattr(ind, "reproduction_goods", 0))})
                child.inheritance_received += child.balance
                child.birth_food_received = child_food
                self.turn_child_initial_wealth_total[p] += child.balance

                # 家庭教育：不再消耗货币，每满 100 教育用品为子代增加临时智慧。
                education_gain_per_100 = max(0, int(b.get("education_temp_int_per_100_goods", b.get("education_temp_int_per_100_balance", 10))))
                usable_education_goods = (max(0, ind.education_goods) // edu_unit) * edu_unit
                if usable_education_goods > 0:
                    self.consume_individual_good(p, ind, "education_goods", usable_education_goods)
                family_temp_int = int((usable_education_goods // edu_unit) * education_gain_per_100)
                child.temp_intelligence = int(family_temp_int)
                child.education_temp_intelligence_received = int(family_temp_int)
                ind.education_temp_intelligence_given += int(family_temp_int)
                ind.education_goods_used_for_child += usable_education_goods

                # 政府教育：消耗政府教育用品，不消耗政府货币。
                if gov_education_enabled and gov_education_remaining > 0:
                    exempt_threshold = int(pop_cfg.get("wealth_tax_exempt_threshold", 600))
                    high_threshold = int(pop_cfg.get("wealth_tax_threshold", 1500))
                    if ind.balance < exempt_threshold:
                        target_goods = survival_cost * 2
                    elif ind.balance < high_threshold:
                        target_goods = survival_cost
                    else:
                        target_goods = max(0, survival_cost // 2)

                    gov_goods = min(gov_education_remaining, self.government_education_goods[p], max(0, int(target_goods)))
                    if gov_goods > 0:
                        self.government_education_goods[p] -= gov_goods
                        gov_education_remaining -= gov_goods
                        temp_per_100 = max(0, int(pop_cfg.get("gov_education_temp_int_per_100", 5)))
                        gov_temp_int = int((gov_goods // 100) * temp_per_100)
                        self.turn_government_education_total[p] += gov_goods
                        child.temp_intelligence += gov_temp_int
                        child.government_education_investment_received = gov_goods
                        child.government_education_temp_intelligence_received = gov_temp_int
                        child.education_temp_intelligence_received += gov_temp_int

                child.education_capital = education_capital_from_child(child)
                self.apply_evolution_to_child(p, child)

                max_transfer = max(0, ind.balance - 100)
                transfer = int(round(max_transfer * int(round(30 + (ind.morality / 100) * 40)) / 100))
                ind.balance -= transfer
                child.balance += transfer
                ind.inheritance_given += transfer
                child.inheritance_received += transfer
                self.turn_inheritance_transfer_total[p] += transfer
                child.parent_class = parent_class_before_reproduce
                child.birth_class = self.class_rank_label(p, child.balance)[1]
                child.current_class = child.birth_class
                child.class_change = 0
                child.is_upward_mobile = 0
                child.is_downward_mobile = 0
                self.turn_birth_count[p] += 1
                self.newborns_this_turn.append((p, child))
                newborns.append(child)
                if secondary:
                    self.turn_secondary_birth_success_count[p] += 1
                return child

            for ind in pop:
                self.turn_reproduction_eligible_count[p] += 1
                if ind.critical:
                    self.turn_birth_blocked_critical[p] += 1
                    continue
                if getattr(ind, "is_sick", 0):
                    self.turn_birth_blocked_sick[p] += 1
                    continue
                effective_reproduce_chance = self.effective_reproduction_chance(p, ind)
                if random.randint(1, 100) > effective_reproduce_chance:
                    self.turn_birth_blocked_low_reproduce_chance[p] += 1
                    if len(pop) == 1:
                        self.last_survivor_reproduce_chance_failed[p] = 1
                        self.last_survivor_had_reproduction_goods[p] = int(ind.reproduction_goods >= goods_cost)
                        self.last_survivor_had_food_for_birth[p] = int(ind.food >= required_parent_food_for_birth)
                    continue
                self.turn_reproduction_attempt_count[p] += 1
                if ind.reproduction_goods < goods_cost:
                    self.turn_birth_blocked_no_reproduction_goods[p] += 1
                    continue
                if ind.food < required_parent_food_for_birth:
                    self.turn_birth_blocked_no_food_safety[p] += 1
                    if hasattr(self, "turn_birth_blocked_food_safety_with_reproduction_goods"):
                        self.turn_birth_blocked_food_safety_with_reproduction_goods[p] += 1
                    continue

                create_child_for_parent(ind, secondary=False)

            # dev33：二次减概率生育判定按“部族/群体的第二轮繁殖机会”执行，
            # 而不是按人口数量强制恢复。只有仍具备完整生育资源的既有个体才进入第二轮，
            # 因此低人口且人均资源充足时会自然增加出生；资源紧张时不会凭空出生。
            if secondary_birth_enabled and secondary_birth_ratio > 0:
                for ind in list(pop):
                    self.turn_secondary_birth_eligible_count[p] += 1
                    if ind.critical or getattr(ind, "is_sick", 0):
                        self.turn_secondary_birth_blocked_sick_or_critical[p] += 1
                        continue
                    if ind.reproduction_goods < goods_cost:
                        self.turn_secondary_birth_blocked_no_reproduction_goods[p] += 1
                        continue
                    if ind.food < required_parent_food_for_birth:
                        self.turn_secondary_birth_blocked_no_food_safety[p] += 1
                        continue
                    self.turn_secondary_birth_condition_ready_count[p] += 1
                    effective_reproduce_chance = self.effective_reproduction_chance(p, ind)
                    reduced_chance = max(0, min(100, int(round(effective_reproduce_chance * secondary_birth_ratio / 100))))
                    self.turn_secondary_birth_attempt_count[p] += 1
                    if random.randint(1, 100) > reduced_chance:
                        self.turn_secondary_birth_blocked_low_reproduce_chance[p] += 1
                        continue
                    create_child_for_parent(ind, secondary=True)

            pop.extend(newborns)

    def prepare_evolution_samples_before_survival(self):
        if not self.is_feature_enabled("enable_evolution"):
            return
        for p, pop in self.populations.items():
            self.evolution_samples[p] = []
            for ind in pop:
                if ind.birth_turn == self.turn:
                    continue
                ind.pre_survival_balance = ind.balance
                ind.pre_survival_market_value = self.inventory_total_value(ind, p)
                ind.turn_income = ind.pre_survival_market_value - getattr(ind, "turn_start_market_value", self.inventory_total_value(ind, p))
                # 系统级第七阶段：进化适应度采样从单一市场价值变化扩展为多因子样本。
                # 注意：自然遗传变异始终存在；这里仅为 enable_evolution 开启时的定向偏置提供更稳健依据。
                survival_cost = max(1, int(self.cfg.get("base", {}).get("survival_cost", 100)))
                food_surplus = max(0, int(getattr(ind, "food", 0)) - survival_cost)
                medical_surplus = max(0, int(getattr(ind, "medical_goods", 0)) - (survival_cost if getattr(ind, "is_sick", 0) else 0))
                self.evolution_samples[p].append({
                    "morality": ind.morality,
                    "strength": ind.strength,
                    "reproduce": ind.reproduce,
                    "labor": ind.labor,
                    "income": ind.turn_income,
                    "market_value_delta": ind.turn_income,
                    "wage_income": int(getattr(ind, "wage_received", 0)),
                    "birth_success": int(getattr(ind, "did_reproduce", 0)),
                    "health_state": 0 if getattr(ind, "critical", False) else (-1 if getattr(ind, "is_sick", 0) else 1),
                    "health_index": int(getattr(ind, "health_index", 100)),
                    "education_capital": int(getattr(ind, "education_capital", 0)),
                    "reproductive_security": float(getattr(ind, "reproductive_security_score", 0)),
                    "survival_stock": food_surplus + medical_surplus,
                })

    def survival_phase(self):
        cost = int(self.cfg["base"].get("survival_cost", 100))
        for p, pop in self.populations.items():
            survivors = []
            for ind in pop:
                # dev29：出生发生在 reproduce_phase，本回合出生的新生儿不应立刻进入同一回合的生存消耗。
                # 否则父代转移给子代的“下一回合基础食物”会在出生当回合被立即扣掉。
                if getattr(ind, "birth_turn", -1) == self.turn:
                    self.turn_newborn_survival_skipped_count[p] += 1
                    survivors.append(ind)
                    continue

                ind.survival_rounds += 1
                ind.life -= 1

                if ind.life <= 0:
                    self.mark_death(p, ind, "life_end")
                    continue

                if ind.critical:
                    # 濒死个体本回合仍只参与救助和生存。若能满足食物与医疗需求，则恢复；否则死亡。
                    food_paid = self.consume_individual_good(p, ind, "food", cost)
                    medical_paid = cost if not ind.is_sick else self.consume_individual_good(p, ind, "medical_goods", cost)
                    if food_paid >= cost and (not ind.is_sick or medical_paid >= cost):
                        was_sick = bool(ind.is_sick)
                        apply_health_after_survival(ind, food_paid=food_paid, medical_paid=medical_paid, survival_cost=cost, was_sick=was_sick, was_critical=True)
                        if was_sick:
                            medical_level = self.state["population_config"][p].get("medical_level", 50)
                            if random.random() * 100 <= medical_recovery_chance(medical_level, getattr(ind, "health_index", 100), medical_paid=medical_paid, survival_cost=cost, was_critical=True):
                                ind.is_sick = 0
                                ind.medical_recovery_this_turn = 1
                                self.turn_medical_recovery_count[p] += 1
                        if getattr(ind, "health_deteriorated_this_turn", 0):
                            self.turn_health_deterioration_count[p] += 1
                        ind.critical = False
                        ind.recovered_from_critical_this_turn = 1
                        ind.survival_cost_paid += food_paid
                        self.turn_recovered_critical_count[p] += 1
                        # dev32：记录低人口濒死恢复情况，用于判断 critical 机制是否过硬。
                        if len(pop) < 5:
                            self.turn_recovered_critical_when_pop_below5[p] += 1
                        self.turn_survival_cost_total[p] += food_paid + (medical_paid if ind.is_sick else 0)
                        survivors.append(ind)
                    else:
                        if food_paid < cost:
                            ind.food_shortage += cost - food_paid
                            self.turn_food_shortage_count[p] += 1
                        if ind.is_sick and medical_paid < cost:
                            ind.medical_goods_needed += cost
                            ind.medical_goods_shortage += cost - medical_paid
                            self.turn_medical_shortage_count[p] += 1
                        apply_health_after_survival(ind, food_paid=food_paid, medical_paid=medical_paid, survival_cost=cost, was_sick=bool(ind.is_sick), was_critical=True)
                        if getattr(ind, "health_deteriorated_this_turn", 0):
                            self.turn_health_deterioration_count[p] += 1
                        self.mark_death(p, ind, "critical_goods_shortage")
                    continue

                food_paid = self.consume_individual_good(p, ind, "food", cost)
                if food_paid < cost:
                    ind.food_shortage += cost - food_paid
                    self.turn_food_shortage_count[p] += 1
                    apply_health_after_survival(ind, food_paid=food_paid, medical_paid=0, survival_cost=cost, was_sick=bool(ind.is_sick), was_critical=False)
                    if getattr(ind, "health_deteriorated_this_turn", 0):
                        self.turn_health_deterioration_count[p] += 1
                    if self.enter_critical_or_die(p, ind, "food_shortage"):
                        survivors.append(ind)
                    continue

                medical_paid = 0
                if ind.is_sick:
                    ind.medical_goods_needed += cost
                    medical_paid = self.consume_individual_good(p, ind, "medical_goods", cost)
                    if medical_paid < cost:
                        ind.medical_goods_shortage += cost - medical_paid
                        self.turn_medical_shortage_count[p] += 1
                        apply_health_after_survival(ind, food_paid=food_paid, medical_paid=medical_paid, survival_cost=cost, was_sick=True, was_critical=False)
                        if getattr(ind, "health_deteriorated_this_turn", 0):
                            self.turn_health_deterioration_count[p] += 1
                        if self.enter_critical_or_die(p, ind, "medical_goods_shortage"):
                            survivors.append(ind)
                        continue
                    else:
                        medical_level = self.state["population_config"][p].get("medical_level", 50)
                        apply_health_after_survival(ind, food_paid=food_paid, medical_paid=medical_paid, survival_cost=cost, was_sick=True, was_critical=False)
                        if random.random() * 100 <= medical_recovery_chance(medical_level, getattr(ind, "health_index", 100), medical_paid=medical_paid, survival_cost=cost, was_critical=False):
                            ind.is_sick = 0
                            ind.medical_recovery_this_turn = 1
                            self.turn_medical_recovery_count[p] += 1

                if not getattr(ind, "is_sick", 0):
                    apply_health_after_survival(ind, food_paid=food_paid, medical_paid=medical_paid, survival_cost=cost, was_sick=False, was_critical=False)
                if getattr(ind, "health_deteriorated_this_turn", 0):
                    self.turn_health_deterioration_count[p] += 1

                ind.survival_cost_paid += food_paid + medical_paid
                self.turn_survival_cost_total[p] += food_paid + medical_paid
                survivors.append(ind)
            self.populations[p] = survivors

    def mark_death(self, p, ind, reason):
        # dev32：低人口死亡原因诊断。这里的 pop_count_before_death 是死亡发生前的人口数，
        # 只用于观察寿命断代/濒死链路，不改变死亡行为。
        pop_count_before_death = len(self.populations.get(p, []))
        if reason == "life_end":
            has_reproduction_goods = int(getattr(ind, "reproduction_goods", 0)) >= self.reproduction_goods_required_per_birth()
            has_food_for_birth = int(getattr(ind, "food", 0)) >= self.parent_food_required_for_birth()
            could_work = (not getattr(ind, "critical", False)) and self.labor_participation_probability(ind, p) > 0
            could_reproduce = (not getattr(ind, "critical", False)) and (not getattr(ind, "is_sick", 0)) and has_reproduction_goods and has_food_for_birth
            if has_reproduction_goods:
                self.death_life_end_with_reproduction_goods[p] += 1
                self.turn_death_life_end_with_reproduction_goods[p] += 1
            if has_food_for_birth:
                self.death_life_end_with_food_for_birth[p] += 1
                self.turn_death_life_end_with_food_for_birth[p] += 1
            if could_work:
                self.turn_life_end_with_can_work[p] += 1
            if could_reproduce:
                self.turn_life_end_with_can_reproduce[p] += 1
            if has_reproduction_goods and has_food_for_birth:
                self.turn_life_end_with_food_and_reproduction_goods[p] += 1
            if pop_count_before_death < 3:
                self.turn_deaths_life_end_when_pop_below3[p] += 1
            if pop_count_before_death < 5:
                self.turn_deaths_life_end_when_pop_below5[p] += 1
        elif reason == "food_shortage" and pop_count_before_death < 5:
            self.turn_deaths_food_shortage_when_pop_below5[p] += 1
        elif reason == "medical_goods_shortage" and pop_count_before_death < 5:
            self.turn_deaths_medical_shortage_when_pop_below5[p] += 1
        elif reason == "critical_goods_shortage" and pop_count_before_death < 5:
            self.turn_deaths_critical_goods_shortage_when_pop_below5[p] += 1

        # dev37：记录最近一次死亡个体的尾部状态，用于判断是否“具备条件但被寿命截断”。
        self.turn_last_death_life_remaining[p] = int(getattr(ind, "life", 0))
        self.turn_last_death_had_food_for_birth[p] = int(int(getattr(ind, "food", 0)) >= self.parent_food_required_for_birth())
        self.turn_last_death_had_reproduction_goods[p] = int(int(getattr(ind, "reproduction_goods", 0)) >= self.reproduction_goods_required_per_birth())
        self.turn_last_death_was_sick[p] = int(getattr(ind, "is_sick", 0))
        self.turn_last_death_was_critical[p] = int(getattr(ind, "critical", False))
        self.turn_last_death_could_work[p] = int((not getattr(ind, "critical", False)) and self.labor_participation_probability(ind, p) > 0)
        self.turn_last_death_could_reproduce[p] = int((not getattr(ind, "critical", False)) and (not getattr(ind, "is_sick", 0)) and self.turn_last_death_had_food_for_birth[p] and self.turn_last_death_had_reproduction_goods[p])

        if pop_count_before_death == 1:
            self.last_survivor_death_reason[p] = reason
            self.last_survivor_had_reproduction_goods[p] = int(
                int(getattr(ind, "reproduction_goods", 0)) >= self.reproduction_goods_required_per_birth()
            )
            self.last_survivor_had_food_for_birth[p] = int(
                int(getattr(ind, "food", 0)) >= self.parent_food_required_for_birth()
            )
        deposit = max(0, ind.balance)
        self.government_deposit[p] += deposit
        ind.deposit_to_government_on_death = deposit
        ind.balance = 0
        # 死亡遗留商品全部进入本部族政府库存，作为后续实物救助来源。
        self.transfer_all_goods_to_government(p, ind)
        ind.end_balance = 0
        ind.died_this_turn = 1
        ind.death_reason = reason
        self.death_survival_rounds[p].append(ind.survival_rounds)
        self.turn_death_count[p] += 1
        self.dead_individuals_this_turn.append((p, ind))
        self.log_event("死亡", f"{getattr(ind, 'code', ind.id)} 死亡，原因：{reason}，货币转入政府{deposit}", entity_type="individual", entity_id=str(getattr(ind, "code", ind.id)), population=p, event_type="death", data={"reason": str(reason), "deposit_to_government": int(deposit), "age_round": int(getattr(ind, "survival_rounds", 0)), "life": int(getattr(ind, "life", 0)), "food": int(getattr(ind, "food", 0)), "medical_goods": int(getattr(ind, "medical_goods", 0)), "reproduction_goods": int(getattr(ind, "reproduction_goods", 0))})

    def update_dev37_low_population_labor_diagnostics(self):
        """dev37：记录低人口时劳动链路断点。

        该函数只读取已有劳动、公司和库存状态，不改变劳动概率、公司招工、工资或人口。
        注意：部分旧评分函数内部含随机微扰。诊断调用必须保存并恢复随机状态，
        避免“观察行为”改变后续模拟路径。
        """
        rng_state = random.getstate()
        try:
            self._update_dev37_low_population_labor_diagnostics_impl()
        finally:
            random.setstate(rng_state)

    def _update_dev37_low_population_labor_diagnostics_impl(self):
        for p, pop in self.populations.items():
            count = len(pop)
            if count <= 0 or count >= 5:
                continue
            self.turn_pop_below5_flag[p] = 1
            if count < 3:
                self.turn_pop_below3_flag[p] = 1
            eligible = [ind for ind in pop if not getattr(ind, "critical", False)]
            sick_count = sum(1 for ind in pop if getattr(ind, "is_sick", 0))
            critical_count = sum(1 for ind in pop if getattr(ind, "critical", False))
            candidate_count = int(self.turn_labor_candidate_count.get(p, 0))
            worker_count = int(self.turn_labor_worker_count.get(p, 0))
            self.turn_labor_eligible_count_when_pop_below5[p] = len(eligible)
            self.turn_labor_willing_count_when_pop_below5[p] = candidate_count
            self.turn_actual_worker_count_when_pop_below5[p] = worker_count
            if count < 3:
                self.turn_labor_eligible_count_when_pop_below3[p] = len(eligible)
                self.turn_labor_willing_count_when_pop_below3[p] = candidate_count
                self.turn_actual_worker_count_when_pop_below3[p] = worker_count
            self.turn_no_worker_reason_sick_count[p] = sick_count
            self.turn_no_worker_reason_critical_count[p] = critical_count
            self.turn_no_worker_reason_low_labor_count[p] = max(0, len(eligible) - candidate_count)

            positive_profit = 0
            stopped_by_stock = 0
            stopped_by_cash = 0
            stopped_by_resource = 0
            company_demand = 0
            for good in GOOD_FIELDS:
                score = self.branch_expected_profit_score(p, good) if hasattr(self, "branch_expected_profit_score") else 0
                if score > 0:
                    positive_profit += 1
                    company_demand += 1
                branch = self.companies.get(p, {}).get(good, {}) if hasattr(self, "companies") else {}
                initial_stock = max(1, int(branch.get("initial_stock", 1)))
                stock = int(branch.get("stock", 0))
                if stock > initial_stock * 3:
                    stopped_by_stock += 1
                if int(branch.get("money", 0)) <= 0:
                    stopped_by_cash += 1
            if self.government_production_resource.get(p, 0) <= 0:
                stopped_by_resource = len(GOOD_FIELDS)
            self.turn_company_demand_for_workers_when_pop_below5[p] = company_demand
            self.turn_branches_with_positive_expected_profit_when_pop_below5[p] = positive_profit
            self.turn_branches_stopped_by_stock_when_pop_below5[p] = stopped_by_stock
            self.turn_branches_stopped_by_cash_when_pop_below5[p] = stopped_by_cash
            self.turn_branches_stopped_by_resource_when_pop_below5[p] = stopped_by_resource
            if count < 3:
                self.turn_company_demand_for_workers_when_pop_below3[p] = company_demand
                self.turn_branches_with_positive_expected_profit_when_pop_below3[p] = positive_profit
            self.turn_government_production_resource_when_pop_below5[p] = int(self.government_production_resource.get(p, 0))
            totals = self.company_totals(p) if hasattr(self, "companies") else {"money": 0, "stock": 0}
            self.turn_company_total_stock_when_pop_below5[p] = int(totals.get("stock", 0))
            self.turn_company_total_money_when_pop_below5[p] = int(totals.get("money", 0))
            if hasattr(self, "turn_labor_positive_profit_but_no_worker_when_pop_below5"):
                if positive_profit > 0 and worker_count <= 0:
                    self.turn_labor_positive_profit_but_no_worker_when_pop_below5[p] = 1

    def update_population_risk_diagnostics(self):
        # dev31/dev36/dev37：只记录低人口状态持续时间、劳动者空窗、公司状态和最后个体快照；不改变行为。
        for p, pop in self.populations.items():
            count = len(pop)
            if count == 1:
                self.single_survivor_turn_count[p] += 1
            if 0 < count < 3:
                self.turns_at_population_below3[p] += 1
            if 0 < count < 5:
                workers = int(self.turn_labor_worker_count.get(p, 0))
                wages = int(self.turn_company_wage_paid.get(p, 0))
                if workers <= 0:
                    self.turns_with_no_workers_when_pop_below5[p] += 1
                    company_cash = int(self.company_totals(p).get("money", 0)) if hasattr(self, "companies") else 0
                    company_stock = int(self.company_totals(p).get("stock", 0)) if hasattr(self, "companies") else 0
                    if company_cash > 0:
                        self.company_has_cash_but_no_workers_count[p] += 1
                    if company_stock > 0:
                        self.company_has_stock_but_no_workers_count[p] += 1
                if wages <= 0:
                    self.turns_with_no_wages_when_pop_below5[p] += 1

            if 0 < count < 5:
                self.pop_below5_turn_count[p] += 1
            if 0 < count < 3:
                self.pop_below3_turn_count[p] += 1

            if 0 < count < 5 and hasattr(self, "turn_parent_food_requirement"):
                required_food = self.parent_food_required_for_birth()
                required_goods = self.reproduction_goods_required_per_birth()
                potential = [i for i in pop if self.is_potential_parent_for_dev38(i)]
                with_goods = [i for i in potential if int(getattr(i, "reproduction_goods", 0)) >= required_goods]
                food_ready = [i for i in with_goods if int(getattr(i, "food", 0)) >= required_food]
                self.turn_parent_food_requirement[p] = required_food
                self.turn_potential_parent_count_when_pop_below5[p] = len(potential)
                self.turn_potential_parent_with_reproduction_goods_when_pop_below5[p] = len(with_goods)
                self.turn_potential_parent_food_ready_when_pop_below5[p] = len(food_ready)
                gap_total = sum(max(0, required_food - int(getattr(i, "food", 0))) for i in with_goods)
                self.turn_parent_food_gap_when_pop_below5[p] = int(gap_total)
                if count < 3:
                    self.turn_parent_food_gap_when_pop_below3[p] = int(gap_total)

            if 0 < count <= 3:
                sample = list(pop)
                self.turn_low_pop_snapshot_count[p] = count
                def avg_attr(attr):
                    return round(sum(float(getattr(ind, attr, 0)) for ind in sample) / max(1, len(sample)), 4)
                self.turn_last_individuals_avg_money[p] = avg_attr("balance")
                self.turn_last_individuals_avg_food[p] = avg_attr("food")
                self.turn_last_individuals_avg_medical_goods[p] = avg_attr("medical_goods")
                self.turn_last_individuals_avg_reproduction_goods[p] = avg_attr("reproduction_goods")
                self.turn_last_individuals_avg_labor[p] = avg_attr("labor")
                self.turn_last_individuals_avg_reproduce[p] = avg_attr("reproduce")
                self.turn_last_individuals_avg_life_remaining[p] = avg_attr("life")
                self.turn_last_individuals_avg_age[p] = avg_attr("age_round")
                self.turn_last_individuals_sick_count[p] = sum(1 for ind in sample if getattr(ind, "is_sick", 0))
                self.turn_last_individuals_critical_count[p] = sum(1 for ind in sample if getattr(ind, "critical", False))
                required_food = self.parent_food_required_for_birth()
                required_goods = self.reproduction_goods_required_per_birth()
                self.turn_last_individuals_has_food_for_birth_count[p] = sum(1 for ind in sample if int(getattr(ind, "food", 0)) >= required_food)
                self.turn_last_individuals_has_reproduction_goods_count[p] = sum(1 for ind in sample if int(getattr(ind, "reproduction_goods", 0)) >= required_goods)
                if hasattr(self, "turn_last_individuals_parent_food_gap_avg"):
                    self.turn_last_individuals_parent_food_gap_avg[p] = round(sum(max(0, required_food - int(getattr(ind, "food", 0))) for ind in sample) / max(1, len(sample)), 4)
                self.turn_last_individuals_can_work_count[p] = sum(1 for ind in sample if (not getattr(ind, "critical", False)) and self.labor_participation_probability(ind, p) > 0)
                self.turn_last_individuals_can_reproduce_count[p] = sum(1 for ind in sample if (not getattr(ind, "critical", False)) and (not getattr(ind, "is_sick", 0)) and int(getattr(ind, "food", 0)) >= required_food and int(getattr(ind, "reproduction_goods", 0)) >= required_goods)

    def evolution_sample_fitness(self, sample):
        """系统级第七阶段：多因子进化适应度。

        该适应度只用于定向进化偏置，不改变自然遗传变异。
        权重全部来自 base 配置，便于后续实验和 GUI 参数化。
        """
        base = self.cfg.get("base", {})
        survival_cost = max(1, int(base.get("survival_cost", 100)))
        market_w = float(base.get("evolution_weight_market_value", 50)) / 100.0
        birth_w = float(base.get("evolution_weight_birth_success", 80)) / 100.0
        labor_w = float(base.get("evolution_weight_labor_income", 30)) / 100.0
        health_w = float(base.get("evolution_weight_health", 30)) / 100.0
        stock_w = float(base.get("evolution_weight_survival_stock", 20)) / 100.0
        market_component = float(sample.get("market_value_delta", sample.get("income", 0)))
        wage_component = float(sample.get("wage_income", 0))
        birth_component = float(sample.get("birth_success", 0)) * survival_cost
        health_component = float(sample.get("health_state", 0)) * survival_cost
        health_index_component = (float(sample.get("health_index", 100)) / 100.0) * survival_cost
        education_component = min(float(sample.get("education_capital", 0)), 100.0) * 0.25
        reproductive_security_component = (float(sample.get("reproductive_security", 0)) / 100.0) * survival_cost * 0.5
        stock_component = min(float(sample.get("survival_stock", 0)), survival_cost * 3)
        return (
            market_component * market_w
            + wage_component * labor_w
            + birth_component * birth_w
            + (health_component + health_index_component) * health_w
            + education_component * labor_w
            + reproductive_security_component * birth_w
            + stock_component * stock_w
        )

    def evolution_compare_signal(self, samples, param):
        if len(samples) < 2:
            return 0.0, 0.0
        vals = sorted(s[param] for s in samples)
        med = vals[len(vals) // 2]
        high = [self.evolution_sample_fitness(s) for s in samples if s[param] >= med]
        low = [self.evolution_sample_fitness(s) for s in samples if s[param] < med]
        if not high or not low:
            return 0.0, 0.0
        ha, la = sum(high) / len(high), sum(low) / len(low)
        gap = ha - la
        scale = max(1.0, (sum(abs(self.evolution_sample_fitness(s)) for s in samples) / len(samples)))
        signal = max(-1.0, min(1.0, gap / scale))
        return signal, gap

    def evolution_phase(self):
        # 系统级第七阶段：加权、平滑的定向进化偏置。
        # 旧算法只比较属性高低组的本回合市场价值变化，方向变化过于频繁。
        # 新算法保留同一思想，但将适应度扩展为市场价值、工资、生育成功、健康状态和生存库存，
        # 并使用指数平滑减少短期噪声。自然遗传变异不受该开关影响。
        if not self.is_feature_enabled("enable_evolution"):
            return
        base = self.cfg.get("base", {})
        use_weighted = bool(int(base.get("enable_weighted_evolution_algorithm", 1)))
        alpha = max(0.0, min(1.0, float(base.get("evolution_direction_smoothing_rate", 35)) / 100.0))
        threshold = max(0.0, float(base.get("evolution_min_direction_signal", 8)) / 100.0)
        window = max(2, int(base.get("evolution_cycle_window", 20)))
        for p, samples in self.evolution_samples.items():
            prev = self.evolution_direction[p].copy()
            new = {"morality": 0, "strength": 0, "reproduce": 0, "labor": 0}
            self.turn_evolution_sample_count[p] = len(samples)
            if len(samples) < 2:
                self.evolution_direction[p] = prev if self.evolution_ready[p] else new
                self.evolution_ready[p] = True
                continue

            fitness_values = [self.evolution_sample_fitness(s) for s in samples]
            self.turn_evolution_fitness_avg[p] = round(sum(fitness_values) / max(1, len(fitness_values)), 4)

            if not use_weighted:
                # 保留旧算法路径，便于回归比较。
                for param in new:
                    vals = sorted(s[param] for s in samples)
                    med = vals[len(vals) // 2]
                    high = [s["income"] for s in samples if s[param] >= med]
                    low = [s["income"] for s in samples if s[param] < med]
                    if not high or not low:
                        new[param] = prev[param]
                    else:
                        ha, la = sum(high) / len(high), sum(low) / len(low)
                        new[param] = 1 if ha > la else (-1 if ha < la else prev[param])
            else:
                gap_fields = {
                    "morality": "turn_evolution_fitness_gap_morality",
                    "strength": "turn_evolution_fitness_gap_strength",
                    "reproduce": "turn_evolution_fitness_gap_reproduce",
                    "labor": "turn_evolution_fitness_gap_labor",
                }
                signal_fields = {
                    "morality": "turn_evolution_signal_morality",
                    "strength": "turn_evolution_signal_strength",
                    "reproduce": "turn_evolution_signal_reproduce",
                    "labor": "turn_evolution_signal_labor",
                }
                for param in new:
                    raw_signal, gap = self.evolution_compare_signal(samples, param)
                    prev_score = self.evolution_direction_score[p].get(param, 0.0)
                    score = (1.0 - alpha) * prev_score + alpha * raw_signal
                    self.evolution_direction_score[p][param] = score
                    setattr(self, gap_fields[param], {**getattr(self, gap_fields[param]), p: round(gap, 4)})
                    setattr(self, signal_fields[param], {**getattr(self, signal_fields[param]), p: round(score, 4)})
                    if score > threshold:
                        new[param] = 1
                    elif score < -threshold:
                        new[param] = -1
                    else:
                        new[param] = 0

            self.evolution_direction[p] = new
            self.evolution_ready[p] = True
            if new != prev:
                self.turn_evolution_direction_change_count[p] += 1
            hist = self.evolution_direction_history.setdefault(p, [])
            hist.append(new.copy())
            if len(hist) > window:
                del hist[:-window]


    def trust_update_phase(self):
        # BOT8 dev5：部族社会信任动态更新。
        # 研究依据：社会信任会降低协调成本、支持公共品合作；掠夺、侵略、不平等和高濒死比例会削弱合作预期。
        # 为避免信任成为过强开关，每回合变化被限制在 -3 到 +3。
        survival_cost = max(1, self.cfg["base"].get("survival_cost", 100))
        for p, pop in self.populations.items():
            count = max(1, len(pop))
            gini = self.calculate_gini([i.balance for i in pop])
            critical_count = sum(1 for i in pop if i.critical)

            gain_aid = min(1.5, self.turn_government_aid_total[p] / (survival_cost * count) * 8)
            gain_rescue = min(1.0, self.turn_individual_rescue_total[p] / (survival_cost * count) * 5)
            gain_education = min(1.0, self.turn_government_education_total[p] / (survival_cost * count) * 3)
            # dev14：成功市场交易代表正常交换秩序运转，给予非常小的信任正向修正。
            gain_market = min(0.5, self.turn_market_trade_count[p] / count * 0.5)

            loss_plunder = min(1.5, self.turn_internal_plunder_count[p] / count * 10)
            loss_invasion = min(1.0, self.turn_invasion_attempt_count[p] / count * 8)
            loss_gini = max(0.0, min(1.5, (gini - 0.35) * 3))
            loss_critical = min(0.75, critical_count / count * 2)

            raw_change = gain_aid + gain_rescue + gain_education + gain_market - loss_plunder - loss_invasion - loss_gini - loss_critical
            change = max(-3.0, min(3.0, raw_change))
            old_trust = self.tribe_trust.get(p, 60)
            self.tribe_trust[p] = max(0.0, min(100.0, old_trust + change))

            self.turn_trust_change[p] = round(self.tribe_trust[p] - old_trust, 4)
            self.turn_trust_gain_from_aid[p] = round(gain_aid, 4)
            self.turn_trust_gain_from_rescue[p] = round(gain_rescue, 4)
            self.turn_trust_gain_from_education[p] = round(gain_education, 4)
            self.turn_trust_loss_from_plunder[p] = round(loss_plunder, 4)
            self.turn_trust_loss_from_invasion[p] = round(loss_invasion, 4)
            self.turn_trust_loss_from_gini[p] = round(loss_gini, 4)
            self.turn_trust_loss_from_critical[p] = round(loss_critical, 4)

    def restore_populations_if_only_one_left(self):
        if not self.is_feature_enabled("enable_restore_populations"):
            return
        alive = [p for p, pop in self.populations.items() if len(pop) > 0]
        if len(alive) != 1:
            return
        source = alive[0]
        for target in self.population_names:
            if target == source:
                continue
            self.populations[target] = [Individual.clone_from(ind) for ind in self.populations[source]]
            self.env_resource[target] = self.env_resource[source]
            self.env_capacity[target] = self.env_capacity[source]
            self.env_health[target] = self.env_health[source]
            self.resource_pressure[target] = self.resource_pressure[source]
            self.env_damage_buffer[target] = self.env_damage_buffer[source]
            self.env_recovery_buffer[target] = self.env_recovery_buffer[source]
            self.government_deposit[target] = self.government_deposit[source]
            self.tribe_trust[target] = self.tribe_trust[source]
            self.evolution_direction[target] = self.evolution_direction[source].copy()
            self.evolution_ready[target] = self.evolution_ready[source]
            self.death_survival_rounds[target] = self.death_survival_rounds[source].copy()
            self.state["population_config"][target] = self.state["population_config"][source].copy()

    def get_avg_dead_lifespan(self, p):
        d = self.death_survival_rounds[p]
        return 0 if not d else int(round(sum(d) / len(d)))

    def get_population_summary_rows(self):
        self.update_total_wealth()
        rows = []
        for p, pop in self.populations.items():
            count = len(pop)
            balances = [i.balance for i in pop]
            total_bal = sum(balances)
            total_food = sum(getattr(i, "food", 0) for i in pop)
            total_medical = sum(getattr(i, "medical_goods", 0) for i in pop)
            total_education = sum(getattr(i, "education_goods", 0) for i in pop)
            total_reproduction = sum(getattr(i, "reproduction_goods", 0) for i in pop)
            total_tools = sum(getattr(i, "tools", 0) for i in pop)
            survival_cost = int(self.cfg["base"].get("survival_cost", 100))
            child_cost = self.reproduction_goods_required_per_birth()
            food_hard_shortage = sum(1 for i in pop if getattr(i, "food", 0) < survival_cost)
            medical_hard_shortage = sum(1 for i in pop if getattr(i, "is_sick", 0) and getattr(i, "medical_goods", 0) < survival_cost)
            education_shortage = sum(1 for i in pop if getattr(i, "education_goods", 0) < child_cost)
            reproduction_shortage = sum(1 for i in pop if getattr(i, "reproduction_goods", 0) < child_cost)
            gini = self.calculate_gini(balances)
            if count:
                avg_bal = int(round(total_bal / count))
                avg_int = int(round(sum(i.intelligence for i in pop) / count))
                avg_str = int(round(sum(i.strength for i in pop) / count))
                avg_mor = int(round(sum(i.morality for i in pop) / count))
                avg_rep = int(round(sum(i.reproduce for i in pop) / count))
                avg_lab = int(round(sum(i.labor for i in pop) / count))
                avg_health = round(sum(float(getattr(i, "health_index", 100)) for i in pop) / count, 4)
                avg_education_capital = round(sum(float(getattr(i, "education_capital", 0)) for i in pop) / count, 4)
                avg_reproductive_security = round(sum(float(getattr(i, "reproductive_security_score", 0)) for i in pop) / count, 4)
                ratio = round((avg_str / self.cfg["base"]["total_ability"]) * 100, 4)
                med_bal = self.median_value(balances)
                min_bal = min(balances)
                max_bal = max(balances)
            else:
                avg_bal = avg_int = avg_str = avg_mor = avg_rep = avg_lab = ratio = 0
                avg_health = avg_education_capital = avg_reproductive_security = 0
                med_bal = min_bal = max_bal = 0
            # dev32：小族群核查诊断。只输出分布与低人口经济状态，不改变机制。
            if count:
                age_values = [int(self.turn - getattr(i, "birth_turn", 0) + int(getattr(i, "initial_age_rounds", 0))) for i in pop]
                life_values = [int(getattr(i, "life", 0)) for i in pop]
                avg_age_round = round(sum(age_values) / count, 4)
                min_age_round = min(age_values)
                max_age_round = max(age_values)
                avg_life_remaining = round(sum(life_values) / count, 4)
                min_life_remaining = min(life_values)
                max_life_remaining = max(life_values)
            else:
                avg_age_round = min_age_round = max_age_round = 0
                avg_life_remaining = min_life_remaining = max_life_remaining = 0
            # dev36：最后 1-3 个体的寿命与可繁殖状态诊断，用于区分寿命断代与物资断代。
            if 0 < count <= 3:
                last3_life_values = [int(getattr(i, "life", 0)) for i in pop]
                last3_avg_life_remaining = round(sum(last3_life_values) / max(1, len(last3_life_values)), 4)
                last3_min_life_remaining = min(last3_life_values)
                last3_reproductive_eligible_count = sum(
                    1 for i in pop
                    if not getattr(i, "critical", False)
                    and not getattr(i, "is_sick", 0)
                    and int(getattr(i, "reproduction_goods", 0)) >= self.reproduction_goods_required_per_birth()
                    and int(getattr(i, "food", 0)) >= self.parent_food_required_for_birth()
                )
            else:
                last3_avg_life_remaining = 0
                last3_min_life_remaining = 0
                last3_reproductive_eligible_count = 0

            low_population_below5 = 0 < count < 5
            workers_when_below5 = self.turn_labor_worker_count[p] if low_population_below5 else 0
            wage_when_below5 = self.turn_company_wage_paid[p] if low_population_below5 else 0
            food_bought_when_below5 = sum(int(getattr(i, "market_food_bought", 0)) for i in pop) if low_population_below5 else 0
            company_food_stock_when_below5 = int(self.companies[p]["food"].get("stock", 0)) if low_population_below5 and hasattr(self, "companies") else 0
            government_food_when_below5 = int(self.government_food[p]) if low_population_below5 else 0

            food_values = [int(getattr(i, "food", 0)) for i in pop]
            money_values = [int(getattr(i, "balance", 0)) for i in pop]
            medical_values = [int(getattr(i, "medical_goods", 0)) for i in pop]
            reproduction_values = [int(getattr(i, "reproduction_goods", 0)) for i in pop]
            wage_values = [int(getattr(i, "wage_received", 0)) for i in pop if int(getattr(i, "wage_received", 0)) > 0]
            age0 = self.cohort_stats(pop, lambda i: self.age_round_of(i) == 0)
            age1to3 = self.cohort_stats(pop, lambda i: 1 <= self.age_round_of(i) <= 3)
            age4to8 = self.cohort_stats(pop, lambda i: 4 <= self.age_round_of(i) <= 8)
            avg_wage = int(round(sum(wage_values) / max(1, len(wage_values)))) if wage_values else 0
            min_wage = min(wage_values) if wage_values else 0
            median_wage = self.median_value(wage_values)
            bottom20_wage = self.bottom_percent_average(wage_values, 20)
            survival_cost_for_diag = max(1, int(self.cfg["base"].get("survival_cost", 100)))
            food_cost_for_diag = max(1, self.goods_cost(p, "food", survival_cost_for_diag))
            reproduction_cost_for_diag = max(1, self.goods_cost(p, "reproduction_goods", self.reproduction_goods_required_per_birth()))

            class_summary = self.get_class_summary(p, pop)
            company_totals_for_score = self.company_totals(p) if hasattr(self, "companies") else {"money": 0, "stock": 0}
            policy_hard_unmet = (
                self.turn_food_hard_unsatisfied_amount[p]
                + self.turn_medical_hard_unsatisfied_amount[p]
                + self.turn_reproduction_hard_unsatisfied_amount[p]
            ) if hasattr(self, "turn_food_hard_unsatisfied_amount") else 0
            policy_aid_unmet = (
                self.turn_food_aid_unmet_count[p]
                + self.turn_medical_aid_unmet_count[p]
                + self.turn_critical_medical_aid_unmet_count[p]
            )
            self.turn_company_resilience_score[p] = company_resilience_score(
                branch_money_total=company_totals_for_score.get("money", 0),
                branch_stock_total=company_totals_for_score.get("stock", 0),
                survival_cost=survival_cost,
                population_count=max(1, count),
            )
            self.turn_government_policy_pressure_score[p] = government_policy_pressure_score(
                hard_unmet_total=policy_hard_unmet,
                aid_unmet_count=policy_aid_unmet,
                fiscal_deposit=self.government_deposit.get(p, 0),
                survival_cost=survival_cost,
                population_count=max(1, count),
            )
            rows.append({
                "Turn": self.turn,
                "Population": p,
                "PopCount": count,
                "SharedEnvEnabled": int(self.is_feature_enabled("enable_shared_environment_resource")),
                "DisasterOccurred": self.turn_disaster_occurred[p],
                "DisasterType": self.turn_disaster_type[p],
                "DisasterStrength": self.turn_disaster_strength[p],
                "EnvResource": self.env_resource[p],
                "EnvCapacity": self.env_capacity[p],
                "EnvHealth": self.env_health[p],
                "ResourcePressure": self.resource_pressure[p],
                "ResourceRegenActual": self.turn_resource_regen_total[p],
                "EnvConsumption": self.turn_env_consumption_total[p],
                "EnvHealthChange": self.turn_env_health_change[p],
                "EnvResourceUseRate": round(self.env_resource[p] / max(1, self.env_capacity[p]), 4),
                "ResourceUseToRegenRatio": round(self.turn_population_resource_used[p] / max(1, self.turn_resource_regen_total[p]), 4),
                "LaborResourceUnused": max(0, int(self.turn_population_resource_quota[p]) - int(self.turn_population_resource_used[p])),
                "LaborResourceUnusedRate": round(max(0, int(self.turn_population_resource_quota[p]) - int(self.turn_population_resource_used[p])) / max(1, int(self.turn_population_resource_quota[p])), 4),
                "ResourceLimitReached": int(self.resource_pressure[p] >= 0.95 or (self.turn_population_resource_used[p] / max(1, self.turn_resource_regen_total[p])) >= 0.95),
                "FoodOperatingStockTarget": self.company_operating_stock_target(p, "food"),
                "MedicalOperatingStockTarget": self.company_operating_stock_target(p, "medical_goods"),
                "EducationOperatingStockTarget": self.company_operating_stock_target(p, "education_goods"),
                "ReproductionOperatingStockTarget": self.company_operating_stock_target(p, "reproduction_goods"),
                "GovernmentDeposit": self.government_deposit[p],
                "TotalFood": total_food,
                "TotalMedicalGoods": total_medical,
                "TotalEducationGoods": total_education,
                "TotalReproductionGoods": total_reproduction,
                "TotalTools": total_tools,
                "GovernmentFood": self.government_food[p],
                "GovernmentMedicalGoods": self.government_medical_goods[p],
                "GovernmentEducationGoods": self.government_education_goods[p],
                "GovernmentReproductionGoods": self.government_reproduction_goods[p],
                "GovernmentTools": self.government_tools[p],
                "UsePopulationScaledInitials": int(self.use_population_scaled_initials(p)),
                "CompanyInitialMoneyEffective": sum(int(b.get("initial_money", 0)) for b in self.companies.get(p, {}).values()),
                "GovernmentInitialMoneyEffective": max(0, int(self.state["population_config"].get(p, {}).get("government_initial_money_per_capita", 0))) * self.initial_population_reference(p) if self.use_population_scaled_initials(p) else 0,
                "CompanyInitialEducationStockTarget": int(self.companies.get(p, {}).get("education_goods", {}).get("initial_stock", 0)),
                "CompanyInitialReproductionStockTarget": int(self.companies.get(p, {}).get("reproduction_goods", {}).get("initial_stock", 0)),
                "CompanyMoneyTotal": self.company_totals(p)["money"],
                "CompanyGoodsStockTotal": self.company_totals(p)["stock"],
                "CompanyWagesPaid": self.company_totals(p)["wages"],
                "CompanyGoodsProduced": self.company_totals(p)["produced"],
                "CompanySalesIncome": self.company_totals(p)["sales"],
                "CompanyInventoryListed": sum(self.turn_company_inventory_listed[p].values()),
                "CompanyInventorySoldToIndividuals": sum(self.turn_company_inventory_sold_to_individuals[p].values()),
                "CompanyInventorySoldToGovernment": sum(self.turn_company_inventory_sold_to_government[p].values()),
                "CompanyInventoryUnsold": sum(self.turn_company_inventory_unsold[p].values()),
                "CompanyInventoryListingRatio": int(round(sum(self.turn_company_inventory_listing_ratio[p].values()) / max(1, sum(1 for v in self.turn_company_inventory_listing_ratio[p].values() if v > 0)))),
                "CompanyOrderbookAskCount": sum(self.turn_company_orderbook_ask_count[p].values()),
                "CompanyHardNeedReleaseEnabledCount": self.turn_company_hard_need_release_enabled_count[p],
                "FoodCompanyHardNeedPressure": self.turn_company_hard_need_release_pressure[p].get("food", 0),
                "MedicalCompanyHardNeedPressure": self.turn_company_hard_need_release_pressure[p].get("medical_goods", 0),
                "ReproductionCompanyHardNeedPressure": self.turn_company_hard_need_release_pressure[p].get("reproduction_goods", 0),
                "FoodCompanySellableStock": self.turn_company_sellable_stock[p].get("food", 0),
                "MedicalCompanySellableStock": self.turn_company_sellable_stock[p].get("medical_goods", 0),
                "EducationCompanySellableStock": self.turn_company_sellable_stock[p].get("education_goods", 0),
                "ReproductionCompanySellableStock": self.turn_company_sellable_stock[p].get("reproduction_goods", 0),
                "EducationInventoryResilienceGap": self.turn_repro_education_resilience_gap[p].get("education_goods", 0),
                "EducationInventoryResilienceWeightAdded": self.turn_repro_education_resilience_weight_added[p].get("education_goods", 0),
                "ReproductionInventoryResilienceGap": self.turn_repro_education_resilience_gap[p].get("reproduction_goods", 0),
                "ReproductionInventoryResilienceWeightAdded": self.turn_repro_education_resilience_weight_added[p].get("reproduction_goods", 0),
                "HardNeedProductionResponseEnabled": int(self.state["population_config"].get(p, {}).get("enable_hard_need_production_response", 1)),
                "FoodHardNeedProductionBonus": self.turn_hard_need_production_bonus[p].get("food", 0),
                "MedicalHardNeedProductionBonus": self.turn_hard_need_production_bonus[p].get("medical_goods", 0),
                "ReproductionHardNeedProductionBonus": self.turn_hard_need_production_bonus[p].get("reproduction_goods", 0),
                "EducationNeedProductionBonus": self.turn_hard_need_production_bonus[p].get("education_goods", 0),
                "FoodHardNeedUnmetForProduction": self.turn_hard_need_unmet_for_production[p].get("food", 0),
                "MedicalHardNeedUnmetForProduction": self.turn_hard_need_unmet_for_production[p].get("medical_goods", 0),
                "ReproductionHardNeedUnmetForProduction": self.turn_hard_need_unmet_for_production[p].get("reproduction_goods", 0),
                "EducationNeedUnmetForProduction": self.turn_hard_need_unmet_for_production[p].get("education_goods", 0),
                "FoodCompanyHardNeedReleaseListed": self.turn_company_hard_need_release_listed[p].get("food", 0),
                "MedicalCompanyHardNeedReleaseListed": self.turn_company_hard_need_release_listed[p].get("medical_goods", 0),
                "ReproductionCompanyHardNeedReleaseListed": self.turn_company_hard_need_release_listed[p].get("reproduction_goods", 0),
                "FoodCompanyInventoryListed": self.turn_company_inventory_listed[p].get("food", 0),
                "FoodCompanySoldToIndividuals": self.turn_company_inventory_sold_to_individuals[p].get("food", 0),
                "FoodCompanySoldToGovernment": self.turn_company_inventory_sold_to_government[p].get("food", 0),
                "FoodCompanyInventoryUnsold": self.turn_company_inventory_unsold[p].get("food", 0),
                "MedicalCompanyInventoryListed": self.turn_company_inventory_listed[p].get("medical_goods", 0),
                "MedicalCompanySoldToIndividuals": self.turn_company_inventory_sold_to_individuals[p].get("medical_goods", 0),
                "MedicalCompanySoldToGovernment": self.turn_company_inventory_sold_to_government[p].get("medical_goods", 0),
                "MedicalCompanyInventoryUnsold": self.turn_company_inventory_unsold[p].get("medical_goods", 0),
                "EducationCompanyInventoryListed": self.turn_company_inventory_listed[p].get("education_goods", 0),
                "EducationCompanySoldToIndividuals": self.turn_company_inventory_sold_to_individuals[p].get("education_goods", 0),
                "EducationCompanySoldToGovernment": self.turn_company_inventory_sold_to_government[p].get("education_goods", 0),
                "EducationCompanyInventoryUnsold": self.turn_company_inventory_unsold[p].get("education_goods", 0),
                "ReproductionCompanyInventoryListed": self.turn_company_inventory_listed[p].get("reproduction_goods", 0),
                "ReproductionCompanySoldToIndividuals": self.turn_company_inventory_sold_to_individuals[p].get("reproduction_goods", 0),
                "ReproductionCompanySoldToGovernment": self.turn_company_inventory_sold_to_government[p].get("reproduction_goods", 0),
                "ReproductionCompanyInventoryUnsold": self.turn_company_inventory_unsold[p].get("reproduction_goods", 0),
                "NewbornSurvivalSkippedCount": self.turn_newborn_survival_skipped_count[p],
                "ReproductionGoodsDemandCount": self.turn_reproduction_goods_demand_count[p],
                "ReproductionGoodsDemandBlockedByPoorOldLogic": self.turn_reproduction_goods_demand_blocked_by_poor_old_logic[p],
                "ReproductionGoodsDemandBlockedByFood": self.turn_reproduction_goods_demand_blocked_by_food[p],
                "ReproductionGoodsDemandBlockedBySickOrCritical": self.turn_reproduction_goods_demand_blocked_by_sick_or_critical[p],
                "ReproductionGoodsSpendingBlockedByPoorOldLogic": self.turn_reproduction_goods_spending_blocked_by_poor_old_logic[p],
                "GovernmentPurchaseToCompany": self.turn_government_purchase_to_company[p],
                "CompanyResourcePurchased": self.turn_company_resource_purchased[p],
                "CompanyResourceCost": self.turn_company_resource_cost[p],
                "CompanyExpectedProfit": self.turn_company_expected_profit[p],
                "CompanyActualRevenue": self.turn_company_actual_revenue[p],
                "CompanyWagePaid": self.turn_company_wage_paid[p],
                "CompanyDividendPaid": self.turn_company_dividend_paid[p],
                "RichTaxIncome": self.turn_rich_tax_income[p],
                "GovernmentProductionResource": self.env_resource[p],
                "GovernmentOrderbookPurchaseFood": self.turn_government_orderbook_purchase[p].get("food", 0),
                "GovernmentOrderbookPurchaseMedicalGoods": self.turn_government_orderbook_purchase[p].get("medical_goods", 0),
                "GovernmentOrderbookPurchaseEducationGoods": self.turn_government_orderbook_purchase[p].get("education_goods", 0),
                "GovernmentOrderbookPurchaseReproductionGoods": self.turn_government_orderbook_purchase[p].get("reproduction_goods", 0),
                "GovernmentOrderbookPurchaseSpending": self.turn_government_orderbook_purchase_spending[p],
                "GovernmentReproductionGoodsReleased": self.turn_government_reproduction_goods_released[p],
                "GovernmentReproductionGoodsReleaseTargets": self.turn_government_reproduction_goods_release_targets[p],
                "GovernmentSurplusFoodDeleted": self.turn_government_surplus_deleted[p].get("food", 0),
                "GovernmentSurplusMedicalGoodsDeleted": self.turn_government_surplus_deleted[p].get("medical_goods", 0),
                "GovernmentSurplusEducationGoodsDeleted": self.turn_government_surplus_deleted[p].get("education_goods", 0),
                "GovernmentSurplusReproductionGoodsDeleted": self.turn_government_surplus_deleted[p].get("reproduction_goods", 0),
                "GovernmentSurplusToolsDeleted": self.turn_government_surplus_deleted[p].get("tools", 0),
                "GovernmentSurplusValueTotal": self.turn_government_surplus_value[p],
                "FoodBranchMoney": self.companies[p]["food"]["money"],
                "FoodBranchStock": self.companies[p]["food"]["stock"],
                "MedicalBranchMoney": self.companies[p]["medical_goods"]["money"],
                "MedicalBranchStock": self.companies[p]["medical_goods"]["stock"],
                "EducationBranchMoney": self.companies[p]["education_goods"]["money"],
                "EducationBranchStock": self.companies[p]["education_goods"]["stock"],
                "ReproductionBranchMoney": self.companies[p]["reproduction_goods"]["money"],
                "ReproductionBranchStock": self.companies[p]["reproduction_goods"]["stock"],
                "CompanyReproductionGoodsStock": self.companies[p]["reproduction_goods"]["stock"],
                "CompanyReproductionGoodsSellable": self.company_sellable_amount(p, "reproduction_goods"),
                "ReproductionGoodsHardBuyerCount": self.turn_reproduction_goods_hard_buyer_count[p],
                "ReproductionGoodsHardDemandTotal": self.turn_reproduction_goods_hard_demand_total[p],
                "ReproductionGoodsHardDemandSatisfied": self.turn_reproduction_goods_hard_demand_satisfied[p],
                "ReproductionGoodsHardDemandUnsatisfied": self.turn_reproduction_goods_hard_demand_unsatisfied[p],
                "ReproductionGoodsBlockedNoCompanyStock": self.turn_reproduction_goods_blocked_no_company_stock[p],
                "ReproductionGoodsBlockedNoMoney": self.turn_reproduction_goods_blocked_no_money[p],
                "ReproductionGoodsCompanySalesVolume": self.turn_reproduction_goods_company_sales_volume[p],
                "ReproductionGoodsIndividualSalesVolume": self.turn_reproduction_goods_individual_sales_volume[p],
                "IndividualFoodTotal": total_food,
                "IndividualMedicalGoodsTotal": total_medical,
                "IndividualEducationGoodsTotal": total_education,
                "IndividualReproductionGoodsTotal": total_reproduction,
                "IndividualToolsTotal": total_tools,
                "FoodHardShortageCount": food_hard_shortage,
                "MedicalHardShortageCount": medical_hard_shortage,
                "EducationGoodsShortageCount": education_shortage,
                "ReproductionGoodsShortageCount": reproduction_shortage,
                "FoodHardDemandTotal": self.turn_hard_demand[p].get("food", 0),
                "MedicalHardDemandTotal": self.turn_hard_demand[p].get("medical_goods", 0),
                "ReproductionHardDemandTotal": self.turn_hard_demand[p].get("reproduction_goods", 0),
                "FoodReserveDemandTotal": self.turn_reserve_demand[p].get("food", 0),
                "MedicalReserveDemandTotal": self.turn_reserve_demand[p].get("medical_goods", 0),
                "FoodProducedTotal": self.turn_goods_production[p]["food"],
                "MedicalGoodsProducedTotal": self.turn_goods_production[p]["medical_goods"],
                "EducationGoodsProducedTotal": self.turn_goods_production[p]["education_goods"],
                "ReproductionGoodsProducedTotal": self.turn_goods_production[p]["reproduction_goods"],
                "ToolsProducedTotal": self.turn_goods_production[p]["tools"],
                "FoodConsumedTotal": self.current_goods_consumption[p]["food"],
                "MedicalGoodsConsumedTotal": self.current_goods_consumption[p]["medical_goods"],
                "EducationGoodsConsumedTotal": self.current_goods_consumption[p]["education_goods"],
                "ReproductionGoodsConsumedTotal": self.current_goods_consumption[p]["reproduction_goods"],
                "ToolsConsumedTotal": self.current_goods_consumption[p]["tools"],
                "MarketTradeCount": self.turn_market_trade_count[p],
                "MarketTradeVolume": self.turn_market_trade_volume[p],
                "LocalTradeVolume": sum(self.turn_market_local_volume[p].values()),
                "ImportVolume": sum(self.turn_market_import_volume[p].values()),
                "ExportVolume": sum(self.turn_market_export_volume[p].values()),
                "TradeTaxIncome": sum(self.turn_trade_tax_income[p].values()),
                "ImportTaxIncome": sum(self.turn_import_tax_income[p].values()),
                "ImportSpending": self.turn_import_spending[p],
                "ExportIncome": self.turn_export_income[p],
                "MarketFoodVolume": self.turn_market_food_volume[p],
                "MarketMedicalGoodsVolume": self.turn_market_medical_goods_volume[p],
                "MarketEducationGoodsVolume": self.turn_market_education_goods_volume[p],
                "MarketReproductionGoodsVolume": self.turn_market_reproduction_goods_volume[p],
                "FoodPriceIndex": self.market_price_index[p]["food"],
                "FoodDemand": self.turn_market_demand[p]["food"],
                "FoodSupply": self.turn_market_supply[p]["food"],
                "FoodUnmetDemand": self.turn_market_unmet_demand[p]["food"],
                "FoodUnsoldSupply": self.turn_market_unsold_supply[p]["food"],
                "FoodLocalTradeVolume": self.turn_market_local_volume[p]["food"],
                "FoodImportVolume": self.turn_market_import_volume[p]["food"],
                "FoodExportVolume": self.turn_market_export_volume[p]["food"],
                "FoodTradeTaxIncome": self.turn_trade_tax_income[p]["food"],
                "FoodImportTaxIncome": self.turn_import_tax_income[p]["food"],
                "MedicalGoodsPriceIndex": self.market_price_index[p]["medical_goods"],
                "MedicalGoodsDemand": self.turn_market_demand[p]["medical_goods"],
                "MedicalGoodsSupply": self.turn_market_supply[p]["medical_goods"],
                "MedicalGoodsUnmetDemand": self.turn_market_unmet_demand[p]["medical_goods"],
                "MedicalGoodsUnsoldSupply": self.turn_market_unsold_supply[p]["medical_goods"],
                "MedicalGoodsLocalTradeVolume": self.turn_market_local_volume[p]["medical_goods"],
                "MedicalGoodsImportVolume": self.turn_market_import_volume[p]["medical_goods"],
                "MedicalGoodsExportVolume": self.turn_market_export_volume[p]["medical_goods"],
                "MedicalGoodsTradeTaxIncome": self.turn_trade_tax_income[p]["medical_goods"],
                "MedicalGoodsImportTaxIncome": self.turn_import_tax_income[p]["medical_goods"],
                "EducationGoodsPriceIndex": self.market_price_index[p]["education_goods"],
                "EducationGoodsDemand": self.turn_market_demand[p]["education_goods"],
                "EducationGoodsSupply": self.turn_market_supply[p]["education_goods"],
                "EducationGoodsUnmetDemand": self.turn_market_unmet_demand[p]["education_goods"],
                "EducationGoodsUnsoldSupply": self.turn_market_unsold_supply[p]["education_goods"],
                "EducationGoodsLocalTradeVolume": self.turn_market_local_volume[p]["education_goods"],
                "EducationGoodsImportVolume": self.turn_market_import_volume[p]["education_goods"],
                "EducationGoodsExportVolume": self.turn_market_export_volume[p]["education_goods"],
                "EducationGoodsTradeTaxIncome": self.turn_trade_tax_income[p]["education_goods"],
                "EducationGoodsImportTaxIncome": self.turn_import_tax_income[p]["education_goods"],
                "ReproductionGoodsPriceIndex": self.market_price_index[p]["reproduction_goods"],
                "ReproductionGoodsDemand": self.turn_market_demand[p]["reproduction_goods"],
                "ReproductionGoodsSupply": self.turn_market_supply[p]["reproduction_goods"],
                "ReproductionGoodsUnmetDemand": self.turn_market_unmet_demand[p]["reproduction_goods"],
                "ReproductionGoodsUnsoldSupply": self.turn_market_unsold_supply[p]["reproduction_goods"],
                "ReproductionGoodsLocalTradeVolume": self.turn_market_local_volume[p]["reproduction_goods"],
                "ReproductionGoodsImportVolume": self.turn_market_import_volume[p]["reproduction_goods"],
                "ReproductionGoodsExportVolume": self.turn_market_export_volume[p]["reproduction_goods"],
                "ReproductionGoodsTradeTaxIncome": self.turn_trade_tax_income[p]["reproduction_goods"],
                "ReproductionGoodsImportTaxIncome": self.turn_import_tax_income[p]["reproduction_goods"],
                "GovernmentPurchaseFood": self.turn_government_purchase_food[p],
                "GovernmentPurchaseMedicalGoods": self.turn_government_purchase_medical_goods[p],
                "GovernmentPurchaseSpending": self.turn_government_purchase_spending[p],
                "GovernmentStockpileFood": self.turn_government_stockpile_food[p],
                "GovernmentStockpileMedicalGoods": self.turn_government_stockpile_medical_goods[p],
                "GovernmentStockpileSpending": self.turn_government_stockpile_spending[p],
                "GovernmentReleaseFood": self.turn_government_release_food[p],
                "GovernmentReleaseMedicalGoods": self.turn_government_release_medical_goods[p],
                "GovernmentReleaseIncome": self.turn_government_release_income[p],
                "GovernmentSubsidyValue": self.turn_government_subsidy_value[p],
                "MarketStabilityIndex": self.turn_market_stability_index[p],
                "FoodShortageCount": self.turn_food_shortage_count[p],
                "MedicalShortageCount": self.turn_medical_shortage_count[p],
                "SickCount": self.turn_sick_count[p],
                "NewSickCount": self.turn_new_sick_count[p],
                "Security": self.state["population_config"][p]["security"],
                "MedicalLevel": self.state["population_config"][p].get("medical_level", 50),
                "Trust": round(self.tribe_trust.get(p, 0), 4),
                "TrustChange": self.turn_trust_change[p],
                "CriticalCount": sum(1 for i in pop if i.critical),
                "PoorCount": class_summary["PoorCount"],
                "LowerCount": class_summary["LowerCount"],
                "MiddleCount": class_summary["MiddleCount"],
                "RichCount": class_summary["RichCount"],
                "UpwardMobilityCount": class_summary["UpwardMobilityCount"],
                "DownwardMobilityCount": class_summary["DownwardMobilityCount"],
                "SameClassCount": class_summary["SameClassCount"],
                "UpwardMobilityRate": class_summary["UpwardMobilityRate"],
                "DownwardMobilityRate": class_summary["DownwardMobilityRate"],
                "TotalBalance": total_bal,
                "AvgBalance": avg_bal,
                "MedianBalance": med_bal,
                "MinBalance": min_bal,
                "MaxBalance": max_bal,
                "AvgIntelligence": avg_int,
                "AvgStrength": avg_str,
                "AvgMorality": avg_mor,
                "AvgReproduce": avg_rep,
                "AvgLabor": avg_lab,
                "AvgHealthIndex": avg_health,
                "AvgEducationCapital": avg_education_capital,
                "AvgReproductiveSecurity": avg_reproductive_security,
                "MedicalRecoveryCount": self.turn_medical_recovery_count[p],
                "HealthDeteriorationCount": self.turn_health_deterioration_count[p],
                "AvgReproductiveSecurityBonus": round(self.turn_reproductive_security_bonus_sum[p] / max(1, self.turn_reproductive_security_count[p]), 4),
                "CompanyResilienceScore": self.turn_company_resilience_score[p],
                "GovernmentPolicyPressureScore": self.turn_government_policy_pressure_score[p],
                "AvgDeadLifeSpan": self.get_avg_dead_lifespan(p),
                "Gini": gini,
                "LaborCandidateCount": self.turn_labor_candidate_count[p],
                "LaborWorkerCount": self.turn_labor_worker_count[p],
                "WorkersPaidCount": self.turn_workers_paid_count[p],
                "WorkersPaidEnoughForFoodCount": self.turn_workers_paid_enough_for_food_count[p],
                "WorkersPaidEnoughForReproductionCount": self.turn_workers_paid_enough_for_reproduction_count[p],
                "LaborRequestTotal": self.turn_labor_request_total[p],
                "LaborAllocatedTotal": self.turn_labor_allocated_total[p],
                "LaborUnmetDemand": self.turn_labor_unmet_demand[p],
                "AvgAllocatedResource": int(round(self.turn_labor_allocated_total[p] / max(1, self.turn_labor_worker_count[p]))),
                "PopulationResourceClaim": self.turn_population_resource_claim[p],
                "PopulationResourceQuota": self.turn_population_resource_quota[p],
                "PopulationResourceUsed": self.turn_population_resource_used[p],
                "PopulationResourceShortage": self.turn_population_resource_shortage[p],
                "ProductionBudgetTotal": self.turn_labor_gross_total[p],
                "GoodsProducedTotal": self.turn_production_total[p],
                "InternalPlunderCount": self.turn_internal_plunder_count[p],
                "InternalPlunderVictimLoss": self.turn_internal_plunder_victim_loss_total[p],
                "InternalPlunderGain": self.turn_internal_plunder_gain_total[p],
                "InternalPlunderSystemLoss": self.turn_internal_plunder_system_loss_total[p],
                "InternalPlunderTotalValueLoss": self.turn_internal_plunder_total_value_loss[p],
                "InternalPlunderTotalValueGain": self.turn_internal_plunder_total_value_gain[p],
                "SanctionCount": self.turn_sanction_count[p],
                "InvasionAttemptCount": self.turn_invasion_attempt_count[p],
                "InvasionSuccessCount": self.turn_invasion_success_count[p],
                "InvasionVictimLoss": self.turn_invasion_victim_loss_total[p],
                "InvasionGainTotal": self.turn_invasion_gain_total[p],
                "InvasionSystemLoss": self.turn_invasion_system_loss_total[p],
                "InvasionTotalValueLoss": self.turn_invasion_total_value_loss[p],
                "InvasionTotalValueGain": self.turn_invasion_total_value_gain[p],
                "GovernmentAidTotal": self.turn_government_aid_total[p],
                "GovernmentEducationTotal": self.turn_government_education_total[p],
                "GovAidBudgetUsed": self.turn_gov_aid_budget_used[p],
                "GovAidBudgetRemaining": self.turn_gov_aid_budget_remaining[p],
                "GoodsTaxTotal": self.turn_labor_tax_total[p],
                "WealthTaxTotal": self.turn_wealth_tax_total[p],
                "IndividualRescueTotal": self.turn_individual_rescue_total[p],
                "MoralDonationTotal": self.turn_moral_donation_total[p],
                "MoralDonationCount": self.turn_moral_donation_count[p],
                "SurvivalCostTotal": self.turn_survival_cost_total[p],
                "ReproductionGoodsConsumed": self.turn_reproduce_cost_total[p],
                "ChildInitialWealthTotal": self.turn_child_initial_wealth_total[p],
                "InheritanceTransferTotal": self.turn_inheritance_transfer_total[p],
                "BirthCount": self.turn_birth_count[p],
                "ReproductionEligibleCount": self.turn_reproduction_eligible_count[p],
                "ReproductionAttemptCount": self.turn_reproduction_attempt_count[p],
                "SecondaryBirthEligibleCount": self.turn_secondary_birth_eligible_count[p],
                "SecondaryBirthConditionReadyCount": self.turn_secondary_birth_condition_ready_count[p],
                "SecondaryBirthAttemptCount": self.turn_secondary_birth_attempt_count[p],
                "SecondaryBirthSuccessCount": self.turn_secondary_birth_success_count[p],
                "SecondaryBirthBlockedSickOrCritical": self.turn_secondary_birth_blocked_sick_or_critical[p],
                "SecondaryBirthBlockedNoReproductionGoods": self.turn_secondary_birth_blocked_no_reproduction_goods[p],
                "SecondaryBirthBlockedNoFoodSafety": self.turn_secondary_birth_blocked_no_food_safety[p],
                "SecondaryBirthBlockedLowReproduceChance": self.turn_secondary_birth_blocked_low_reproduce_chance[p],
                "BirthBlockedCritical": self.turn_birth_blocked_critical[p],
                "BirthBlockedSick": self.turn_birth_blocked_sick[p],
                "BirthBlockedNoMoney": self.turn_birth_blocked_no_money[p],
                "BirthBlockedNoReproductionGoods": self.turn_birth_blocked_no_reproduction_goods[p],
                "BirthBlockedNoFoodSafety": self.turn_birth_blocked_no_food_safety[p],
                "BirthBlockedLowReproduceChance": self.turn_birth_blocked_low_reproduce_chance[p],
                "BirthBlockedOther": self.turn_birth_blocked_other[p],
                "CumulativeBirthCount": self.cumulative_birth_count[p],
                "CumulativeDeathCount": self.cumulative_death_count[p],
                "BirthDeathRatio": round(self.cumulative_birth_count[p] / max(1, self.cumulative_death_count[p]), 4),
                "CumulativeBirthBlockedCritical": self.cumulative_birth_blocked_critical[p],
                "CumulativeBirthBlockedSick": self.cumulative_birth_blocked_sick[p],
                "CumulativeBirthBlockedNoMoney": self.cumulative_birth_blocked_no_money[p],
                "CumulativeBirthBlockedNoReproductionGoods": self.cumulative_birth_blocked_no_reproduction_goods[p],
                "CumulativeBirthBlockedNoFoodSafety": self.cumulative_birth_blocked_no_food_safety[p],
                "CumulativeBirthBlockedLowReproduceChance": self.cumulative_birth_blocked_low_reproduce_chance[p],
                "CumulativeBirthBlockedOther": self.cumulative_birth_blocked_other[p],
                "BirthFoodTransferredToChild": self.turn_birth_food_transfer_total[p],
                "DeathCount": self.turn_death_count[p],
                "EnteredCriticalCount": self.turn_entered_critical_count[p],
                "RecoveredFromCriticalCount": self.turn_recovered_critical_count[p],
                "SingleSurvivorTurnCount": self.single_survivor_turn_count[p],
                "TurnsAtPopulationBelow3": self.turns_at_population_below3[p],
                "LastSurvivorDeathReason": self.last_survivor_death_reason[p],
                "LastSurvivorReproduceChanceFailed": self.last_survivor_reproduce_chance_failed[p],
                "LastSurvivorHadReproductionGoods": self.last_survivor_had_reproduction_goods[p],
                "LastSurvivorHadFoodForBirth": self.last_survivor_had_food_for_birth[p],
                "AvgAgeRound": avg_age_round,
                "MinAgeRound": min_age_round,
                "MaxAgeRound": max_age_round,
                "AvgLifeRemaining": avg_life_remaining,
                "MinLifeRemaining": min_life_remaining,
                "MaxLifeRemaining": max_life_remaining,
                "DeathsByLifeEndWhenPopulationBelow3": self.turn_deaths_life_end_when_pop_below3[p],
                "DeathsByLifeEndWhenPopulationBelow5": self.turn_deaths_life_end_when_pop_below5[p],
                "DeathsByFoodShortageWhenPopulationBelow5": self.turn_deaths_food_shortage_when_pop_below5[p],
                "DeathsByMedicalShortageWhenPopulationBelow5": self.turn_deaths_medical_shortage_when_pop_below5[p],
                "DeathsByCriticalGoodsShortageWhenPopulationBelow5": self.turn_deaths_critical_goods_shortage_when_pop_below5[p],
                "EnteredCriticalWhenPopulationBelow5": self.turn_entered_critical_when_pop_below5[p],
                "RecoveredCriticalWhenPopulationBelow5": self.turn_recovered_critical_when_pop_below5[p],
                "WorkersWhenPopulationBelow5": workers_when_below5,
                "WagePaidWhenPopulationBelow5": wage_when_below5,
                "FoodBoughtWhenPopulationBelow5": food_bought_when_below5,
                "CompanyFoodStockWhenPopulationBelow5": company_food_stock_when_below5,
                "GovernmentFoodWhenPopulationBelow5": government_food_when_below5,
                "FoodGini": self.calculate_gini(food_values),
                "MoneyGini": self.calculate_gini(money_values),
                "MedicalGoodsGini": self.calculate_gini(medical_values),
                "ReproductionGoodsGini": self.calculate_gini(reproduction_values),
                "Bottom20FoodAvg": self.bottom_percent_average(food_values, 20),
                "Bottom20MoneyAvg": self.bottom_percent_average(money_values, 20),
                "Bottom20MedicalGoodsAvg": self.bottom_percent_average(medical_values, 20),
                "Bottom20ReproductionGoodsAvg": self.bottom_percent_average(reproduction_values, 20),
                "FoodBelowSurvivalCostCount": sum(1 for v in food_values if v < survival_cost),
                "FoodZeroCount": sum(1 for v in food_values if v <= 0),
                "MoneyZeroCount": sum(1 for v in money_values if v <= 0),
                "MedicalGoodsZeroCount": sum(1 for v in medical_values if v <= 0),
                "ReproductionGoodsZeroCount": sum(1 for v in reproduction_values if v <= 0),
                "FoodAidEligibleCount": self.turn_food_aid_eligible_count[p],
                "FoodAidReceivedCount": self.turn_food_aid_received_count[p],
                "FoodAidUnmetCount": self.turn_food_aid_unmet_count[p],
                "GovernmentFoodBeforeAid": self.turn_government_food_before_aid[p],
                "GovernmentFoodAfterAid": self.turn_government_food_after_aid[p],
                "FoodShortageWithGovernmentFoodCount": self.turn_food_shortage_with_government_food_count[p],
                "MedicalAidEligibleCount": self.turn_medical_aid_eligible_count[p],
                "MedicalAidReceivedCount": self.turn_medical_aid_received_count[p],
                "MedicalAidUnmetCount": self.turn_medical_aid_unmet_count[p],
                "GovernmentMedicalGoodsBeforeAid": self.turn_government_medical_goods_before_aid[p],
                "GovernmentMedicalGoodsAfterAid": self.turn_government_medical_goods_after_aid[p],
                "MedicalShortageWithGovernmentMedicalGoodsCount": self.turn_medical_shortage_with_government_medical_goods_count[p],
                "CriticalMedicalNeedCount": self.turn_critical_medical_need_count[p],
                "CriticalMedicalAidReceivedCount": self.turn_critical_medical_aid_received_count[p],
                "CriticalMedicalAidUnmetCount": self.turn_critical_medical_aid_unmet_count[p],
                "CriticalRecoveredCount": self.turn_recovered_critical_count[p],
                "CriticalDiedCount": self.turn_deaths_critical_goods_shortage_when_pop_below5[p] + self.turn_deaths_food_shortage_when_pop_below5[p] + self.turn_deaths_medical_shortage_when_pop_below5[p],
                "MedicalGoodsBoughtByCritical": self.turn_medical_goods_bought_by_critical[p],
                "MedicalGoodsBoughtByHealthy": self.turn_medical_goods_bought_by_healthy[p],
                "CompanyMedicalGoodsStock": int(self.companies[p]["medical_goods"].get("stock", 0)) if hasattr(self, "companies") else 0,
                "Age0Count": age0["count"],
                "Age1To3Count": age1to3["count"],
                "Age4To8Count": age4to8["count"],
                "Age0AvgFood": age0["food"],
                "Age0AvgMoney": age0["money"],
                "Age0AvgMedicalGoods": age0["medical"],
                "Age0AvgReproductionGoods": age0["reproduction"],
                "Age0CriticalCount": age0["critical"],
                "Age1To3AvgFood": age1to3["food"],
                "Age1To3AvgMoney": age1to3["money"],
                "Age1To3AvgMedicalGoods": age1to3["medical"],
                "Age1To3AvgReproductionGoods": age1to3["reproduction"],
                "Age1To3CriticalCount": age1to3["critical"],
                "TotalWagesPaid": self.turn_total_wages_paid[p],
                "AvgWagePerWorker": avg_wage,
                "MedianWagePerWorker": median_wage,
                "MinWagePerWorker": min_wage,
                "WorkersCount": self.turn_labor_worker_count[p],
                "WageToSurvivalCostRatio": round(avg_wage / survival_cost_for_diag, 4),
                "WageToFoodPriceRatio": round(avg_wage / food_cost_for_diag, 4),
                "WageToReproductionGoodsPriceRatio": round(avg_wage / reproduction_cost_for_diag, 4),
                "Bottom20WageAvg": bottom20_wage,
                "CompanyCashBeforeWages": self.turn_company_cash_before_wages[p],
                "CompanyCashAfterWages": self.turn_company_cash_after_wages[p],
                "CompanyCashAfterResourcePurchase": self.turn_company_cash_after_resource_purchase[p],
                "CompanyUnableToPayFullWagesCount": self.turn_company_unable_to_pay_full_wages_count[p],
                "CompanyProductionStoppedByCashCount": self.turn_company_production_stopped_by_cash_count[p],
                "CompanyProductionStoppedByStockCount": self.turn_company_production_stopped_by_stock_count[p],
                "EffectiveBuyWillingnessAvg": round(self.turn_effective_buy_willingness_sum[p] / max(1, self.turn_effective_buy_willingness_count[p]), 4),
                "WageConsumptionBonusAvg": round(self.turn_wage_consumption_bonus_sum[p] / max(1, self.turn_effective_buy_willingness_count[p]), 4),
                "WageResponsiveBuyerCount": self.turn_wage_responsive_buyer_count[p],
                "WageResponsiveExtraCapTotal": self.turn_wage_responsive_extra_cap_total[p],
                "WageFundedMarketSpending": self.turn_wage_funded_market_spending[p],
                "WorkerMarketSpending": self.turn_worker_market_spending[p],
                "WorkerMarketSpendingToCompany": self.turn_worker_market_spending_to_company[p],
                "FoodHardNeedCount": self.turn_food_hard_need_count[p],
                "FoodHardNeedAmount": self.turn_food_hard_need_amount[p],
                "FoodHardSpendingCap": self.turn_food_hard_spending_cap[p],
                "FoodHardActualSpending": self.turn_food_hard_actual_spending[p],
                "FoodHardSatisfiedAmount": self.turn_food_hard_satisfied_amount[p],
                "FoodHardUnsatisfiedAmount": self.turn_food_hard_unsatisfied_amount[p],
                "MedicalHardNeedCount": self.turn_medical_hard_need_count[p],
                "MedicalHardNeedAmount": self.turn_medical_hard_need_amount[p],
                "MedicalHardSpendingCap": self.turn_medical_hard_spending_cap[p],
                "MedicalHardActualSpending": self.turn_medical_hard_actual_spending[p],
                "MedicalHardSatisfiedAmount": self.turn_medical_hard_satisfied_amount[p],
                "MedicalHardUnsatisfiedAmount": self.turn_medical_hard_unsatisfied_amount[p],
                "ReproductionHardNeedCount": self.turn_reproduction_hard_need_count[p],
                "ReproductionHardNeedAmount": self.turn_reproduction_hard_need_amount[p],
                "ReproductionHardSpendingCap": self.turn_reproduction_hard_spending_cap[p],
                "ReproductionHardActualSpending": self.turn_reproduction_hard_actual_spending[p],
                "ReproductionHardSatisfiedAmount": self.turn_reproduction_hard_satisfied_amount[p],
                "ReproductionHardUnsatisfiedAmount": self.turn_reproduction_hard_unsatisfied_amount[p],
                "HardNeedSpendingTotal": self.turn_hard_need_spending_total[p],
                "ReserveNeedSpendingTotal": self.turn_reserve_need_spending_total[p],
                "HardNeedBlockedByNoCash": self.turn_hard_need_blocked_by_no_cash[p],
                "HardNeedBlockedByNoMarketStock": self.turn_hard_need_blocked_by_no_market_stock[p],
                "HardNeedBlockedByHighPrice": self.turn_hard_need_blocked_by_high_price[p],
                "HardNeedBlockedByBudgetCap": self.turn_hard_need_blocked_by_budget_cap[p],
                "FoodHardNeedSatisfiedRate": round(self.turn_food_hard_satisfied_amount[p] / max(1, self.turn_food_hard_need_amount[p]), 4),
                "MedicalHardNeedSatisfiedRate": round(self.turn_medical_hard_satisfied_amount[p] / max(1, self.turn_medical_hard_need_amount[p]), 4),
                "ReproductionHardNeedSatisfiedRate": round(self.turn_reproduction_hard_satisfied_amount[p] / max(1, self.turn_reproduction_hard_need_amount[p]), 4),
                "InventorySalesDividendPaid": self.turn_inventory_sales_dividend_paid[p],
                "InventorySalesDividendRecipients": self.turn_inventory_sales_dividend_recipients[p],
                "HistoricalInventorySalesIncome": self.turn_historical_inventory_sales_income[p],
                "InventorySalesDividendEligibleBranches": self.turn_inventory_sales_dividend_eligible_branches[p],
                "InventorySalesDividendBlockedByCashProtection": self.turn_inventory_sales_dividend_blocked_by_cash_protection[p],
                "InventorySalesDividendBlockedByNoHistoricalIncome": self.turn_inventory_sales_dividend_blocked_by_no_historical_income[p],
                "InventorySalesDividendCashFloor": self.turn_inventory_sales_dividend_cash_floor[p],
                "ExcessCashDividendPaid": self.turn_excess_cash_dividend_paid[p],
                "ExcessCashDividendRecipients": self.turn_excess_cash_dividend_recipients[p],
                "ExcessCashDividendPool": self.turn_excess_cash_dividend_pool[p],
                "ExcessCashDividendEligibleBranches": self.turn_excess_cash_dividend_eligible_branches[p],
                "ExcessCashDividendBlockedByNoExcessCash": self.turn_excess_cash_dividend_blocked_by_no_excess_cash[p],
                "ExcessCashDividendBlockedByNoRecipients": self.turn_excess_cash_dividend_blocked_by_no_recipients[p],
                "LaborWorkerCountWhenPopBelow5": workers_when_below5,
                "TurnsWithNoWorkersWhenPopBelow5": self.turns_with_no_workers_when_pop_below5[p],
                "TurnsWithNoWagesWhenPopBelow5": self.turns_with_no_wages_when_pop_below5[p],
                "CompanyHasCashButNoWorkersCount": self.company_has_cash_but_no_workers_count[p],
                "CompanyHasStockButNoWorkersCount": self.company_has_stock_but_no_workers_count[p],
                "PopBelow5TurnCount": self.pop_below5_turn_count[p],
                "PopBelow3TurnCount": self.pop_below3_turn_count[p],
                "LaborEligibleCountWhenPopBelow5": self.turn_labor_eligible_count_when_pop_below5[p],
                "LaborEligibleCountWhenPopBelow3": self.turn_labor_eligible_count_when_pop_below3[p],
                "LaborWillingCountWhenPopBelow5": self.turn_labor_willing_count_when_pop_below5[p],
                "LaborWillingCountWhenPopBelow3": self.turn_labor_willing_count_when_pop_below3[p],
                "ActualWorkerCountWhenPopBelow5": self.turn_actual_worker_count_when_pop_below5[p],
                "ActualWorkerCountWhenPopBelow3": self.turn_actual_worker_count_when_pop_below3[p],
                "NoWorkerReasonSickCount": self.turn_no_worker_reason_sick_count[p],
                "NoWorkerReasonCriticalCount": self.turn_no_worker_reason_critical_count[p],
                "NoWorkerReasonLowLaborCount": self.turn_no_worker_reason_low_labor_count[p],
                "NoWorkerReasonNoCompanyDemandCount": self.turn_no_worker_reason_no_company_demand_count[p],
                "NoWorkerReasonNoExpectedProfitCount": self.turn_no_worker_reason_no_expected_profit_count[p],
                "NoWorkerReasonNoResourceCount": self.turn_no_worker_reason_no_resource_count[p],
                "CompanyDemandForWorkersWhenPopBelow5": self.turn_company_demand_for_workers_when_pop_below5[p],
                "CompanyDemandForWorkersWhenPopBelow3": self.turn_company_demand_for_workers_when_pop_below3[p],
                "BranchesWithPositiveExpectedProfitWhenPopBelow5": self.turn_branches_with_positive_expected_profit_when_pop_below5[p],
                "BranchesWithPositiveExpectedProfitWhenPopBelow3": self.turn_branches_with_positive_expected_profit_when_pop_below3[p],
                "BranchesStoppedByStockWhenPopBelow5": self.turn_branches_stopped_by_stock_when_pop_below5[p],
                "BranchesStoppedByCashWhenPopBelow5": self.turn_branches_stopped_by_cash_when_pop_below5[p],
                "BranchesStoppedByResourceWhenPopBelow5": self.turn_branches_stopped_by_resource_when_pop_below5[p],
                "GovernmentProductionResourceWhenPopBelow5": self.turn_government_production_resource_when_pop_below5[p],
                "CompanyTotalStockWhenPopBelow5": self.turn_company_total_stock_when_pop_below5[p],
                "CompanyTotalMoneyWhenPopBelow5": self.turn_company_total_money_when_pop_below5[p],
                "LowPopSnapshotCount": self.turn_low_pop_snapshot_count[p],
                "LastIndividualsAvgMoney": self.turn_last_individuals_avg_money[p],
                "LastIndividualsAvgFood": self.turn_last_individuals_avg_food[p],
                "LastIndividualsAvgMedicalGoods": self.turn_last_individuals_avg_medical_goods[p],
                "LastIndividualsAvgReproductionGoods": self.turn_last_individuals_avg_reproduction_goods[p],
                "LastIndividualsAvgLabor": self.turn_last_individuals_avg_labor[p],
                "LastIndividualsAvgReproduce": self.turn_last_individuals_avg_reproduce[p],
                "LastIndividualsAvgLifeRemaining": self.turn_last_individuals_avg_life_remaining[p],
                "LastIndividualsAvgAge": self.turn_last_individuals_avg_age[p],
                "LastIndividualsSickCount": self.turn_last_individuals_sick_count[p],
                "LastIndividualsCriticalCount": self.turn_last_individuals_critical_count[p],
                "LastIndividualsCanWorkCount": self.turn_last_individuals_can_work_count[p],
                "LastIndividualsCanReproduceCount": self.turn_last_individuals_can_reproduce_count[p],
                "LastIndividualsHasFoodForBirthCount": self.turn_last_individuals_has_food_for_birth_count[p],
                "LastIndividualsHasReproductionGoodsCount": self.turn_last_individuals_has_reproduction_goods_count[p],
                "LifeEndWithCanReproduce": self.turn_life_end_with_can_reproduce[p],
                "LifeEndWithCanWork": self.turn_life_end_with_can_work[p],
                "LifeEndWithFoodAndReproductionGoods": self.turn_life_end_with_food_and_reproduction_goods[p],
                "LastDeathLifeRemaining": self.turn_last_death_life_remaining[p],
                "LastDeathHadFoodForBirth": self.turn_last_death_had_food_for_birth[p],
                "LastDeathHadReproductionGoods": self.turn_last_death_had_reproduction_goods[p],
                "LastDeathWasSick": self.turn_last_death_was_sick[p],
                "LastDeathWasCritical": self.turn_last_death_was_critical[p],
                "LastDeathCouldWork": self.turn_last_death_could_work[p],
                "LastDeathCouldReproduce": self.turn_last_death_could_reproduce[p],
                "Last3PopulationAvgLifeRemaining": last3_avg_life_remaining,
                "Last3PopulationMinLifeRemaining": last3_min_life_remaining,
                "Last3PopulationReproductiveEligibleCount": last3_reproductive_eligible_count,
                "DeathByLifeEndWithReproductionGoods": self.death_life_end_with_reproduction_goods[p],
                "DeathByLifeEndWithFoodForBirth": self.death_life_end_with_food_for_birth[p],
                "TurnDeathByLifeEndWithReproductionGoods": self.turn_death_life_end_with_reproduction_goods[p],
                "TurnDeathByLifeEndWithFoodForBirth": self.turn_death_life_end_with_food_for_birth[p],
                "LaborCandidateRawCount": self.turn_labor_candidate_raw_count[p],
                "LaborCandidatesTrimmedByTendency": self.turn_labor_candidates_trimmed_by_tendency[p],
                "LaborAllocatedCandidateCount": self.turn_labor_allocated_candidate_count[p],
                "LaborCandidatesWithoutAllocation": self.turn_labor_candidates_without_allocation[p],
                "LaborPositiveProfitButNoWorkerWhenPopBelow5": self.turn_labor_positive_profit_but_no_worker_when_pop_below5[p],
                "ParentFoodRequirement": self.turn_parent_food_requirement[p],
                "PotentialParentCountWhenPopBelow5": self.turn_potential_parent_count_when_pop_below5[p],
                "PotentialParentWithReproductionGoodsWhenPopBelow5": self.turn_potential_parent_with_reproduction_goods_when_pop_below5[p],
                "PotentialParentFoodReadyWhenPopBelow5": self.turn_potential_parent_food_ready_when_pop_below5[p],
                "ParentFoodGapWhenPopBelow5": self.turn_parent_food_gap_when_pop_below5[p],
                "ParentFoodGapWhenPopBelow3": self.turn_parent_food_gap_when_pop_below3[p],
                "LastIndividualsParentFoodGapAvg": self.turn_last_individuals_parent_food_gap_avg[p],
                "FoodBoughtByPotentialParent": self.turn_food_bought_by_potential_parent[p],
                "FoodAidToPotentialParent": self.turn_food_aid_to_potential_parent[p],
                "BirthBlockedFoodSafetyWithReproductionGoods": self.turn_birth_blocked_food_safety_with_reproduction_goods[p],
                "EvolutionMorality": self.evolution_direction[p]["morality"],
                "EvolutionStrength": self.evolution_direction[p]["strength"],
                "EvolutionReproduce": self.evolution_direction[p]["reproduce"],
                "EvolutionLabor": self.evolution_direction[p]["labor"],
                "EvolutionReady": int(self.evolution_ready[p]),
                "EvolutionSampleCount": self.turn_evolution_sample_count[p],
                "EvolutionDirectionChangeCount": self.turn_evolution_direction_change_count[p],
                "EvolutionFitnessAvg": self.turn_evolution_fitness_avg[p],
                "EvolutionFitnessGapMorality": self.turn_evolution_fitness_gap_morality[p],
                "EvolutionFitnessGapStrength": self.turn_evolution_fitness_gap_strength[p],
                "EvolutionFitnessGapReproduce": self.turn_evolution_fitness_gap_reproduce[p],
                "EvolutionFitnessGapLabor": self.turn_evolution_fitness_gap_labor[p],
                "EvolutionSignalMorality": self.turn_evolution_signal_morality[p],
                "EvolutionSignalStrength": self.turn_evolution_signal_strength[p],
                "EvolutionSignalReproduce": self.turn_evolution_signal_reproduce[p],
                "EvolutionSignalLabor": self.turn_evolution_signal_labor[p],
            })
        return rows

    def get_overview(self):
        self.update_total_wealth()
        return {
            "Turn": self.turn,
            "PopulationTypes": len(self.population_names),
            "TotalPopulation": sum(len(pop) for pop in self.populations.values()),
            "TotalSocialWealth": self.total_social_wealth,
            "TotalEnvResource": self.shared_env_resource if self.is_feature_enabled("enable_shared_environment_resource") else sum(self.env_resource.values()),
            "AvgEnvHealth": int(round(sum(self.env_health.values()) / max(1, len(self.env_health)))),
            "AvgResourcePressure": round(sum(self.resource_pressure.values()) / max(1, len(self.resource_pressure)), 4),
            "AvgTrust": round(sum(self.tribe_trust.values()) / max(1, len(self.tribe_trust)), 4),
            "SharedEnvEnabled": int(self.is_feature_enabled("enable_shared_environment_resource")),
            "TotalGovernmentDeposit": sum(self.government_deposit.values()),
            "TotalFood": sum(sum(getattr(i, "food", 0) for i in pop) for pop in self.populations.values()),
            "TotalMedicalGoods": sum(sum(getattr(i, "medical_goods", 0) for i in pop) for pop in self.populations.values()),
            "TotalEducationGoods": sum(sum(getattr(i, "education_goods", 0) for i in pop) for pop in self.populations.values()),
            "TotalReproductionGoods": sum(sum(getattr(i, "reproduction_goods", 0) for i in pop) for pop in self.populations.values()),
            "TotalCompanyMoney": sum(self.company_totals(p)["money"] for p in self.population_names) if hasattr(self, "companies") else 0,
            "TotalCompanyStock": sum(self.company_totals(p)["stock"] for p in self.population_names) if hasattr(self, "companies") else 0,
            "TotalProduction": sum(self.turn_production_total.values()),
            "TotalInvasionGain": sum(self.turn_invasion_gain_total.values()),
            "TotalInternalPlunderLoss": sum(self.turn_internal_plunder_system_loss_total.values()),
            "TotalInvasionLoss": sum(self.turn_invasion_system_loss_total.values()),
            "TotalSurvivalCost": sum(self.turn_survival_cost_total.values()),
        }

    def build_individual_record(self, p, ind):
        ind.end_balance = ind.balance
        return {
            "Turn": self.turn,
            "Population": p,
            "ID": ind.id,
            "Code": getattr(ind, "code", ""),
            "AncestorCode": getattr(ind, "ancestor_code", ""),
            "AncestorIndex": getattr(ind, "ancestor_index", 0),
            "LineageSequence": getattr(ind, "lineage_sequence", 0),
            "BirthTurn": ind.birth_turn,
            "ParentClass": getattr(ind, "parent_class", ""),
            "BirthClass": getattr(ind, "birth_class", ""),
            "CurrentClass": self.update_individual_class(p, ind)[1],
            "ClassChange": getattr(ind, "class_change", 0),
            "IsUpwardMobile": getattr(ind, "is_upward_mobile", 0),
            "IsDownwardMobile": getattr(ind, "is_downward_mobile", 0),
            "AgeRound": self.turn - ind.birth_turn + int(getattr(ind, "initial_age_rounds", 0)),
            "InitialAgeRounds": int(getattr(ind, "initial_age_rounds", 0)),
            "Life": ind.life,
            "SurvivalRounds": ind.survival_rounds,
            "Critical": int(ind.critical),
            "UsedCriticalChance": int(ind.used_critical_chance),
            "CharityBanned": int(ind.charity_banned),
            "Role": ind.role,
            "AffectedByDisaster": getattr(ind, "affected_by_disaster", 0),
            "DisasterBalanceLoss": getattr(ind, "disaster_balance_loss", 0),
            "TribeTrust": round(self.tribe_trust.get(p, 0), 4),
            "Morality": ind.morality,
            "Strength": ind.strength,
            "Intelligence": ind.intelligence,
            "TemporaryIntelligence": getattr(ind, "temp_intelligence", 0),
            "EffectiveIntelligence": ind.effective_intelligence(),
            "AbilityTotal": ind.strength + ind.intelligence,
            "Reproduce": ind.reproduce,
            "Labor": ind.labor,
            "TurnStartBalance": ind.turn_start_balance,
            "AfterLaborBalance": ind.after_labor_balance,
            "AfterTaxBalance": ind.after_tax_balance,
            "AfterPlunderBalance": ind.after_plunder_balance,
            "AfterInvasionBalance": ind.after_invasion_balance,
            "AfterGovernmentAidBalance": ind.after_government_aid_balance,
            "AfterRescueBalance": ind.after_rescue_balance,
            "AfterReproduceBalance": ind.after_reproduce_balance,
            "PreSurvivalBalance": ind.pre_survival_balance,
            "EndBalance": ind.end_balance,
            "Balance": ind.balance,
            "Money": ind.balance,
            "TurnStartMarketValue": getattr(ind, "turn_start_market_value", 0),
            "PreSurvivalMarketValue": getattr(ind, "pre_survival_market_value", 0),
            "Food": getattr(ind, "food", 0),
            "MedicalGoods": getattr(ind, "medical_goods", 0),
            "EducationGoods": getattr(ind, "education_goods", 0),
            "ReproductionGoods": getattr(ind, "reproduction_goods", 0),
            "Tools": getattr(ind, "tools", 0),
            "DidMarketTrade": getattr(ind, "did_market_trade", 0),
            "MarketMoneySpent": getattr(ind, "market_money_spent", 0),
            "MarketMoneyEarned": getattr(ind, "market_money_earned", 0),
            "MarketImportValue": getattr(ind, "market_import_value", 0),
            "MarketExportValue": getattr(ind, "market_export_value", 0),
            "MarketTaxPaid": getattr(ind, "market_tax_paid", 0),
            "GovernmentPurchaseSold": getattr(ind, "government_purchase_sold", 0),
            "MarketPartnerClass": getattr(ind, "market_partner_class", ""),
            "MarketFoodBought": getattr(ind, "market_food_bought", 0),
            "MarketFoodSold": getattr(ind, "market_food_sold", 0),
            "MarketMedicalGoodsBought": getattr(ind, "market_medical_goods_bought", 0),
            "MarketMedicalGoodsSold": getattr(ind, "market_medical_goods_sold", 0),
            "MarketEducationGoodsBought": getattr(ind, "market_education_goods_bought", 0),
            "MarketEducationGoodsSold": getattr(ind, "market_education_goods_sold", 0),
            "MarketReproductionGoodsBought": getattr(ind, "market_reproduction_goods_bought", 0),
            "MarketReproductionGoodsSold": getattr(ind, "market_reproduction_goods_sold", 0),
            "MarketGoodsBoughtValue": getattr(ind, "market_goods_bought_value", 0),
            "MarketGoodsSoldValue": getattr(ind, "market_goods_sold_value", 0),
            "MarketUnmetFoodNeed": getattr(ind, "market_unmet_food_need", 0),
            "MarketUnmetMedicalNeed": getattr(ind, "market_unmet_medical_goods_need", 0),
            "MarketUnmetEducationNeed": getattr(ind, "market_unmet_education_goods_need", 0),
            "MarketUnmetReproductionNeed": getattr(ind, "market_unmet_reproduction_goods_need", 0),
            "TurnIncome": ind.turn_income,
            "DidLabor": ind.did_labor,
            "EmployerBranch": getattr(ind, "employer_branch", ""),
            "WageReceived": getattr(ind, "wage_received", 0),
            "DividendReceived": getattr(ind, "dividend_received", 0),
            "ProducedGoodsValue": getattr(ind, "produced_goods_value", 0),
            "PrimaryProductionGood": getattr(ind, "primary_production_good", ""),
            "ProductionPriceResponse": getattr(ind, "production_price_response", 0),
            "TotalMarketNeed": getattr(ind, "total_market_need", 0),
            "TotalMarketUnmetNeed": getattr(ind, "total_market_unmet_need", 0),
            "LaborParticipationChance": ind.labor_participation_chance,
            "ResourceAccessScore": ind.resource_access_score,
            "RequestedResource": ind.requested_resource,
            "AllocatedResource": ind.allocated_resource,
            "PopulationResourceClaim": ind.population_resource_claim,
            "PopulationResourceQuota": ind.population_resource_quota,
            "SharedResourceEnabled": ind.shared_resource_enabled,
            "LaborNetProduction": ind.labor_net_production,
            "LaborIncomeAfterTax": ind.labor_income_after_tax,
            "EnvConsumedByLabor": ind.env_consumed_by_labor,
            "FoodProduced": getattr(ind, "food_produced", 0),
            "MedicalGoodsProduced": getattr(ind, "medical_goods_produced", 0),
            "EducationGoodsProduced": getattr(ind, "education_goods_produced", 0),
            "ReproductionGoodsProduced": getattr(ind, "reproduction_goods_produced", 0),
            "ToolsProduced": getattr(ind, "tools_produced", 0),
            "FoodConsumed": getattr(ind, "food_consumed", 0),
            "MedicalGoodsConsumed": getattr(ind, "medical_goods_consumed", 0),
            "EducationGoodsConsumed": getattr(ind, "education_goods_consumed", 0),
            "ReproductionGoodsConsumed": getattr(ind, "reproduction_goods_consumed", 0),
            "ToolsConsumed": getattr(ind, "tools_consumed", 0),
            "FoodTaxPaid": getattr(ind, "food_tax_paid", 0),
            "MedicalGoodsTaxPaid": getattr(ind, "medical_goods_tax_paid", 0),
            "EducationGoodsTaxPaid": getattr(ind, "education_goods_tax_paid", 0),
            "ReproductionGoodsTaxPaid": getattr(ind, "reproduction_goods_tax_paid", 0),
            "ToolsTaxPaid": getattr(ind, "tools_tax_paid", 0),
            "FoodAidReceived": getattr(ind, "food_aid_received", 0),
            "MedicalAidReceived": getattr(ind, "medical_aid_received", 0),
            "IsSick": getattr(ind, "is_sick", 0),
            "BecameSickThisTurn": getattr(ind, "became_sick_this_turn", 0),
            "SicknessRisk": getattr(ind, "sickness_risk", 0),
            "HealthIndex": getattr(ind, "health_index", 100),
            "HealthDeltaThisTurn": getattr(ind, "health_delta_this_turn", 0),
            "MedicalRecoveryThisTurn": getattr(ind, "medical_recovery_this_turn", 0),
            "HealthDeterioratedThisTurn": getattr(ind, "health_deteriorated_this_turn", 0),
            "EducationCapital": getattr(ind, "education_capital", 0),
            "ReproductiveSecurityScore": getattr(ind, "reproductive_security_score", 0),
            "ReproductiveSecurityBonus": getattr(ind, "reproductive_security_bonus", 0),
            "MedicalGoodsNeeded": getattr(ind, "medical_goods_needed", 0),
            "MedicalGoodsShortage": getattr(ind, "medical_goods_shortage", 0),
            "FoodShortage": getattr(ind, "food_shortage", 0),
            "EducationGoodsUsedForChild": getattr(ind, "education_goods_used_for_child", 0),
            "ReproductionGoodsUsed": getattr(ind, "reproduction_goods_used", 0),
            "MoneyUsedForReproduction": getattr(ind, "money_used_for_reproduction", 0),
            "WealthTaxPaid": ind.wealth_tax_paid,
            "RichTaxPaid": getattr(ind, "rich_tax_paid", 0),
            "TotalTaxPaid": ind.total_tax_paid,
            "DidInternalPlunder": ind.did_internal_plunder,
            "InternalPlunderGain": ind.internal_plunder_gain,
            "InternalPlunderVictimLossCaused": ind.internal_plunder_victim_loss_caused,
            "InternalPlunderSystemLossCaused": ind.internal_plunder_system_loss_caused,
            "WasInternalPlunderVictim": ind.was_internal_plunder_victim,
            "InternalPlunderLoss": ind.internal_plunder_loss,
            "InternalPlunderTotalValueGain": getattr(ind, "internal_plunder_total_value_gain", 0),
            "InternalPlunderTotalValueLoss": getattr(ind, "internal_plunder_total_value_loss", 0),
            "InternalPlunderFoodGain": getattr(ind, "internal_plunder_food_gain", 0),
            "InternalPlunderFoodLoss": getattr(ind, "internal_plunder_food_loss", 0),
            "InternalPlunderMedicalGoodsGain": getattr(ind, "internal_plunder_medical_goods_gain", 0),
            "InternalPlunderMedicalGoodsLoss": getattr(ind, "internal_plunder_medical_goods_loss", 0),
            "InternalPlunderEducationGoodsGain": getattr(ind, "internal_plunder_education_goods_gain", 0),
            "InternalPlunderEducationGoodsLoss": getattr(ind, "internal_plunder_education_goods_loss", 0),
            "InternalPlunderReproductionGoodsGain": getattr(ind, "internal_plunder_reproduction_goods_gain", 0),
            "InternalPlunderReproductionGoodsLoss": getattr(ind, "internal_plunder_reproduction_goods_loss", 0),
            "InternalPlunderToolsGain": getattr(ind, "internal_plunder_tools_gain", 0),
            "InternalPlunderToolsLoss": getattr(ind, "internal_plunder_tools_loss", 0),
            "WasSanctioned": ind.was_sanctioned,
            "SanctionLoss": ind.sanction_loss,
            "DidInvasion": ind.did_invasion,
            "InvasionSuccess": ind.invasion_success,
            "InvasionGain": ind.invasion_gain,
            "InvasionVictimLossCaused": ind.invasion_victim_loss_caused,
            "InvasionSystemLossCaused": ind.invasion_system_loss_caused,
            "WasInvasionVictim": ind.was_invasion_victim,
            "InvasionLoss": ind.invasion_loss,
            "InvasionTotalValueGain": getattr(ind, "invasion_total_value_gain", 0),
            "InvasionTotalValueLoss": getattr(ind, "invasion_total_value_loss", 0),
            "InvasionFoodGain": getattr(ind, "invasion_food_gain", 0),
            "InvasionFoodLoss": getattr(ind, "invasion_food_loss", 0),
            "InvasionMedicalGoodsGain": getattr(ind, "invasion_medical_goods_gain", 0),
            "InvasionMedicalGoodsLoss": getattr(ind, "invasion_medical_goods_loss", 0),
            "InvasionEducationGoodsGain": getattr(ind, "invasion_education_goods_gain", 0),
            "InvasionEducationGoodsLoss": getattr(ind, "invasion_education_goods_loss", 0),
            "InvasionReproductionGoodsGain": getattr(ind, "invasion_reproduction_goods_gain", 0),
            "InvasionReproductionGoodsLoss": getattr(ind, "invasion_reproduction_goods_loss", 0),
            "InvasionToolsGain": getattr(ind, "invasion_tools_gain", 0),
            "InvasionToolsLoss": getattr(ind, "invasion_tools_loss", 0),
            "InvasionFailLifeLoss": ind.invasion_fail_life_loss,
            "GovernmentAidReceived": ind.government_aid_received,
            "IndividualRescueGiven": ind.individual_rescue_given,
            "IndividualRescueReceived": ind.individual_rescue_received,
            "MoralDonationGiven": getattr(ind, "moral_donation_given", 0),
            "MoralDonationReceived": getattr(ind, "moral_donation_received", 0),
            "DidReproduce": ind.did_reproduce,
            "ChildCount": ind.child_count,
            "ReproductionGoodsConsumed": getattr(ind, "reproduction_goods_consumed_for_child", 0),
            "ReproductionMoneyTransferredToChild": getattr(ind, "reproduction_money_transferred_to_child", 0),
            "BirthFoodTransferredToChild": getattr(ind, "birth_food_transferred_to_child", 0),
            "BirthFoodReceived": getattr(ind, "birth_food_received", 0),
            "InheritanceGiven": ind.inheritance_given,
            "InheritanceReceived": ind.inheritance_received,
            "EducationTempIntelligenceReceived": ind.education_temp_intelligence_received,
            "GovernmentEducationInvestmentReceived": getattr(ind, "government_education_investment_received", 0),
            "GovernmentEducationTempIntelligenceReceived": getattr(ind, "government_education_temp_intelligence_received", 0),
            "EducationTempIntelligenceGiven": ind.education_temp_intelligence_given,
            "SurvivalCostPaid": ind.survival_cost_paid,
            "EnteredCriticalThisTurn": ind.entered_critical_this_turn,
            "RecoveredFromCriticalThisTurn": ind.recovered_from_critical_this_turn,
            "DiedThisTurn": ind.died_this_turn,
            "DeathReason": ind.death_reason,
            "DepositToGovernmentOnDeath": ind.deposit_to_government_on_death,
        }

    def record_output_data(self):
        # dev11：缓存本回合汇总，避免 GUI 和输出重复计算；个体详细记录默认每 5 回合一次。
        # 新生与死亡个体每回合都记录，避免关键生命周期事件丢失。
        rows = self.current_summary_rows if getattr(self, "current_summary_rows", None) else self.get_population_summary_rows()
        self.summary_output_rows.extend(rows)
        should_record_all = (self.turn % 5 == 0)
        recorded_ids = set()
        if should_record_all:
            for p, pop in self.populations.items():
                for ind in pop:
                    self.individual_output_rows.append(self.build_individual_record(p, ind))
                    recorded_ids.add(ind.id)
        for p, ind in self.newborns_this_turn:
            if ind.id not in recorded_ids:
                self.individual_output_rows.append(self.build_individual_record(p, ind))
                recorded_ids.add(ind.id)
        for p, ind in self.dead_individuals_this_turn:
            self.individual_output_rows.append(self.build_individual_record(p, ind))

    def record_history(self):
        self.turn_history.append(self.turn)
        for p, pop in self.populations.items():
            count = len(pop)
            total_bal = sum(i.balance for i in pop)
            self.population_history[p].append(count)
            self.total_balance_history[p].append(int(round(total_bal / 100)))
            self.gini_history[p].append(self.calculate_gini([i.balance for i in pop]))
            self.production_history[p].append(self.turn_production_total[p])
            self.invasion_gain_history[p].append(self.turn_invasion_gain_total[p])
            self.env_health_history[p].append(self.env_health[p])
            self.resource_pressure_history[p].append(self.resource_pressure[p])
            if not count:
                for k in self.avg_stat[p]:
                    self.avg_stat[p][k].append(0)
                self.str_total_ratio_history[p].append(0)
                continue
            avg_int = int(round(sum(i.intelligence for i in pop) / count))
            avg_str = int(round(sum(i.strength for i in pop) / count))
            self.avg_stat[p]["intelligence"].append(avg_int)
            self.avg_stat[p]["strength"].append(avg_str)
            self.avg_stat[p]["balance"].append(int(round(total_bal / count)))
            self.avg_stat[p]["dead_lifespan"].append(self.get_avg_dead_lifespan(p))
            self.avg_stat[p]["labor"].append(int(round(sum(i.labor for i in pop) / count)))
            self.avg_stat[p]["morality"].append(int(round(sum(i.morality for i in pop) / count)))
            self.avg_stat[p]["reproduce"].append(int(round(sum(i.reproduce for i in pop) / count)))
            self.avg_stat[p]["critical"].append(sum(1 for i in pop if i.critical))
            self.str_total_ratio_history[p].append(round((avg_str / self.cfg["base"]["total_ability"]) * 100, 4))

    def update_cumulative_diagnostics(self):
        # dev24：记录累计出生/死亡与出生阻断原因，便于灭绝后仍能诊断中间过程。
        for p in self.population_names:
            self.cumulative_birth_count[p] += int(self.turn_birth_count.get(p, 0))
            self.cumulative_death_count[p] += int(self.turn_death_count.get(p, 0))
            self.cumulative_birth_blocked_critical[p] += int(self.turn_birth_blocked_critical.get(p, 0))
            self.cumulative_birth_blocked_sick[p] += int(self.turn_birth_blocked_sick.get(p, 0))
            self.cumulative_birth_blocked_no_money[p] += int(self.turn_birth_blocked_no_money.get(p, 0))
            self.cumulative_birth_blocked_no_reproduction_goods[p] += int(self.turn_birth_blocked_no_reproduction_goods.get(p, 0))
            self.cumulative_birth_blocked_no_food_safety[p] += int(self.turn_birth_blocked_no_food_safety.get(p, 0))
            self.cumulative_birth_blocked_low_reproduce_chance[p] += int(self.turn_birth_blocked_low_reproduce_chance.get(p, 0))
            self.cumulative_birth_blocked_other[p] += int(self.turn_birth_blocked_other.get(p, 0))

    def run_turn(self):
        # dev24：如果所有部族人口已经为 0，则不再继续无效运行。
        if sum(len(pop) for pop in self.populations.values()) <= 0:
            return False
        self.turn += 1

        # 在本回合所有机制阶段执行前，先应用“启用回合 / 禁用回合”。
        # 这样设置为第 N 回合的调度，会从第 N 回合开始影响模型。
        self.apply_switch_schedules()

        self.start_phase()
        self.labor_phase()
        self.update_dev37_low_population_labor_diagnostics()
        self.snapshot_balances("after_labor_balance")
        self.tax_phase()
        self.snapshot_balances("after_tax_balance")
        # BOT8 dev10：市场阶段放在生产/税收之后、掠夺和侵略之前。
        # 这样代码可以根据本回合生产后的库存计算个体需求，掠夺/侵略则体现对正常经济秩序的破坏。
        self.market_phase()
        self.distribute_inventory_sales_dividends()
        self.distribute_excess_cash_dividends()
        self.environment_update_phase()
        self.internal_plunder_phase()
        self.snapshot_balances("after_plunder_balance")
        self.invasion_phase()
        self.snapshot_balances("after_invasion_balance")
        self.government_aid_phase()
        self.snapshot_balances("after_government_aid_balance")
        self.individual_rescue_phase()
        self.moral_donation_phase()
        self.snapshot_balances("after_rescue_balance")
        self.government_reproduction_goods_release_phase()
        self.reproduce_phase()
        self.snapshot_balances("after_reproduce_balance")
        self.prepare_evolution_samples_before_survival()
        self.survival_phase()
        # dev29：政府剩余价值删除延后到既有救助、繁殖和生存消耗之后，避免刚买入或死亡遗留的公共库存
        # 在本回合尚未服务生存/教育/繁殖用途前就被清理。
        self.government_surplus_value_cleanup_phase()
        self.update_population_risk_diagnostics()
        self.evolution_phase()
        self.trust_update_phase()
        self.restore_populations_if_only_one_left()
        # 将本回合商品消耗记录保存为下一回合生产结构依据。
        if hasattr(self, "current_goods_consumption"):
            self.last_goods_consumption = {p: self.current_goods_consumption[p].copy() for p in self.population_names}
        if hasattr(self, "turn_market_unmet_demand"):
            self.last_market_unmet_demand = {p: self.turn_market_unmet_demand[p].copy() for p in self.population_names}
        if hasattr(self, "turn_birth_blocked_no_reproduction_goods"):
            self.last_birth_blocked_no_reproduction_goods = {p: self.turn_birth_blocked_no_reproduction_goods[p] for p in self.population_names}
        if hasattr(self, "turn_hard_demand"):
            self.last_hard_demand = {p: self.turn_hard_demand[p].copy() for p in self.population_names}
        if hasattr(self, "turn_reserve_demand"):
            self.last_reserve_demand = {p: self.turn_reserve_demand[p].copy() for p in self.population_names}
        if hasattr(self, "turn_reproduction_goods_hard_demand_unsatisfied"):
            self.last_reproduction_goods_hard_demand_unsatisfied = {p: self.turn_reproduction_goods_hard_demand_unsatisfied[p] for p in self.population_names}
        self.last_resource_use_to_regen_ratio = {
            p: round(self.turn_population_resource_used[p] / max(1, self.turn_resource_regen_total[p]), 4)
            for p in self.population_names
        }
        self.update_cumulative_diagnostics()
        self.current_summary_rows = self.get_population_summary_rows()
        self.record_output_data()
        self.record_history()
        if hasattr(self, "entity_state_snapshots"):
            self.entity_state_snapshots.append(collect_entity_state_snapshot(self))
        return sum(len(pop) for pop in self.populations.values()) > 0
