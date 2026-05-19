# BOT8 dev36 实装报告

## 版本定位

BOT8 dev36：超额现金分层分红与劳动空窗诊断版。

本版继续遵守当前开发约束：

- 不加入人口恢复倍率；
- 不加入最低出生概率；
- 不加强制出生；
- 不加强制自给补给；
- 不让政府凭空创造资源；
- 不直接调高默认工资。

## 修改文件

- `config.py`
- `model.py`
- `output.py`
- `gui_settings.py`
- `README.md`

## 新增文件

- `run_dev36_tests.py`
- `quick_dev36_parallel.py`
- `BOT8_dev36_TEST_RESULTS.json`
- `BOT8_dev36_IMPLEMENTATION_REPORT.md`

## 新增机制：超额现金分层分红

新增配置：

```python
enable_excess_cash_dividend = False
excess_cash_dividend_ratio = 20
excess_cash_dividend_min_cash_ratio = 120
excess_cash_dividend_recipient_mode = 1
excess_cash_dividend_recent_turns = 5
```

该机制默认关闭。开启后，只从分公司超过运营现金阈值的真实超额现金中提取分红池：

```text
excess_cash = branch_money - initial_money * min_cash_ratio / 100
dividend_pool = excess_cash * dividend_ratio / 100
```

分红对象：

- `0`：所有非濒死个体；
- `1`：本回合本分公司劳动者；
- `2`：近期本分公司劳动者。

默认使用 `1`，即本回合劳动者，避免变成全体平均补贴。

## 新增诊断字段

```text
ExcessCashDividendPaid
ExcessCashDividendRecipients
ExcessCashDividendPool
ExcessCashDividendEligibleBranches
ExcessCashDividendBlockedByNoExcessCash
ExcessCashDividendBlockedByNoRecipients
LaborWorkerCountWhenPopBelow5
TurnsWithNoWorkersWhenPopBelow5
TurnsWithNoWagesWhenPopBelow5
CompanyHasCashButNoWorkersCount
CompanyHasStockButNoWorkersCount
Last3PopulationAvgLifeRemaining
Last3PopulationMinLifeRemaining
Last3PopulationReproductiveEligibleCount
DeathByLifeEndWithReproductionGoods
DeathByLifeEndWithFoodForBirth
TurnDeathByLifeEndWithReproductionGoods
TurnDeathByLifeEndWithFoodForBirth
```

## 测试摘要

测试种子：`20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88`。

### 5 人 × 1000

| 设置 | 存活 | 平均灭绝回合 | 平均峰值人口 |
|---|---:|---:|---:|
| 基线 | 0/10 | 174.7 | 12.8 |
| 本回合劳动者分红 10% | 0/10 | 57.5 | 11.9 |
| 本回合劳动者分红 20% | 0/10 | 129.8 | 12.4 |
| 本回合劳动者分红 30% | 0/10 | 119.8 | 13.6 |
| 近期劳动者分红 20% | 0/10 | 266.6 | 12.2 |
| 近期劳动者分红 30% | 0/10 | 177.0 | 12.6 |

### 10 人 × 1000

| 设置 | 存活 | 平均最终人口 | 平均峰值人口 |
|---|---:|---:|---:|
| 基线 | 9/10 | 9.8 | 24.5 |
| 本回合劳动者分红 10% | 10/10 | 13.1 | 25.3 |
| 本回合劳动者分红 20% | 9/10 | 11.5 | 25.6 |
| 本回合劳动者分红 30% | 9/10 | 11.1 | 24.5 |

## 结论

1. 超额现金分红比 dev35 的“历史库存销售收入 + 现金保护”更符合公司财务逻辑，但对 5 人长期稳定仍不足。
2. `10 人 × 1000` 中，本回合劳动者分红 10% 达到 10/10 存活，值得保留为实验预设，但不建议直接默认开启。
3. `5 人 × 1000` 的核心瓶颈已经转向：低人口劳动者空窗 + life_end 断代。
4. 低人口时经常出现公司有钱、有库存，但没有劳动者，因此分红和工资都无法形成连续购买力。
5. 多个 `life_end` 死亡发生时，个体已具备生育用品甚至出生食物条件，说明寿命尾部机制需要进一步核查。

## 下一步建议

建议 dev37 聚焦：

```text
BOT8 dev37：低人口劳动空窗与寿命尾部机制核查版
```

优先方向：

1. 核查低人口时为什么劳动者为空；
2. 检查 `labor_participation_probability` 是否过低或是否被年龄/critical/资源分配间接压制；
3. 检查最后 1–3 人的 `life`、`reproduction_goods`、`food`、`labor`、`critical` 状态；
4. 先增加诊断，不直接延长寿命；
5. 如证据充分，再考虑将硬性 `life_end` 改为尾部概率死亡，而不是强制续命。
