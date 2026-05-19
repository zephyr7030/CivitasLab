# BOT8 dev31 实装报告

版本名：BOT8 dev31：政府买方开关拆分、公共库存诊断与小族群初始条件版

## 开发原则

本次继续严格遵守：

- 不加入人口恢复倍率
- 不加入最低出生概率
- 不加入强制出生
- 不加入强制自给补给
- 不加入政府额外创造资源或无限补贴
- 优先修复代码逻辑、开关语义、库存链路和诊断缺口

## 修改文件

- `config.py`
- `model.py`
- `output.py`
- `gui_settings.py`
- `settings_io.py`
- `README.md`

## 新增文件

- `run_dev31_tests.py`
- `BOT8_dev31_TEST_RESULTS.json`
- `BOT8_dev31_IMPLEMENTATION_REPORT.md`

## 主要修改

### 1. 拆分政府订单簿最后买方与宏观调控开关

新增机制开关：

```python
"enable_government_orderbook_buyer": True
```

`market_phase()` 现在使用该开关控制政府是否作为订单簿最后买方。`enable_government_macro_control` 不再承担这一语义。

### 2. 公共生育用品释放路径

新增基础参数：

```python
"enable_government_reproduction_goods_release": False
```

已实现 `government_reproduction_goods_release_phase()`，但默认关闭。该阶段只释放政府已经拥有的生育用品，不创造资源，不提高出生率，不绕过生育阶段的随机判断和食物安全线。

测试中发现，直接默认开启会放大出生/死亡波动，因此保留为实验开关，不作为默认修复。

### 3. 政府生育用品剩余价值删除上限修正

`government_stock_limit()` 对 `reproduction_goods` 不再只使用 `pop_count * child_units * 0.5`，而会参考：

- 当前生育用品刚性买方缺口
- 上一回合因缺生育用品导致的出生失败信号
- 当前人口对应的基础保留量

### 4. 小族群正常初始条件预设

新增基础参数：

```python
"enable_small_group_initial_conditions": True
"small_group_initial_population_threshold": 5
"small_group_initial_food_rounds": 5
"small_group_initial_medical_goods_ratio": 50
"small_group_initial_reproduction_goods_ratio": 100
```

该预设只影响初始化阶段。它不会在运行中补给资源、提高出生率或阻止死亡。

### 5. 单人断代诊断字段

新增 summary 输出字段：

- `SingleSurvivorTurnCount`
- `TurnsAtPopulationBelow3`
- `LastSurvivorDeathReason`
- `LastSurvivorReproduceChanceFailed`
- `LastSurvivorHadReproductionGoods`
- `LastSurvivorHadFoodForBirth`

### 6. 公共生育用品输出字段

新增 summary 输出字段：

- `GovernmentReproductionGoodsReleased`
- `GovernmentReproductionGoodsReleaseTargets`

## 测试结果

测试种子：

```text
20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88
```

### 10 人 × 100 回合

- 存活：10 / 10
- 平均最终人口：10.4
- 最大货币守恒误差：0

### 10 人 × 1000 回合

- 存活：9 / 10
- 灭绝：1 / 10，seed 88，第 440 回合灭绝
- 平均最终人口：9.9
- 最大货币守恒误差：0

### 5 人 × 1000 回合

- 存活：0 / 10
- 平均灭绝回合：167.5
- 对比关闭小族群初始条件：平均灭绝回合 104.1
- 说明小族群正常初始条件能延后灭绝，但不能根治 5 人长期随机断代。

### 关闭政府订单簿最后买方

- 条件：10 人 × 100 回合 × 10 种子，`enable_government_orderbook_buyer = False`
- 存活：0 / 10
- 平均灭绝回合：7.3
- 说明政府订单簿最后买方是当前市场流动性闭环的必要部分。

## 当前结论

1. dev31 保持了 dev30 在 10 人长期测试中的表现：10 人 × 1000 回合仍为 9/10 存活。
2. 小族群初始条件对 5 人测试有帮助，但还不能使 5 人族群长期稳定。
3. 公共生育用品释放不能简单默认开启，否则会放大出生/死亡波动。
4. 下一步不应加入强制人口恢复，建议继续检查疾病/濒死机制、寿命结束机制、食物购买力和工资闭环。
