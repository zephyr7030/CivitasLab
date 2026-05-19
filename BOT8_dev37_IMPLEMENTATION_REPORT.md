# BOT8 dev37 实装与诊断报告

版本名：BOT8 dev37：低人口劳动空窗与寿命尾部机制核查版

## 目标

本版只做诊断，不改变工资、生育率、寿命、政府救助、分红默认值或人口机制。

继续遵守：

- 不加入人口恢复倍率
- 不加入最低出生概率
- 不加强制出生
- 不加强制自给补给
- 不让政府凭空创造资源
- 不直接调高默认工资
- 不默认开启库存/超额现金分红

## 关键实现

### 1. 低人口劳动空窗诊断

新增字段：

- PopBelow5TurnCount
- PopBelow3TurnCount
- LaborEligibleCountWhenPopBelow5 / 3
- LaborWillingCountWhenPopBelow5 / 3
- ActualWorkerCountWhenPopBelow5 / 3
- NoWorkerReasonSickCount
- NoWorkerReasonCriticalCount
- NoWorkerReasonLowLaborCount
- NoWorkerReasonNoCompanyDemandCount
- NoWorkerReasonNoExpectedProfitCount
- NoWorkerReasonNoResourceCount
- CompanyDemandForWorkersWhenPopBelow5 / 3
- BranchesWithPositiveExpectedProfitWhenPopBelow5 / 3
- BranchesStoppedByStockWhenPopBelow5
- BranchesStoppedByCashWhenPopBelow5
- BranchesStoppedByResourceWhenPopBelow5
- GovernmentProductionResourceWhenPopBelow5
- CompanyTotalStockWhenPopBelow5
- CompanyTotalMoneyWhenPopBelow5

注意：诊断中会读取旧的公司预期收益评分函数。该函数内部含随机微扰，因此 dev37 在诊断函数内保存并恢复 random 状态，避免“观察行为”改变后续模拟路径。

### 2. 最后 1–3 人状态快照

新增字段：

- LowPopSnapshotCount
- LastIndividualsAvgMoney
- LastIndividualsAvgFood
- LastIndividualsAvgMedicalGoods
- LastIndividualsAvgReproductionGoods
- LastIndividualsAvgLabor
- LastIndividualsAvgReproduce
- LastIndividualsAvgLifeRemaining
- LastIndividualsAvgAge
- LastIndividualsSickCount
- LastIndividualsCriticalCount
- LastIndividualsCanWorkCount
- LastIndividualsCanReproduceCount
- LastIndividualsHasFoodForBirthCount
- LastIndividualsHasReproductionGoodsCount

### 3. 寿命尾部死亡诊断

新增字段：

- LifeEndWithCanReproduce
- LifeEndWithCanWork
- LifeEndWithFoodAndReproductionGoods
- LastDeathLifeRemaining
- LastDeathHadFoodForBirth
- LastDeathHadReproductionGoods
- LastDeathWasSick
- LastDeathWasCritical
- LastDeathCouldWork
- LastDeathCouldReproduce

## 测试

运行：

```bash
python3 -m py_compile *.py
python3 run_dev37_tests.py
```

测试种子：

```text
20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88
```

### 5 人 × 1000

- 存活：0 / 10
- 平均灭绝回合：174.7
- 平均峰值人口：12.8
- 平均出生：66.6
- 平均死亡：71.6
- 货币守恒误差：0

死亡原因累计：

- food_shortage：148
- life_end：487
- medical_goods_shortage：12
- critical_goods_shortage：69

关键诊断均值：

- 平均低人口回合：30.8
- 平均人口低于 3 回合：6.0
- 平均低人口无劳动者回合：9.1
- 平均低人口无工资回合：13.8
- 低人口时平均可劳动资格人数：2.0877
- 低人口时平均候选/愿意劳动人数：1.8801
- 低人口时平均实际劳动人数：0.7178
- 低人口时平均正收益分公司数量：1.2051
- 低人口时平均公司库存：3499.79
- 低人口时平均公司货币：485.47
- 最后 1–2 人平均可工作人数：0.9957
- 最后 1–2 人平均可生育人数：0.0
- 最后 1–2 人有出生食物安全线人数：0.0
- 最后 1–2 人有生育用品人数：0.2941
- life_end 时仍可工作：平均 47.4 次/种子
- life_end 时已同时满足食物与生育用品：平均 1.0 次/种子

### 10 人 × 1000

- 存活：9 / 10
- 平均最终人口：9.8
- 平均峰值人口：24.5
- 平均出生：671.9
- 平均死亡：672.1
- 货币守恒误差：0

唯一灭绝种子：seed=2，第 407 回合灭绝。

## 诊断结论

1. 5 人小族群低人口阶段并不是完全没有劳动资格。低人口时平均可劳动资格人数约 2.09，候选/愿意劳动人数约 1.88，但实际劳动人数只有约 0.72。
2. 低人口时公司通常仍有库存和现金，且平均仍有约 1.2 个正收益分公司。说明“公司完全没资源”不是主因。
3. 低人口劳动链路存在明显断档：平均 30.8 个低人口回合中约 9.1 回合没有劳动者、13.8 回合没有工资。
4. 最后 1–2 人几乎从不满足完整生育条件；主要缺口不是生育意愿，而是父代食物安全线。最后 1–2 人有生育用品的均值仍有 0.2941，但有出生食物安全线的人数为 0。
5. life_end 是 5 人长期灭绝最大死亡原因，但“具备完整生育条件却被寿命截断”的情况较少。更多情况是：个体仍可工作或有生育用品，但缺出生所需父代食物安全库存。
6. 下一步不宜直接调高工资或延长寿命。更优先应核查：低人口下为什么候选劳动者不能稳定变成实际劳动者；以及父代食物安全线在低人口后期为什么长期无法满足。

## 下一步建议

建议进入 dev38：低人口最低劳动岗位与父代食物安全线核查版。

优先方向：

1. 检查公司 positive expected profit 下仍未录用劳动者的原因。
2. 检查 allocated_resource / actual_resource / branch money 在低人口时是否导致候选劳动者未生产。
3. 检查父代食物安全线是否因市场购买量、政府救助顺序或出生后消耗顺序长期无法达到。
4. 不直接调高工资、不改生育率、不延长寿命。
5. 如果证据充分，再考虑“低人口基础岗位保留”或“公司最低运营岗位”，但应基于公司库存/现金/正收益，而不是基于人口恢复倍率。
