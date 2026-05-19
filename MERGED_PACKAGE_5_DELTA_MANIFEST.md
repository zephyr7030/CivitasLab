# MERGED_PACKAGE_5_DELTA_MANIFEST

## Stage

Merged Package 5：研究指标库 + 自动报告 + 多运行研究分析

## New files

```text
metrics/__init__.py
metrics/common.py
metrics/population_metrics.py
metrics/resource_metrics.py
metrics/market_metrics.py
metrics/company_metrics.py
metrics/government_metrics.py
metrics/evolution_metrics.py
metrics/inequality_metrics.py
metrics/orderbook_metrics.py
metrics/report_builder.py
tools/build_research_report.py
tools/compare_research_reports.py
gui_new/pages/research_report_page.py
docs/research_metrics/CivitasLab_merged_package_5_research_metrics.md
docs/release/CivitasLab_windows_minimal_runtime_strategy.md
requirements-runtime-core.txt
requirements-runtime-gui.txt
reports/system_stage/merged_package_5_report.md
next_session/START_FROM_MERGED_PACKAGE_5.txt
MERGED_PACKAGE_5_DELTA_MANIFEST.md
```

## Modified files

```text
gui_new/main_window.py
gui_new/data/experiment_db_provider.py
```

## Apply command

```powershell
Expand-Archive .\CivitasLab_2_0_0_merged_package_5_delta_files.zip -DestinationPath . -Force
```

## Smoke tests

```powershell
python -m py_compile metrics\*.py tools\build_research_report.py tools\compare_research_reports.py gui_new\pages\research_report_page.py gui_new\main_window.py
python tools\check_summary_headers.py
python tools\check_parameter_specs.py
python tools\run_baseline.py --mode quick --out experiments\system_stage\local_m5_quick_baseline.json
python tools\update_experiment_db.py
python tools\build_research_report.py --manifest experiments\manifests\stage6_preset_quick.json --out reports\research\local_m5_report.md
```
