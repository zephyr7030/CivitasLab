# CivitasLab 2.0.0 GitHub-ready Package Manifest

This package is prepared from the latest available full package baseline:

```text
CivitasLab_2_0_0_package_7_3_gui_workflow_fix_full.zip
```

Additional GitHub/Codex preparation added in this package:

- `.gitignore`
- `README.md`
- `CODEX_TASK_GUIDE.md`
- `docs/github/GITHUB_MIGRATION_GUIDE.md`
- `docs/codex/CODEX_NEXT_TASKS.md`
- `.github/workflows/civitaslab-checks.yml`
- `VERSION` if it was missing

Generated heavyweight historical JSON test outputs and local runtime artifacts are excluded from this GitHub-ready package. Historical implementation reports and current source/docs/tools are retained.

Current known priority after uploading to GitHub:

1. Continue GUI workflow repair.
2. Keep Rust/PyO3 experimental and disabled by default.
3. Build regression suite before Windows packaging.
