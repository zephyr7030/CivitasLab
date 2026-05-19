# CivitasLab 2.0.0 Package E 增量文件清单

本压缩包只包含 Package E 本次修改/新增文件，不是完整项目包。请将压缩包内容解压覆盖到 Package D 项目根目录。

## 覆盖/新增文件

- `tools/preset_utils.py`
- `tools/list_presets.py`
- `tools/run_experiment_queue.py`
- `tools/create_experiment_grid.py`
- `tools/summarize_manifest_results.py`
- `presets/high_market_society.yaml`
- `gui_new/data/experiment_db_provider.py`
- `gui_new/pages/preset_library_page.py`
- `gui_new/pages/experiment_grid_page.py`
- `gui_new/pages/multi_run_compare_page.py`
- `gui_new/main_window.py`
- `docs/experiment_system/CivitasLab_package_E_grid_and_compare.md`
- `reports/system_stage/system_stage_package_E_report.md`
- `next_session/START_FROM_PACKAGE_E.txt`

## 覆盖后建议执行

```bash
python -m py_compile tools/preset_utils.py tools/list_presets.py tools/run_experiment_queue.py tools/create_experiment_grid.py tools/summarize_manifest_results.py gui_new/data/experiment_db_provider.py gui_new/pages/preset_library_page.py gui_new/pages/experiment_grid_page.py gui_new/pages/multi_run_compare_page.py gui_new/main_window.py
python tools/list_presets.py
python tools/create_experiment_grid.py --preset high_market_society --out experiments/manifests/local_package_E_grid_test.json --turns 5 --populations 5 --seeds 1,2 --param population.A.individual_buy_willingness=60,90
python tools/run_experiment_queue.py --resume experiments/manifests/local_package_E_grid_test.json --max-cases 1
python tools/update_experiment_db.py
python tools/query_experiment_db.py --summary
```
