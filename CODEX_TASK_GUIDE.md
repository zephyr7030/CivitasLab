# CivitasLab Codex Task Guide

## Project identity

CivitasLab is a research-oriented social/economic/ecological simulation platform. BOT8 is the early prototype name. Current stage: CivitasLab 2.0.0.

## Current priority

The current priority is **GUI stabilization and research workflow usability**.

Do not move to final packaging or release engineering until the GUI is stable and a regression suite exists.

## Hard rules

- Do not delete the old Tkinter GUI.
- Do not delete comments or parameter descriptions.
- Do not remove ParameterSpec coverage.
- Do not modify orderbook live path unless explicitly requested.
- Do not enable Rust live path by default.
- Do not add heavy dependencies such as pandas, PyYAML, SQLAlchemy, or python-docx unless explicitly approved.
- Do not use forced population recovery to hide model bugs.
- Keep English config keys stable; Chinese labels are display-layer only.
- Preserve the Rust/PyO3 prototype, but keep it experimental.
- Do not implement or deepen tool mechanics unless explicitly requested.

## Required checks after changes

Run:

```powershell
python tools\check_summary_headers.py
python tools\check_parameter_specs.py
python tools\run_baseline.py --mode quick --out experiments\system_stage\codex_quick_baseline.json
python tools\gui_smoke_check.py --out experiments\system_stage\codex_gui_smoke.json
```

If GUI data path, runtime, reports, events, or snapshots changed, also run:

```powershell
python tools\gui_runtime_probe.py --preset stable_small_group --turns 100 --population 20 --out experiments\system_stage\codex_runtime_probe.json
```

If orderbook shadow logic changed, also run:

```powershell
python tools\shadow_compare_orderbook_adapter.py --preset stable_small_group --turns 10 --population 10 --out experiments\system_stage\codex_shadow_adapter.json
python tools\assess_orderbook_shadow_convergence.py experiments\system_stage\codex_shadow_adapter.json --threshold-ratio 0.01
```

## GUI requirements

The GUI must serve research users, not just developers.

Default navigation should focus on:

- Research workflow
- Model observation
- Experiment management
- Model configuration

Developer tools should be hidden by default.

## Known current GUI risks

- Runtime overview and runtime control still need cleaner separation.
- Observation pages can still appear empty if the latest run data path is not clear or event/snapshot output is missing.
- High-speed simulation can still be CPU-heavy; GUI observe mode and headless batch mode should be separated.
- Custom chart workflow must become more intuitive for multi-metric research use.
- Preset clicks must always produce clear feedback and state changes.
- Parameter names/categories must display Chinese labels while preserving English config keys.

## Rust policy

Rust/PyO3 orderbook backend is experimental.

Allowed:

- Keep source
- Keep validation tools
- Keep fallback
- Show backend status in developer tools

Not allowed:

- Enable Rust live path by default
- Expose Rust live toggle to ordinary researchers
- Require Rust for normal GUI or CLI operation
