"""BOT8 参数元数据原型。

本文件是新 GUI、参数说明按钮、参数分级、预设系统和未来配置校验的统一来源。
当前阶段不替换旧 config.py；只提供结构化描述、默认值校验和 UI 生成依据。
"""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ParameterSpec:
    key: str
    default: Any
    value_type: str
    category: str
    level: str
    label_zh: str
    label_en: str = ""
    unit: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    visible_in_basic: bool = False
    visible_in_advanced: bool = True
    visible_in_debug: bool = False
    deprecated: bool = False
    experimental: bool = False
    affects_core_logic: bool = True
    requires_restart: bool = False
    depends_on: Optional[str] = None
    help_zh: str = ""


def _help(action, default, unit, phase, formula, up, down, related, outputs, user, risk):
    return f"""参数作用：{action}
默认值：{default}
单位：{unit or '无'}
影响阶段：{phase}
计算关系：{formula}
调高/开启影响：{up}
调低/关闭影响：{down}
关联参数：{related}
关联输出字段：{outputs}
普通用户是否建议修改：{user}
风险提示：{risk}""".strip()


PARAMETER_SPECS = [
    # ========================
    # 机制开关
    # ========================
    ParameterSpec(
        key="enable_market", default=True, value_type="bool", category="switches", level="A",
        label_zh="启用订单簿市场", label_en="Enable market", unit="开关", visible_in_basic=True,
        help_zh=_help("控制个体、公司与政府是否通过市场订单簿进行商品交易。", "开启", "开关", "市场交易阶段", "开启后执行公司/个体卖单、个体买单、政府最后买方和市场价格更新。", "商品通过价格与库存流通，模型更接近当前主机制。", "市场交易停用，生产、库存、工资和生存链路会显著失真。", "enable_government_orderbook_buyer、individual_buy_willingness、government_buy_willingness", "MarketFoodVolume、FoodHardNeedSatisfiedRate、CompanyInventorySoldToIndividuals", "建议保持开启。", "关闭后许多 dev27 之后的修复机制不会发挥作用。"),
    ),
    ParameterSpec(
        key="enable_government_orderbook_buyer", default=True, value_type="bool", category="switches", level="B",
        label_zh="启用政府订单簿最后买方", label_en="Enable government orderbook buyer", unit="开关", visible_in_advanced=True,
        help_zh=_help("控制政府是否在个体购买后作为最后买方购买订单簿剩余商品。", "开启", "开关", "市场交易阶段", "个体购买完成后，政府按买入意愿和财政保留规则购买剩余卖单。", "增加公司库存流通和市场收入回流，降低库存僵死。", "公司库存更容易堆积，工资和生产循环可能断裂。", "government_buy_willingness、enable_government_macro_control", "CompanyInventorySoldToGovernment、GovernmentSurplusValueTotal", "普通用户建议保持开启。", "关闭后长期稳定性通常显著下降。"),
    ),
    ParameterSpec(
        key="enable_government_macro_control", default=True, value_type="bool", category="switches", level="C",
        label_zh="启用政府宏观调控", label_en="Enable government macro control", unit="开关", visible_in_advanced=True,
        help_zh=_help("控制旧宏观调控相关逻辑是否启用。", "开启", "开关", "政府调控阶段", "与订单簿最后买方分离；用于保留公共库存缓冲和宏观调控语义。", "政府调控相关输出更完整。", "仅保留市场基础交易，公共调控能力降低。", "enable_government_orderbook_buyer、government_buy_willingness", "GovernmentFood、GovernmentSurplusValueTotal、MarketStabilityIndex", "高级用户修改。", "该开关与订单簿最后买方已经拆分，不能再混为一个机制。"),
    ),
    ParameterSpec(
        key="enable_tax_system", default=True, value_type="bool", category="switches", level="C",
        label_zh="启用税收系统", label_en="Enable tax system", unit="开关", visible_in_advanced=True,
        help_zh=_help("控制税收系统是否启用。当前主要生效的是富人资产税。", "开启", "开关", "税收/政府财政阶段", "当前交易税、进口税、劳动税多数为历史保留或弱生效字段。", "政府财政可通过富人资产税获得回流。", "政府财政回流减少。", "wealth_tax_threshold、wealth_tax_rate、trade_tax_rate、import_tax_rate", "GovernmentTaxIncome、WealthTaxIncome", "高级用户修改。", "不要误以为所有税率字段都在主交易路径中完全生效。"),
    ),
    ParameterSpec(
        key="enable_internal_plunder", default=True, value_type="bool", category="switches", level="C",
        label_zh="启用内部掠夺", label_en="Enable internal plunder", unit="开关", visible_in_advanced=True,
        help_zh=_help("控制同一部族内部个体之间的掠夺行为。", "开启", "开关", "社会行为阶段", "按个体道德、贫困和风险参数决定是否发生内部财富转移与系统损耗。", "增加社会不稳定压力和财富再分布。", "减少内部冲击，但可能使模型少一个真实压力源。", "internal_plunder_min、internal_plunder_max、plunder_gain_rate", "InternalPlunderVictimLoss、InternalPlunderGain、InternalPlunderSystemLoss", "默认保持开启；实验时可关闭。", "早期测试显示简单关闭未必更稳定。"),
    ),

    # ========================
    # 基础运行参数
    # ========================
    ParameterSpec(
        key="max_turns", default=200, value_type="int", category="base", level="A",
        label_zh="模拟最大回合数", label_en="Maximum turns", unit="回合", min_value=1, max_value=1000000, step=1, visible_in_basic=True,
        help_zh=_help("设置本次模拟最多运行多少回合。", "200", "回合", "运行控制", "主循环最多执行 max_turns 次；人口归零时提前停止。", "能观察更长期的稳定性与资源极限。", "运行更快，但可能看不到长期问题。", "save_interval、random_seed", "Turn、PopCount、BirthCount、DeathCount", "建议普通用户可修改。", "回合数过高时应使用批量模式，避免实时图表拖慢。"),
    ),
    ParameterSpec(
        key="population_count", default=1, value_type="int", category="base", level="A",
        label_zh="启用部族数量", label_en="Population group count", unit="个", min_value=1, max_value=10, step=1, visible_in_basic=True,
        help_zh=_help("设置参与模拟的部族数量。", "1", "个", "初始化阶段", "按 A-J 标签启用对应部族配置。", "可以观察多部族市场、侵袭和资源竞争。", "模型更简单，便于单部族机制校准。", "MAX_POPULATION_TYPES、DEFAULT_POPULATION_CONFIG", "PopulationCount、TradeFlow、InvasionGainTotal", "普通用户可修改。", "当前部分逻辑历史上曾只稳定支持 1-3 部族，多部族需回归测试。"),
    ),
    ParameterSpec(
        key="initial_population", default=5, value_type="int", category="base", level="A",
        label_zh="每个部族初始人口", label_en="Initial population", unit="人", min_value=1, max_value=100000, step=1, visible_in_basic=True,
        help_zh=_help("设置每个部族开始时创建的个体数量。", "5", "人", "初始化阶段", "每个启用部族初始化 initial_population 个个体。", "初始劳动力、消费需求和繁殖机会增加。", "更容易出现小族群随机断代与劳动空窗。", "use_population_scaled_initials、company_initial_money_per_capita", "PopCount、CompanyInitialMoneyEffective", "普通用户可修改。", "关闭按人口规模初始资产时，人口规模改变可能导致初始资源不匹配。"),
    ),
    ParameterSpec(
        key="initial_balance", default=100, value_type="float", category="base", level="B",
        label_zh="个体初始货币", label_en="Initial individual money", unit="货币", min_value=0, max_value=100000, step=1, visible_in_advanced=True,
        help_zh=_help("设置每个初始个体拥有的货币余额。", "100", "货币", "初始化阶段", "初始个体 balance = initial_balance。", "初期购买力增强。", "初期市场消费不足，可能更依赖工资。", "labor_reward_ratio、individual_buy_willingness", "AvgMoney、MoneyGini、WorkerMarketSpending", "常规研究可修改。", "过高会放大早期消费和生育压力。"),
    ),
    ParameterSpec(
        key="survival_cost", default=100, value_type="float", category="base", level="B",
        label_zh="每回合基础生存食物需求", label_en="Survival food cost", unit="食物", min_value=1, max_value=100000, step=1, visible_in_advanced=True,
        help_zh=_help("设置每个个体每回合基础生存所需食物数量。", "100", "食物", "生存阶段、繁殖条件、医疗刚需", "food_hard_need = max(0, survival_cost - food)。", "生存压力和父代食物安全要求提高。", "生存压力降低，人口更容易增长。", "child_initial_food、parent_food_required_for_birth_multiplier、reproduction_goods_required_per_birth", "FoodHardNeedAmount、FoodShortageCount、ParentFoodRequirement", "高级用户修改。", "这是核心尺度参数，改动会影响大量机制。"),
    ),
    ParameterSpec(
        key="resource_regen", default=2000, value_type="float", category="environment", level="B",
        label_zh="每回合环境资源再生量", label_en="Resource regeneration", unit="资源", min_value=0, max_value=100000000, step=1, visible_in_advanced=True,
        help_zh=_help("设置环境每回合可再生的生产资源量。", "2000", "资源", "资源再生与生产阶段", "ResourceUseToRegenRatio = PopulationResourceUsed / resource_regen。", "资源上限提高，可承载更高人口。", "资源更快成为人口上限。", "initial_env_resource、environment_safe_harvest_ratio", "ResourceUseToRegenRatio、LaborResourceUnusedRate、EnvHealth", "高级用户修改。", "过高可能长期达不到资源极限；过低会使模型进入资源压力测试。"),
    ),

    # ========================
    # 繁殖 / 新生儿
    # ========================
    ParameterSpec(
        key="child_initial_balance", default=100, value_type="int", category="legacy", level="E",
        label_zh="旧版新生儿初始货币兼容值", label_en="Legacy child initial balance", unit="兼容单位", min_value=0, max_value=10000, step=1,
        visible_in_basic=False, visible_in_advanced=False, visible_in_debug=True, deprecated=True, affects_core_logic=False,
        help_zh=_help("旧版本用于表示新生个体初始货币的兼容字段。", "100", "兼容单位", "配置兼容", "当前已拆分为 child_initial_money、child_initial_food、reproduction_goods_required_per_birth。", "不建议调高。", "不建议调低。", "child_initial_money、child_initial_food、reproduction_goods_required_per_birth", "无直接推荐输出字段", "不建议普通用户修改。", "后续 GUI 应隐藏该字段，只作为旧设置文件兼容入口。"),
    ),
    ParameterSpec(
        key="child_initial_money", default=0, value_type="float", category="reproduction", level="C",
        label_zh="新生儿初始货币转移上限", label_en="Child initial money transfer", unit="货币", min_value=0, max_value=100000, step=1, visible_in_advanced=True,
        help_zh=_help("设置出生时父代最多转移给子代的货币。", "0", "货币", "繁殖阶段", "money_transfer = min(parent.balance, child_initial_money)。", "新生代初始购买力增强。", "新生代更依赖后续工资/救助/家庭资源。", "child_initial_food、reproduction_goods_required_per_birth", "BirthCount、Age0AvgMoney", "高级用户修改。", "不应再用旧 child_initial_balance 代替该参数。"),
    ),
    ParameterSpec(
        key="child_initial_food", default=100, value_type="float", category="reproduction", level="B",
        label_zh="新生儿初始食物", label_en="Child initial food", unit="食物", min_value=0, max_value=100000, step=1, visible_in_advanced=True,
        help_zh=_help("设置出生时父代转移给子代的食物数量。", "100", "食物", "繁殖阶段", "子代出生当回合跳过生存消耗，该食物用于下一回合生存。", "新生儿早期生存更稳。", "新生儿更快进入食物刚需。", "survival_cost、parent_food_required_for_birth_multiplier", "NewbornSurvivalSkippedCount、Age0AvgFood", "高级用户修改。", "不应把该参数同时当作货币或生育用品数量。"),
    ),
    ParameterSpec(
        key="reproduction_goods_required_per_birth", default=100, value_type="float", category="reproduction", level="B",
        label_zh="每次出生所需生育用品", label_en="Reproduction goods required per birth", unit="生育用品", min_value=0, max_value=100000, step=1, visible_in_advanced=True,
        help_zh=_help("设置每次成功出生消耗的生育用品数量。", "100", "生育用品", "繁殖阶段与生育用品购买阶段", "出生时扣除 reproduction_goods_required_per_birth。", "出生物资门槛更高，出生减少。", "出生物资门槛降低，人口更易增长。", "company_initial_reproduction_goods_ratio、ReproductionHardNeedSatisfiedRate", "BirthBlockedNoReproductionGoods、ReproductionHardNeedAmount", "高级用户修改。", "不建议用该参数强行控制人口，应优先通过生产与市场链路调节。"),
    ),
    ParameterSpec(
        key="parent_food_required_for_birth_multiplier", default=3, value_type="float", category="reproduction", level="C",
        label_zh="父代出生前食物安全倍数", label_en="Parent food safety multiplier for birth", unit="倍", min_value=0, max_value=20, step=0.1, visible_in_advanced=True,
        help_zh=_help("设置父代在出生前需要保有的食物安全库存倍数。", "3", "倍 survival_cost", "繁殖判定阶段", "ParentFoodRequirement = survival_cost × parent_food_required_for_birth_multiplier。", "出生更谨慎，断代风险可能上升。", "出生更容易，但可能带来食物压力。", "survival_cost、child_initial_food", "BirthBlockedFoodSafetyWithReproductionGoods、ParentFoodGap", "高级用户修改。", "当前原则是不优先降低该参数，而应先修生产和市场链路。"),
    ),
    ParameterSpec(
        key="enable_secondary_birth_check", default=True, value_type="bool", category="reproduction", level="B",
        label_zh="启用二次减概率生育判定", label_en="Enable secondary reduced-probability birth check", unit="开关", visible_in_advanced=True,
        help_zh=_help("允许已成功生育且仍满足完整条件的个体再进行一次减概率生育判定。", "开启", "开关", "繁殖阶段", "secondary_chance = reproduce × secondary_birth_chance_ratio。", "低人口资源宽松时可能更快增长。", "出生次数减少。", "secondary_birth_chance_ratio、reproduction_goods_required_per_birth", "SecondaryBirthSuccessCount、BirthCount", "高级用户可修改。", "比例过高会放大后续食物和医疗压力。"),
    ),
    ParameterSpec(
        key="secondary_birth_chance_ratio", default=50, value_type="float", category="reproduction", level="C",
        label_zh="二次生育概率比例", label_en="Secondary birth chance ratio", unit="%", min_value=0, max_value=100, step=1, visible_in_advanced=True,
        depends_on="enable_secondary_birth_check",
        help_zh=_help("设置第二次生育判定相对原生育倾向的折减比例。", "50", "%", "繁殖阶段", "第二次判定概率 = reproduce × secondary_birth_chance_ratio / 100。", "二次出生更多。", "二次出生更少。", "enable_secondary_birth_check、reproduce", "SecondaryBirthSuccessCount", "高级用户修改。", "过高会导致早期人口峰值过大。"),
    ),

    # ========================
    # 初始资产规模关联
    # ========================
    ParameterSpec(
        key="use_population_scaled_initials", default=1, value_type="bool", category="initial_conditions", level="A",
        label_zh="按族群规模自动计算初始资金和库存", label_en="Scale initial money and inventory by population size", unit="开关", visible_in_basic=True,
        help_zh=_help("开启后，公司和政府初始资金/库存按初始人口自动计算。", "开启", "开关", "初始化阶段", "公司初始货币 = 初始人口 × company_initial_money_per_capita。", "不同人口规模下初始条件更一致。", "允许手动输入固定初始资产。", "company_initial_money_per_capita、government_initial_money_per_capita、company_initial_food_rounds", "UsePopulationScaledInitials、CompanyInitialMoneyEffective、GovernmentInitialMoneyEffective", "建议保持开启。", "关闭后手动资金/库存若与人口规模不匹配，会造成非预期崩溃或膨胀。"),
    ),
    ParameterSpec(
        key="company_initial_money_per_capita", default=400, value_type="float", category="initial_conditions", level="B",
        label_zh="公司人均初始资金", label_en="Company initial money per capita", unit="货币/人", min_value=0, max_value=100000, step=1, visible_in_advanced=True,
        depends_on="use_population_scaled_initials",
        help_zh=_help("按初始人口计算公司初始资金。", "400", "货币/人", "初始化阶段", "CompanyInitialMoneyEffective = initial_population × company_initial_money_per_capita。", "公司抗工资和生产资源冲击能力增强。", "公司现金流更紧，早期生产可能不足。", "use_population_scaled_initials、labor_reward_ratio", "CompanyInitialMoneyEffective、CompanyCashAfterWages", "高级用户修改。", "过高会推高早期生产和人口峰值。"),
    ),
    ParameterSpec(
        key="government_initial_money_per_capita", default=20, value_type="float", category="initial_conditions", level="B",
        label_zh="政府人均初始财政", label_en="Government initial money per capita", unit="货币/人", min_value=0, max_value=100000, step=1, visible_in_advanced=True,
        depends_on="use_population_scaled_initials",
        help_zh=_help("按初始人口计算政府初始财政。", "20", "货币/人", "初始化阶段", "GovernmentInitialMoneyEffective = initial_population × government_initial_money_per_capita。", "政府早期订单簿购买和救助能力增强。", "政府缓冲减弱。", "enable_government_orderbook_buyer、government_buy_willingness", "GovernmentInitialMoneyEffective、GovernmentDeposit", "高级用户修改。", "过高可能让政府过度吸收市场库存。"),
    ),
    ParameterSpec(
        key="company_initial_food_rounds", default=3, value_type="float", category="initial_conditions", level="B",
        label_zh="公司初始食物库存回合数", label_en="Company initial food rounds", unit="回合", min_value=0, max_value=1000, step=0.1, visible_in_advanced=True,
        help_zh=_help("按人口和 survival_cost 计算公司初始食物库存。", "3", "回合", "初始化阶段", "公司初始食物 = 初始人口 × survival_cost × company_initial_food_rounds。", "早期市场食物供给更稳。", "早期食物刚需更可能无库存可买。", "survival_cost、use_population_scaled_initials", "CompanyInitialFoodStock、FoodCompanySellableStock", "高级用户修改。", "过高会延后资源生产压力显现。"),
    ),
    ParameterSpec(
        key="company_initial_reproduction_goods_ratio", default=100, value_type="float", category="initial_conditions", level="B",
        label_zh="公司初始生育用品比例", label_en="Company initial reproduction goods ratio", unit="% 每人一次出生量", min_value=0, max_value=10000, step=1, visible_in_advanced=True,
        help_zh=_help("按初始人口和每次出生所需生育用品计算公司初始生育用品库存。", "100", "%", "初始化阶段", "库存 = 初始人口 × reproduction_goods_required_per_birth × ratio/100。", "早期出生物资更充足。", "小族群早期可能更容易因生育用品不足断代。", "reproduction_goods_required_per_birth、enable_repro_education_inventory_resilience", "CompanyInitialReproductionStockTarget、ReproductionCompanyStock", "高级用户修改。", "过高会推高早期出生峰值。"),
    ),

    # ========================
    # 公司/生产/工资
    # ========================
    ParameterSpec(
        key="labor_reward_ratio", default=60, value_type="float", category="company", level="B",
        label_zh="劳动产出工资比例", label_en="Labor reward ratio", unit="%", min_value=0, max_value=100, step=1, visible_in_advanced=True,
        help_zh=_help("控制公司将劳动产出市场价值中的多少比例作为工资支付给劳动者。", "60", "%", "公司化劳动与工资阶段", "计划工资 = 产出市场价值 × labor_reward_ratio/100。", "个体购买力和消费回流增强。", "公司留存提高但个体购买力下降。", "company_initial_money_per_capita、enable_wage_responsive_consumption", "TotalWagesPaid、AvgWagePerWorker、WorkerMarketSpendingToCompany", "高级用户修改。", "过高可能造成公司现金流压力；过低会造成个体刚需购买不足。"),
    ),
    ParameterSpec(
        key="company_wage_ratio", default=30, value_type="float", category="legacy", level="E",
        label_zh="旧版公司工资比例", label_en="Legacy company wage ratio", unit="%", min_value=0, max_value=100, step=1, visible_in_debug=True,
        deprecated=True, affects_core_logic=False,
        help_zh=_help("旧版本工资字段；当前主工资逻辑使用 labor_reward_ratio。", "30", "%", "兼容字段", "不建议在新机制中使用。", "无建议。", "无建议。", "labor_reward_ratio", "无直接推荐输出字段", "普通用户不应修改。", "后续应从普通 GUI 隐藏，避免与 labor_reward_ratio 混淆。"),
    ),
    ParameterSpec(
        key="company_production_tendency", default=60, value_type="float", category="company", level="C",
        label_zh="公司生产参与倾向", label_en="Company production tendency", unit="%", min_value=0, max_value=100, step=1, visible_in_advanced=True,
        help_zh=_help("影响公司将劳动候选转化为生产劳动的倾向。", "60", "%", "劳动分配与生产阶段", "较高时更多候选进入生产分配。", "实际劳动更频繁，生产与工资增加。", "劳动空窗增加。", "labor_reward_ratio、company_profit_sensitivity", "LaborCandidateRawCount、ActualWorkerCountWhenPopBelow5", "高级用户修改。", "过低会导致低人口劳动链断档。"),
    ),
    ParameterSpec(
        key="enable_wage_responsive_consumption", default=1, value_type="bool", category="market", level="B",
        label_zh="启用工资响应消费", label_en="Enable wage responsive consumption", unit="开关", visible_in_advanced=True,
        help_zh=_help("让当回合收到工资的个体提高储备类消费意愿。", "开启", "开关", "市场购买阶段", "工资越高，有效买入意愿越高，但刚需预算已有独立规则。", "工资更快通过消费回流公司。", "消费意愿只使用基础值。", "wage_consumption_bonus_per_survival、wage_consumption_bonus_cap", "EffectiveBuyWillingnessAvg、WageFundedMarketSpending", "高级用户修改。", "不应让该机制覆盖食物/医疗/生育刚需预算规则。"),
    ),
    ParameterSpec(
        key="enable_company_hard_need_inventory_release", default=1, value_type="bool", category="market", level="B",
        label_zh="启用公司刚需库存释放", label_en="Enable company hard-need inventory release", unit="开关", visible_in_advanced=True,
        help_zh=_help("当食物或医疗刚需存在时，公司更积极把对应历史库存挂入订单簿。", "开启", "开关", "订单簿卖单生成阶段", "刚需压力存在时，可售库存不再被初始库存目标过度锁住。", "减少公司有库存但市场无货的情况。", "公司更保守保留库存，刚需可能买不到。", "company_hard_need_listing_multiplier、company_hard_need_min_listing_ratio", "FoodCompanyHardNeedReleaseListed、HardNeedBlockedByNoMarketStock", "建议保持开启。", "当前只建议对食物/医疗使用，生育用品全量释放可能放大出生波动。"),
    ),
    ParameterSpec(
        key="enable_hard_need_production_response", default=1, value_type="bool", category="company_production", level="B",
        label_zh="启用硬刚需生产响应", label_en="Enable hard-need production response", unit="开关", visible_in_advanced=True, experimental=True,
        help_zh=_help("当硬刚需未满足且环境资源未接近上限时，提高公司对相关商品的生产倾向。", "开启", "开关", "公司生产权重计算阶段", "生产权重 += 上一回合未满足刚需 × 响应权重。", "闲置资源更容易转化为刚需商品。", "生产更依赖利润和旧权重。", "hard_need_resource_use_threshold、hard_need_production_response_weight", "FoodHardNeedProductionBonus、ResourceUseToRegenRatio", "建议保持开启。", "权重过高可能导致生产结构过度集中。"),
    ),
    ParameterSpec(
        key="hard_need_resource_use_threshold", default=80, value_type="float", category="company_production", level="C",
        label_zh="硬刚需生产响应资源使用阈值", label_en="Hard-need production resource threshold", unit="%", min_value=0, max_value=1000, step=1, visible_in_advanced=True,
        depends_on="enable_hard_need_production_response",
        help_zh=_help("当资源使用率低于该阈值时，硬刚需未满足可增加生产权重。", "80", "%", "公司生产权重计算阶段", "ResourceUseToRegenRatio < threshold 时允许响应。", "更长时间允许生产响应。", "更早停止额外生产响应。", "enable_hard_need_production_response", "ResourceUseToRegenRatio、HardNeedProductionResponseEnabled", "高级用户修改。", "过高可能接近资源极限时仍扩大生产。"),
    ),

    # ========================
    # 市场/购买意愿
    # ========================
    ParameterSpec(
        key="individual_buy_willingness", default=80, value_type="float", category="market", level="B",
        label_zh="个体储备消费意愿", label_en="Individual buy willingness", unit="点", min_value=0, max_value=100, step=1, visible_in_advanced=True,
        help_zh=_help("控制个体对储备类商品的基础购买意愿。食物/医疗/生育刚需已有独立预算规则。", "80", "点", "市场购买阶段", "储备消费预算会乘以有效买入意愿。", "储备购买增加。", "储备购买减少。", "enable_wage_responsive_consumption、wage_consumption_bonus_cap", "EffectiveBuyWillingnessAvg、ReserveNeedSpendingTotal", "高级用户修改。", "不要用该参数修复刚需消费；刚需预算由 dev40 独立规则处理。"),
    ),
    ParameterSpec(
        key="government_buy_willingness", default=60, value_type="float", category="market", level="B",
        label_zh="政府订单簿买入意愿", label_en="Government buy willingness", unit="点", min_value=0, max_value=100, step=1, visible_in_advanced=True,
        help_zh=_help("控制政府作为订单簿最后买方时的买入积极程度。", "60", "点", "政府订单簿购买阶段", "影响政府购买剩余卖单的预算释放和价格敏感度。", "公司库存更容易销售给政府。", "政府收储减少，公司库存可能堆积。", "enable_government_orderbook_buyer", "CompanyInventorySoldToGovernment、GovernmentSurplusValueTotal", "高级用户修改。", "过高可能让政府过快吸收市场库存并产生剩余价值删除。"),
    ),

    # ========================
    # 族群基础属性
    # ========================
    ParameterSpec(
        key="morality", default=60, value_type="float", category="population", level="B",
        label_zh="亲社会倾向", label_en="Prosocial tendency", unit="点", min_value=0, max_value=100, step=1, visible_in_advanced=True,
        help_zh=_help("影响施舍、掠夺等社会行为倾向。", "60", "点", "社会行为阶段", "道德越高，掠夺风险通常越低。", "内部冲突下降，互助行为可能增加。", "内部冲突风险上升。", "enable_internal_plunder、enable_moral_donation", "AvgMorality、InternalPlunderVictimLoss", "常规研究可修改。", "字段名仍为 morality，UI 后续建议显示为亲社会倾向。"),
    ),
    ParameterSpec(
        key="strength", default=300, value_type="float", category="population", level="B",
        label_zh="体质值", label_en="Constitution", unit="点", min_value=0, max_value=10000, step=1, visible_in_advanced=True,
        help_zh=_help("影响个体疾病、濒死和冲突相关能力。", "300", "点", "生存、疾病、冲突阶段", "历史字段名为 strength，但当前语义更接近体质/生命抵抗。", "生存和抵抗能力增强。", "疾病和濒死风险上升。", "min_strength、max_strength、medical_level", "AvgStrength、CriticalCount", "常规研究可修改。", "UI 应逐步从“武力”改名为“体质值”。"),
    ),
    ParameterSpec(
        key="reproduce", default=50, value_type="float", category="population", level="B",
        label_zh="繁殖倾向", label_en="Reproduction tendency", unit="点", min_value=0, max_value=100, step=1, visible_in_advanced=True,
        help_zh=_help("影响个体通过生育随机判定的概率。", "50", "点", "繁殖阶段", "基础出生判定约与 reproduce 成正比，同时受食物、生育用品、健康条件约束。", "出生尝试更容易成功。", "出生更少。", "max_reproduce、secondary_birth_chance_ratio", "AvgReproduceTendency、BirthBlockedLowReproduceChance", "常规研究可修改。", "提高该值会把压力转移到食物/生育用品链路，不能单独保证稳定。"),
    ),
    ParameterSpec(
        key="labor", default=55, value_type="float", category="population", level="B",
        label_zh="生产参与倾向", label_en="Labor participation tendency", unit="点", min_value=0, max_value=100, step=1, visible_in_advanced=True,
        help_zh=_help("影响个体成为劳动候选者的概率。", "55", "点", "劳动候选阶段", "劳动倾向越高，个体越可能参与公司生产。", "生产、工资和消费回流增加。", "低人口时更容易出现劳动空窗。", "company_production_tendency、labor_reward_ratio", "LaborCandidateRawCount、WorkersCount", "常规研究可修改。", "过高可能加速资源消耗，需结合资源利用率观察。"),
    ),
]


# ========================
# 系统级第四阶段：第二批人工精写参数说明
# ========================
# 这些参数从自动补齐升级为人工精写，优先覆盖初始条件、市场、生产响应、价格和寿命等高价值参数。
PARAMETER_SPECS.extend([
    ParameterSpec(
        key="enable_initial_age_distribution", default=False, value_type="bool", category="initial_conditions", level="C",
        label_zh="启用初始年龄分布", label_en="Enable initial age distribution", unit="开关", visible_in_advanced=True,
        help_zh=_help("控制初始个体是否拥有分散年龄，而不是全部从同一年龄起点开始。", "关闭", "开关", "初始化阶段", "开启后初始 age_round 按 initial_age_distribution_ratio 生成。", "初始死亡波更分散，更接近自然族群。", "初始个体更接近同龄 cohort，适合控制实验。", "initial_age_distribution_ratio、min_life、max_life", "AvgAgeRound、DeathsByLifeEndWhenPopulationBelow5", "高级用户修改。", "开启后会改变早期寿命结构，需与旧基线对比。"),
    ),
    ParameterSpec(
        key="initial_age_distribution_ratio", default=60, value_type="float", category="initial_conditions", level="C",
        label_zh="初始年龄分布比例", label_en="Initial age distribution ratio", unit="% min_life", min_value=0, max_value=100, step=1, visible_in_advanced=True, depends_on="enable_initial_age_distribution",
        help_zh=_help("设置初始个体年龄分布上限相对最低寿命的比例。", "60", "%", "初始化阶段", "初始年龄上限 = min_life × initial_age_distribution_ratio / 100。", "初始年龄更分散，早期寿命压力更接近真实族群。", "初始个体年龄更接近 0。", "enable_initial_age_distribution、min_life", "InitialAgeRounds、AvgAgeRound", "高级用户修改。", "比例过高可能让部分个体开局接近寿命尾部。"),
    ),
    ParameterSpec(
        key="enable_small_group_initial_conditions", default=True, value_type="bool", category="initial_conditions", level="B",
        label_zh="启用小族群正常初始条件", label_en="Enable small-group initial conditions", unit="开关", visible_in_advanced=True,
        help_zh=_help("当初始人口较少时，给予按规则计算的基础食物、医疗和生育用品起点。", "开启", "开关", "初始化阶段", "当 initial_population <= 阈值时应用 small_group_* 参数。", "小族群开局不再像完全裸启动，长期测试更稳定。", "小族群更容易因开局物资不足断代。", "small_group_initial_population_threshold、small_group_initial_food_rounds", "Age0AvgFood、CompanyInitialReproductionStockTarget", "建议保持开启。", "这只影响初始条件，不是运行时补贴。"),
    ),
    ParameterSpec(
        key="small_group_initial_food_rounds", default=5, value_type="float", category="initial_conditions", level="C",
        label_zh="小族群初始食物回合数", label_en="Small-group initial food rounds", unit="回合", min_value=0, max_value=100, step=0.1, visible_in_advanced=True, depends_on="enable_small_group_initial_conditions",
        help_zh=_help("设置小族群开局时个体或系统拥有的基础食物缓冲。", "5", "回合", "初始化阶段", "初始食物缓冲与 survival_cost 成比例。", "早期食物压力降低。", "更早暴露市场/生产链路问题。", "survival_cost、small_group_initial_population_threshold", "FoodZeroCount、FoodShortageCount", "高级用户修改。", "过高会推迟资源压力显现。"),
    ),
    ParameterSpec(
        key="company_initial_medical_goods_ratio", default=50, value_type="float", category="initial_conditions", level="B",
        label_zh="公司初始医疗用品比例", label_en="Company initial medical goods ratio", unit="% 每人一单位", min_value=0, max_value=10000, step=1, visible_in_advanced=True,
        help_zh=_help("按初始人口与 survival_cost 计算公司医疗用品初始库存。", "50", "%", "初始化阶段", "公司初始医疗用品 = 初始人口 × survival_cost × ratio/100。", "早期疾病和濒死恢复更稳定。", "早期医疗刚需更依赖生产响应。", "survival_cost、use_population_scaled_initials", "CompanyMedicalGoodsStock、MedicalHardNeedSatisfiedRate", "高级用户修改。", "过高会削弱医疗生产链路压力测试。"),
    ),
    ParameterSpec(
        key="company_initial_education_goods_ratio", default=100, value_type="float", category="initial_conditions", level="B",
        label_zh="公司初始教育用品比例", label_en="Company initial education goods ratio", unit="% 每人一单位", min_value=0, max_value=10000, step=1, visible_in_advanced=True,
        help_zh=_help("按初始人口计算公司教育用品初始库存。", "100", "%", "初始化阶段", "教育用品库存 = 初始人口 × survival_cost × ratio/100。", "教育资源更充足，新生代临时智慧提升更稳定。", "教育用品更快进入短缺。", "education_temp_int_per_100_goods、enable_repro_education_inventory_resilience", "CompanyInitialEducationStockTarget、EducationCompanyStock", "高级用户修改。", "当前教育机制仍较轻，后续需结合教育研究预设校准。"),
    ),
    ParameterSpec(
        key="government_initial_food_rounds", default=1, value_type="float", category="initial_conditions", level="B",
        label_zh="政府初始食物库存回合数", label_en="Government initial food rounds", unit="回合", min_value=0, max_value=1000, step=0.1, visible_in_advanced=True,
        help_zh=_help("按初始人口和 survival_cost 计算政府公共食物库存。", "1", "回合", "初始化阶段", "政府初始食物 = 初始人口 × survival_cost × rounds。", "政府早期救助缓冲更强。", "早期食物风险更多由市场承担。", "enable_government_aid、survival_cost", "GovernmentFood、FoodAidReceivedCount", "高级用户修改。", "过高会让政府库存替代市场压力。"),
    ),
    ParameterSpec(
        key="enable_repro_education_inventory_resilience", default=1, value_type="bool", category="company", level="B",
        label_zh="启用生育/教育用品库存韧性", label_en="Enable reproduction/education inventory resilience", unit="开关", visible_in_advanced=True,
        help_zh=_help("让公司生产权重对生育用品和教育用品库存缺口更敏感。", "开启", "开关", "公司生产权重阶段", "库存缺口按 repro_education_inventory_resilience_weight 转化为生产权重。", "更容易补充生育和教育用品库存。", "公司更依赖利润和旧权重选择商品。", "repro_inventory_target_births_ratio、education_inventory_target_births_ratio", "ReproductionInventoryResilienceWeightAdded、EducationInventoryResilienceWeightAdded", "建议保持开启。", "权重过高会挤出食物/医疗生产。"),
    ),
    ParameterSpec(
        key="repro_education_inventory_resilience_weight", default=50, value_type="float", category="company", level="C",
        label_zh="生育/教育库存韧性权重", label_en="Repro/education inventory resilience weight", unit="权重", min_value=0, max_value=1000, step=1, visible_in_advanced=True, depends_on="enable_repro_education_inventory_resilience",
        help_zh=_help("控制生育用品和教育用品库存缺口转化为生产权重的强度。", "50", "权重", "公司生产权重阶段", "生产权重 += 库存缺口 × 权重系数。", "更积极补库存。", "库存缺口响应变弱。", "repro_inventory_target_births_ratio、education_inventory_target_births_ratio", "ReproductionInventoryResilienceWeightAdded、EducationInventoryResilienceWeightAdded", "高级用户修改。", "过高会造成生产结构偏向生育/教育用品。"),
    ),
    ParameterSpec(
        key="food_hard_need_production_weight", default=120, value_type="float", category="company", level="C",
        label_zh="食物刚需生产响应权重", label_en="Food hard-need production weight", unit="权重", min_value=0, max_value=1000, step=1, visible_in_advanced=True, depends_on="enable_hard_need_production_response",
        help_zh=_help("控制食物刚需未满足时对食物生产权重的额外提升。", "120", "权重", "公司生产权重阶段", "FoodHardNeedProductionBonus 与该权重成正比。", "食物生产对刚需短缺更敏感。", "食物短缺更多依赖原有利润和库存逻辑解决。", "hard_need_production_response_weight、hard_need_resource_use_threshold", "FoodHardNeedProductionBonus、FoodHardNeedSatisfiedRate", "高级用户修改。", "过高可能挤出医疗/生育用品生产。"),
    ),
    ParameterSpec(
        key="medical_hard_need_production_weight", default=100, value_type="float", category="company", level="C",
        label_zh="医疗刚需生产响应权重", label_en="Medical hard-need production weight", unit="权重", min_value=0, max_value=1000, step=1, visible_in_advanced=True, depends_on="enable_hard_need_production_response",
        help_zh=_help("控制医疗刚需未满足时对医疗用品生产权重的额外提升。", "100", "权重", "公司生产权重阶段", "MedicalHardNeedProductionBonus 与该权重成正比。", "医疗用品生产更积极响应疾病与濒死压力。", "医疗用品更多依赖原有生产权重。", "hard_need_production_response_weight、medical_subsidy_rate", "MedicalHardNeedProductionBonus、MedicalHardNeedSatisfiedRate", "高级用户修改。", "过高可能让医疗库存长期过剩。"),
    ),
    ParameterSpec(
        key="reproduction_hard_need_production_weight", default=80, value_type="float", category="company", level="C",
        label_zh="生育用品刚需生产响应权重", label_en="Reproduction hard-need production weight", unit="权重", min_value=0, max_value=1000, step=1, visible_in_advanced=True, depends_on="enable_hard_need_production_response",
        help_zh=_help("控制生育用品刚需未满足时对生育用品生产权重的额外提升。", "80", "权重", "公司生产权重阶段", "ReproductionHardNeedProductionBonus 与该权重成正比。", "生育用品更容易补足。", "出生物资更依赖库存韧性和利润逻辑。", "reproduction_goods_required_per_birth、enable_repro_education_inventory_resilience", "ReproductionHardNeedProductionBonus、BirthBlockedNoReproductionGoods", "高级用户修改。", "过高会推高出生峰值并增加后续资源压力。"),
    ),
    ParameterSpec(
        key="company_hard_need_listing_multiplier", default=100, value_type="float", category="market", level="C",
        label_zh="公司刚需库存上架倍数", label_en="Company hard-need listing multiplier", unit="%", min_value=0, max_value=1000, step=1, visible_in_advanced=True, depends_on="enable_company_hard_need_inventory_release",
        help_zh=_help("控制食物/医疗刚需压力下公司库存进入订单簿的额外上架力度。", "100", "%", "订单簿上架阶段", "存在刚需压力时，上架量按该倍数放大。", "刚需商品更容易买到。", "公司更保守保留库存。", "company_hard_need_min_listing_ratio、enable_company_hard_need_inventory_release", "FoodCompanyHardNeedReleaseListed、MedicalCompanyHardNeedReleaseListed", "高级用户修改。", "过高可能使公司库存下降过快。"),
    ),
    ParameterSpec(
        key="company_hard_need_min_listing_ratio", default=50, value_type="float", category="market", level="C",
        label_zh="公司刚需最低上架比例", label_en="Company hard-need minimum listing ratio", unit="%", min_value=0, max_value=100, step=1, visible_in_advanced=True, depends_on="enable_company_hard_need_inventory_release",
        help_zh=_help("设置刚需压力下公司可售库存的最低上架比例。", "50", "%", "订单簿上架阶段", "最低上架量 = 可售库存 × company_hard_need_min_listing_ratio / 100。", "刚需期间公司释放库存更积极。", "公司更倾向保留库存。", "company_hard_need_listing_multiplier", "CompanyHardNeedReleaseEnabledCount、FoodCompanySellableStock", "高级用户修改。", "过高会让市场短期供给充足但公司库存缓冲降低。"),
    ),
    ParameterSpec(
        key="wage_consumption_bonus_per_survival", default=10, value_type="float", category="market", level="C",
        label_zh="工资响应消费增益", label_en="Wage responsive consumption bonus", unit="意愿点/生存成本", min_value=0, max_value=100, step=1, visible_in_advanced=True, depends_on="enable_wage_responsive_consumption",
        help_zh=_help("控制当回合工资收入提高个体有效买入意愿的强度。", "10", "点", "订单簿购买预算阶段", "工资约等于 survival_cost 时增加该数值的买入意愿。", "工资更快转化为消费。", "工资更多留存在个体现金中。", "wage_consumption_bonus_cap、labor_reward_ratio", "WageConsumptionBonusAvg、WorkerMarketSpendingToCompany", "高级用户修改。", "过高可能让储备消费过强。"),
    ),
    ParameterSpec(
        key="wage_consumption_bonus_cap", default=20, value_type="float", category="market", level="C",
        label_zh="工资响应消费增益上限", label_en="Wage responsive consumption cap", unit="意愿点", min_value=0, max_value=100, step=1, visible_in_advanced=True, depends_on="enable_wage_responsive_consumption",
        help_zh=_help("限制工资响应消费最多增加多少有效买入意愿。", "20", "点", "订单簿购买预算阶段", "effective_buy_willingness <= base + cap。", "允许工资收入更显著转化为储备消费。", "抑制工资驱动的额外消费。", "wage_consumption_bonus_per_survival、individual_buy_willingness", "EffectiveBuyWillingnessAvg、WageResponsiveExtraCapTotal", "高级用户修改。", "过高会削弱储备消费的价格敏感性。"),
    ),
    ParameterSpec(
        key="min_life", default=17, value_type="int", category="demography", level="B",
        label_zh="最低寿命", label_en="Minimum life", unit="回合", min_value=1, max_value=10000, step=1, visible_in_advanced=True,
        help_zh=_help("设置个体出生时寿命随机范围的下限。", "17", "回合", "个体初始化与出生阶段", "life 在 min_life 与 max_life 之间取值。", "死亡压力延后，人口更容易累积。", "寿命结束压力提前。", "max_life、enable_initial_age_distribution", "DeathCount、AvgLifeRemaining、life_end 死亡原因", "高级用户修改。", "不应用寿命参数掩盖市场/生产链路问题。"),
    ),
    ParameterSpec(
        key="max_life", default=23, value_type="int", category="demography", level="B",
        label_zh="最高寿命", label_en="Maximum life", unit="回合", min_value=1, max_value=10000, step=1, visible_in_advanced=True,
        help_zh=_help("设置个体出生时寿命随机范围的上限。", "23", "回合", "个体初始化与出生阶段", "life 在 min_life 与 max_life 之间取值。", "寿命尾部更长，断代风险下降。", "寿命尾部更短，生命周期压力增强。", "min_life、initial_age_distribution_ratio", "MaxLifeRemaining、DeathsByLifeEndWhenPopulationBelow5", "高级用户修改。", "过高会削弱模型生命周期更新压力。"),
    ),
    ParameterSpec(
        key="min_price_index", default=1, value_type="float", category="market", level="C",
        label_zh="最低价格指数", label_en="Minimum price index", unit="价格指数", min_value=0.01, max_value=10000, step=0.1, visible_in_advanced=True,
        help_zh=_help("限制市场价格指数最低值，避免价格降到不可计算或无意义区间。", "1", "价格指数", "市场价格更新阶段", "price_index = clamp(price_index, min_price_index, max_price_index)。", "价格下限更高，公司收入更稳但消费者压力更大。", "价格可更低，低价清库存更明显。", "max_price_index、price_adjust_speed", "FoodPriceIndex、MarketFoodVolume", "高级用户修改。", "过低可能造成极端低价和统计噪声。"),
    ),
    ParameterSpec(
        key="max_price_index", default=500, value_type="float", category="market", level="C",
        label_zh="最高价格指数", label_en="Maximum price index", unit="价格指数", min_value=1, max_value=100000, step=1, visible_in_advanced=True,
        help_zh=_help("限制市场价格指数最高值，避免短缺时价格无限上升。", "500", "价格指数", "市场价格更新阶段", "price_index = clamp(price_index, min_price_index, max_price_index)。", "短缺价格压力更强。", "价格上限更低，刚需购买更容易但公司收益受限。", "min_price_index、price_adjust_speed", "FoodPriceIndex、HardNeedBlockedByHighPrice", "高级用户修改。", "过高可能导致刚需预算耗尽，过低可能削弱短缺信号。"),
    ),
    ParameterSpec(
        key="price_adjust_speed", default=10, value_type="float", category="market", level="C",
        label_zh="价格调整速度", label_en="Price adjustment speed", unit="%", min_value=0, max_value=1000, step=1, visible_in_advanced=True,
        help_zh=_help("控制供需压力对价格指数的调整速度。", "10", "%", "市场价格更新阶段", "价格变化幅度与供需缺口和该参数相关。", "价格更快反映短缺/过剩。", "价格更平滑。", "min_price_index、max_price_index", "FoodPriceIndex、MarketStabilityIndex", "高级用户修改。", "过高会造成价格震荡。"),
    ),
    ParameterSpec(
        key="production_resource_price", default=1, value_type="float", category="company", level="C",
        label_zh="生产资源价格", label_en="Production resource price", unit="货币/资源", min_value=0, max_value=100000, step=0.1, visible_in_advanced=True,
        help_zh=_help("设置公司向政府购买生产资源时的单位价格。", "1", "货币/资源", "生产资源购买阶段", "资源成本 = 购买量 × production_resource_price。", "政府财政收入增加，公司生产成本上升。", "公司生产更便宜，政府财政收入下降。", "government_deposit、company_initial_money_per_capita", "CompanyResourcePurchased、GovernmentDeposit", "高级用户修改。", "过高会导致公司现金流不足。"),
    ),
    ParameterSpec(
        key="company_profit_sensitivity", default=100, value_type="float", category="company", level="C",
        label_zh="公司利润敏感度", label_en="Company profit sensitivity", unit="权重", min_value=0, max_value=10000, step=1, visible_in_advanced=True,
        help_zh=_help("控制利润信号对公司生产/分公司选择的影响强度。", "100", "权重", "公司生产决策阶段", "预期收益评分会按该敏感度放大或缩小。", "公司更追逐利润商品。", "公司生产结构更平滑。", "hard_need_production_response_weight、company_production_tendency", "CompanyExpectedProfit、BranchesWithPositiveExpectedProfitWhenPopBelow5", "高级用户修改。", "过高可能让刚需商品在低利润时被挤出。"),
    ),
])


# ========================
# 系统级第三阶段：自动补齐型参数元数据
# ========================
# 说明：上方 PARAMETER_SPECS 中的条目是“人工精写说明”的核心参数。
# 为了让新 GUI、配置校验和参数说明库能够覆盖所有现有配置项，
# 这里根据 config.DEFAULT_SETTINGS 自动为尚未精写的参数生成“补齐型元数据”。
# 这些条目不会改变旧 config.py 的行为；后续应逐步将高价值参数从自动补齐升级为人工精写。

def _category_level_for_key(section, key):
    if section == "switches":
        return "switches", "C", "开关"
    if section == "mutation":
        return "mutation", "D", "点/倍率"
    if section == "population":
        return "population", "C", "点/数量"
    # base / behavior
    if "tax" in key:
        return "tax", "D", "%"
    if "price" in key or "market" in key or "buy" in key:
        return "market", "C", "点/倍率"
    if "government" in key or key.startswith("gov_"):
        return "government", "C", "货币/比例"
    if "company" in key or "wage" in key or "labor" in key:
        return "company", "C", "货币/比例"
    if "food" in key or "medical" in key or "reproduction" in key or "education" in key:
        return "goods", "C", "数量/比例"
    if "env" in key or "resource" in key:
        return "environment", "C", "资源/比例"
    return section, "C", "数值"


def _value_type_for_value(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


def _auto_help(key, default, section, category):
    return _help(
        f"配置项 {key} 的自动补齐说明。该参数来自旧 config.py 的 {section} 分组，当前已纳入 ParameterSpec 校验体系。",
        str(default),
        "按参数语义",
        "按旧模型中引用该参数的阶段生效",
        "当前阶段保持旧逻辑不变；后续会逐步补充精确公式、关联字段和 UI 解释。",
        "可能增强对应机制强度，具体影响需结合源码引用位置和回归测试判断。",
        "可能削弱对应机制强度，具体影响需结合源码引用位置和回归测试判断。",
        "待精写说明补充",
        "待精写说明补充",
        "暂归入高级设置或高级调试，不建议普通用户随意修改。",
        "这是自动补齐说明，不代表该参数已经完成最终语义审计；系统级开发后续应逐项精写。",
    )


def _iter_config_defaults_for_specs():
    try:
        import config
    except Exception:
        return []
    rows = []
    settings = getattr(config, "DEFAULT_SETTINGS", {})
    for section in ("switches", "base", "behavior", "mutation"):
        for key, value in settings.get(section, {}).items():
            rows.append((section, key, value))
    pop_a = settings.get("population", {}).get("A", {})
    for key, value in pop_a.items():
        rows.append(("population", key, value))
    return rows


def _build_auto_supplemental_specs():
    existing = {spec.key for spec in PARAMETER_SPECS}
    supplemental = []
    for section, key, default in _iter_config_defaults_for_specs():
        if key in existing:
            continue
        category, level, unit = _category_level_for_key(section, key)
        value_type = _value_type_for_value(default)
        spec = ParameterSpec(
            key=key,
            default=default,
            value_type=value_type,
            category=category,
            level=level,
            label_zh=key,
            label_en=key,
            unit=unit,
            visible_in_basic=False,
            visible_in_advanced=(level in {"B", "C"}),
            visible_in_debug=True,
            experimental=("dev" in key or "debug" in key or "diagnostic" in key),
            affects_core_logic=True,
            help_zh=_auto_help(key, default, section, category),
        )
        supplemental.append(spec)
        existing.add(key)
    return supplemental


AUTO_SUPPLEMENTAL_PARAMETER_SPECS = _build_auto_supplemental_specs()
PARAMETER_SPECS.extend(AUTO_SUPPLEMENTAL_PARAMETER_SPECS)


def specs_by_key():
    return {spec.key: spec for spec in PARAMETER_SPECS}


def specs_for_category(category):
    return [spec for spec in PARAMETER_SPECS if spec.category == category]


def visible_specs(levels=("A", "B", "C")):
    return [spec for spec in PARAMETER_SPECS if spec.level in levels and not spec.deprecated]
