# BOT8 dev42 实装报告

## 目标

继续核查 dev41 后 5 人早期灭绝和生育用品/教育用品链路问题，并按用户要求：

1. 不采用人口恢复倍率、最低出生率、强制出生、自给补给等外部干预。
2. 对公司生育用品和教育用品库存增加一定韧性，从生产比率和生产意愿相关逻辑入手。
3. 政府和公司初始资金、初始库存默认关联族群大小。
4. 关联算法先运行测试后给出方案。
5. UI 中默认关联开启时，手动输入灰色不可键入；关闭默认后恢复可输入。

## 主要修改

### 1. 按族群规模默认初始资产

新增人口配置：

```python
use_population_scaled_initials = 1
company_initial_money_per_capita = 400
government_initial_money_per_capita = 20
government_initial_food_rounds = 1
government_initial_medical_goods_ratio = 25
government_initial_education_goods_ratio = 25
government_initial_reproduction_goods_ratio = 25
company_initial_food_rounds = 3
company_initial_medical_goods_ratio = 50
company_initial_education_goods_ratio = 100
company_initial_reproduction_goods_ratio = 100
```

含义：

- 公司初始货币 = 初始人口 × 每人公司初始货币。
- 政府初始财政 = 初始人口 × 每人政府初始货币。
- 公司/政府初始库存按初始人口、`survival_cost`、`reproduction_goods_required_per_birth` 计算。
- 关闭 `use_population_scaled_initials` 后，恢复手动 `company_initial_money`。

### 2. 生育用品/教育用品库存韧性

新增：

```python
enable_repro_education_inventory_resilience = 1
repro_inventory_target_births_ratio = 150
education_inventory_target_births_ratio = 100
repro_education_inventory_resilience_weight = 50
```

逻辑：

- 按当前人口计算公司生育用品/教育用品目标储备。
- 若公司库存低于目标储备，则把缺口转换为生产权重。
- 该机制不改变出生条件、不凭空生成库存，只影响公司生产结构。

### 3. UI 逻辑

- 新增 `use_population_scaled_initials` 输入项。
- 当其为 1 时，`company_initial_money` 手动输入框置灰不可编辑。
- 当其为 0 时，`company_initial_money` 恢复正常输入。

## 测试摘要

种子：`20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88`

### 关键对照

| 设置 | 5人×1000 | 10人×1000 |
|---|---:|---:|
| dev41 等价设置 | 8/10 | 10/10 |
| 仅按规模初始资产与库存增强 | 10/10 | 10/10 |
| dev42 默认 | 10/10 | 5/5 已核查 |

### dev42 默认短中期

| 测试 | 存活 | 平均最终人口 | 平均峰值人口 |
|---|---:|---:|---:|
| 5人×10 | 10/10 | 13.9 | 14.4 |
| 5人×100 | 10/10 | 17.2 | 29.6 |
| 5人×1000 | 10/10 | 24.2 | 38.3 |
| 10人×100 | 10/10 | 50.1 | 60.0 |
| 10人×1000（5种子核查） | 5/5 | 53.0 | 67.8 |

货币守恒最大误差：0。

## 结论

最有效的不是单独提高生产韧性，而是先让初始资金/库存规模与族群大小匹配。生育用品/教育用品韧性作为生产侧补强可保留，但当前测试显示大部分稳定性提升来自：

1. 公司初始生育/教育库存从每人 0.5 次出生量提高到 1.0 次出生量；
2. 公司初始资金按人口缩放；
3. 政府拥有少量按人口缩放的公共库存缓冲。

## 下一步建议

进入 dev43：人口峰值后资源压力与稳定区间核查版。

重点不是继续提高生育用品库存，而是检查：

1. dev42 后 10 人族群平均最终人口约 50，是否过高；
2. 人口峰值后是否会自然下降并进入波动区间；
3. 食物短缺和 life_end 的死亡是否形成正常压力；
4. 是否需要调低 `company_initial_money_per_capita`、政府公共库存比例或生育/教育库存目标比例，以避免人口被初始资产推得过高。
