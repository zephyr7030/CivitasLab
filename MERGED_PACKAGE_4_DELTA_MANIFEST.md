# Merged Package 4 Delta Manifest

## Apply order

Apply after:

1. Package D full package
2. Package E delta
3. Merged Package 1 delta
4. Merged Package 2 delta
5. Merged Package 2.1 delta
6. Merged Package 3 delta

## Files

```text
gui_new/core/__init__.py
gui_new/core/page_lifecycle.py
gui_new/core/navigation.py
gui_new/services/__init__.py
gui_new/services/runtime_state_service.py
gui_new/services/chart_export_service.py
gui_new/models/__init__.py
gui_new/models/chart_catalog.py
gui_new/data/time_series_store.py
gui_new/widgets/realtime_chart.py
gui_new/pages/dashboard_page.py
gui_new/pages/chart_center_page.py
gui_new/pages/market_orderbook_page.py
gui_new/pages/output_browser_page.py
gui_new/pages/debug_diagnostics_page.py
gui_new/main_window.py
docs/gui/CivitasLab_merged_package_4_gui_professionalization.md
reports/system_stage/merged_package_4_report.md
next_session/START_FROM_MERGED_PACKAGE_4.txt
MERGED_PACKAGE_4_DELTA_MANIFEST.md
```

## Local apply

```powershell
Expand-Archive .\CivitasLab_2_0_0_merged_package_4_delta_files.zip -DestinationPath . -Force
```
