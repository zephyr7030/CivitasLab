# BOT8 2.0.0 / dev28 当前交接文件

## 0. 当前分支

- 项目：BOT8：生物演化
- 当前代码版本：BOT8 dev28
- 基础版本：BOT8_dev27_full_model.zip
- 本次开发目标：优先完成 dev28 的“公司库存流通与停产清算修复”，保留但暂不执行 GUI 大改。

## 1. 本次优先级裁定

本项目同时有两份交接文档：

1. `docs/BOT8_2.0.0_HANDOFF_DEV28_PLAN.md`：要求 dev28 优先修复公司历史库存不上架问题。
2. `docs/BOT8_2.0.0_HANDOFF_GUI_PLAN.md`：要求后续新增 PySide6 + PyQtGraph 新 GUI 原型。

由于 dev28 文档明确指出当前最确定的结构性问题是“公司停产后历史库存不上架，政府和个体买不到公司库存，导致收入与工资断流”，因此本次开发先完成机制修复。GUI 计划继续保留到后续版本，不在 dev28 混入执行。

## 2. dev28 已完成内容

### 2.1 公司历史库存进入订单簿

原 dev27 逻辑：

```text
公司卖单上架量 = min(公司库存, 本回合生产量)
```

问题：当公司停产时，本回合生产量为 0，即使公司仍有大量历史库存，也不会进入订单簿。

当前 dev28 逻辑：

```text
sellable = company_sellable_amount(pop, good)
produced = 本回合生产量
inventory_based = sellable * listing_ratio
listing_amount = min(sellable, max(produced, inventory_based))
```

这样即使本回合生产量为 0，只要存在可售库存，公司仍会继续上架历史库存。

### 2.2 上架比例

- 普通库存：上架 20% 可售库存。
- 库存严重过剩：上架 50% 可售库存。
- 判断标准：`stock > initial_stock * 3`。
- 若 `initial_stock <= 0`，按严重过剩处理，避免除零或库存目标缺失导致不上架。

### 2.3 公司价格梯度

普通库存：

```text
0.7 - 1.8 × 当前价格
```

严重过剩库存：

```text
0.3 - 1.0 × 当前价格
```

单笔交易仍保留最低总价保护，避免 0 价格成交。

### 2.4 生产决策与销售决策分离

公司仍可因预期收益不佳而：

```text
0 招工
0 新生产
```

但不再因此退出市场。订单簿阶段仍会执行历史库存上架、个体购买、政府最后购买、剩余价值清理和价格结算。

### 2.5 新增统计字段

汇总输出新增：

```text
CompanyInventoryListed
CompanyInventorySoldToIndividuals
CompanyInventorySoldToGovernment
CompanyInventoryUnsold
CompanyInventoryListingRatio
CompanyOrderbookAskCount
```

商品细分新增：

```text
FoodCompanyInventoryListed
FoodCompanySoldToIndividuals
FoodCompanySoldToGovernment
FoodCompanyInventoryUnsold
MedicalCompanyInventoryListed
MedicalCompanySoldToIndividuals
MedicalCompanySoldToGovernment
MedicalCompanyInventoryUnsold
EducationCompanyInventoryListed
EducationCompanySoldToIndividuals
EducationCompanySoldToGovernment
EducationCompanyInventoryUnsold
ReproductionCompanyInventoryListed
ReproductionCompanySoldToIndividuals
ReproductionCompanySoldToGovernment
ReproductionCompanyInventoryUnsold
```

`market.csv` 也新增按商品展开的：

```text
CompanyInventoryListed
CompanySoldToIndividuals
CompanySoldToGovernment
CompanyInventoryUnsold
```

## 3. 修改文件

### 修改

- `config.py`
  - `PROJECT_VERSION` 从 `27` 更新为 `28`。
- `model.py`
  - 新增公司库存上架比例函数。
  - 修改公司订单簿上架量算法。
  - 修改公司价格梯度算法。
  - 新增公司库存流通统计。
  - 新增订单簿结束后的公司未售库存统计。
  - 修正订单簿交易中“先扣款后校验卖方库存”的潜在安全问题。
- `output.py`
  - 新增 summary.xlsx / summary csv 相关字段。
  - 新增 market.csv 公司库存流通字段。
- `README.md`
  - 新增 dev28 说明。

### 新增

- `BOT8_2.0.0_HANDOFF.md`
- `BOT8_dev28_IMPLEMENTATION_REPORT.md`
- `docs/BOT8_2.0.0_HANDOFF_DEV28_PLAN.md`
- `docs/BOT8_2.0.0_HANDOFF_GUI_PLAN.md`

### 未删除

- 未删除旧 GUI。
- 未删除旧图表代码。
- 未删除 GUI 文案。
- 未删除感叹号说明按钮文本。
- 未改变旧 GUI 启动方式。

## 4. 启动方式

旧 GUI 仍按原方式启动：

```bash
python main.py
```

Windows 下也可运行：

```bash
python main.pyw
```

## 5. 已运行检查

已运行：

```bash
python -m py_compile *.py
```

通过。

已运行无 GUI 长测：

1. 5 人 × 1000 回合，随机种子 20260517。
2. 10 人 × 100 回合，随机种子 20260517。
3. 10 人 × 1000 回合，随机种子 20260517。

结果摘要见 `BOT8_dev28_IMPLEMENTATION_REPORT.md`。

## 6. 当前测试结论

最低验收项已达成：

- 不报错。
- 总货币守恒。
- 公司停产后仍能继续上架历史库存。
- 存在 `CompanyGoodsProduced = 0` 且 `CompanyInventoryListed > 0` 的回合。
- 政府最后买方能买到公司历史库存。
- `CompanyInventoryUnsold`、`CompanyInventorySoldToGovernment`、`CompanyInventorySoldToIndividuals` 有记录。
- 剩余价值机制有记录。

但理想验收项未完全达成：

- 10 人 × 100 回合仍在第 88 回合归零。
- dev28 修复了“库存不上架”问题，但没有完全解决人口断裂。

## 7. dev29 建议方向

由于 dev28 后公司库存已能流通，但人口仍会归零，下一步不应回退本次修复，而应继续观察以下链条：

1. 公司销售库存获得收入后，是否能触发复产。
2. 公司库存销售收入是否需要进入分红或复产预算。
3. 停产期间个体无工资，是否需要“库存销售收益回流劳动者”机制。
4. 政府购买后的剩余价值删除是否过快抽走实物流通。
5. 小群体寿命结束压力是否大于繁殖补充速度。

建议 dev29 名称：

```text
BOT8 dev29：公司复产与库存销售收入回流校准版
```

dev29 不建议立即大改 GUI。GUI 原型可作为独立分支执行，避免和机制校准互相干扰。
