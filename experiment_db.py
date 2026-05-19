"""SQLite experiment index for CivitasLab 2.0.0.

This module is intentionally independent from the simulation live path. It reads
RunManifest JSON files and preset files, then builds a small SQLite catalog that
GUI pages and command-line tools can query without scanning many folders.

Design rules:
- Use Python stdlib only (sqlite3/json/pathlib).
- Do not modify simulation results.
- Treat manifests as source-of-truth and the database as a rebuildable cache.
- Skip config snapshot JSON files; they are inputs attached to manifests, not runs.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "experiments" / "civitaslab_experiments.sqlite"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class IndexStats:
    db_path: str
    manifest_count: int
    run_count: int
    task_count: int
    output_count: int
    metric_count: int
    preset_count: int
    skipped_json_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "db_path": self.db_path,
            "manifest_count": self.manifest_count,
            "run_count": self.run_count,
            "task_count": self.task_count,
            "output_count": self.output_count,
            "metric_count": self.metric_count,
            "preset_count": self.preset_count,
            "skipped_json_count": self.skipped_json_count,
        }


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            manifest_path TEXT UNIQUE NOT NULL,
            schema_version INTEGER,
            preset TEXT,
            preset_file TEXT,
            config_snapshot_path TEXT,
            config_hash TEXT,
            output_root TEXT,
            created_at TEXT,
            updated_at TEXT,
            total_tasks INTEGER DEFAULT 0,
            done INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            pending INTEGER DEFAULT 0,
            running INTEGER DEFAULT 0,
            survival_count INTEGER DEFAULT 0,
            max_abs_money_delta REAL DEFAULT 0,
            any_header_missing INTEGER DEFAULT 0,
            manifest_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            run_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            preset TEXT,
            status TEXT,
            seed INTEGER,
            turns INTEGER,
            initial_population INTEGER,
            started_at TEXT,
            finished_at TEXT,
            output_dir TEXT,
            event_manifest_path TEXT,
            snapshot_manifest_path TEXT,
            survived INTEGER,
            final_population INTEGER,
            peak_population INTEGER,
            births INTEGER,
            deaths INTEGER,
            money_delta REAL,
            runtime_seconds REAL,
            avg_turn_seconds REAL,
            event_count INTEGER,
            event_chunk_count INTEGER,
            snapshot_chunk_count INTEGER,
            error TEXT,
            result_json TEXT,
            PRIMARY KEY (run_id, task_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS metrics (
            run_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL,
            metric_text TEXT,
            PRIMARY KEY (run_id, task_id, metric_name),
            FOREIGN KEY (run_id, task_id) REFERENCES tasks(run_id, task_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS outputs (
            run_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            output_type TEXT NOT NULL,
            path TEXT NOT NULL,
            exists_on_disk INTEGER DEFAULT 0,
            bytes INTEGER DEFAULT 0,
            PRIMARY KEY (run_id, task_id, output_type, path),
            FOREIGN KEY (run_id, task_id) REFERENCES tasks(run_id, task_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS presets (
            preset_id TEXT PRIMARY KEY,
            preset_file TEXT UNIQUE,
            name TEXT,
            description TEXT,
            tags_json TEXT,
            overrides_json TEXT,
            raw_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_runs_preset ON runs(preset);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_seed ON tasks(seed);
        CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
        CREATE INDEX IF NOT EXISTS idx_outputs_type ON outputs(output_type);
        """
    )
    con.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )


def clear_index(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        DELETE FROM outputs;
        DELETE FROM metrics;
        DELETE FROM tasks;
        DELETE FROM runs;
        DELETE FROM presets;
        """
    )


def project_relative(path_value: Any, root: Path = ROOT) -> str:
    """Normalize paths to project-relative strings when possible.

    Older reports may contain absolute paths from temporary sandboxes. When a
    value contains an `outputs/runs/...` suffix, recover that portable suffix.
    """
    if path_value is None:
        return ""
    text = str(path_value).replace("\\", "/")
    if not text:
        return ""
    p = Path(text)
    try:
        return str(p.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        pass
    marker = "outputs/runs/"
    if marker in text:
        return text[text.index(marker):]
    marker = "experiments/manifests/"
    if marker in text:
        return text[text.index(marker):]
    return text


def path_exists_and_size(path_text: str, root: Path = ROOT) -> Tuple[int, int]:
    if not path_text:
        return 0, 0
    p = Path(path_text)
    if not p.is_absolute():
        p = root / p
    if p.exists():
        try:
            size = p.stat().st_size if p.is_file() else 0
        except OSError:
            size = 0
        return 1, int(size)
    return 0, 0


def is_run_manifest_payload(payload: Dict[str, Any]) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("tasks"), list) and bool(payload.get("run_id"))


def iter_manifest_paths(manifest_dir: str | Path | None = None) -> Iterable[Path]:
    directory = Path(manifest_dir) if manifest_dir else ROOT / "experiments" / "manifests"
    if not directory.exists():
        return []
    return sorted(path for path in directory.glob("*.json") if not path.name.endswith(".config_snapshot.json"))


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def metric_items(result: Dict[str, Any]) -> Iterable[Tuple[str, Any]]:
    """Flatten stable scalar metrics from a RunResult-like dict."""
    scalar_names = [
        "turns_completed",
        "requested_turns",
        "initial_population",
        "final_population",
        "peak_population",
        "tail_avg_population",
        "births",
        "deaths",
        "money_delta",
        "resource_use_to_regen_tail_avg",
        "labor_resource_unused_tail_avg",
        "food_hard_satisfied_tail_avg",
        "medical_hard_satisfied_tail_avg",
        "reproduction_hard_satisfied_tail_avg",
        "hard_need_blocked_no_stock_sum",
        "food_hard_unsatisfied_sum",
        "medical_hard_unsatisfied_sum",
        "reproduction_hard_unsatisfied_sum",
        "runtime_seconds",
        "avg_turn_seconds",
        "event_count",
        "event_chunk_count",
        "snapshot_chunk_count",
        "entity_snapshot_turns",
        "latest_individual_snapshot_count",
        "latest_company_snapshot_count",
        "latest_government_snapshot_count",
    ]
    for name in scalar_names:
        if name in result:
            yield name, result.get(name)
    if "survived" in result:
        yield "survived", 1 if result.get("survived") else 0
    for reason, value in (result.get("death_reasons") or {}).items():
        yield f"death_reason.{reason}", value
    for phase, value in (result.get("events_by_phase") or {}).items():
        yield f"events_by_phase.{phase}", value
    for entity_type, value in (result.get("events_by_entity_type") or {}).items():
        yield f"events_by_entity_type.{entity_type}", value


def insert_metric(con: sqlite3.Connection, run_id: str, task_id: str, name: str, value: Any) -> None:
    numeric_value: Optional[float]
    text_value: Optional[str]
    try:
        if isinstance(value, bool):
            numeric_value = 1.0 if value else 0.0
            text_value = None
        elif value is None:
            numeric_value = None
            text_value = None
        else:
            numeric_value = float(value)
            text_value = None
    except (TypeError, ValueError):
        numeric_value = None
        text_value = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    con.execute(
        """
        INSERT OR REPLACE INTO metrics(run_id, task_id, metric_name, metric_value, metric_text)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, task_id, name, numeric_value, text_value),
    )


def insert_output(con: sqlite3.Connection, run_id: str, task_id: str, output_type: str, path_value: Any) -> None:
    path_text = project_relative(path_value)
    if not path_text:
        return
    exists, size = path_exists_and_size(path_text)
    con.execute(
        """
        INSERT OR REPLACE INTO outputs(run_id, task_id, output_type, path, exists_on_disk, bytes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, task_id, output_type, path_text, exists, size),
    )


def index_manifest(con: sqlite3.Connection, path: Path, payload: Dict[str, Any]) -> None:
    run_id = str(payload.get("run_id"))
    summary = payload.get("summary") or {}
    manifest_path = project_relative(path)
    con.execute(
        """
        INSERT OR REPLACE INTO runs(
            run_id, manifest_path, schema_version, preset, preset_file,
            config_snapshot_path, config_hash, output_root, created_at, updated_at,
            total_tasks, done, failed, pending, running, survival_count,
            max_abs_money_delta, any_header_missing, manifest_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            manifest_path,
            int(payload.get("schema_version") or 0),
            payload.get("preset"),
            project_relative(payload.get("preset_file")),
            project_relative(payload.get("config_snapshot_path")),
            payload.get("config_hash"),
            project_relative(payload.get("output_root")),
            payload.get("created_at"),
            payload.get("updated_at"),
            int(summary.get("total_tasks") or 0),
            int(summary.get("done") or 0),
            int(summary.get("failed") or 0),
            int(summary.get("pending") or 0),
            int(summary.get("running") or 0),
            int(summary.get("survival_count") or 0),
            float(summary.get("max_abs_money_delta") or 0),
            1 if summary.get("any_header_missing") else 0,
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    tasks = payload.get("tasks") or []
    for task in tasks:
        task_id = str(task.get("task_id") or f"task_{len(task)}")
        result = task.get("result") or {}
        con.execute(
            """
            INSERT OR REPLACE INTO tasks(
                run_id, task_id, preset, status, seed, turns, initial_population,
                started_at, finished_at, output_dir, event_manifest_path,
                snapshot_manifest_path, survived, final_population, peak_population,
                births, deaths, money_delta, runtime_seconds, avg_turn_seconds,
                event_count, event_chunk_count, snapshot_chunk_count, error, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                task_id,
                task.get("preset") or payload.get("preset"),
                task.get("status"),
                int(task.get("seed") or 0),
                int(task.get("turns") or 0),
                int(task.get("initial_population") or 0),
                task.get("started_at"),
                task.get("finished_at"),
                project_relative(task.get("output_dir") or result.get("output_dir")),
                project_relative(task.get("event_manifest_path") or result.get("event_manifest_path")),
                project_relative(task.get("snapshot_manifest_path") or result.get("snapshot_manifest_path")),
                None if "survived" not in result else (1 if result.get("survived") else 0),
                result.get("final_population"),
                result.get("peak_population"),
                result.get("births"),
                result.get("deaths"),
                result.get("money_delta"),
                result.get("runtime_seconds"),
                result.get("avg_turn_seconds"),
                result.get("event_count"),
                result.get("event_chunk_count"),
                result.get("snapshot_chunk_count"),
                task.get("error"),
                json.dumps(result, ensure_ascii=False) if result else None,
            ),
        )
        if result:
            for name, value in metric_items(result):
                insert_metric(con, run_id, task_id, name, value)
        insert_output(con, run_id, task_id, "case_dir", task.get("output_dir") or result.get("output_dir"))
        insert_output(con, run_id, task_id, "event_manifest", task.get("event_manifest_path") or result.get("event_manifest_path"))
        insert_output(con, run_id, task_id, "snapshot_manifest", task.get("snapshot_manifest_path") or result.get("snapshot_manifest_path"))
        insert_output(con, run_id, task_id, "event_dir", result.get("event_dir"))
        insert_output(con, run_id, task_id, "snapshot_dir", result.get("snapshot_dir"))


def read_simple_preset(path: Path) -> Dict[str, Any]:
    """Read preset metadata without requiring PyYAML.

    Prefer the project preset utility when available. Fall back to a conservative
    line parser so this database layer remains usable during tooling refactors.
    """
    try:
        from tools.preset_utils import read_preset  # type: ignore

        payload = read_preset(path)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        meta: Dict[str, Any] = {}
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key in {"id", "name", "description", "tags"}:
                meta[key] = value
        return meta


def index_presets(con: sqlite3.Connection, preset_dir: str | Path | None = None) -> int:
    directory = Path(preset_dir) if preset_dir else ROOT / "presets"
    count = 0
    if not directory.exists():
        return 0
    for path in sorted(directory.glob("*.yaml")):
        payload = read_simple_preset(path)
        preset_id = str(payload.get("id") or path.stem)
        tags = payload.get("tags") or []
        overrides = payload.get("overrides") or {}
        con.execute(
            """
            INSERT OR REPLACE INTO presets(
                preset_id, preset_file, name, description, tags_json, overrides_json, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                preset_id,
                project_relative(path),
                payload.get("name") or preset_id,
                payload.get("description") or "",
                json.dumps(tags, ensure_ascii=False),
                json.dumps(overrides, ensure_ascii=False, sort_keys=True),
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        count += 1
    return count


def rebuild_database(
    db_path: str | Path = DEFAULT_DB_PATH,
    manifest_dir: str | Path | None = None,
    preset_dir: str | Path | None = None,
) -> IndexStats:
    db_path = Path(db_path)
    with connect(db_path) as con:
        init_schema(con)
        clear_index(con)
        manifest_count = 0
        skipped_count = 0
        for path in iter_manifest_paths(manifest_dir):
            payload = read_json(path)
            if not payload or not is_run_manifest_payload(payload):
                skipped_count += 1
                continue
            index_manifest(con, path, payload)
            manifest_count += 1
        preset_count = index_presets(con, preset_dir)
        run_count = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        task_count = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        output_count = con.execute("SELECT COUNT(*) FROM outputs").fetchone()[0]
        metric_count = con.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        con.commit()
    return IndexStats(
        db_path=project_relative(db_path),
        manifest_count=int(manifest_count),
        run_count=int(run_count),
        task_count=int(task_count),
        output_count=int(output_count),
        metric_count=int(metric_count),
        preset_count=int(preset_count),
        skipped_json_count=int(skipped_count),
    )


def rows_to_dicts(rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


def list_runs(db_path: str | Path = DEFAULT_DB_PATH, limit: int = 50, preset: str | None = None) -> List[Dict[str, Any]]:
    with connect(db_path) as con:
        init_schema(con)
        if preset:
            rows = con.execute(
                """
                SELECT run_id, preset, created_at, updated_at, total_tasks, done, failed, pending,
                       survival_count, max_abs_money_delta, manifest_path, output_root
                FROM runs WHERE preset = ? ORDER BY COALESCE(updated_at, created_at, '') DESC LIMIT ?
                """,
                (preset, int(limit)),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT run_id, preset, created_at, updated_at, total_tasks, done, failed, pending,
                       survival_count, max_abs_money_delta, manifest_path, output_root
                FROM runs ORDER BY COALESCE(updated_at, created_at, '') DESC LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
    return rows_to_dicts(rows)


def list_tasks(
    db_path: str | Path = DEFAULT_DB_PATH,
    run_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sql = f"""
        SELECT run_id, task_id, preset, status, seed, turns, initial_population,
               survived, final_population, births, deaths, money_delta, runtime_seconds,
               output_dir, event_manifest_path, snapshot_manifest_path, error
        FROM tasks{where}
        ORDER BY run_id DESC, task_id ASC LIMIT ?
    """
    params.append(int(limit))
    with connect(db_path) as con:
        init_schema(con)
        rows = con.execute(sql, params).fetchall()
    return rows_to_dicts(rows)


def list_presets(db_path: str | Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with connect(db_path) as con:
        init_schema(con)
        rows = con.execute(
            "SELECT preset_id, preset_file, name, description, tags_json FROM presets ORDER BY preset_id"
        ).fetchall()
    return rows_to_dicts(rows)


def aggregate_metrics(db_path: str | Path = DEFAULT_DB_PATH, metric_name: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
    with connect(db_path) as con:
        init_schema(con)
        if metric_name:
            rows = con.execute(
                """
                SELECT metric_name, COUNT(*) AS n, AVG(metric_value) AS avg_value,
                       MIN(metric_value) AS min_value, MAX(metric_value) AS max_value
                FROM metrics WHERE metric_name = ? AND metric_value IS NOT NULL
                GROUP BY metric_name LIMIT ?
                """,
                (metric_name, int(limit)),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT metric_name, COUNT(*) AS n, AVG(metric_value) AS avg_value,
                       MIN(metric_value) AS min_value, MAX(metric_value) AS max_value
                FROM metrics WHERE metric_value IS NOT NULL
                GROUP BY metric_name ORDER BY metric_name LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
    return rows_to_dicts(rows)


def summarize_database(db_path: str | Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    with connect(db_path) as con:
        init_schema(con)
        summary = {
            "db_path": project_relative(db_path),
            "schema_version": con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
            "runs": con.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
            "tasks": con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
            "done_tasks": con.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0],
            "failed_tasks": con.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'").fetchone()[0],
            "pending_tasks": con.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0],
            "outputs": con.execute("SELECT COUNT(*) FROM outputs").fetchone()[0],
            "metrics": con.execute("SELECT COUNT(*) FROM metrics").fetchone()[0],
            "presets": con.execute("SELECT COUNT(*) FROM presets").fetchone()[0],
        }
    return {k: int(v) if isinstance(v, bool) is False and isinstance(v, int) else v for k, v in summary.items()}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild or query the CivitasLab SQLite experiment index.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--rebuild", action="store_true", help="rebuild index from manifests and presets")
    parser.add_argument("--summary", action="store_true", help="print database summary")
    parser.add_argument("--list-runs", action="store_true", help="list indexed runs")
    parser.add_argument("--list-tasks", action="store_true", help="list indexed tasks")
    parser.add_argument("--list-presets", action="store_true", help="list indexed presets")
    parser.add_argument("--metric", help="aggregate one metric name")
    parser.add_argument("--run-id", help="filter tasks by run_id")
    parser.add_argument("--status", help="filter tasks by status")
    parser.add_argument("--preset", help="filter runs by preset")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    if args.rebuild:
        payload: Any = rebuild_database(args.db).to_dict()
    elif args.summary:
        payload = summarize_database(args.db)
    elif args.list_runs:
        payload = list_runs(args.db, limit=args.limit, preset=args.preset)
    elif args.list_tasks:
        payload = list_tasks(args.db, run_id=args.run_id, status=args.status, limit=args.limit)
    elif args.list_presets:
        payload = list_presets(args.db)
    elif args.metric:
        payload = aggregate_metrics(args.db, metric_name=args.metric, limit=args.limit)
    else:
        payload = summarize_database(args.db)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
