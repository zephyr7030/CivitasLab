# BOT8 dev28 实装报告

## 1. 实装目标

基于 dev27 完整包完成 dev28 核心修复：公司即使不生产，也必须把部分可售历史库存挂到订单簿。库存越过剩，上架比例越高，价格越低。

## 2. 核心修改

### 2.1 公司库存上架量

修改前：

```python
listing_amount = min(stock, goods_produced)
```

修改后：

```python
sellable = company_sellable_amount(pop, good)
produced = branch["goods_produced"]
inventory_based = sellable * listing_ratio
listing_amount = min(sellable, max(produced, inventory_based))
```

### 2.2 上架比例

```python
if initial_stock <= 0 or stock > initial_stock * 3:
    listing_ratio = 0.50
else:
    listing_ratio = 0.20
```

### 2.3 价格梯度

普通库存：

```text
0.7 - 1.8 × 当前价格
```

严重过剩库存：

```text
0.3 - 1.0 × 当前价格
```

### 2.4 输出统计

新增总字段：

- CompanyInventoryListed
- CompanyInventorySoldToIndividuals
- CompanyInventorySoldToGovernment
- CompanyInventoryUnsold
- CompanyInventoryListingRatio
- CompanyOrderbookAskCount

新增商品细分字段并同步到 market.csv。

## 3. 检查结果

### 3.1 编译检查

```bash
python -m py_compile *.py
```

结果：通过。

### 3.2 测试 A：5 人 × 1000 回合

设置：

- 部族数：1
- 初始人口：5
- 最大回合：1000
- 随机种子：20260517
- 人口为 0 停止

结果：

```text
实际运行回合：56
最终人口：0
累计出生：19
累计死亡：24
最后一回合 CompanyGoodsProduced：0
最后一回合 CompanyInventoryListed：54
最后一回合 CompanyInventorySoldToGovernment：54
最后一回合 CompanyInventorySoldToIndividuals：0
最后一回合 CompanyInventoryUnsold：0
最后一回合 GovernmentSurplusValueTotal：36
存在 CompanyGoodsProduced = 0 且 CompanyInventoryListed > 0 的回合：21
首次出现该情况：第 8 回合
最大 CompanyInventoryListed：2895
最大 CompanyInventorySoldToGovernment：2013
最大 CompanyInventorySoldToIndividuals：1191
总货币：1500 -> 1500，守恒
```

### 3.3 测试 B：10 人 × 100 回合

设置：

- 部族数：1
- 初始人口：10
- 最大回合：100
- 随机种子：20260517
- 人口为 0 停止

结果：

```text
实际运行回合：88
最终人口：0
累计出生：23
累计死亡：33
最后一回合 CompanyGoodsProduced：0
最后一回合 CompanyInventoryListed：854
最后一回合 CompanyInventorySoldToGovernment：0
最后一回合 CompanyInventorySoldToIndividuals：109
最后一回合 CompanyInventoryUnsold：745
最后一回合 GovernmentSurplusValueTotal：0
存在 CompanyGoodsProduced = 0 且 CompanyInventoryListed > 0 的回合：36
首次出现该情况：第 9 回合
最大 CompanyInventoryListed：4602
最大 CompanyInventorySoldToGovernment：2024
最大 CompanyInventorySoldToIndividuals：1503
总货币：2000 -> 2000，守恒
```

### 3.4 测试 C：10 人 × 1000 回合

结果与测试 B 相同，因第 88 回合人口归零后停止。

## 4. 验收判断

### 已达成

- 不报错。
- 总货币守恒。
- 公司停产后仍会继续上架历史库存。
- `CompanyInventoryListed > 0`，即使 `CompanyGoodsProduced = 0`。
- 政府最后买方能买到公司历史库存。
- `CompanyInventoryUnsold`、`CompanyInventorySoldToGovernment`、`CompanyInventorySoldToIndividuals` 有记录。
- 剩余价值机制有记录。

### 未达成或需继续校准

- 10 人 × 100 回合未能存活到第 100 回合。
- dev28 修复库存僵死，但人口仍会断裂。
- 停产后虽然历史库存可销售，公司收入恢复，但该收入尚未充分转化为工资、分红或复产动力。

## 5. dev29 建议

建议 dev29 聚焦：公司复产与库存销售收入回流。

可检查方向：

1. 分公司获得库存销售收入后，是否应该降低预期收益惩罚或提高复产概率。
2. 公司历史库存销售收入是否应该触发劳动者分红、公共财政回流或复产准备金。
3. 政府购买后剩余价值删除是否过早减少可救助库存。
4. 小初始人口下寿命结束死亡是否需要单独校准。

不建议在 dev29 同时进行 GUI 大改，以免机制调试和界面重构互相干扰。
