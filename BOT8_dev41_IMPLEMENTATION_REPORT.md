# BOT8 dev41 实装报告：公司硬刚需库存释放与订单簿供给核查版

## 修改原则

本版本继续遵守：

- 不加入人口恢复倍率
- 不加入最低出生概率
- 不强制出生
- 不加入自给补给
- 不让政府凭空创造资源
- 不继续调高工资
- 不降低父代食物安全线
- 不延长寿命

本版本只修复订单簿供给侧的逻辑问题：公司已有食物/医疗库存时，如果市场中存在对应刚性需求，不应继续让“分公司初始库存目标”完全阻断上架。

## 核查发现

在 dev40 中，刚需消费预算释放已经修复，但仍出现大量 `HardNeedBlockedByNoMarketStock`。进一步核查发现：

- 低人口尾段，个体存在食物刚需；
- 公司食物分公司仍有大量库存；
- 但 `company_sellable_amount()` 因为 `initial_stock` 目标，只允许极少量食物进入订单簿；
- 结果是公司有库存、个体有刚需、但订单簿可买库存不足。

典型现象：公司食物库存约 1600–1800，但订单簿食物上架只有几十单位，食物刚需无法满足。

## 应用修改

新增人口配置参数：

```python
enable_company_hard_need_inventory_release = 1
company_hard_need_listing_multiplier = 100
company_hard_need_min_listing_ratio = 50
```

机制含义：

- 仅对 `food` 和 `medical_goods` 生效；
- 当当前回合存在食物/医疗刚性需求，或上一回合对应商品未满足需求时，公司可动用库存进入订单簿；
- 公司仍按订单簿出售并获得货币，不创造资源；
- 生育用品不纳入本次新增释放规则，避免放大出生波动；生育用品继续沿用已有 hard buyer 规则。

新增函数：

- `population_current_hard_need()`
- `company_hard_need_release_pressure()`
- `company_hard_need_inventory_release_enabled()`

修改函数：

- `company_sellable_amount()`
- `company_inventory_listing_ratio()`
- `orderbook_company_listing_amount()`

新增输出字段：

- `CompanyHardNeedReleaseEnabledCount`
- `FoodCompanyHardNeedPressure`
- `MedicalCompanyHardNeedPressure`
- `ReproductionCompanyHardNeedPressure`
- `FoodCompanySellableStock`
- `MedicalCompanySellableStock`
- `ReproductionCompanySellableStock`
- `FoodCompanyHardNeedReleaseListed`
- `MedicalCompanyHardNeedReleaseListed`
- `ReproductionCompanyHardNeedReleaseListed`

## 测试结果

测试种子：

```text
20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88
```

| 测试 | dev40 存活 | dev41 存活 | 说明 |
|---|---:|---:|---|
| 5 人 × 10 回合 | 10/10 | 10/10 | 保持稳定 |
| 5 人 × 100 回合 | 7/10 | 8/10 | 小幅改善 |
| 5 人 × 1000 回合 | 2/10 | 8/10 | 显著改善 |
| 10 人 × 100 回合 | 10/10 | 10/10 | 保持稳定 |
| 10 人 × 1000 回合 | 10/10 | 10/10 | 保持稳定 |

货币守恒误差：0。

## 新结论

公司硬刚需库存释放是有效修复：

- 5 人 × 1000 从 dev40 的 2/10 存活提升到 dev41 的 8/10 存活；
- 10 人 × 1000 保持 10/10 存活；
- 说明 dev40 后的主要瓶颈之一确实是“公司库存没有足量进入订单簿”。

但仍有两个 5 人种子灭绝：

- seed 999：第 34 回合灭绝，峰值人口 7，出生 7，死亡 12；
- seed 17：第 73 回合灭绝，峰值人口 16，出生 25，死亡 30。

下一步建议继续核查早期灭绝种子，不要再扩大食物释放比例。重点看：

1. seed 999 为什么早期峰值人口只有 7；
2. seed 17 是否属于 life_end 断代；
3. 医疗用品库存释放是否仍存在类似食物的供给断层；
4. 生育用品 hard buyer 规则是否过于保守，但不要直接放开生育用品释放。
