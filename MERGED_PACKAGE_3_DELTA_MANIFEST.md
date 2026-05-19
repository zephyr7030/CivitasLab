# MERGED_PACKAGE_3_DELTA_MANIFEST

This delta should be applied on top of:
Package D full project + Package E delta + Merged Package 1 delta + Merged Package 2 delta + Merged Package 2.1 delta.

## Added files

- rust/civitas_orderbook/Cargo.toml
- rust/civitas_orderbook/pyproject.toml
- rust/civitas_orderbook/src/lib.rs
- requirements-rust-orderbook.txt
- tools/rust_orderbook_bridge.py
- tools/check_rust_orderbook_equivalence.py
- tools/benchmark_rust_orderbook.py
- tools/shadow_compare_rust_orderbook.py
- docs/performance/CivitasLab_merged_package_3_rust_orderbook.md
- reports/system_stage/merged_package_3_report.md
- next_session/START_FROM_MERGED_PACKAGE_3.txt
- MERGED_PACKAGE_3_DELTA_MANIFEST.md

## Modified files

None.

## Important notes

- This delta does not modify the live model path.
- Rust is optional until native validation passes locally.
- Use --require-rust to force native backend validation.
