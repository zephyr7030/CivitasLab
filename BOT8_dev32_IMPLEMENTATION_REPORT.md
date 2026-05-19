# BOT8 dev32 实装与核查报告

版本名：BOT8 dev32：濒死、寿命断代、小族群工资闭环核查版

## 原则

本版继续遵守当前开发原则：

- 不加入人口恢复倍率
- 不加入最低出生概率
- 不加入强制出生
- 不加入强制自给补给
- 不加入政府额外创造资源或无限补贴
- 不直接把提高生育意愿作为默认修复手段

本版只新增诊断字段与测试脚本，用于判断 5 人小族群长期灭绝的具体链路。

## 修改文件

- `config.py`
  - 版本号 31 -> 32
- `model.py`
  - 新增濒死、寿命断代、小族群工资—食物闭环诊断字段
- `output.py`
  - 新增 summary 输出字段
- `README.md`
  - 增加 dev32 说明

## 新增文件

- `run_dev32_tests.py`
- `quick_dev32_parallel.py`
- `BOT8_dev32_CHECK_RESULTS.json`
- `BOT8_dev32_IMPLEMENTATION_REPORT.md`

## 新增诊断字段

- `AvgAgeRound`
- `MinAgeRound`
- `MaxAgeRound`
- `AvgLifeRemaining`
- `MinLifeRemaining`
- `MaxLifeRemaining`
- `DeathsByLifeEndWhenPopulationBelow3`
- `DeathsByLifeEndWhenPopulationBelow5`
- `DeathsByFoodShortageWhenPopulationBelow5`
- `DeathsByMedicalShortageWhenPopulationBelow5`
- `DeathsByCriticalGoodsShortageWhenPopulationBelow5`
- `EnteredCriticalWhenPopulationBelow5`
- `RecoveredCriticalWhenPopulationBelow5`
- `WorkersWhenPopulationBelow5`
- `WagePaidWhenPopulationBelow5`
- `FoodBoughtWhenPopulationBelow5`
- `CompanyFoodStockWhenPopulationBelow5`
- `GovernmentFoodWhenPopulationBelow5`

这些字段只记录状态，不改变模拟行为。

## 编译检查

已通过：

```bash
python3 -m py_compile *.py run_dev32_tests.py quick_dev32_parallel.py
```

## 关键测试结果

测试种子：

```text
20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88
```

### 默认初始生育意愿 50

10 人 × 100 回合：

- 10 / 10 存活
- 平均最终人口：10.4
- 货币守恒误差：0

10 人 × 1000 回合：

- 9 / 10 存活
- 灭绝种子：88，第 440 回合
- 平均最终人口：9.9
- 平均人口：11.22
- 货币守恒误差：0

5 人 × 1000 回合：

- 0 / 10 存活
- 平均灭绝回合：167.5
- 平均人口：6.43
- 货币守恒误差：0

### 初始生育意愿 55 对比

10 人 × 1000 回合：

- 8 / 10 存活
- 平均最终人口：10.1
- 平均人口：11.64

5 人 × 1000 回合：

- 0 / 10 存活
- 平均灭绝回合：223.7
- 平均人口：6.11

### 初始生育意愿 60 对比

10 人 × 1000 回合：

- 9 / 10 存活
- 平均最终人口：12.1
- 平均人口：11.38

5 人 × 1000 回合：

- 0 / 10 存活
- 平均灭绝回合：140.8
- 平均人口：6.59

## 对“加大初始生育意愿参数”的判断

不建议 dev32 直接把默认初始生育意愿从 50 提高到 60。

理由：

1. 10 人 × 1000 回合下，50 与 60 都是 9 / 10 存活，60 没有解决长期灭绝问题。
2. 5 人 × 1000 回合下，60 反而让平均灭绝回合从 167.5 降到 140.8。
3. 生育意愿提高会减少 `LowReproduceChance`，但会增加出生尝试，从而同步放大 `NoReproductionGoods` 和 `NoFoodSafety` 阻断。
4. 当前更像是“生育用品/食物安全/寿命断代/低人口经济循环”共同限制，而不是单纯生育意愿不足。

可考虑把 55 作为小族群实验预设，因为它把 5 人平均灭绝回合提高到 223.7，但它会让 10 人 × 1000 的存活数从 9/10 降到 8/10，因此不应作为默认全局值。

## 新建议

下一步不建议继续提高生育意愿，而建议：

1. 核查生育用品与食物安全线的耦合。当前提高生育意愿会增加 `NoReproductionGoods` 和 `NoFoodSafety`，说明繁殖链路的瓶颈在物资与食物安全，而不是纯概率。
2. 核查小族群低人口时的工资—食物购买闭环。dev32 诊断已显示低于 5 人时仍有工资和食物购买，但不能稳定避免灭绝，需要进一步看购买后是否被同回合生存/繁殖消耗击穿。
3. 核查寿命断代是否需要从“剩余 life 随机”改为更真实的初始年龄结构，而不是运行中强制续命。
4. 对生育用品释放做受限实验，而不是默认开启公共释放。只允许释放超过政府保留库存且当前可繁殖个体有足够父代食物的部分。
5. 增加“小族群正常初始条件预设 v2”，把初始生育用品从 1 次出生量调整到 2 次出生量进行测试，但仍只影响初始化，不运行中补贴。
