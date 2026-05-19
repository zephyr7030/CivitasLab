# MERGED_PACKAGE_2_DELTA_MANIFEST

## 新增文件

- `orderbook_core.py`
- `orderbook_shadow_adapter.py`
- `tools/check_orderbook_boundary.py`
- `tools/check_orderbook_shadow_adapter.py`
- `tools/orderbook_fixture_builder.py`
- `tools/shadow_compare_report.py`
- `tools/shadow_compare_orderbook.py`
- `tools/shadow_compare_orderbook_adapter.py`
- `tools/analyze_shadow_differences.py`
- `tools/build_orderbook_replay_fixture.py`
- `tools/replay_orderbook_fixture.py`
- `docs/orderbook/CivitasLab_merged_package_2_orderbook_shadow.md`
- `reports/system_stage/merged_package_2_report.md`
- `next_session/START_FROM_MERGED_PACKAGE_2.txt`
- `MERGED_PACKAGE_2_DELTA_MANIFEST.md`

## 修改文件

无 live path 修改。

## 覆盖方法

```powershell
Expand-Archive .\CivitasLab_2_0_0_merged_package_2_delta_files.zip -DestinationPath . -Force
```
