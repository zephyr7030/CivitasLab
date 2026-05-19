# Merged Package 7 Delta Manifest

## 新增文件

- gui_new/core/app_paths.py
- gui_new/core/errors.py
- gui_new/core/mode_flags.py
- gui_new/services/runtime_control_service.py
- gui_new/services/experiment_service.py
- gui_new/services/report_service.py
- gui_new/services/file_browser_service.py
- gui_new/services/dependency_probe_service.py
- gui_new/services/developer_mode_service.py
- gui_new/models/navigation_item.py
- gui_new/models/runtime_status.py
- gui_new/models/experiment_summary.py
- gui_new/models/report_export_result.py
- gui_new/pages/experiment_design_page.py
- gui_new/pages/parameter_reference_page.py
- gui_new/pages/rust_native_validation_page.py
- gui_new/pages/shadow_compare_page.py
- gui_new/pages/schema_checks_page.py
- metrics/report_exporters.py
- tools/gui_smoke_check.py
- tools/gui_runtime_probe.py
- docs/gui/CivitasLab_merged_package_7_gui_research_platform.md
- docs/performance/CivitasLab_rust_native_manual_validation.md
- reports/system_stage/merged_package_7_report.md
- next_session/START_FROM_MERGED_PACKAGE_7.txt

## 修改文件

- gui_new/app.py
- gui_new/main_window.py
- gui_new/core/navigation.py
- gui_new/models/chart_catalog.py
- gui_new/pages/chart_center_page.py
- gui_new/pages/debug_diagnostics_page.py
- gui_new/pages/output_browser_page.py
- gui_new/pages/preset_library_page.py
- gui_new/pages/research_report_page.py
- simulation_runner.py
- tools/preset_utils.py
- tools/list_presets.py
- tools/build_research_report.py
- presets/*.yaml

## 覆盖方法

在项目根目录执行：

```powershell
Expand-Archive .\CivitasLab_2_0_0_merged_package_7_gui_research_platform_delta_files.zip -DestinationPath . -Force
```
