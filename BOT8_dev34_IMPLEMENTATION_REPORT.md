# BOT8 dev34 实装报告

## 目标

执行 dev34 核查建议：资源/财富分布、政府救助释放、新生代贫困队列、医疗用品链路、工资闭环，并考虑但不默认调高工资。

## 修改文件

- config.py
- model.py
- output.py
- gui_settings.py
- README.md

## 新增文件

- run_dev34_tests.py
- quick_dev34_parallel.py
- BOT8_dev34_TEST_RESULTS.json
- BOT8_dev34_IMPLEMENTATION_REPORT.md

## 机制修改

新增库存销售收入分红实验开关：

```python
enable_inventory_sales_dividend = False
inventory_sales_dividend_ratio = 10
```

默认关闭。开启后只从公司当回合销售收入中分红，不创造货币，不提高生育概率，不强制救助。

## 诊断字段

新增：

- FoodGini / MoneyGini / MedicalGoodsGini / ReproductionGoodsGini
- Bottom20FoodAvg / Bottom20MoneyAvg / Bottom20MedicalGoodsAvg / Bottom20ReproductionGoodsAvg
- FoodZeroCount / MoneyZeroCount / MedicalGoodsZeroCount / ReproductionGoodsZeroCount
- FoodAidEligibleCount / FoodAidReceivedCount / FoodAidUnmetCount
- MedicalAidEligibleCount / MedicalAidReceivedCount / MedicalAidUnmetCount
- CriticalMedicalNeedCount / CriticalMedicalAidReceivedCount / CriticalMedicalAidUnmetCount
- Age0Count / Age1To3Count / Age4To8Count
- Age0AvgFood / Age1To3AvgFood / Age1To3AvgMoney / Age1To3CriticalCount
- AvgWagePerWorker / MedianWagePerWorker / WageToSurvivalCostRatio
- CompanyCashBeforeWages / CompanyCashAfterWages / CompanyUnableToPayFullWagesCount
- InventorySalesDividendPaid / InventorySalesDividendRecipients

## 测试摘要

详见 `BOT8_dev34_TEST_RESULTS.json`。

关键结果：

- 默认 5 人 × 1000：0/10 存活，平均灭绝回合 174.7。
- 工资 55，5 人 × 1000：1/10 存活，平均灭绝回合 203.33。
- 工资 60，5 人 × 1000：0/10 存活，平均灭绝回合 163.2。
- 分红 10%，5 人 × 1000：1/10 存活，平均灭绝回合 281.56。
- 分红 15%，5 人 × 1000：4/10 存活，平均灭绝回合 432.5。
- 默认 10 人 × 1000：9/10 存活。
- 工资 55，10 人 × 1000：7/10 存活。
- 分红 10%，10 人 × 1000：8/10 存活。

## 结论

直接调高工资不是当前最佳默认修改。工资 55 能改善 5 人小族群，但会降低 10 人长期稳定性。工资 60 更不稳定。库存销售收入分红更有潜力，尤其是 15% 对 5 人长期存活改善明显，但公司现金压力上升，需要 dev35 继续校准。
