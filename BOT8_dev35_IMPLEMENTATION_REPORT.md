# BOT8 dev35 实装与继续探究报告

## 1. 本版目标

基于 dev34 测试结论，应用库存销售收入回流校准与公司现金流保护：

- 测试 12%–15% 库存销售收入分红；
- 加入公司现金保护；
- 区分历史库存清算收入与本回合生产销售收入；
- 不直接调高工资；
- 不加入人口恢复倍率、最低出生概率或强制出生。

## 2. 修改文件

- config.py
- model.py
- output.py
- gui_settings.py
- README.md

新增：

- run_dev35_tests.py
- BOT8_dev35_TEST_RESULTS.json
- BOT8_dev35_IMPLEMENTATION_REPORT.md

## 3. 新增配置

```python
enable_inventory_sales_dividend = False
inventory_sales_dividend_ratio = 10
inventory_sales_dividend_historical_only = True
inventory_sales_dividend_cash_protection = True
inventory_sales_dividend_min_cash_ratio = 120
inventory_sales_dividend_cash_floor_ratio = 100
```

默认仍关闭分红实验。

## 4. 新增诊断字段

- HistoricalInventorySalesIncome
- InventorySalesDividendEligibleBranches
- InventorySalesDividendBlockedByCashProtection
- InventorySalesDividendBlockedByNoHistoricalIncome
- InventorySalesDividendCashFloor

## 5. 测试摘要

### 5 人 × 1000，历史库存清算收入 + 现金保护

| 分红比例 | 存活 | 平均灭绝回合 |
|---:|---:|---:|
| 12% | 0/10 | 173.3 |
| 13% | 0/10 | 166.2 |
| 14% | 0/10 | 183.7 |
| 15% | 0/10 | 167.9 |

结论：现金保护和历史收入限定使分红太弱，无法解决 5 人长期灭绝。

### 10 人 × 1000

| 设置 | 存活 | 平均最终人口 |
|---|---:|---:|
| 基线 | 9/10 | 9.8 |
| 历史库存 + 现金保护 14% | 7/10 | 8.0 |
| 历史库存 + 现金保护 15% | 9/10 | 11.8 |

结论：15% 对 10 人没有明显退化，但对 5 人帮助不足。

### 探究测试

| 设置 | 5 人 × 1000 存活 | 平均灭绝回合 |
|---|---:|---:|
| 全部销售收入、无现金保护、15% | 4/10 | 432.5 |
| 历史库存收入、无现金保护、15% | 0/10 | 112.9 |
| 全部销售收入、120/100 现金保护、15% | 0/10 | 165.1 |

结论：dev34 中有效的不是“历史库存清算收入”本身，而是更大规模、更连续的公司收入回流。但无保护全额回流会带来公司现金流副作用。

## 6. 新建议

不建议把 dev35 的历史库存 + 现金保护分红设为默认开启，也不建议继续简单调高分红比例。下一步建议：

1. 改为“超额现金分层分红”：只从分公司超过目标现金的部分按比例分红，而不是按销售收入比例分红。
2. 将分红对象从“所有非濒死个体平均分配”改为“近期劳动者/历史劳动贡献者优先”，避免资源流向没有生产贡献但会立即扩大消费压力的群体。
3. 单独核查人口低于 5 时的劳动者数量、工资空窗和 life_end 断代。
4. 暂不调高工资默认值。工资 55/60 之前已显示会损害 10 人长期稳定。

