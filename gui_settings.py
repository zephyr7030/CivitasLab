import copy
import re
import tkinter as tk
from tkinter import ttk, messagebox

from config import PROJECT_NAME, DEFAULT_SETTINGS, POP_LABELS, MECHANISM_SWITCHES
from settings_io import load_settings, save_settings, normalize_settings, get_param_range, range_text


class StartConfigWindow:
    """启动设置界面。

    本文件只负责 GUI 参数编辑，不直接修改模型运行逻辑。
    说明文本集中放在 PARAM_HELP 和 help_text() 中，避免后续改界面时误删说明。
    """

    PARAM_HELP = {
        "switches.enable_invasion": (
            "【侵略机制】\n\n"
            "控制是否启用部族之间的侵略行为。\n\n"
            "开启后，每个非濒死个体都可能根据自身武力和自身存款，被判定为侵略者。"
            "武力越高、存款越低，侵略倾向越强。侵略者会尝试攻击其他部族中武力低于自己的随机个体。\n\n"
            "侵略成功时，目标个体失去全部存款，侵略者获得其中一部分，另一部分作为掠夺损耗消失。"
            "侵略失败时，侵略者会扣除寿命。\n\n"
            "关闭后，部族之间不会发生侵略，部族间差异主要来自资源、繁殖、死亡和内部行为。"
        ),
        "switches.enable_internal_plunder": (
            "【部族内掠夺机制】\n\n"
            "控制是否启用同一部族内部的个体掠夺行为。\n\n"
            "开启后，在开始阶段被道德检定判定为掠夺者的个体，会尝试掠夺同部族内武力低于自己的个体。"
            "被掠夺者减少存款，掠夺者获得其中一部分，剩余部分作为损耗消失。\n\n"
            "该机制用于模拟低道德、高武力个体对群体财富分配、贫富差距和内部秩序的影响。"
        ),
        "switches.enable_government_aid": (
            "【政府救助机制】\n\n"
            "控制是否启用政府存款对贫困个体的补助。\n\n"
            "政府存款来源包括个体死亡时的剩余存款，以及部族内掠夺者被治安制裁后失去的全部存款。\n\n"
            "开启后，救助阶段中政府存款会优先资助本部族内存款低于100的个体，直到其存款达到100或政府存款耗尽。"
        ),
        "switches.enable_rescue": (
            "【个体间救助机制】\n\n"
            "控制是否启用高道德个体对弱势个体的直接救助。\n\n"
            "开启后，被道德检定判定为救助者且自身存款高于救助门槛的个体，会尝试救助本部族内濒死或低存款个体。\n\n"
            "该机制用于观察个体道德行为对部族存续、贫困个体存活率和财富再分配的影响。"
        ),
        "switches.enable_evolution": (
            "【进化机制】\n\n"
            "控制是否启用基于收益表现的进化方向判定。\n\n"
            "开启后，每回合结束前，系统会比较同一部族内不同属性高低个体的本回合收益表现。"
            "如果某项属性较高的个体平均收益更好，则该属性在下一代中更可能正向变异；反之可能负向变异。\n\n"
            "当前参与进化方向判定的属性包括：道德、武力、繁殖倾向、劳动意愿。"
        ),
        "switches.enable_restore_populations": (
            "【恢复多部族机制】\n\n"
            "控制是否在只剩一个部族存活时，自动恢复其他启用部族。\n\n"
            "开启后，如果某一回合结束后只剩一个部族仍有个体存活，系统会把该部族的个体、环境资源、政府存款和部分运行状态复制到其他启用部族。\n\n"
            "该机制用于避免模拟过早进入单一部族垄断状态，方便长期观察演化趋势。当前默认关闭。"
        ),
        "switches.enable_disaster": (
            "【灾害与系统韧性机制】\n\n"
            "控制是否启用低频外部冲击。开启后，每回合会按灾害概率随机判定是否发生灾害。\n\n"
            "当前包含四类灾害：干旱、疫病、经济危机、社会动荡。该机制用于测试部族在资源、财富、信任、教育和阶层结构方面的系统韧性。"
        ),
        "switches.enable_shared_environment_resource": (
            "【部族间共用环境资源机制】\n\n"
            "控制多个部族是否共享同一个环境资源池。\n\n"
            "关闭时，每个部族拥有独立环境资源、环境承载力和环境健康。\n\n"
            "开启时，所有启用部族先竞争同一个共享资源池，系统会按平等份额、劳动需求份额和能力份额为各部族分配资源配额，然后各个部族再在内部把配额分给个体。\n\n"
            "该机制用于模拟水源、草场、渔场、森林等公共池资源。"
        ),
        "switches.enable_market": (
            "【基础商品市场与政府采购机制】\n\n"
            "控制是否启用基础商品交易和政府采购。\n\n"
            "开启后，市场阶段位于劳动生产之后、掠夺和侵略之前。个体会根据即将发生的生存、医疗、生育和教育需求购买食物、医疗用品、教育用品和生育用品；库存超过安全线的个体可出售对应商品。\n\n"
            "政府会在个体交易之后，按照上回合物资消耗比例形成意向库存，并用政府货币从本部族库存过剩个体处采购食物和医疗用品。当前所有商品价格暂定为1商品单位=1货币。"
        ),
        "switches.enable_global_trade": (
            "【跨部族自由交易机制】\n\n"
            "控制是否允许个体在本部族市场无法满足需求后，向其他部族购买商品。\n\n"
            "开启后：个体仍然优先在本部族市场购买；本地供给不足或价格无法满足需求时，才会按卖方部族价格跨部族购买。跨部族交易会产生进口税和交易税。\n\n"
            "关闭后：市场交易只发生在本部族内部。"
        ),

        "switches.enable_moral_donation": (
            "【道德施舍机制】\n\n"
            "高级调试机制，默认关闭。\n\n"
            "开启后，高道德且拥有剩余库存的个体会在政府救助和个体救助之后，向同部族总市场价值较低的个体进行小额施舍。\n\n"
            "施舍优先转移食物、医疗用品、教育用品和生育用品，必要时少量转移货币。该机制不创造也不销毁货币或商品，只改变部族内部的分配结构。"
        ),

        "base.max_turns": (
            "【运行回合数】\n\n"
            "设置模拟最多运行多少个回合。运行到此回合数后，脚本会停止模拟并保存 Excel 汇总文件和 CSV 个体数据文件。\n\n"
            "每个完整回合会依次执行开始、劳动、内部掠夺、部族间侵略、政府救助、个体救助、繁殖、生存、进化和数据记录等阶段。\n\n"
            "数值越大，越适合观察长期演化趋势，但运行时间和输出文件体积也会增加。"
        ),
        "base.save_interval": (
            "【自动保存间隔回合】\n\n"
            "设置每隔多少回合自动保存一次结果。例如设置为10，表示第10、20、30回合等自动保存。\n\n"
            "数值越小，保存越频繁，数据更安全，但运行效率可能下降；数值越大，保存次数减少，但中途退出时可能丢失更多未保存数据。"
        ),
        "base.disaster_probability": (
            "【灾害概率】\n\n"
            "设置启用灾害机制后，每回合发生灾害的概率。默认3，表示每回合3%概率。\n\n"
            "该值越高，外部冲击越频繁；稳定观察时建议保持较低，压力测试时可以提高。"
        ),
        "base.disaster_strength": (
            "【灾害强度】\n\n"
            "设置灾害发生时的基础冲击强度。默认20，表示中等强度。\n\n"
            "干旱会按该强度降低本回合资源再生；疫病会影响该比例附近的个体寿命；经济危机会按比例削减个体存款；社会动荡会降低信任并临时增加掠夺倾向。"
        ),
        "base.population_count": (
            "【启用部族数】\n\n"
            "目前只支持1-3个部族。\n\n"
            "1表示只启用A；2表示启用A/B；3表示启用A/B/C。默认值为3。"
        ),
        "base.initial_population": (
            "【每部族初始个体数】\n\n"
            "设置每个启用部族在模拟开始时拥有多少个初始个体。例如设置为100且启用3个部族，则初始总个体数为300。\n\n"
            "初始个体会根据对应部族的初始道德、武力、繁殖倾向和劳动意愿生成，并受到变异参数影响。"
        ),
        "base.initial_env_resource": (
            "【全局默认初始环境资源】\n\n"
            "这是全局默认环境资源值。当前模型中，每个部族也可在《部族设置》中单独设置自己的初始环境资源，部族自己的值优先生效。\n\n"
            "环境资源用于劳动生产，不等于货币或商品库存。个体劳动会消耗环境资源，并根据有效智慧产出多类商品。"
        ),
        "base.resource_regen": (
            "【全局默认环境再生】\n\n"
            "这是全局默认的每回合环境资源再生量。部族设置里的再生量优先生效。\n\n"
            "环境资源只能通过再生产生，不会因为掠夺、救助、遗产或政府存款而增加。"
        ),
        "base.initial_balance": (
            "【初始个体存款】\n\n"
            "设置初始个体出生时拥有的个人存款。个人存款在当前商品经济中代表货币，主要用于市场购买、税收、生育转移、教育和其他交易行为。\n\n"
            "该值会影响部族早期抗风险能力。"
        ),
        "base.survival_cost": (
            "【基础生存需求单位】\n\n"
            "设置每个个体每回合的基础生存需求单位。当前主要表示食物需求，也作为生病时医疗用品需求的基准。\n\n"
            "存款足够则扣除后存活；存款不足且未使用过濒死机会，则耗尽存款进入濒死；已使用濒死机会仍无法支付则死亡。"
        ),
        "base.child_initial_balance": (
            "【新生个体初始存款】\n\n"
            "设置新生个体出生时自带的存款。该财富计入社会财富系统。\n\n"
            "该值越高，新生个体越容易度过早期生存压力。"
        ),
        "base.total_ability": (
            "【总能力值】\n\n"
            "设置个体武力值与智慧值之和。当前模型满足：武力值 + 智慧值 = 总能力值。\n\n"
            "因此提高武力通常会降低智慧，提高智慧通常会降低武力。"
        ),
        "base.min_strength": (
            "【最小武力】\n\n"
            "设置个体武力值允许出现的最低值。武力影响部族内掠夺和部族间侵略。\n\n"
            "该值也会影响部族设置中初始武力拉条的最低端。"
        ),
        "base.max_strength": (
            "【最大武力】\n\n"
            "设置个体武力值允许出现的最高值。武力越高，个体在掠夺和侵略中越有优势，但通常意味着智慧更低。\n\n"
            "该值也会影响部族设置中初始武力拉条的最高端。"
        ),
        "base.min_intelligence": (
            "【最小智慧】\n\n"
            "设置个体智慧值允许出现的最低值。智慧影响劳动产出。\n\n"
            "由于武力与智慧之和固定，该值会反向限制武力可取范围。"
        ),
        "base.max_intelligence": (
            "【最大智慧】\n\n"
            "设置个体智慧值允许出现的最高值。智慧越高，劳动生产效率越高。\n\n"
            "由于武力与智慧之和固定，该值会反向限制武力可取范围。"
        ),
        "base.min_life": (
            "【最小寿命】\n\n"
            "设置个体出生时随机寿命的最低值。个体每经历一个生存阶段，寿命会减少。寿命耗尽时个体死亡。"
        ),
        "base.max_life": (
            "【最大寿命】\n\n"
            "设置个体出生时随机寿命的最高值。初始寿命会在最小寿命和最大寿命之间随机生成。\n\n"
            "该值越高，个体平均存活时间越长，行为累积影响越明显。"
        ),
        "base.labor_env_cost": (
            "【标准劳动资源份额】\n\n"
            "设置一个劳动者在标准生产状态下需要的环境资源份额。BOT8 2.4.0 后，该值不再表示每个劳动者固定消耗量，而是资源分配算法中的标准份额。\n\n"
            "实际获得资源会根据资源分配模式、部族配额、劳动候选人数和资源不足程度变化。"
        ),
        "base.education_temp_int_per_100_goods": (
            "【教育临时智慧】\n\n"
            "BOT8 2.4.0 新增。个体生育时，母代每消耗100教育用品，会使子代获得该数值的临时智慧。\n\n"
            "临时智慧伴随个体一生，不会遗传，不计入基础智慧值，也不计入总能力限制。默认10。"
        ),
        "base.max_production": (
            "【最高智慧劳动产出】\n\n"
            "设置智慧达到最大值时的最高商品生产预算。实际生产预算会按有效智慧、获得的环境资源份额等因素计算，并分配为食物、医疗用品、教育用品、生育用品和工具。dev11 起不再扣除抽象劳动成本。"
        ),
        "base.min_reproduce": (
            "【最小生育倾向】\n\n"
            "设置个体繁殖倾向允许出现的最低值。繁殖倾向越高，繁殖阶段通过繁殖检定的概率越高。"
        ),
        "base.max_reproduce": (
            "【最大生育倾向】\n\n"
            "设置个体繁殖倾向允许出现的最高值。繁殖倾向越高，部族增长潜力越强，但也可能造成更强资源压力。"
        ),
        "behavior.internal_plunder_min": "【部族内掠夺最小比例】\n\n设置部族内掠夺发生时，被掠夺者存款可能损失的最低比例。",
        "behavior.internal_plunder_max": "【部族内掠夺最大比例】\n\n设置部族内掠夺发生时，被掠夺者存款可能损失的最高比例。该值越高，内部掠夺对贫富差距和死亡率的影响越强。",
        "behavior.rescue_min_ratio": "【个体救助最小比例】\n\n设置个体救助行为中，救助者最低可能捐出的自身存款比例。",
        "behavior.rescue_max_ratio": "【个体救助最大比例】\n\n设置个体救助行为中，救助者最高可能捐出的自身存款比例。实际捐出值会在最小和最大之间随机生成。",
        "behavior.rescue_min_balance": "【救助者最低存款】\n\n设置个体成为实际救助者所需的最低存款条件，避免贫困个体继续救助导致自身快速死亡。",
        "behavior.plunder_gain_rate": "【掠夺实际获得比例】\n\n设置掠夺行为中的有效收益比例。例如70表示目标损失100时，掠夺者获得70，剩余30作为损耗消失。",
        "behavior.invasion_fail_life_loss": "【侵略失败寿命扣除】\n\n设置个体在部族间侵略失败时扣除的寿命值。该值越高，侵略风险越大。",
        "behavior.invasion_strength_weight": "【侵略武力权重】\n\n设置侵略倾向计算中武力因素所占权重。越高越倾向让高武力个体发动侵略。",
        "behavior.invasion_poverty_weight": "【侵略贫困权重】\n\n设置侵略倾向计算中贫困因素所占权重。越高表示低存款压力越容易转化为侵略行为。",
        "behavior.invasion_success_sigma": "【侵略成功率正态sigma】\n\n设置侵略成功率计算中的正态分布平滑参数。越小武力差距影响越剧烈，越大影响越平缓。BOT8 2.2.0 默认值为200，使成功率不容易因武力差距过早接近极端。",
        "behavior.invasion_base_risk": "【侵略基础风险】\n\nBOT8 2.2.0 新增。最终侵略概率 = 原始侵略概率 × 侵略基础风险 / 100。默认20，用于把侵略行为控制在更适合观察长期演化的频率。",
        "behavior.invasion_loot_min": "【侵略掠夺最小比例】\n\nBOT8 2.2.0 新增。侵略成功后不再夺取目标全部存款，而是在该最小比例和最大比例之间随机夺取目标存款。默认30。",
        "behavior.invasion_loot_max": "【侵略掠夺最大比例】\n\nBOT8 2.2.0 新增。侵略成功后不再夺取目标全部存款，而是在最小比例和该最大比例之间随机夺取目标存款。默认70。",

        "mutation.morality": "【道德变异幅度】\n\n设置新生个体继承道德值时的随机浮动幅度。越高，道德演化波动越大。",
        "mutation.strength": "【武力变异幅度】\n\n设置新生个体继承武力值时的随机浮动幅度。武力变化后，智慧会自动调整以保持总能力约束。",
        "mutation.reproduce": "【生育倾向变异幅度】\n\n设置新生个体继承繁殖倾向时的随机浮动幅度。越高，繁殖能力代际波动越明显。",
        "mutation.labor": "【劳动意愿变异幅度】\n\n设置新生个体继承劳动意愿时的随机浮动幅度。越高，部族内部生产参与差异越大。",
    }

    POPULATION_HELP = {
        "morality": "【部族 {pop} 初始道德】\n\n设置该部族初始个体的道德基础值。道德较低更容易成为掠夺者，道德较高更容易成为救助者。初始个体生成时会结合道德变异幅度随机浮动。该参数影响早期内部秩序、掠夺频率、救助频率和贫富差距。",
        "strength": "【部族 {pop} 初始武力】\n\n设置该部族初始个体的武力基础值。该项同时支持数值输入和拉条输入，两者会即时同步。界面会同步显示对应智慧值。当前模型满足：武力值 + 智慧值 = 总能力值。因此提高初始武力通常会降低初始智慧。武力影响掠夺和侵略，智慧影响劳动生产效率。",
        "reproduce": "【部族 {pop} 初始生育倾向】\n\n设置该部族初始个体的繁殖倾向基础值。繁殖倾向越高，个体在繁殖阶段越容易通过繁殖检定。只有存款足够支付繁殖消耗的正常个体才会进行繁殖判定。",
        "labor": "【部族 {pop} 初始劳动意愿】\n\n设置该部族初始个体的劳动意愿基础值。劳动意愿越高，个体越容易参与劳动生产。劳动阶段中，高智慧个体会优先消耗环境资源进行生产。",
        "initial_env_resource": "【部族 {pop} 初始环境资源】\n\n设置该部族在模拟开始时拥有的环境资源。环境资源不等于存款，属于自然资源系统，只能通过每回合资源再生产生。劳动会消耗环境资源并产出社会财富。",
        "resource_regen": "【部族 {pop} 每回合资源再生】\n\n设置该部族每回合开始阶段自动增加的环境资源数量。这是环境资源系统唯一的新增来源。越高表示该部族可长期支持的生产规模越大。",
        "env_capacity": "【部族 {pop} 环境承载力】\n\n表示该部族环境资源可恢复到的上限，相当于可再生资源模型中的承载力 K。环境再生后资源不会超过该值。BOT8 2.2.0 默认值为初始环境资源的5倍，例如初始资源12000时承载力为60000。",
        "env_health": "【部族 {pop} 环境健康】\n\nBOT8 2.1.0 新增。范围0-100，用来表示生态系统维持再生功能的状态。实际环境再生=基础再生×环境健康/100。默认100表示未退化。数值越低，每回合实际再生越少。",
        "env_degradation_rate": "【部族 {pop} 环境退化速度】\n\n表示资源压力超过1时，环境健康下降的基准幅度。BOT8 2.2.0 默认10，并通过 env_damage_buffer 累积小压力，累计满1才减少环境健康，使退化更平滑。",
        "env_recovery_rate": "【部族 {pop} 环境恢复速度】\n\n表示资源压力较低时，环境健康可恢复的基准幅度。BOT8 2.2.0 默认3，并通过恢复缓冲池逐步生效，用于模拟生态恢复通常慢于破坏但能被持续低压力改善。",
        "trust": "【部族 {pop} 社会信任】\n\n设置该部族初始社会信任值，范围0-100。信任会温和影响劳动参与、道德检定中的掠夺/救助倾向，以及共用资源下的部族组织能力。默认60表示略高于中性的稳定社会。",
        "security": "【部族 {pop} 治安度】\n\n设置该部族对内部掠夺者的制裁概率。掠夺者完成掠夺后会进行治安检定；成功则失去全部存款，进入政府存款。治安度越高，掠夺者越容易被制裁。",
        "gov_aid_budget_ratio": "【部族 {pop} 政府救助预算比例】\n\n设置该部族政府每回合最多拿出多少比例的政府存款用于救助。默认50，表示最多使用政府存款的一半，剩余政府存款会保留到后续回合。",
        "labor_tax_rate": "【部族 {pop} 劳动税率】\n\n设置该部族对劳动净收入征收的税率。劳动税进入本部族政府存款，用于救助等公共支出。默认10。",
        "wealth_tax_exempt_threshold": "【部族 {pop} 财富税免税线】\n\n个体存款低于该值时不征收财富税。默认600，用于保护低存款个体的基本生存缓冲。",
        "wealth_tax_threshold": "【部族 {pop} 财富税高档阈值】\n\n个体存款超过该值的部分按高档财富税率征收；免税线到该阈值之间按低档税率征收。默认1500。",
        "wealth_tax_low_rate": "【部族 {pop} 财富税低档税率】\n\n设置财富税免税线到高档阈值之间的低档税率。默认1。",
        "wealth_tax_rate": "【部族 {pop} 财富税高档税率】\n\n设置超过财富税高档阈值部分的高档税率。默认2。",
        "import_tax_rate": "【部族 {pop} 进口税率】\n\n设置本部族个体从其他部族购买商品时额外缴纳的税率。进口税进入买方所属部族政府存款。默认5，表示跨部族购买100货币商品时额外向本部族政府缴纳5货币。",
        "trade_tax_rate": "【部族 {pop} 交易税率】\n\n设置本部族个体作为卖方完成商品交易时征收的交易税率。交易税进入卖方所属部族政府存款。本地交易和跨部族交易都适用。默认2。",
        "market_control_budget_ratio": "【部族 {pop} 市场调控预算比例】\n\n设置政府每回合最多使用多少比例的公共财政余额进行市场调控。该预算用于低价收储和高价投放中的商品购买，不会发行新货币。",
        "food_subsidy_rate": "【部族 {pop} 食物折价投放率】\n\n当食物价格高于宏观调控高价阈值时，政府可用公共库存向短缺个体折价投放食物。该值表示相对市场价的折价比例。",
        "medical_subsidy_rate": "【部族 {pop} 医疗物资折价投放率】\n\n当医疗物资价格高于宏观调控高价阈值时，政府可用公共库存向短缺个体折价投放医疗物资。该值表示相对市场价的折价比例。",
        "gov_education_enabled": "【部族 {pop} 政府教育启用】\n\n设置该部族是否启用政府教育机制。0表示关闭，1表示开启。开启后，政府会在繁殖阶段使用教育预算为新生个体增加临时智慧。",
        "gov_education_budget_ratio": "【部族 {pop} 政府教育预算比例】\n\n设置繁殖阶段最多使用多少比例的政府存款进行公共教育投入。默认20，表示最多使用政府存款的20%。",
        "gov_education_temp_int_per_100": "【部族 {pop} 政府教育临时智慧效率】\n\n设置每投入100政府存款能给新生个体增加多少临时智慧。默认5。临时智慧伴随个体一生，不遗传，不计入基础智慧和总能力限制。",
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{PROJECT_NAME} - 启动设置")
        try:
            self.root.state("zoomed")
        except Exception:
            self.root.geometry("1280x720")
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        self.settings = load_settings()
        self.vars = {}
        self.entry_widgets = {}
        self.schedule_vars = {}
        self.schedule_widgets = {}
        self.schedule_labels = {}

        self.selected_population = tk.StringVar(value="A")
        self.current_population = "A"
        self.population_field_vars = {}
        self.population_entry_widgets = {}
        self.strength_scale = None
        self.strength_display_label = None
        self.is_syncing_strength = False

        self.build_ui()

    # =====================================================
    #                  说明、读取、校验
    # =====================================================

    def help_text(self, path):
        text = self.PARAM_HELP.get(path)
        if text is None and path.startswith("population."):
            parts = path.split(".")
            if len(parts) == 3:
                pop, field = parts[1], parts[2]
                template = self.POPULATION_HELP.get(field, "")
                text = template.format(pop=pop)
        if text is None:
            text = ""
        return f"{text}\n\n{range_text(path)}"

    def show_help(self, path, label):
        if path.startswith("population."):
            parts = path.split(".")
            if len(parts) == 3:
                path = f"population.{self.current_population}.{parts[2]}"
        messagebox.showinfo(label, self.help_text(path))

    def get_path(self, path):
        cur = self.settings
        for key in path.split("."):
            cur = cur[key]
        return cur

    def set_path(self, path, value):
        cur = self.settings
        keys = path.split(".")
        for key in keys[:-1]:
            cur = cur[key]
        cur[keys[-1]] = value

    def get_base_int(self, key):
        path = f"base.{key}"
        if path in self.vars:
            try:
                return int(self.vars[path].get())
            except ValueError:
                pass
        return int(self.settings["base"][key])

    def calculate_display_intelligence(self, strength):
        total = self.get_base_int("total_ability")
        min_int = self.get_base_int("min_intelligence")
        max_int = self.get_base_int("max_intelligence")
        return int(max(min_int, min(max_int, total - strength)))

    def is_valid_value(self, path, text):
        r = get_param_range(path)
        if r is None:
            return True
        try:
            value = int(text)
        except ValueError:
            return False
        return r[0] <= value <= r[1]

    def is_valid_population_value(self, field, text):
        try:
            value = int(text)
        except ValueError:
            return False
        if field == "strength":
            return self.get_base_int("min_strength") <= value <= self.get_base_int("max_strength")
        r = get_param_range(f"population.{self.current_population}.{field}")
        return True if r is None else r[0] <= value <= r[1]

    def validate_entry(self, path):
        if path not in self.entry_widgets:
            return True
        ok = self.is_valid_value(path, self.vars[path].get())
        self.entry_widgets[path].configure(bg="white" if ok else "#ffb3b3")
        if path in ["base.min_strength", "base.max_strength", "base.total_ability", "base.min_intelligence", "base.max_intelligence"]:
            self.update_strength_slider_range()
            self.update_strength_display_from_var()
        if path == "base.max_turns":
            for key, action in list(self.schedule_widgets.keys()):
                self.validate_schedule_entry(key, action)
        return ok

    def validate_population_entry(self, field):
        if field not in self.population_entry_widgets:
            return True
        ok = self.is_valid_population_value(field, self.population_field_vars[field].get())
        entry = self.population_entry_widgets[field]
        if str(entry.cget("state")) == "disabled":
            entry.configure(disabledbackground="#e6e6e6", disabledforeground="#777777")
        else:
            entry.configure(bg="white" if ok else "#ffb3b3")
        return ok

    def update_scaled_initials_ui_state(self):
        """dev42：按人口默认初始资产开启时，手动初始货币输入置灰。
        关闭后恢复黑色可键入状态。"""
        if "use_population_scaled_initials" not in self.population_field_vars:
            return
        try:
            use_default = int(self.population_field_vars["use_population_scaled_initials"].get()) != 0
        except Exception:
            use_default = True
        manual_fields = ["company_initial_money"]
        for field in manual_fields:
            entry = self.population_entry_widgets.get(field)
            if not entry:
                continue
            if use_default:
                entry.configure(state="disabled", disabledbackground="#e6e6e6", disabledforeground="#777777")
            else:
                entry.configure(state="normal", fg="black", bg="white")
            self.validate_population_entry(field)

    def parse_schedule_rounds(self, text):
        text = str(text).replace("，", ",").replace("；", ",").replace(";", ",")
        text = re.sub(r"\s+", ",", text)
        result = []
        for item in text.split(","):
            item = item.strip()
            if item:
                result.append(int(item))
        return result

    def validate_schedule_entry(self, key, action):
        widget = self.schedule_widgets.get((key, action))
        var = self.schedule_vars.get((key, action))
        switch_var = self.vars.get(f"switches.{key}")
        if widget is None or var is None:
            return True

        if switch_var is not None and not switch_var.get():
            widget.configure(state="disabled", disabledbackground="#eeeeee")
            return True

        widget.configure(state="normal")
        text = var.get().strip()
        if not text:
            widget.configure(bg="white")
            return True
        try:
            rounds = self.parse_schedule_rounds(text)
            max_turns = self.get_base_int("max_turns")
            ok = all(1 <= n <= max_turns for n in rounds)
        except Exception:
            ok = False
        widget.configure(bg="white" if ok else "#ffb3b3")
        return ok

    def update_schedule_state(self, key):
        for action in ["enable_rounds", "disable_rounds"]:
            self.validate_schedule_entry(key, action)

    def validate_all_entries(self):
        normal_ok = all(self.validate_entry(path) for path in self.entry_widgets)
        pop_ok = all(self.validate_population_entry(field) for field in self.population_entry_widgets)
        schedule_ok = all(self.validate_schedule_entry(k, a) for k, a in self.schedule_widgets)
        return normal_ok and pop_ok and schedule_ok

    # =====================================================
    #                  控件生成
    # =====================================================

    def make_help_button(self, parent, path, label):
        ttk.Button(parent, text="!", width=3, command=lambda: self.show_help(path, label)).pack(side="left", padx=4)

    def make_int_entry_grid(self, parent, path, label, row, col):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, sticky="ew", padx=10, pady=4)
        ttk.Label(frame, text=label, width=26).pack(side="left")
        var = tk.StringVar(value=str(self.get_path(path)))
        self.vars[path] = var
        entry = tk.Entry(frame, textvariable=var, width=14)
        entry.pack(side="left")
        self.entry_widgets[path] = entry
        var.trace_add("write", lambda *args, p=path: self.validate_entry(p))
        self.validate_entry(path)
        self.make_help_button(frame, path, label)

    def make_grouped_entries(self, parent, title, items, columns=2):
        group = ttk.LabelFrame(parent, text=title)
        group.pack(fill="x", padx=8, pady=8)
        for c in range(columns):
            group.columnconfigure(c, weight=1)
        for index, (path, label) in enumerate(items):
            self.make_int_entry_grid(group, path, label, index // columns, index % columns)
        return group

    def make_switch_row(self, parent, switch_key, label, row):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
        frame.columnconfigure(4, weight=1)

        path = f"switches.{switch_key}"
        var = tk.BooleanVar(value=bool(self.get_path(path)))
        self.vars[path] = var

        check = ttk.Checkbutton(frame, text=label, variable=var, command=lambda k=switch_key: self.update_schedule_state(k))
        check.grid(row=0, column=0, sticky="w")
        self.make_help_button_grid(frame, path, label, 0, 1)

        schedule = self.settings.get("switch_schedules", {}).get(switch_key, {"enable_rounds": "", "disable_rounds": ""})

        ttk.Label(frame, text="启用回合").grid(row=0, column=2, sticky="e", padx=(18, 4))
        enable_var = tk.StringVar(value=str(schedule.get("enable_rounds", "")))
        self.schedule_vars[(switch_key, "enable_rounds")] = enable_var
        enable_entry = tk.Entry(frame, textvariable=enable_var, width=18)
        enable_entry.grid(row=0, column=3, sticky="w")
        self.schedule_widgets[(switch_key, "enable_rounds")] = enable_entry

        ttk.Label(frame, text="禁用回合").grid(row=0, column=4, sticky="e", padx=(18, 4))
        disable_var = tk.StringVar(value=str(schedule.get("disable_rounds", "")))
        self.schedule_vars[(switch_key, "disable_rounds")] = disable_var
        disable_entry = tk.Entry(frame, textvariable=disable_var, width=18)
        disable_entry.grid(row=0, column=5, sticky="w")
        self.schedule_widgets[(switch_key, "disable_rounds")] = disable_entry

        enable_var.trace_add("write", lambda *args, k=switch_key: self.validate_schedule_entry(k, "enable_rounds"))
        disable_var.trace_add("write", lambda *args, k=switch_key: self.validate_schedule_entry(k, "disable_rounds"))
        self.update_schedule_state(switch_key)

    def make_help_button_grid(self, parent, path, label, row, col):
        ttk.Button(parent, text="!", width=3, command=lambda: self.show_help(path, label)).grid(row=row, column=col, sticky="w", padx=4)

    def make_population_int_entry(self, parent, field, label, row, col):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, sticky="ew", padx=10, pady=4)
        ttk.Label(frame, text=label, width=20).pack(side="left")
        var = tk.StringVar()
        self.population_field_vars[field] = var
        entry = tk.Entry(frame, textvariable=var, width=14)
        entry.pack(side="left")
        self.population_entry_widgets[field] = entry
        var.trace_add("write", lambda *args, f=field: self.validate_population_entry(f))
        if field == "use_population_scaled_initials":
            var.trace_add("write", lambda *args: self.update_scaled_initials_ui_state())
        self.make_help_button(frame, f"population.{self.current_population}.{field}", label)

    def make_population_strength_control(self, parent, row):
        frame = ttk.LabelFrame(parent, text="初始武力值")
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        self.population_field_vars["strength"] = tk.StringVar()

        top = ttk.Frame(frame)
        top.pack(fill="x", padx=8, pady=4)
        ttk.Label(top, text="武力数值", width=12).pack(side="left")
        entry = tk.Entry(top, textvariable=self.population_field_vars["strength"], width=14)
        entry.pack(side="left")
        self.population_entry_widgets["strength"] = entry
        self.strength_display_label = ttk.Label(top, text="武力：0    智慧：0", font=("Microsoft YaHei", 10, "bold"))
        self.strength_display_label.pack(side="left", padx=12)
        self.make_help_button(top, f"population.{self.current_population}.strength", "初始武力值")

        self.strength_scale = tk.Scale(
            frame,
            from_=self.get_base_int("min_strength"),
            to=self.get_base_int("max_strength"),
            orient="horizontal",
            resolution=1,
            command=self.on_strength_scale_change,
        )
        self.strength_scale.pack(fill="x", padx=8, pady=4)
        self.population_field_vars["strength"].trace_add("write", lambda *args: self.on_strength_entry_change())

    def on_strength_entry_change(self):
        if self.is_syncing_strength:
            return
        text = self.population_field_vars["strength"].get()
        ok = self.validate_population_entry("strength")
        try:
            strength = int(text)
        except ValueError:
            self.update_strength_display_invalid()
            return
        self.update_strength_display(strength)
        if ok and self.strength_scale:
            self.is_syncing_strength = True
            self.strength_scale.set(strength)
            self.is_syncing_strength = False

    def on_strength_scale_change(self, value):
        if self.is_syncing_strength:
            return
        strength = int(float(value))
        self.is_syncing_strength = True
        self.population_field_vars["strength"].set(str(strength))
        self.is_syncing_strength = False
        self.validate_population_entry("strength")
        self.update_strength_display(strength)

    def update_strength_display_invalid(self):
        if self.strength_display_label:
            self.strength_display_label.config(text="武力：无效    智慧：无效")

    def update_strength_display(self, strength):
        if self.strength_display_label:
            self.strength_display_label.config(text=f"武力：{strength}    智慧：{self.calculate_display_intelligence(strength)}")

    def update_strength_display_from_var(self):
        if "strength" not in self.population_field_vars:
            return
        try:
            strength = int(self.population_field_vars["strength"].get())
        except ValueError:
            self.update_strength_display_invalid()
            return
        self.update_strength_display(strength)
        self.validate_population_entry("strength")

    def update_strength_slider_range(self):
        if self.strength_scale:
            self.strength_scale.configure(from_=self.get_base_int("min_strength"), to=self.get_base_int("max_strength"))

    def build_scrollable_tab(self, notebook, title):
        outer = ttk.Frame(notebook)
        notebook.add(outer, text=title)
        canvas = tk.Canvas(outer)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas)
        content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return content

    # =====================================================
    #                  部族设置同步
    # =====================================================

    def load_population_to_panel(self, pop=None):
        pop = pop or self.current_population
        data = self.settings["population"][pop]
        for field in [
            "morality", "reproduce", "labor",
            "initial_env_resource", "resource_regen", "env_capacity", "env_health",
            "env_degradation_rate", "env_recovery_rate", "security", "medical_level", "trust",
            "gov_aid_budget_ratio", "labor_tax_rate", "wealth_tax_exempt_threshold",
            "wealth_tax_threshold", "wealth_tax_low_rate", "wealth_tax_rate",
            "import_tax_rate", "trade_tax_rate",
            "market_control_budget_ratio", "food_subsidy_rate", "medical_subsidy_rate",
            "gov_education_enabled", "gov_education_budget_ratio", "gov_education_temp_int_per_100",
            "use_population_scaled_initials", "company_initial_money", "company_initial_money_per_capita", "government_initial_money_per_capita",
            "government_initial_food_rounds", "government_initial_medical_goods_ratio", "government_initial_education_goods_ratio", "government_initial_reproduction_goods_ratio",
            "company_initial_food_rounds", "company_initial_medical_goods_ratio", "company_initial_education_goods_ratio", "company_initial_reproduction_goods_ratio",
            "enable_repro_education_inventory_resilience", "repro_inventory_target_births_ratio", "education_inventory_target_births_ratio", "repro_education_inventory_resilience_weight",
            "company_production_tendency", "labor_reward_ratio", "enable_wage_responsive_consumption", "wage_consumption_bonus_per_survival", "wage_consumption_bonus_cap", "production_resource_price", "company_profit_sensitivity", "enable_company_hard_need_inventory_release", "company_hard_need_listing_multiplier", "company_hard_need_min_listing_ratio", "individual_buy_willingness", "government_buy_willingness"
        ]:
            self.population_field_vars[field].set(str(data.get(field, "")))
        self.update_strength_slider_range()
        strength = int(data["strength"])
        self.is_syncing_strength = True
        self.population_field_vars["strength"].set(str(strength))
        if self.strength_scale:
            self.strength_scale.set(strength)
        self.is_syncing_strength = False
        self.update_strength_display(strength)
        for field in self.population_entry_widgets:
            self.validate_population_entry(field)
        self.update_scaled_initials_ui_state()

    def save_population_from_panel(self, pop=None):
        pop = pop or self.current_population
        for field in [
            "morality", "strength", "reproduce", "labor",
            "initial_env_resource", "resource_regen", "env_capacity", "env_health",
            "env_degradation_rate", "env_recovery_rate", "security", "medical_level", "trust",
            "gov_aid_budget_ratio", "labor_tax_rate", "wealth_tax_exempt_threshold",
            "wealth_tax_threshold", "wealth_tax_low_rate", "wealth_tax_rate",
            "import_tax_rate", "trade_tax_rate",
            "market_control_budget_ratio", "food_subsidy_rate", "medical_subsidy_rate",
            "gov_education_enabled", "gov_education_budget_ratio", "gov_education_temp_int_per_100",
            "use_population_scaled_initials", "company_initial_money", "company_initial_money_per_capita", "government_initial_money_per_capita",
            "government_initial_food_rounds", "government_initial_medical_goods_ratio", "government_initial_education_goods_ratio", "government_initial_reproduction_goods_ratio",
            "company_initial_food_rounds", "company_initial_medical_goods_ratio", "company_initial_education_goods_ratio", "company_initial_reproduction_goods_ratio",
            "enable_repro_education_inventory_resilience", "repro_inventory_target_births_ratio", "education_inventory_target_births_ratio", "repro_education_inventory_resilience_weight",
            "company_production_tendency", "labor_reward_ratio", "enable_wage_responsive_consumption", "wage_consumption_bonus_per_survival", "wage_consumption_bonus_cap", "production_resource_price", "company_profit_sensitivity", "enable_company_hard_need_inventory_release", "company_hard_need_listing_multiplier", "company_hard_need_min_listing_ratio", "individual_buy_willingness", "government_buy_willingness"
        ]:
            try:
                self.settings["population"][pop][field] = int(self.population_field_vars[field].get())
            except Exception:
                pass

    def on_population_selected(self, event=None):
        old_pop = self.current_population
        new_pop = self.selected_population.get()
        if old_pop == new_pop:
            return
        self.save_population_from_panel(old_pop)
        self.current_population = new_pop
        self.load_population_to_panel(new_pop)

    # =====================================================
    #                  UI 构建
    # =====================================================

    def build_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text=PROJECT_NAME, font=("Microsoft YaHei", 18, "bold")).pack(anchor="w", padx=12, pady=(10, 0))

        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        switch_tab = self.build_scrollable_tab(notebook, "机制开关")
        switch_group = ttk.LabelFrame(switch_tab, text="机制开关与运行回合调度")
        switch_group.pack(fill="x", padx=8, pady=8)
        switch_group.columnconfigure(0, weight=1)
        ttk.Label(
            switch_group,
            text="说明：启用/禁用回合支持多个数字，如 10,25,50；只有左侧机制总开关勾选时，调度输入框才生效。",
            foreground="#555555",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 6))
        for index, (switch_key, label) in enumerate(MECHANISM_SWITCHES, start=1):
            self.make_switch_row(switch_group, switch_key, label, index)

        base_tab = self.build_scrollable_tab(notebook, "基础参数")
        self.make_grouped_entries(base_tab, "运行与保存", [
            ("base.max_turns", "运行回合数"),
            ("base.save_interval", "自动保存间隔回合"),
            ("base.disaster_probability", "灾害概率"),
            ("base.disaster_strength", "灾害强度"),
            ("base.initial_population", "每部族初始个体数"),
        ])
        self.make_grouped_entries(base_tab, "财富与资源默认值", [
            ("base.initial_env_resource", "全局默认初始环境资源"),
            ("base.resource_regen", "全局默认环境再生"),
            ("base.initial_balance", "初始个体存款"),
            ("base.survival_cost", "基础生存需求单位"),
            ("base.child_initial_balance", "旧版子代初始值兼容字段"),
            ("base.child_initial_money", "子代初始货币"),
            ("base.child_initial_food", "子代初始食物"),
            ("base.reproduction_goods_required_per_birth", "每次出生所需生育用品"),
            ("base.parent_food_required_for_birth_multiplier", "父代出生前食物安全倍数"),
            ("base.enable_secondary_birth_check", "启用二次减概率生育判定"),
            ("base.secondary_birth_chance_ratio", "二次生育概率比例"),
            ("base.enable_government_reproduction_goods_release", "启用公共生育用品释放"),
            ("base.enable_inventory_sales_dividend", "启用库存销售收入分红实验"),
            ("base.inventory_sales_dividend_ratio", "库存销售收入分红比例"),
            ("base.inventory_sales_dividend_historical_only", "仅使用历史库存清算收入分红"),
            ("base.inventory_sales_dividend_cash_protection", "启用分红现金保护"),
            ("base.inventory_sales_dividend_min_cash_ratio", "分红触发现金阈值%"),
            ("base.inventory_sales_dividend_cash_floor_ratio", "分红后现金保留底线%"),
            ("base.enable_excess_cash_dividend", "启用超额现金分层分红实验"),
            ("base.excess_cash_dividend_ratio", "超额现金分红比例%"),
            ("base.excess_cash_dividend_min_cash_ratio", "超额现金阈值%"),
            ("base.excess_cash_dividend_recipient_mode", "超额分红对象模式0全体1本回合劳动者2近期劳动者"),
            ("base.excess_cash_dividend_recent_turns", "近期劳动者窗口回合"),
            ("base.education_temp_int_per_100_goods", "教育临时智慧/100教育用品"),
        ])
        self.make_grouped_entries(base_tab, "能力与寿命", [
            ("base.total_ability", "总能力值"),
            ("base.min_strength", "最小武力"),
            ("base.max_strength", "最大武力"),
            ("base.min_intelligence", "最小智慧"),
            ("base.max_intelligence", "最大智慧"),
            ("base.min_life", "最小寿命"),
            ("base.max_life", "最大寿命"),
            ("base.enable_initial_age_distribution", "启用初始年龄分布"),
            ("base.initial_age_distribution_ratio", "初始年龄分布比例"),
            ("base.enable_small_group_initial_conditions", "启用小族群正常初始条件"),
            ("base.small_group_initial_population_threshold", "小族群初始条件阈值"),
            ("base.small_group_initial_food_rounds", "小族群初始食物回合数"),
            ("base.small_group_initial_medical_goods_ratio", "小族群初始医疗用品比例"),
            ("base.small_group_initial_reproduction_goods_ratio", "小族群初始生育用品比例"),
        ])
        self.make_grouped_entries(base_tab, "劳动与繁殖", [
            ("base.labor_env_cost", "劳动环境资源消耗"),
            ("base.max_production", "最高商品生产预算"),
            ("base.min_reproduce", "最小生育倾向"),
            ("base.max_reproduce", "最大生育倾向"),
        ])

        behavior_tab = self.build_scrollable_tab(notebook, "行为参数")
        self.make_grouped_entries(behavior_tab, "常用行为参数", [
            ("behavior.plunder_gain_rate", "掠夺商品获得比例"),
            ("behavior.rescue_min_ratio", "个体救助最小比例"),
            ("behavior.rescue_max_ratio", "个体救助最大比例"),
            ("behavior.rescue_min_balance", "救助者最低货币"),
            ("behavior.invasion_base_risk", "侵略基础风险"),
            ("behavior.invasion_fail_life_loss", "侵略失败寿命扣除"),
        ])

        advanced_tab = self.build_scrollable_tab(notebook, "高级调试")
        advanced_switch_group = ttk.LabelFrame(advanced_tab, text="高级机制开关")
        advanced_switch_group.pack(fill="x", padx=8, pady=8)
        advanced_switch_group.columnconfigure(0, weight=1)
        self.make_switch_row(advanced_switch_group, "enable_moral_donation", "道德施舍机制", 0)

        self.make_grouped_entries(advanced_tab, "资源与采收调试", [
            ("base.environment_safe_harvest_ratio", "可持续采收比例"),
        ])
        self.make_grouped_entries(advanced_tab, "市场价格调试", [
            ("base.price_adjust_speed", "价格调整速度"),
            ("base.min_price_index", "最低价格指数"),
            ("base.max_price_index", "最高价格指数"),
            ("base.market_control_low_price_index", "宏观调控低价阈值"),
            ("base.market_control_high_price_index", "宏观调控高价阈值"),
        ])
        self.make_grouped_entries(advanced_tab, "部族内掠夺调试", [
            ("behavior.internal_plunder_min", "部族内掠夺最小比例"),
            ("behavior.internal_plunder_max", "部族内掠夺最大比例"),
        ])
        self.make_grouped_entries(advanced_tab, "部族间侵略调试", [
            ("behavior.invasion_strength_weight", "侵略武力权重"),
            ("behavior.invasion_poverty_weight", "侵略贫困权重"),
            ("behavior.invasion_success_sigma", "侵略成功率正态sigma"),
            ("behavior.invasion_loot_min", "侵略掠夺最小比例"),
            ("behavior.invasion_loot_max", "侵略掠夺最大比例"),
        ])

        mutation_tab = self.build_scrollable_tab(notebook, "遗传变异参数")
        self.make_grouped_entries(mutation_tab, "遗传与变异", [
            ("mutation.morality", "道德变异幅度"),
            ("mutation.strength", "武力变异幅度"),
            ("mutation.reproduce", "生育倾向变异幅度"),
            ("mutation.labor", "劳动意愿变异幅度"),
        ])

        population_tab = self.build_scrollable_tab(notebook, "部族设置")
        selector_group = ttk.LabelFrame(population_tab, text="部族选择")
        selector_group.pack(fill="x", padx=8, pady=8)
        selector_group.columnconfigure(1, weight=1)

        ttk.Label(selector_group, text="启用部族数", width=20).grid(row=0, column=0, sticky="w", padx=10, pady=6)
        count_path = "base.population_count"
        count_var = tk.StringVar(value=str(self.get_path(count_path)))
        self.vars[count_path] = count_var
        count_entry = tk.Entry(selector_group, textvariable=count_var, width=14)
        count_entry.grid(row=0, column=1, sticky="w", pady=6)
        self.entry_widgets[count_path] = count_entry
        count_var.trace_add("write", lambda *args, p=count_path: self.validate_entry(p))
        self.validate_entry(count_path)
        self.make_help_button_grid(selector_group, count_path, "启用部族数", 0, 2)

        ttk.Label(selector_group, text="当前设置部族", width=20).grid(row=1, column=0, sticky="w", padx=10, pady=6)
        pop_box = ttk.Combobox(selector_group, textvariable=self.selected_population, values=POP_LABELS, state="readonly", width=12)
        pop_box.grid(row=1, column=1, sticky="w", pady=6)
        pop_box.bind("<<ComboboxSelected>>", self.on_population_selected)

        initial_group = ttk.LabelFrame(population_tab, text="部族初始个体参数")
        initial_group.pack(fill="x", padx=8, pady=8)
        initial_group.columnconfigure(0, weight=1)
        initial_group.columnconfigure(1, weight=1)
        self.make_population_int_entry(initial_group, "morality", "初始道德", 0, 0)
        self.make_population_int_entry(initial_group, "reproduce", "初始生育倾向", 0, 1)
        self.make_population_strength_control(initial_group, 1)
        self.make_population_int_entry(initial_group, "labor", "初始劳动意愿", 2, 0)

        pop_param_group = ttk.LabelFrame(population_tab, text="部族参数")
        pop_param_group.pack(fill="x", padx=8, pady=8)
        pop_param_group.columnconfigure(0, weight=1)
        pop_param_group.columnconfigure(1, weight=1)
        self.make_population_int_entry(pop_param_group, "initial_env_resource", "初始环境资源", 0, 0)
        self.make_population_int_entry(pop_param_group, "resource_regen", "每回合资源再生", 0, 1)
        self.make_population_int_entry(pop_param_group, "env_capacity", "环境承载力", 1, 0)
        self.make_population_int_entry(pop_param_group, "env_health", "初始环境健康", 1, 1)
        self.make_population_int_entry(pop_param_group, "env_degradation_rate", "环境退化速度", 2, 0)
        self.make_population_int_entry(pop_param_group, "env_recovery_rate", "环境恢复速度", 2, 1)
        self.make_population_int_entry(pop_param_group, "security", "治安度", 3, 0)
        self.make_population_int_entry(pop_param_group, "medical_level", "医疗水平", 3, 1)
        self.make_population_int_entry(pop_param_group, "trust", "社会信任", 4, 0)

        government_group = ttk.LabelFrame(population_tab, text="政府参数")
        government_group.pack(fill="x", padx=8, pady=8)
        government_group.columnconfigure(0, weight=1)
        government_group.columnconfigure(1, weight=1)
        self.make_population_int_entry(government_group, "gov_aid_budget_ratio", "政府救助预算比例", 0, 0)
        self.make_population_int_entry(government_group, "labor_tax_rate", "劳动实物税率", 0, 1)
        self.make_population_int_entry(government_group, "wealth_tax_exempt_threshold", "财富税免税线", 1, 0)
        self.make_population_int_entry(government_group, "wealth_tax_threshold", "财富税高档阈值", 1, 1)
        self.make_population_int_entry(government_group, "wealth_tax_low_rate", "财富税低档税率", 2, 0)
        self.make_population_int_entry(government_group, "wealth_tax_rate", "财富税高档税率", 2, 1)
        self.make_population_int_entry(government_group, "import_tax_rate", "进口税率", 3, 0)
        self.make_population_int_entry(government_group, "trade_tax_rate", "交易税率", 3, 1)
        self.make_population_int_entry(government_group, "market_control_budget_ratio", "市场调控预算比例", 4, 0)
        self.make_population_int_entry(government_group, "food_subsidy_rate", "食物折价投放率", 4, 1)
        self.make_population_int_entry(government_group, "medical_subsidy_rate", "医疗物资折价投放率", 5, 0)
        self.make_population_int_entry(government_group, "gov_education_enabled", "政府教育启用(0/1)", 5, 1)
        self.make_population_int_entry(government_group, "gov_education_budget_ratio", "政府教育预算比例", 6, 0)
        self.make_population_int_entry(government_group, "gov_education_temp_int_per_100", "政府教育临时智慧效率", 6, 1)

        company_group = ttk.LabelFrame(population_tab, text="公司参数")
        company_group.pack(fill="x", padx=8, pady=8)
        company_group.columnconfigure(0, weight=1)
        company_group.columnconfigure(1, weight=1)
        self.make_population_int_entry(company_group, "use_population_scaled_initials", "按人口默认初始资产(0/1)", 0, 0)
        self.make_population_int_entry(company_group, "company_initial_money", "公司初始货币(手动)", 0, 1)
        self.make_population_int_entry(company_group, "company_initial_money_per_capita", "公司每人初始货币", 0, 2)
        self.make_population_int_entry(company_group, "government_initial_money_per_capita", "政府每人初始货币", 0, 3)
        self.make_population_int_entry(company_group, "company_initial_reproduction_goods_ratio", "公司生育库存%", 1, 0)
        self.make_population_int_entry(company_group, "company_initial_education_goods_ratio", "公司教育库存%", 1, 1)
        self.make_population_int_entry(company_group, "government_initial_reproduction_goods_ratio", "政府生育库存%", 1, 2)
        self.make_population_int_entry(company_group, "government_initial_education_goods_ratio", "政府教育库存%", 1, 3)
        self.make_population_int_entry(company_group, "enable_repro_education_inventory_resilience", "生育/教育库存韧性", 2, 0)
        self.make_population_int_entry(company_group, "repro_inventory_target_births_ratio", "生育库存目标%", 2, 1)
        self.make_population_int_entry(company_group, "education_inventory_target_births_ratio", "教育库存目标%", 2, 2)
        self.make_population_int_entry(company_group, "repro_education_inventory_resilience_weight", "库存韧性权重%", 2, 3)
        self.make_population_int_entry(company_group, "company_production_tendency", "公司生产倾向", 3, 0)
        self.make_population_int_entry(company_group, "labor_reward_ratio", "劳动报酬比例", 3, 1)
        self.make_population_int_entry(company_group, "enable_company_hard_need_inventory_release", "公司刚需库存释放", 4, 0)
        self.make_population_int_entry(company_group, "company_hard_need_listing_multiplier", "刚需上架倍数%", 5, 0)
        self.make_population_int_entry(company_group, "company_hard_need_min_listing_ratio", "刚需最低上架比例%", 6, 0)
        self.make_population_int_entry(company_group, "enable_wage_responsive_consumption", "工资响应消费", 3, 2)
        self.make_population_int_entry(company_group, "wage_consumption_bonus_per_survival", "工资消费意愿增量", 3, 3)
        self.make_population_int_entry(company_group, "wage_consumption_bonus_cap", "工资消费意愿上限", 4, 1)
        self.make_population_int_entry(company_group, "production_resource_price", "生产资源价格", 4, 2)
        self.make_population_int_entry(company_group, "company_profit_sensitivity", "公司利润敏感度", 4, 3)
        self.make_population_int_entry(company_group, "individual_buy_willingness", "个体买入意愿", 5, 1)
        self.make_population_int_entry(company_group, "government_buy_willingness", "政府买入意愿", 5, 2)

        self.load_population_to_panel("A")

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="保存参数并开始运行", command=self.start).pack(side="right", padx=8)
        ttk.Button(buttons, text="返回开始界面", command=self.back_to_menu).pack(side="right", padx=8)
        ttk.Button(buttons, text="恢复默认参数", command=self.reset_defaults).pack(side="right", padx=8)

    def collect_settings(self):
        self.save_population_from_panel(self.current_population)
        for path, var in self.vars.items():
            self.set_path(path, bool(var.get()) if isinstance(var, tk.BooleanVar) else int(var.get()))

        self.settings.setdefault("switch_schedules", {})
        for (key, action), var in self.schedule_vars.items():
            self.settings["switch_schedules"].setdefault(key, {"enable_rounds": "", "disable_rounds": ""})
            self.settings["switch_schedules"][key][action] = var.get().strip()

        self.settings = normalize_settings(self.settings)

    def reset_defaults(self):
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)
        save_settings(self.settings)
        self.root.destroy()
        StartConfigWindow().run()

    def back_to_menu(self):
        self.save_population_from_panel(self.current_population)
        self.root.destroy()
        from gui_menu import MainMenuWindow
        MainMenuWindow().run()

    def start(self):
        self.save_population_from_panel(self.current_population)
        if not self.validate_all_entries():
            messagebox.showerror("参数错误", "存在超出范围或非整数的参数，已用红色标出。请修正后再开始。")
            return
        try:
            self.collect_settings()
        except ValueError:
            messagebox.showerror("参数错误", "所有数值参数必须是整数。")
            return
        save_settings(self.settings)
        self.root.destroy()
        from gui_runtime import RuntimeWindow
        RuntimeWindow(self.settings).run()

    def exit_app(self):
        self.root.destroy()
        raise SystemExit

    def run(self):
        self.root.mainloop()
