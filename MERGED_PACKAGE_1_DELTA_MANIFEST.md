# MERGED PACKAGE 1 DELTA MANIFEST

## Package name

CivitasLab_2_0_0_merged_package_1_delta_files.zip

## Apply after

```text
Package D 完整包 + Package E 增量包
```

## Added files

```text
tools/performance_report_utils.py
tools/profile_suite.py
tools/cache_probe.py
tools/demand_plan_probe.py
tools/logic_audit.py
market_demand.py
docs/performance/CivitasLab_merged_package_1_performance_and_logic.md
reports/system_stage/merged_package_1_report.md
next_session/START_FROM_MERGED_PACKAGE_1.txt
MERGED_PACKAGE_1_DELTA_MANIFEST.md
```

## Modified files

```text
model.py
```

## Notes

`model.py` 只新增订单簿事件中的 `buyer_id` 与 `seller_id` 字段，便于审计工具检查自买过滤和成交来源。不改变交易撮合、库存、货币或模型行为。

## Quick test commands

```bash
python -m py_compile model.py market_demand.py tools/performance_report_utils.py tools/profile_suite.py tools/cache_probe.py tools/demand_plan_probe.py tools/logic_audit.py
python tools/check_summary_headers.py
python tools/check_parameter_specs.py
python tools/run_baseline.py --mode quick --out experiments/system_stage/local_m1_quick_baseline.json
python tools/cache_probe.py --preset stable_small_group --population 20 --turns 20 --out experiments/system_stage/local_m1_cache_probe.json
python tools/logic_audit.py --preset stable_small_group --turns 30 --population 20 --out experiments/system_stage/local_m1_logic_audit.json
```
