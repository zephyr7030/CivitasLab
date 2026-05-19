# BOT8 dev43：资源极限诊断与初始规模关联校验版

## 目标

本版继续核查 dev42 的 1-6 项，并特别回应：最终人口限制只能来自资源限制。

本版不改变模型行为，只新增资源极限诊断字段与运行期库存目标观察字段。曾实验将运行期库存目标直接用于公司过剩惩罚，但 5 人 × 1000 退化为 0/10 存活，因此未保留该行为修改。

## 新增诊断字段

- EnvResourceUseRate
- ResourceUseToRegenRatio
- LaborResourceUnused
- LaborResourceUnusedRate
- ResourceLimitReached
- FoodOperatingStockTarget
- MedicalOperatingStockTarget
- EducationOperatingStockTarget
- ReproductionOperatingStockTarget

## 关键核查结果

### 5 人 × 1000 × 10 种子

- 存活：10/10
- 平均最终人口：24.2
- 平均峰值人口：38.3
- 尾段平均人口：25.02
- ResourceUseToRegenRatio：0.193
- LaborResourceUnusedRate：0.807
- ResourceLimitReached：0.0
- EnvHealth：100

结论：5 人测试已经稳定，但远未达到环境资源极限。人口限制仍主要来自商品供给、订单簿库存、工资/购买力、寿命与食物短缺链路，而不是环境资源上限。

### 10 人 × 1000 × 5 种子

- 存活：5/5
- 平均最终人口：53
- 平均峰值人口：67.8
- 尾段平均人口：51.78
- ResourceUseToRegenRatio：0.3736
- LaborResourceUnusedRate：0.6264
- ResourceLimitReached：0.0
- EnvHealth：100

结论：10 人测试人口约 50 并不过高；但仍未达到环境资源极限。当前资源再生量仍大量未转化为实际生产。

## 对 1-6 项的结论

1. 10 人最终人口约 50 不过高，但尚未达到环境极限。资源使用只有再生量的约 37%。
2. 峰值后有下降与波动，但不是资源极限造成，而是市场/商品链路造成。
3. 食物短缺与寿命死亡仍是主要压力，但食物短缺发生时环境资源并未耗尽。
4. company_initial_money_per_capita 暂不应继续调高；货币不是当前最明确瓶颈。
5. 政府公共库存比例暂不应继续调高；它会提高缓冲，但不能让人口上限自然转向资源限制。
6. 生育用品/教育用品初始比例不应继续简单上调；当前更重要的是生产系统能否把未使用的再生资源转成商品。

## 下一步建议

进入 dev44：资源再生利用率与硬需求生产响应修复版。

重点不是增加初始库存，而是让已有机制在硬刚需未满足、环境再生仍大量闲置时，自然提高劳动转化和对应商品生产，使最终人口限制逐步转向环境资源再生上限。
