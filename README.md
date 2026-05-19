# CivitasLab 2.0.0

CivitasLab is a research-oriented social / economic / ecological simulation platform.  
**BOT8** was the early prototype name; old BOT8 filenames and historical reports are kept for compatibility.

Current baseline in this repository package:

- Package D full baseline
- Package E experiment grid / comparison
- Merged Package 1–7.3
- GUI research workflow draft with current known usability issues still under active repair
- Rust/PyO3 orderbook prototype retained as experimental, not enabled by default

## Quick start on Windows

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-runtime-gui.txt
python -m gui_new.app
```

Developer mode:

```powershell
python -m gui_new.app --developer-mode
```

## Core checks

Run these before committing changes:

```powershell
python tools\check_summary_headers.py
python tools\check_parameter_specs.py
python tools\run_baseline.py --mode quick --out experiments\system_stage\local_quick_baseline.json
python tools\gui_smoke_check.py --out experiments\system_stage\local_gui_smoke.json
```

If GUI data paths changed, also run:

```powershell
python tools\gui_runtime_probe.py --preset stable_small_group --turns 100 --population 20 --out experiments\system_stage\local_runtime_probe.json
```

## Current development priority

Do **not** move directly to release packaging yet. The current priority is:

1. GUI workflow repair and real Windows/PySide6 validation.
2. Split read-only overview from runtime control.
3. Make observation pages reliably show latest run data.
4. Make chart center usable for research workflows.
5. Build a regression suite before packaging.

See:

- `CODEX_TASK_GUIDE.md`
- `docs/github/GITHUB_MIGRATION_GUIDE.md`
- `docs/codex/CODEX_NEXT_TASKS.md`

## Runtime dependencies

Core CLI:

```powershell
pip install -r requirements-runtime-core.txt
```

GUI:

```powershell
pip install -r requirements-runtime-gui.txt
```

Optional Rust/PyO3 validation:

```powershell
pip install -r requirements-rust-orderbook.txt
```

Rust native backend is experimental and must not be enabled as live path by default.
