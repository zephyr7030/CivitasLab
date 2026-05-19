# BOT8 dev44 实装报告：资源再生利用率与硬需求生产响应修复版

## 1. 本版目标

dev43 诊断显示，5 人和 10 人长期运行时环境资源并未达到极限：`ResourceUseToRegenRatio` 和 `LaborResourceUnusedRate` 表明仍有大量再生资源和劳动资源未被转化为商品。因此 dev44 的目标不是增加初始资源、提高工资或提高出生率，而是修复：

> 硬刚需未满足 + 环境资源仍闲置 + 公司仍可生产时，公司生产结构和分公司预期收益没有足够响应刚需商品。

本版不加入人口恢复倍率、不加入最低出生概率、不强制出生、不凭空创造资源、不降低出生条件、不延长寿命。

## 2. 已修改文件

- `config.py`
- `model.py`
- `output.py`
- `README.md`

## 3. 新增文件

- `parameter_specs.py`
- `run_dev44_tests.py`
- `BOT8_dev44_TEST_RESULTS.json`
- `BOT8_dev44_IMPLEMENTATION_REPORT.md`

## 4. 输出字段修复

`output.py` 新增：

- `validate_summary_headers(data_log, summary_headers)`
- `warn_summary_header_mismatch(data_log, summary_headers)`

并补齐此前已生成但未进入 `SUMMARY_HEADERS` 的字段，包括：

- `UsePopulationScaledInitials`
- `CompanyInitialMoneyEffective`
- `GovernmentInitialMoneyEffective`
- `CompanyInitialEducationStockTarget`
- `CompanyInitialReproductionStockTarget`
- `EducationCompanySellableStock`
- `EducationInventoryResilienceGap`
- `EducationInventoryResilienceWeightAdded`
- `ReproductionInventoryResilienceGap`
- `ReproductionInventoryResilienceWeightAdded`
- `ToolsProducedTotal`
- `ToolsConsumedTotal`
- `MarketFoodVolume`
- `MarketMedicalGoodsVolume`
- `MarketEducationGoodsVolume`
- `MarketReproductionGoodsVolume`
- `PopulationResourceClaim`
- `PopulationResourceQuota`
- `PopulationResourceUsed`
- `PopulationResourceShortage`
- `InternalPlunderVictimLoss`
- `InternalPlunderGain`
- `InternalPlunderSystemLoss`
- `InvasionVictimLoss`
- `InvasionGainTotal`
- `InvasionSystemLoss`

dev44 也新增并导出硬需求生产响应字段。

## 5. 参数元数据原型

新增 `parameter_specs.py`，包含 `ParameterSpec` 数据结构与首批参数元数据：

- `use_population_scaled_initials`
- `labor_reward_ratio`
- `enable_hard_need_production_response`
- `child_initial_balance`

该文件暂不替换旧 GUI 和旧 `config.py`，只作为下一阶段新 GUI、参数说明按钮、参数分级和参数文档自动生成的基础。

## 6. dev44 新增配置

```python
"enable_hard_need_production_response": 1,
"hard_need_resource_use_threshold": 80,
"hard_need_production_response_weight": 80,
"food_hard_need_production_weight": 120,
"medical_hard_need_production_weight": 100,
"reproduction_hard_need_production_weight": 80,
"education_need_production_weight": 50,
"hard_need_production_weight_cap": 300,
```

## 7. 核心机制修改

新增：

- `get_hard_need_unmet_for_production(pop, good)`
- `get_hard_need_production_bonus(pop, good)`

生产阶段使用上一回合硬需求未满足量作为本回合生产信号，因为生产发生在市场之前。

硬需求生产响应同时进入两处：

1. `goods_production_ratios()`：影响商品生产结构权重。
2. `branch_expected_profit_score()`：影响分公司是否被判断为有正收益岗位，从而避免“有硬需求、有资源，但公司仍不招工”。

当上一回合资源使用率达到或超过 `hard_need_resource_use_threshold` 时，不再额外加权，避免在资源接近极限时继续扩大生产。

如果某商品公司库存已经超过运行期库存目标 3 倍，则额外加权衰减为 30%，避免库存过剩继续被强推生产。

## 8. 新增输出字段

- `HardNeedProductionResponseEnabled`
- `FoodHardNeedProductionBonus`
- `MedicalHardNeedProductionBonus`
- `ReproductionHardNeedProductionBonus`
- `EducationNeedProductionBonus`
- `FoodHardNeedUnmetForProduction`
- `MedicalHardNeedUnmetForProduction`
- `ReproductionHardNeedUnmetForProduction`
- `EducationNeedUnmetForProduction`

## 9. 编译与校验

已通过：

```bash
python -m py_compile *.py
```

1 回合 header 校验结果：

```text
missing_headers = []
unused_headers = []
```

## 10. 测试结果

测试种子：

```text
20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88
```

### 5 人 × 1000 × 10 种子

- 存活：10 / 10
- 平均最终人口：32.7
- 平均峰值人口：44.8
- 尾段平均人口：32.7775
- `ResourceUseToRegenRatio`：0.2823
- `LaborResourceUnusedRate`：0.7177
- `FoodHardNeedSatisfiedRate`：0.8484
- `ReproductionHardNeedSatisfiedRate`：0.8351
- `HardNeedBlockedByNoMarketStock`：81569.9
- 货币守恒误差：0

对比 dev43，5 人尾段人口和资源利用率上升，硬需求缺货阻断明显下降。

### 10 人 × 1000 × 5 种子

- 存活：5 / 5
- 平均最终人口：59.0
- 平均峰值人口：74.2
- 尾段平均人口：57.011
- `ResourceUseToRegenRatio`：0.4776
- `LaborResourceUnusedRate`：0.5224
- `FoodHardNeedSatisfiedRate`：0.8348
- `ReproductionHardNeedSatisfiedRate`：0.8779
- 货币守恒误差：0

### 20 人 × 500 × 3 种子

- 存活：3 / 3
- 平均最终人口：90.6667
- 平均峰值人口：119.3333
- 尾段平均人口：94.8867
- `ResourceUseToRegenRatio`：0.7125
- `LaborResourceUnusedRate`：0.2875
- `ResourceLimitReached`：0.0983
- 货币守恒误差：0

## 11. 结论

dev44 方向有效：生产响应接入分公司预期收益后，人口规模、刚需满足率和资源利用率均提升。20 人测试已开始接近资源使用阈值，说明模型的人口限制正在逐步转向资源限制。

但仍有问题：

- 5 人与 10 人尾段 `ResourceUseToRegenRatio` 仍低于 1。
- `HardNeedBlockedByNoMarketStock` 仍不为 0。
- 食物短缺死亡仍然存在，说明公司生产、订单簿上架、政府库存回流之间仍有损耗。

## 12. 下一步建议：dev45

建议 dev45 聚焦：

1. 检查公司生产后是否足量进入订单簿，而不是只停留在公司库存。
2. 检查公司生产资源购买是否仍受分公司现金不均衡影响。
3. 检查医疗用品生产与医疗刚需满足率，当前医疗满足率仍低于食物/生育用品。
4. 检查 20 人测试接近资源阈值后，人口是否会自然回落并稳定波动。
5. 开始实现 `output_schemas.py`，把 summary_core、market、company、government、diagnostics 拆分。
