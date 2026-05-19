import os
import copy

PROJECT_NAME = "BOT8：生物演化"
# 开发版本号：不等同于最终发布版本号。后续每次开发修改时递增。
PROJECT_VERSION = "44"
MAX_POPULATION_TYPES = 10
POP_LABELS = list("ABCDEFGHIJ")

MECHANISM_SWITCHES = [
    ("enable_invasion", "侵略机制"),
    ("enable_internal_plunder", "部族内掠夺机制"),
    ("enable_government_aid", "政府救助机制"),
    ("enable_rescue", "部族内个体救助机制"),
    ("enable_evolution", "进化机制"),
    ("enable_restore_populations", "恢复多部族机制"),
    ("enable_shared_environment_resource", "部族间共用环境资源机制"),
    ("enable_disaster", "灾害与系统韧性机制"),
    ("enable_market", "基础商品市场与政府采购机制"),
    ("enable_global_trade", "跨部族自由交易机制"),
    ("enable_government_orderbook_buyer", "政府订单簿最后买方"),
    ("enable_government_macro_control", "政府宏观调控机制"),
    ("enable_tax_system", "税收系统"),
]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "civilization_settings.json")
OUTPUT_XLSX_NAME = os.path.join(SCRIPT_DIR, "civilization_summary.xlsx")
OUTPUT_CSV_NAME = os.path.join(SCRIPT_DIR, "civilization_individuals.csv")

# BOT8 2.3.0：50 人稳定观察型默认值。
# 研究依据：生态承载力与可再生资源模型通常需要避免开局即极端超采，
# 因此默认人口、初始资源与资源再生被设置为更适合观察长期趋势的组合。
DEFAULT_INITIAL_ENV_RESOURCE = 12000
DEFAULT_ENV_CAPACITY = DEFAULT_INITIAL_ENV_RESOURCE * 5


def make_population_config(morality=60, strength=300, reproduce=50, labor=55, security=60, trust=60):
    return {
        "morality": morality,
        "strength": strength,
        "reproduce": reproduce,
        "labor": labor,
        "initial_env_resource": DEFAULT_INITIAL_ENV_RESOURCE,
        "resource_regen": 2000,
        # 环境承载力默认设置为初始环境资源的 5 倍，便于观察“可恢复空间”和“资源上限”。
        "env_capacity": DEFAULT_ENV_CAPACITY,
        "env_health": 100,
        # BOT8 2.2.0：退化速度使用整数缩放。实际下降由资源压力差额和 env_damage_buffer 累积决定。
        "env_degradation_rate": 10,
        "env_recovery_rate": 3,
        "security": security,
        # 医疗水平：0-100。用于生病判定，医疗水平越高，个体进入生病状态的概率越低。
        "medical_level": 50,
        # 社会信任：部族级状态变量，范围0-100。默认60表示略高于中性的稳定社会。
        # 参考社会资本和公共池资源治理研究，信任会影响劳动合作、救助、掠夺和共用资源组织能力。
        "trust": trust,
        # 政府相关参数改为部族/部族独立设置，便于比较不同治理结构。
        # gov_aid_budget_ratio：每回合最多使用政府存款的该比例进行救助。
        "gov_aid_budget_ratio": 50,
        # labor_tax_rate：劳动实物税率，按本回合商品生产量征收实物税，进入本部族政府商品库存。
        "labor_tax_rate": 10,
        # 财富税阶梯：低于免税线不征收；免税线到高档阈值按低档税率；超过高档阈值的部分按高档税率。
        "wealth_tax_exempt_threshold": 600,
        "wealth_tax_threshold": 1500,
        "wealth_tax_low_rate": 1,
        "wealth_tax_rate": 2,
        # BOT8 dev17：跨部族贸易税制。进口税进入买方部族政府，交易税进入卖方部族政府。
        "import_tax_rate": 5,
        "trade_tax_rate": 2,
        # BOT8 dev18：政府宏观调控参数。政府通过低价收储、高价投放和民生折价释放库存稳定关键商品市场。
        "market_control_budget_ratio": 20,
        "food_subsidy_rate": 20,
        "medical_subsidy_rate": 20,
        # dev21：公司化劳动。公司作为部族内商品生产主体，个体通过劳动从公司获得工资。
        "company_initial_money": 2000,
        # dev42：初始资产默认按族群规模关联。开启时，公司初始资金由每人资金基数计算，
        # GUI 中手动公司初始货币项置灰；关闭后恢复手动输入 company_initial_money。
        "use_population_scaled_initials": 1,
        "company_initial_money_per_capita": 400,
        "government_initial_money_per_capita": 20,
        "government_initial_food_rounds": 1,
        "government_initial_medical_goods_ratio": 25,
        "government_initial_education_goods_ratio": 25,
        "government_initial_reproduction_goods_ratio": 25,
        "company_initial_food_rounds": 3,
        "company_initial_medical_goods_ratio": 50,
        "company_initial_education_goods_ratio": 100,
        "company_initial_reproduction_goods_ratio": 100,
        # dev42：生育用品/教育用品库存韧性。它不直接放宽出生条件，而是在生产权重中
        # 将“公司库存低于按当前人口计算的目标储备”转化为生产偏好，避免库存长期归零。
        "enable_repro_education_inventory_resilience": 1,
        "repro_inventory_target_births_ratio": 150,
        "education_inventory_target_births_ratio": 100,
        "repro_education_inventory_resilience_weight": 50,
        # dev44：硬刚需生产响应。环境再生资源仍有闲置且上一回合硬刚需未满足时，
        # 公司生产权重会更积极转向食物、医疗用品、生育用品和教育用品。
        # 它不直接增加人口、不降低出生条件，也不凭空创造资源，只改变公司生产结构。
        "enable_hard_need_production_response": 1,
        "hard_need_resource_use_threshold": 80,
        "hard_need_production_response_weight": 80,
        "food_hard_need_production_weight": 120,
        "medical_hard_need_production_weight": 100,
        "reproduction_hard_need_production_weight": 80,
        "education_need_production_weight": 50,
        "hard_need_production_weight_cap": 300,
        "company_production_tendency": 60,
        # dev22：公司工资比例。工资按劳动产出对应的市场价值乘以该比例支付，避免按商品数量直接支付导致公司货币断流。
        "company_wage_ratio": 30,
        # dev26：营收驱动公司。劳动报酬按产出市场价值的一定比例支付；公司不再使用固定最低工资。
        "labor_reward_ratio": 60,
        # dev39：工资响应消费。工资提高后，个体当回合有效买入意愿会随工资收入小幅上升；这不创造货币，只改变有工资个体的消费预算释放速度。
        "enable_wage_responsive_consumption": 1,
        "wage_consumption_bonus_per_survival": 10,
        "wage_consumption_bonus_cap": 20,
        # dev26：生产资源价格。公司生产前需向政府购买生产资源，政府作为生产资源所有者获得财政收入。
        "production_resource_price": 1,
        # dev26：公司利润敏感度。数值越高，公司越倾向生产高收益、可销售、低库存压力商品。
        "company_profit_sensitivity": 100,
        # dev41：公司硬刚需库存释放。公司有库存且市场存在食物/医疗/生育用品刚性缺口时，
        # 不再让“初始库存目标”阻断上架；这不创造资源，只让已有库存进入订单簿销售。
        "enable_company_hard_need_inventory_release": 1,
        "company_hard_need_listing_multiplier": 100,
        "company_hard_need_min_listing_ratio": 50,
        # dev27：订单簿市场买入意愿。个体买入意愿影响其愿意把多少剩余货币用于市场购买。
        "individual_buy_willingness": 80,
        # dev27：政府买入意愿。政府作为最后买方吸收市场剩余，但会保留一定财政，不会无上限耗尽资金。
        "government_buy_willingness": 60,

        # 政府教育参数：每个部族独立设置，便于比较不同公共教育制度。
        # gov_education_enabled 使用 0/1，避免增加新的全局机制开关；1 表示该部族启用政府教育。
        "gov_education_enabled": 1,
        # gov_education_budget_ratio：每回合繁殖阶段最多使用政府教育用品库存的该比例为新生个体提供公共教育。
        "gov_education_budget_ratio": 20,
        # gov_education_temp_int_per_100：每消耗 100 教育用品，给新生个体增加多少临时智慧。
        "gov_education_temp_int_per_100": 5,
    }


DEFAULT_POPULATION_CONFIG = {
    "A": make_population_config(60, 300, 50, 55, 60),
    "B": make_population_config(60, 300, 50, 55, 60),
    "C": make_population_config(60, 300, 50, 55, 60),
}
for p in POP_LABELS:
    DEFAULT_POPULATION_CONFIG.setdefault(p, make_population_config())

DEFAULT_SETTINGS = {
    "switches": {
        "enable_invasion": False,
        "enable_internal_plunder": True,
        "enable_government_aid": True,
        "enable_rescue": True,
        "enable_evolution": True,
        "enable_restore_populations": False,
        "enable_shared_environment_resource": False,
        # BOT8 dev7：灾害机制默认关闭，用于需要压力测试时检验部族系统韧性。
        "enable_disaster": False,
        # BOT8 dev10：基础商品市场默认开启。市场阶段位于生产之后、掠夺/侵略之前。
        "enable_market": True,
        # BOT8 dev17：跨部族自由交易默认关闭。开启后个体优先本地购买，不足再跨部族购买。
        "enable_global_trade": False,
        # dev31：政府订单簿最后买方是市场流动性闭环，不再与旧宏观调控开关混用。
        "enable_government_orderbook_buyer": True,
        # BOT8 dev18：政府宏观调控默认开启，用于观察公共库存缓冲、折价投放和市场稳定指标。
        "enable_government_macro_control": True,
        # BOT8 dev16：道德施舍机制默认关闭，作为高级调试机制。
        "enable_moral_donation": False,
        # dev26：恢复税收系统，但仅启用富人资产税；交易税、进口税、劳动税仍不生效。
        "enable_tax_system": True,
    },

    # 每个机制的运行时启用/禁用调度。
    # enable_rounds / disable_rounds 支持字符串，例如："10, 25, 50"。
    # 只有对应总开关为 True 时，调度才会生效。
    "switch_schedules": {
        "enable_invasion": {"enable_rounds": "", "disable_rounds": ""},
        "enable_internal_plunder": {"enable_rounds": "", "disable_rounds": ""},
        "enable_government_aid": {"enable_rounds": "", "disable_rounds": ""},
        "enable_rescue": {"enable_rounds": "", "disable_rounds": ""},
        "enable_evolution": {"enable_rounds": "", "disable_rounds": ""},
        "enable_restore_populations": {"enable_rounds": "", "disable_rounds": ""},
        "enable_shared_environment_resource": {"enable_rounds": "", "disable_rounds": ""},
        "enable_disaster": {"enable_rounds": "", "disable_rounds": ""},
        "enable_market": {"enable_rounds": "", "disable_rounds": ""},
        "enable_global_trade": {"enable_rounds": "", "disable_rounds": ""},
        "enable_government_orderbook_buyer": {"enable_rounds": "", "disable_rounds": ""},
        "enable_government_macro_control": {"enable_rounds": "", "disable_rounds": ""},
        "enable_moral_donation": {"enable_rounds": "", "disable_rounds": ""},
        "enable_tax_system": {"enable_rounds": "", "disable_rounds": ""},
    },
    "base": {
        "max_turns": 200,
        "save_interval": 10,
        "population_count": 1,
        # BOT8 dev7：灾害机制参数。默认关闭；开启后每回合按概率触发一种外部冲击。
        # disaster_probability=3 表示每回合 3% 概率，适合长期稳定社会的低频压力测试。
        # disaster_strength=20 表示中等强度冲击，避免一两回合直接摧毁模型。
        "disaster_probability": 3,
        "disaster_strength": 20,
        "initial_population": 5,
        "initial_env_resource": DEFAULT_INITIAL_ENV_RESOURCE,
        "resource_regen": 2000,
        "initial_balance": 100,
        "survival_cost": 100,
        # dev29：拆分 child_initial_balance 的旧语义。旧字段仅保留为兼容旧设置/旧 GUI 的参考值，
        # 不再直接同时代表子代货币、生育用品消耗和子代食物。
        "child_initial_balance": 100,
        # 子代出生时由父代转移的货币上限。默认 0 表示不再把旧版“新生儿初始存款”作为出生成本。
        "child_initial_money": 0,
        # 子代出生时由父代转移的食物数量；该食物用于下一回合生存，不应在出生当回合被消耗。
        "child_initial_food": 100,
        # 每次出生需要消耗的生育用品数量。
        "reproduction_goods_required_per_birth": 100,
        # 父代出生前需要保有的食物安全倍数：父代本回合、下回合与子代下回合基础食物。
        "parent_food_required_for_birth_multiplier": 3,
        # dev33：二次减概率生育判定。已成功生育的父代如果仍满足完整生育条件，
        # 可再进行一次按 secondary_birth_chance_ratio 折减后的生育判定。
        # 该机制只依赖既有资源条件，不读取人口数量，也不提供强制人口恢复。
        "enable_secondary_birth_check": True,
        "secondary_birth_chance_ratio": 50,

        # 系统级第七阶段：进化方向算法校准参数。自然遗传变异仍由 mutation.* 控制；
        # 这些参数只影响“定向进化偏置”的方向判定和噪声平滑。
        "enable_weighted_evolution_algorithm": 1,
        "evolution_weight_market_value": 50,
        "evolution_weight_birth_success": 80,
        "evolution_weight_labor_income": 30,
        "evolution_weight_health": 30,
        "evolution_weight_survival_stock": 20,
        "evolution_direction_smoothing_rate": 35,
        "evolution_min_direction_signal": 8,
        "evolution_cycle_window": 20,
        # dev29：预留初始年龄分布。代码检查发现当前 life 已有 17-23 的随机差异；
        # 为避免把开局个体剩余寿命压得过短，默认关闭，后续可作为实验选项启用。
        "enable_initial_age_distribution": False,
        "initial_age_distribution_ratio": 60,
        # dev31：小族群正常初始条件预设。只改变开局禀赋，不在运行中强制恢复人口。
        "enable_small_group_initial_conditions": True,
        "small_group_initial_population_threshold": 5,
        "small_group_initial_food_rounds": 5,
        "small_group_initial_medical_goods_ratio": 50,
        "small_group_initial_reproduction_goods_ratio": 100,
        "enable_government_reproduction_goods_release": False,
        # dev35：库存销售收入分红实验开关。默认关闭；用于比较“直接提高工资”与“库存清算收益回流个体”的效果。
        # 资金只来自公司真实销售收入，不创造货币，也不改变生育概率。
        # dev35 进一步限制：默认只分配历史库存清算收入，并加入公司现金保护，避免抽干复产现金流。
        "enable_inventory_sales_dividend": False,
        "inventory_sales_dividend_ratio": 10,
        "inventory_sales_dividend_historical_only": True,
        "inventory_sales_dividend_cash_protection": True,
        "inventory_sales_dividend_min_cash_ratio": 120,
        "inventory_sales_dividend_cash_floor_ratio": 100,
        # dev36：超额现金分层分红实验。默认关闭；只从分公司超过运营现金阈值的真实盈余中分红，
        # 避免按销售额直接抽走复产现金。recipient_mode：0=所有非濒死个体，1=本回合本分公司劳动者，2=近期本分公司劳动者。
        "enable_excess_cash_dividend": False,
        "excess_cash_dividend_ratio": 20,
        "excess_cash_dividend_min_cash_ratio": 120,
        "excess_cash_dividend_recipient_mode": 1,
        "excess_cash_dividend_recent_turns": 5,
        # 教育用品机制：母代每消耗 100 教育用品，子代获得的临时智慧点数。
        "education_temp_int_per_100_goods": 10,
        "total_ability": 750,
        "min_strength": 100,
        "max_strength": 500,
        "min_intelligence": 100,
        "max_intelligence": 500,
        # BOT8 中的寿命不是现实年龄，而是可参与生存阶段的抽象生命周期。
        "min_life": 17,
        "max_life": 23,
        "labor_env_cost": 100,
        # 可持续采收比例：默认 100 表示劳动阶段最多消耗本回合实际再生量，模拟可持续产出约束。
        "environment_safe_harvest_ratio": 100,
        # dev20：提高最高商品生产预算，使劳动者在商品化经济中具备覆盖自身与非劳动者基础需求的能力。
        # dev11 起删除抽象劳动成本，生产预算直接分配为商品。
        "max_production": 800,
        # BOT8 dev13：商品价格指数。100 表示 1 货币/单位；价格由本回合供需压力动态调整。
        # price_adjust_speed 越高，缺货或滞销对价格的影响越快。
        # 本版不直接调整价格参数，价格波动主要通过生产、囤积、消费行为继续校准。
        "price_adjust_speed": 10,
        # dev20：最低价格指数允许低至 1，用于表达极端过剩商品的市场贬值；单笔交易仍有最低总价保护，避免免费交易。
        "min_price_index": 1,
        "max_price_index": 500,
        # BOT8 dev18：政府宏观调控价格阈值。低于低价阈值时倾向收储，高于高价阈值时倾向投放。
        "market_control_low_price_index": 80,
        "market_control_high_price_index": 150,
        "min_reproduce": 0,
        "max_reproduce": 70,
    },
    "behavior": {
        "internal_plunder_min": 5,
        "internal_plunder_max": 25,
        "rescue_min_ratio": 10,
        "rescue_max_ratio": 20,
        "rescue_min_balance": 400,
        "plunder_gain_rate": 50,
        "invasion_fail_life_loss": 5,
        "invasion_strength_weight": 45,
        "invasion_poverty_weight": 35,
        # BOT8 2.2.0：新增基础侵略风险，用于把原始侵略倾向压缩到更可观察的频率。
        "invasion_base_risk": 10,
        "invasion_success_sigma": 200,
        # 侵略成功不再夺取目标全部存款，而是夺取 30%-70%。
        "invasion_loot_min": 20,
        "invasion_loot_max": 50,
    },
    "mutation": {"morality": 5, "strength": 10, "reproduce": 3, "labor": 5},
    "population": copy.deepcopy(DEFAULT_POPULATION_CONFIG),
}

POP_COLORS = {"A":"tab:blue","B":"tab:orange","C":"tab:green","D":"tab:red","E":"tab:purple","F":"tab:brown","G":"tab:pink","H":"tab:gray","I":"tab:olive","J":"tab:cyan"}

PARAM_RANGES = {
    "base.max_turns": (1, 100000), "base.save_interval": (1, 100000),
    "base.population_count": (1, 3), "base.disaster_probability": (0, 100), "base.disaster_strength": (0, 100), "base.initial_population": (0, 100000),
    "base.initial_env_resource": (0, 10**12), "base.resource_regen": (0, 10**12),
    "base.initial_balance": (0, 10**12), "base.survival_cost": (0, 10**12), "base.child_initial_balance": (0, 10**12),
    "base.child_initial_money": (0, 10**12), "base.child_initial_food": (0, 10**12), "base.reproduction_goods_required_per_birth": (0, 10**12),
    "base.parent_food_required_for_birth_multiplier": (0, 100), "base.enable_secondary_birth_check": (0, 1), "base.secondary_birth_chance_ratio": (0, 100), "base.enable_initial_age_distribution": (0, 1), "base.initial_age_distribution_ratio": (0, 100),
    "base.enable_government_reproduction_goods_release": (0, 1),
    "base.enable_small_group_initial_conditions": (0, 1), "base.small_group_initial_population_threshold": (0, 100000),
    "base.small_group_initial_food_rounds": (0, 100), "base.small_group_initial_medical_goods_ratio": (0, 1000), "base.small_group_initial_reproduction_goods_ratio": (0, 1000),
    "base.enable_inventory_sales_dividend": (0, 1), "base.inventory_sales_dividend_ratio": (0, 100),
    "base.inventory_sales_dividend_historical_only": (0, 1), "base.inventory_sales_dividend_cash_protection": (0, 1),
    "base.inventory_sales_dividend_min_cash_ratio": (0, 500), "base.inventory_sales_dividend_cash_floor_ratio": (0, 500),
    "base.enable_excess_cash_dividend": (0, 1), "base.excess_cash_dividend_ratio": (0, 100),
    "base.excess_cash_dividend_min_cash_ratio": (0, 500), "base.excess_cash_dividend_recipient_mode": (0, 2),
    "base.excess_cash_dividend_recent_turns": (0, 1000),
    "base.education_temp_int_per_100_goods": (0, 100000),
    "base.total_ability": (1, 100000), "base.min_strength": (0, 100000), "base.max_strength": (0, 100000), "base.min_intelligence": (0, 100000), "base.max_intelligence": (0, 100000),
    "base.min_life": (1, 100000), "base.max_life": (1, 100000),
    "base.labor_env_cost": (0, 10**12), "base.environment_safe_harvest_ratio": (0, 1000),
    "base.max_production": (0, 10**12),
    "base.price_adjust_speed": (0, 100), "base.min_price_index": (1, 100000), "base.max_price_index": (1, 100000),
    "base.market_control_low_price_index": (1, 100000), "base.market_control_high_price_index": (1, 100000),
    "base.min_reproduce": (0, 100), "base.max_reproduce": (0, 100),
    "behavior.internal_plunder_min": (0, 100), "behavior.internal_plunder_max": (0, 100),
    "behavior.rescue_min_ratio": (0, 100), "behavior.rescue_max_ratio": (0, 100), "behavior.rescue_min_balance": (0, 10**12),
    "behavior.plunder_gain_rate": (0, 100), "behavior.invasion_fail_life_loss": (0, 100000), "behavior.invasion_strength_weight": (0, 100), "behavior.invasion_poverty_weight": (0, 100), "behavior.invasion_base_risk": (0, 100), "behavior.invasion_success_sigma": (1, 100000),
    "behavior.invasion_loot_min": (0, 100), "behavior.invasion_loot_max": (0, 100),
    "mutation.morality": (0, 100), "mutation.strength": (0, 100000), "mutation.reproduce": (0, 100), "mutation.labor": (0, 100),

    # BOT8 2.1.0/2.2.0 生态承载力与环境退化参数：
    # env_capacity 参考生态承载力 K 的思想，表示该部族环境资源可恢复到的上限。
    # env_health 使用 0-100 指标，便于 GUI 观察和与其他百分制参数对齐。
    # degradation/recovery rate 以整数缩放表达，环境健康变化由资源压力和缓冲池累积决定。
    "population.*.env_capacity": (0, 10**12),
    "population.*.env_health": (0, 100),
    "population.*.env_degradation_rate": (0, 100),
    "population.*.env_recovery_rate": (0, 100),
    "population.*.trust": (0, 100),
    "population.*.medical_level": (0, 100),
    "population.*.gov_aid_budget_ratio": (0, 100),
    "population.*.labor_tax_rate": (0, 100),
    "population.*.wealth_tax_exempt_threshold": (0, 10**12),
    "population.*.wealth_tax_threshold": (0, 10**12),
    "population.*.wealth_tax_low_rate": (0, 100),
    "population.*.wealth_tax_rate": (0, 100),
    "population.*.import_tax_rate": (0, 50),
    "population.*.trade_tax_rate": (0, 50),
    "population.*.market_control_budget_ratio": (0, 100),
    "population.*.food_subsidy_rate": (0, 100),
    "population.*.medical_subsidy_rate": (0, 100),
    "population.*.company_initial_money": (0, 10**12),
    "population.*.use_population_scaled_initials": (0, 1),
    "population.*.company_initial_money_per_capita": (0, 10**12),
    "population.*.government_initial_money_per_capita": (0, 10**12),
    "population.*.government_initial_food_rounds": (0, 100),
    "population.*.government_initial_medical_goods_ratio": (0, 1000),
    "population.*.government_initial_education_goods_ratio": (0, 1000),
    "population.*.government_initial_reproduction_goods_ratio": (0, 1000),
    "population.*.company_initial_food_rounds": (0, 100),
    "population.*.company_initial_medical_goods_ratio": (0, 1000),
    "population.*.company_initial_education_goods_ratio": (0, 1000),
    "population.*.company_initial_reproduction_goods_ratio": (0, 1000),
    "population.*.enable_repro_education_inventory_resilience": (0, 1),
    "population.*.repro_inventory_target_births_ratio": (0, 1000),
    "population.*.education_inventory_target_births_ratio": (0, 1000),
    "population.*.repro_education_inventory_resilience_weight": (0, 1000),
    "population.*.company_production_tendency": (0, 100),
    "population.*.labor_reward_ratio": (0, 100),
    "population.*.enable_wage_responsive_consumption": (0, 1),
    "population.*.wage_consumption_bonus_per_survival": (0, 100),
    "population.*.wage_consumption_bonus_cap": (0, 100),
    "population.*.production_resource_price": (0, 100000),
    "population.*.company_profit_sensitivity": (0, 100),
    "population.*.enable_company_hard_need_inventory_release": (0, 1),
    "population.*.company_hard_need_listing_multiplier": (0, 1000),
    "population.*.company_hard_need_min_listing_ratio": (0, 100),
    "population.*.individual_buy_willingness": (0, 100),
    "population.*.government_buy_willingness": (0, 100),

    "population.*.gov_education_enabled": (0, 1),
    "population.*.gov_education_budget_ratio": (0, 100),
    "population.*.gov_education_temp_int_per_100": (0, 100000),
}
