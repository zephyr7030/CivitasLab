# MERGED_PACKAGE_2_1_DELTA_MANIFEST

## 阶段

Merged Package 2.1：订单簿 Shadow 差异收敛修复

## 新增文件

- `tools/assess_orderbook_shadow_convergence.py`
- `docs/orderbook/CivitasLab_merged_package_2_1_shadow_convergence.md`
- `reports/system_stage/merged_package_2_1_report.md`
- `next_session/START_FROM_MERGED_PACKAGE_2_1.txt`
- `MERGED_PACKAGE_2_1_DELTA_MANIFEST.md`

## 修改文件

- `orderbook_core.py`
- `orderbook_shadow_adapter.py`
- `model.py`
- `tools/shadow_compare_report.py`

## 覆盖方法

```powershell
Expand-Archive .\CivitasLab_2_0_0_merged_package_2_1_delta_files.zip -DestinationPath . -Force
```

## 验收重点

- `python tools\shadow_compare_orderbook_adapter.py --preset stable_small_group --turns 20 --population 20 --out experiments\system_stage\local_m21_adapter_stable.json`
- `python tools\shadow_compare_orderbook_adapter.py --preset high_market_society --turns 20 --population 20 --out experiments\system_stage\local_m21_adapter_market.json`
- `python tools\assess_orderbook_shadow_convergence.py experiments\system_stage\local_m21_adapter_stable.json experiments\system_stage\local_m21_adapter_market.json --threshold-ratio 0.01`
