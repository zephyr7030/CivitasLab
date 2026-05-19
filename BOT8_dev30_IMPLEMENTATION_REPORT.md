# BOT8 dev30 实装报告：订单簿购买优先级与宏观调控开关语义修复版

## 开发原则

本版继续遵守 dev29 后确立的原则：优先修复代码逻辑错误，不加入外部强制干预。

本版未加入：

- 人口恢复倍率
- 最低出生概率
- 强制出生
- 强制自给补给
- 政府额外创造资源或无限补贴
- 默认寿命、生育倾向、工资比例或人口参数调高

## 修改文件

- `config.py`
- `model.py`
- `README.md`

## 新增文件

- `run_dev30_tests.py`
- `BOT8_dev30_TEST_RESULTS_10SEEDS.json`
- `BOT8_dev30_TEST_RESULTS_5P_1000_10SEEDS.json`
- `BOT8_dev30_IMPLEMENTATION_REPORT.md`

## 主要修改

### 1. 订单簿买方内部优先级

dev27 订单簿把所有“买方-商品需求”完全随机打散，导致同一个体可能在缺食物时先购买生育用品、教育用品或其他储备品。

dev30 改为：

- 买方之间仍随机排序；
- 单个买方内部按需求优先级购买；
- 不强制成交，不创造商品，不提高出生率。

### 2. 刚性需求与储备需求拆分购买

第一版“买方内部优先级”如果只按商品排序，会导致食物刚性阶段顺便买入食物储备，挤出生育用品预算。

最终 dev30 改为按需求类型排序：

1. 食物刚性需求：只补足本回合生存线；
2. 医疗刚性需求；
3. 生育用品刚性需求；
4. 生育用品储备需求；
5. 食物储备需求；
6. 医疗储备需求；
7. 教育用品需求。

### 3. 生育用品优先统计接入订单簿路径

旧 `reproduction_goods_priority_sale_phase()` 保留，但不再作为真实市场主路径。

dev30 在订单簿购买阶段对生育用品刚性买方记录：

- `ReproductionGoodsHardBuyerCount`
- `ReproductionGoodsHardDemandTotal`
- `ReproductionGoodsHardDemandSatisfied`
- `ReproductionGoodsHardDemandUnsatisfied`
- `ReproductionGoodsBlockedNoCompanyStock`
- `ReproductionGoodsBlockedNoMoney`

### 4. 政府订单簿最后买方受宏观调控开关控制

`government_orderbook_purchase_phase()` 现在只在：

```python
self.is_feature_enabled("enable_government_macro_control")
```

为 True 时执行。

该修改修复了“GUI / 配置显示宏观调控关闭，但政府仍作为订单簿最后买方购买”的语义不一致。

## 测试结果摘要

### 10 人 × 100 回合 × 10 种子

- 存活：10 / 10
- 平均最终人口：10.4
- 最大货币守恒误差：0

### 10 人 × 1000 回合 × 10 种子

- 存活：9 / 10
- 灭绝种子：seed = 88，第 440 回合
- 平均最终人口：9.9
- 最大货币守恒误差：0

对比 dev29：

- dev29：10 人 × 1000 回合存活 8 / 10
- dev30：10 人 × 1000 回合存活 9 / 10

说明订单簿买方内部优先级修复有效，但仍未达到“所有正常种子长期稳定”的目标。

### 5 人 × 1000 回合 × 10 种子

- 存活：0 / 10
- 最大货币守恒误差：0

说明 5 人初始人口在当前随机寿命、生育概率、疾病、食物短缺和单人断代风险下仍不具备长期稳态。

### 宏观调控关闭烟雾测试

`enable_government_macro_control = False` 时，10 人 × 100 回合 × 10 种子全部快速灭绝。

这说明政府订单簿最后买方在当前模型中不仅是“宏观调控”，也是公司库存流通和市场流动性的关键闭环。后续建议拆分开关语义：

- `enable_government_orderbook_buyer`
- `enable_government_macro_control`

## 新发现

seed = 88 在第 440 回合灭绝时，最后阶段并不是总资源耗尽，而是进入单人随机断代：最后个体仍参与劳动和购买，但该回合未通过随机生育判定，随后寿命结束死亡。

在不加入人口恢复倍率、最低出生概率或强制出生的原则下，这类“单人随机断代”不能通过本版修复完全消除。

## 下一步建议

dev31 不建议立刻加入人口恢复倍率。建议继续修代码语义：

1. 拆分政府最后买方与宏观调控开关；
2. 检查生育用品生产与政府剩余价值删除的冲突；
3. 检查“人口降到 1 人后是否仍应视为可繁殖社会”的模型假设；
4. 为 5 人小族群提供非强制干预的“初始条件预设”，例如更多年龄分布、更多初始家庭库存，而非运行时人口恢复倍率；
5. 增加单人断代诊断字段，例如 `SingleSurvivorTurnCount`、`LastSurvivorDeathReason`、`TurnsAtPopulationBelow3`。
