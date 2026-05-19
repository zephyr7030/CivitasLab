# BOT8 dev40 实装报告：刚需消费预算释放与订单簿购买语义修复版

## 目标

修复订单簿个体购买阶段中“刚性需求被普通消费意愿/价格折扣/储备预算比例过度压缩”的问题。

dev40 不修改工资、生育率、寿命、政府补贴或人口恢复逻辑，只让已有现金、已有库存、已有刚需之间正确发生关系。

## 主要修改

### 1. 新增需求类型

新增需求类型常量：

- `NEED_FOOD_HARD = "food_hard"`
- `NEED_MEDICAL_HARD = "medical_hard"`
- `NEED_REPRODUCTION_HARD = "reproduction_hard"`
- `NEED_REPRODUCTION_RESERVE = "reproduction_reserve"`
- `NEED_FOOD_RESERVE = "food_reserve"`
- `NEED_MEDICAL_RESERVE = "medical_reserve"`
- `NEED_EDUCATION = "education"`

### 2. 按需求类型释放预算

新增/改造：

- `individual_effective_buy_willingness(buyer, good=None, need_kind=None)`
- `individual_orderbook_spending_cap_by_need(buyer, good, price_index, need_kind, need_amount)`
- `orderbook_purchase_one_good(..., need_kind=None)`
- `execute_orderbook_trade(..., need_kind=None)`

规则：

- 食物刚需：可使用当前全部现金；只买生存缺口。
- 医疗刚需：生病个体可使用当前剩余现金；只买医疗刚需缺口。
- 生育用品刚需：满足准备条件后可使用 90% 当前剩余现金；只买生育用品刚需缺口。
- 储备/教育：沿用原来的 `market_spending_limit`、`individual_buy_willingness`、工资响应消费和价格敏感规则。

### 3. 新增诊断字段

新增 summary 输出字段：

- `FoodHardNeedCount`
- `FoodHardNeedAmount`
- `FoodHardSpendingCap`
- `FoodHardActualSpending`
- `FoodHardSatisfiedAmount`
- `FoodHardUnsatisfiedAmount`
- `MedicalHardNeedCount`
- `MedicalHardNeedAmount`
- `MedicalHardSpendingCap`
- `MedicalHardActualSpending`
- `MedicalHardSatisfiedAmount`
- `MedicalHardUnsatisfiedAmount`
- `ReproductionHardNeedCount`
- `ReproductionHardNeedAmount`
- `ReproductionHardSpendingCap`
- `ReproductionHardActualSpending`
- `ReproductionHardSatisfiedAmount`
- `ReproductionHardUnsatisfiedAmount`
- `HardNeedSpendingTotal`
- `ReserveNeedSpendingTotal`
- `HardNeedBlockedByNoCash`
- `HardNeedBlockedByNoMarketStock`
- `HardNeedBlockedByHighPrice`
- `HardNeedBlockedByBudgetCap`
- `FoodHardNeedSatisfiedRate`
- `MedicalHardNeedSatisfiedRate`
- `ReproductionHardNeedSatisfiedRate`

## 行为探针

固定测试：`balance = 200`、`price_index = 200`。

- 食物刚需预算 cap：`200`
- 医疗刚需预算 cap：`200`
- 生育用品刚需预算 cap：`180`
- 食物储备预算 cap：`80`

说明刚需已经不再被旧的 80% 预算、价格折扣和普通买入意愿压缩；储备需求仍然保持旧的价格敏感机制。

## 测试摘要

测试种子：`20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88`。

| 测试 | 存活 | 平均最终人口 | 平均峰值人口 | 平均灭绝回合 |
|---|---:|---:|---:|---:|
| 5人 × 10回合 | 10/10 | 10.4 | 12.2 | - |
| 5人 × 100回合 | 7/10 | 5.9 | 15.1 | 59.67 |
| 5人 × 1000回合 | 2/10 | 2.1 | 18.1 | 232.0 |
| 10人 × 100回合 | 10/10 | 13.8 | 28.2 | - |
| 10人 × 1000回合 | 10/10 | 19.9 | 34.7 | - |

货币守恒误差：`0`。

## 结论

1. dev40 代码层面完成了“刚需预算释放”和“储备预算价格敏感”的双层消费模型。
2. 10 人长期稳定性保持：10人 × 1000 回合为 10/10 存活。
3. 5 人长期仍未完全稳定：5人 × 1000 回合为 2/10 存活，低于 dev39 的 3/10，但平均峰值人口更高，说明刚需预算释放放大了人口增长和后续资源压力。
4. 刚需未满足的主要阻断已经更多暴露为现金不足和订单簿库存不足，而不是预算 cap 错误。

## 下一步建议

不要回退 dev40 的刚需预算语义；它修复了真实逻辑错误。但下一步应检查：

1. 为什么刚需预算释放后，`HardNeedBlockedByNoMarketStock` 仍很高；
2. 为什么 5 人快速增长后食物/生育用品订单簿库存仍不能稳定覆盖底层个体；
3. 是否需要调整公司商品生产结构、分公司初始资金比例或政府生产资源出售结构，而不是继续提高工资/生育率；
4. 继续观察 5 人小族群是否因为增长更快而过早触发资源压力。
