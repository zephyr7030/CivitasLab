# BOT8 dev29 实装报告：繁殖链路与生存阶段逻辑修复版

## 开发原则

本次修复严格遵守用户提出的限制：

- 不加入人口恢复倍率。
- 不加入最低出生概率。
- 不加入强制出生。
- 不加入强制自给补给。
- 不加入政府额外创造资源或无限补贴。
- 优先修复代码逻辑错误、旧变量语义残留、阶段顺序错误和需求判断冲突。

## 修改文件

- `config.py`
- `model.py`
- `output.py`
- `gui_settings.py`
- `README.md`

## 核心修复

### 1. 新生儿出生当回合不再消耗食物

修复前：

`reproduce_phase()` 创建子代并赋予 `child.food = survival_cost`，随后同一回合进入 `survival_phase()`，子代立刻消耗这份食物。

修复后：

`survival_phase()` 跳过 `birth_turn == self.turn` 的新生儿。本回合出生的新生儿从下一回合开始参与完整生存周期。

### 2. 拆分 child_initial_balance 旧语义

新增参数：

- `child_initial_money`
- `child_initial_food`
- `reproduction_goods_required_per_birth`
- `parent_food_required_for_birth_multiplier`

`child_initial_balance` 保留为旧设置/旧 GUI 兼容字段，不再同时代表货币、食物和生育用品。

### 3. 修复生育用品需求被贫穷状态归零

修复前：

```python
if poor or ind.reproduce < 10 or sick or critical:
    return 0
```

修复后：

```python
if ind.reproduce < 10 or sick or critical:
    return 0
if ind.food < survival_cost:
    return 0
return reproduction_goods_required_per_birth
```

货币余额不再决定是否存在生育用品需求，只决定实际购买能力。

### 4. 生育用品硬买方条件前移

购买准备条件从 `food >= survival_cost * 3` 放宽为 `food >= survival_cost`。真正出生仍由 `parent_food_required_for_birth()` 控制，默认仍是 3 倍基础食物。

### 5. 政府剩余价值删除后移

修复前：市场阶段内，政府购买后立即执行剩余价值删除。

修复后：剩余价值删除移动到回合末，在政府救助、繁殖和生存阶段之后执行。

这避免刚买入或死亡遗留的公共库存尚未服务本回合既有用途就被删除。

### 6. 初始年龄分布

代码支持 `enable_initial_age_distribution`，但默认关闭。

检查结论：当前初始个体 `life` 已在 17-23 之间随机。默认开启年龄分布会过度压缩开局个体剩余寿命，导致部分种子早期灭绝更严重，因此作为实验选项保留，不默认启用。

## 新增输出字段

- `NewbornSurvivalSkippedCount`
- `ReproductionGoodsDemandCount`
- `ReproductionGoodsDemandBlockedByPoorOldLogic`
- `ReproductionGoodsDemandBlockedByFood`
- `ReproductionGoodsDemandBlockedBySickOrCritical`
- `ReproductionGoodsSpendingBlockedByPoorOldLogic`
- 个体输出新增 `InitialAgeRounds`

## 测试结果

测试条件：

- 部族数：1
- 初始人口：10
- 随机种子：20260517、1、2、3、42、100、999、2026、17、88

### 10 人 × 100 回合

10/10 存活。

最终人口分别为：

```text
9, 6, 12, 12, 11, 16, 19, 5, 13, 7
```

总货币守恒误差：0。

### 10 人 × 1000 回合

8/10 存活。

灭绝种子：

- seed = 1，第 163 回合灭绝。
- seed = 999，第 943 回合灭绝。

总货币守恒误差：0。

## 结论

dev29 明显改善了 10 人 × 100 回合稳定性，但在“不加入强制人口恢复机制”的约束下，长期 1000 回合仍存在随机断代风险。

下一步建议继续查逻辑闭环，而不是立刻加入人口恢复倍率：

1. 食物短缺为什么仍会在政府有库存的回合发生。
2. 公司生产、工资、个体购买力之间是否仍有长周期断流。
3. 政府库存上限是否对小族群过低，导致回合末删除过多公共食物。
4. 寿命结束是否需要从硬倒计时改成概率曲线；这属于机制重设，需单独确认。
