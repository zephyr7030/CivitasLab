"""Entity state snapshots for CivitasLab runtime inspection.

The snapshot collector is deliberately read-only: it converts the current
simulation state into compact dictionaries for GUI replay and debugging without
changing model behavior.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import csv


class EntityStateSnapshot:
    """Bounded per-turn entity snapshots for individuals, companies and governments."""

    def __init__(self, max_turns: int = 200, writer: Optional[Any] = None):
        self.max_turns = int(max_turns)
        self.turns: List[Dict[str, Any]] = []
        self.writer = writer

    def set_writer(self, writer: Optional[Any]) -> None:
        self.writer = writer

    def append(self, snapshot: Dict[str, Any]) -> None:
        self.turns.append(snapshot)
        if self.writer is not None:
            self.writer.append(snapshot)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def to_list(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        source = self.turns if limit is None else self.turns[-int(limit):]
        return list(source)

    def latest(self) -> Dict[str, Any]:
        return self.turns[-1] if self.turns else {}


def collect_entity_state_snapshot(env: Any) -> Dict[str, Any]:
    """Collect a compact state snapshot from the current Environment."""
    individuals: List[Dict[str, Any]] = []
    companies: List[Dict[str, Any]] = []
    governments: List[Dict[str, Any]] = []

    for pop_name in getattr(env, "population_names", []):
        for ind in env.populations.get(pop_name, []):
            individuals.append({
                "turn": int(getattr(env, "turn", 0)),
                "population": pop_name,
                "id": int(getattr(ind, "id", -1)),
                "code": str(getattr(ind, "code", "")),
                "age_round": int(getattr(ind, "survival_rounds", 0)),
                "life": int(getattr(ind, "life", 0)),
                "money": int(getattr(ind, "balance", 0)),
                "food": int(getattr(ind, "food", 0)),
                "medical_goods": int(getattr(ind, "medical_goods", 0)),
                "education_goods": int(getattr(ind, "education_goods", 0)),
                "reproduction_goods": int(getattr(ind, "reproduction_goods", 0)),
                "labor": int(getattr(ind, "labor", 0)),
                "reproduce": int(getattr(ind, "reproduce", 0)),
                "morality": int(getattr(ind, "morality", 0)),
                "strength": int(getattr(ind, "strength", 0)),
                "intelligence": int(getattr(ind, "intelligence", 0)),
                "sick": int(bool(getattr(ind, "is_sick", False))),
                "critical": int(bool(getattr(ind, "critical", False))),
                "did_labor": int(getattr(ind, "did_labor", 0)),
                "did_reproduce": int(getattr(ind, "did_reproduce", 0)),
                "wage_received": int(getattr(ind, "wage_received", 0)),
                "market_spent": int(getattr(ind, "market_money_spent", 0)),
                "market_earned": int(getattr(ind, "market_money_earned", 0)),
                "death_reason": str(getattr(ind, "death_reason", "")),
            })

        company = getattr(env, "companies", {}).get(pop_name, {})
        for good, branch in company.items():
            companies.append({
                "turn": int(getattr(env, "turn", 0)),
                "population": pop_name,
                "branch": good,
                "money": int(branch.get("money", 0)),
                "stock": int(branch.get("stock", 0)),
                "initial_money": int(branch.get("initial_money", 0)),
                "initial_stock": int(branch.get("initial_stock", 0)),
                "goods_produced": int(branch.get("goods_produced", 0)),
                "wages_paid": int(branch.get("wages_paid", 0)),
                "sales_income": int(branch.get("sales_income", 0)),
                "resource_purchased": int(branch.get("resource_purchased", 0)),
                "resource_cost": int(branch.get("resource_cost", 0)),
                "labor_assigned": int(branch.get("labor_assigned", 0)),
                "expected_profit": int(branch.get("expected_profit", 0)),
            })

        governments.append({
            "turn": int(getattr(env, "turn", 0)),
            "population": pop_name,
            "money": int(getattr(env, "government_deposit", {}).get(pop_name, 0)),
            "food": int(getattr(env, "government_food", {}).get(pop_name, 0)),
            "medical_goods": int(getattr(env, "government_medical_goods", {}).get(pop_name, 0)),
            "education_goods": int(getattr(env, "government_education_goods", {}).get(pop_name, 0)),
            "reproduction_goods": int(getattr(env, "government_reproduction_goods", {}).get(pop_name, 0)),
            "tools": int(getattr(env, "government_tools", {}).get(pop_name, 0)),
            "production_resource": int(getattr(env, "government_production_resource", {}).get(pop_name, 0)),
        })

    return {
        "turn": int(getattr(env, "turn", 0)),
        "individuals": individuals,
        "companies": companies,
        "governments": governments,
    }


def write_entity_state_snapshots(snapshots: Iterable[Dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(snapshots), ensure_ascii=False, indent=2), encoding="utf-8")


def _flatten_snapshot_rows(snapshots: Iterable[Dict[str, Any]], section: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for snapshot in snapshots:
        for row in snapshot.get(section, []):
            rows.append(dict(row))
    return rows


def write_entity_state_snapshots_csv(snapshots: Iterable[Dict[str, Any]], output_dir: str | Path, prefix: str = "") -> Dict[str, str]:
    """Write entity snapshots as three layered CSV files.

    JSON remains useful for prototype replay, while CSV files are easier to inspect,
    stream into data tools, and load into future GUI tables without parsing a large nested document.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_list = list(snapshots)
    files = {}
    for section, filename in [
        ("individuals", "individual_state.csv"),
        ("companies", "company_state.csv"),
        ("governments", "government_state.csv"),
    ]:
        rows = _flatten_snapshot_rows(snapshot_list, section)
        path = output_dir / f"{prefix}{filename}"
        files[section] = str(path)
        if not rows:
            path.write_text("", encoding="utf-8")
            continue
        fieldnames = sorted({key for row in rows for key in row.keys()})
        # Keep the most important columns first.
        preferred = ["turn", "population", "code", "id", "branch"]
        fieldnames = [f for f in preferred if f in fieldnames] + [f for f in fieldnames if f not in preferred]
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    return files


class EntitySnapshotWriter:
    """Chunked writer for per-turn entity state snapshots.

    Each chunk contains three CSV files: individuals, companies and governments.
    This keeps long-running GUI reads bounded and avoids giant in-memory JSON
    documents for detailed runtime windows.
    """

    def __init__(self, output_dir: str | Path, chunk_turns: int = 100, manifest_name: str = "snapshot_manifest.json"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_turns = max(1, int(chunk_turns))
        self.manifest_path = self.output_dir / manifest_name
        self.chunk_index = 0
        self.turn_count_in_chunk = 0
        self.total_turns = 0
        self.chunks: List[Dict[str, Any]] = []
        self._files: Dict[str, Any] = {}
        self._writers: Dict[str, csv.DictWriter] = {}
        self._fieldnames = {
            "individuals": [
                "turn", "population", "code", "id", "age_round", "life", "money", "food", "medical_goods",
                "education_goods", "reproduction_goods", "labor", "reproduce", "morality", "strength", "intelligence",
                "sick", "critical", "did_labor", "did_reproduce", "wage_received", "market_spent", "market_earned", "death_reason",
            ],
            "companies": [
                "turn", "population", "branch", "money", "stock", "initial_money", "initial_stock", "goods_produced",
                "wages_paid", "sales_income", "resource_purchased", "resource_cost", "labor_assigned", "expected_profit",
            ],
            "governments": [
                "turn", "population", "money", "food", "medical_goods", "education_goods", "reproduction_goods", "tools", "production_resource",
            ],
        }
        self._open_next_chunk()

    def _chunk_paths(self, index: int) -> Dict[str, Path]:
        return {
            "individuals": self.output_dir / f"individual_state_{index:06d}.csv",
            "companies": self.output_dir / f"company_state_{index:06d}.csv",
            "governments": self.output_dir / f"government_state_{index:06d}.csv",
        }

    def _open_next_chunk(self) -> None:
        self.close_current()
        self.chunk_index += 1
        self.turn_count_in_chunk = 0
        paths = self._chunk_paths(self.chunk_index)
        self._files = {}
        self._writers = {}
        for section, path in paths.items():
            f = path.open("w", newline="", encoding="utf-8-sig")
            writer = csv.DictWriter(f, fieldnames=self._fieldnames[section], extrasaction="ignore")
            writer.writeheader()
            self._files[section] = f
            self._writers[section] = writer
        self.chunks.append({
            "chunk_index": self.chunk_index,
            "individuals_csv": str(paths["individuals"]),
            "companies_csv": str(paths["companies"]),
            "governments_csv": str(paths["governments"]),
            "turn_count": 0,
            "first_turn": None,
            "last_turn": None,
            "individual_rows": 0,
            "company_rows": 0,
            "government_rows": 0,
        })
        self.write_manifest()

    def close_current(self) -> None:
        for f in self._files.values():
            f.flush()
            f.close()
        self._files = {}
        self._writers = {}

    def append(self, snapshot: Dict[str, Any]) -> None:
        if self.turn_count_in_chunk >= self.chunk_turns:
            self._open_next_chunk()
        if not self._writers:
            self._open_next_chunk()
        chunk = self.chunks[-1]
        turn = snapshot.get("turn")
        for row in snapshot.get("individuals", []):
            self._writers["individuals"].writerow(row)
            chunk["individual_rows"] += 1
        for row in snapshot.get("companies", []):
            self._writers["companies"].writerow(row)
            chunk["company_rows"] += 1
        for row in snapshot.get("governments", []):
            self._writers["governments"].writerow(row)
            chunk["government_rows"] += 1
        self.turn_count_in_chunk += 1
        self.total_turns += 1
        chunk["turn_count"] += 1
        if chunk["first_turn"] is None:
            chunk["first_turn"] = turn
        chunk["last_turn"] = turn

    def write_manifest(self) -> None:
        manifest = {
            "schema_version": 1,
            "format": "csv_chunks",
            "chunk_turns": self.chunk_turns,
            "total_turns": self.total_turns,
            "chunk_count": len(self.chunks),
            "chunks": self.chunks,
        }
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def close(self) -> None:
        self.close_current()
        self.chunks = [chunk for chunk in self.chunks if chunk.get("turn_count", 0) > 0]
        self.write_manifest()

    def paths(self) -> Dict[str, Any]:
        return {
            "snapshot_manifest": str(self.manifest_path),
            "snapshot_dir": str(self.output_dir),
            "snapshot_chunks": self.chunks,
            "snapshot_turns": self.total_turns,
        }


def iter_snapshot_rows(manifest_path: str | Path, section: str, turn_min: int | None = None, turn_max: int | None = None):
    """Yield rows from snapshot CSV chunks for one section."""
    key = {
        "individuals": "individuals_csv",
        "companies": "companies_csv",
        "governments": "governments_csv",
    }.get(section)
    if not key:
        raise ValueError("section must be one of: individuals, companies, governments")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for chunk in manifest.get("chunks", []):
        path = Path(chunk.get(key, ""))
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    turn = int(row.get("turn", 0) or 0)
                except ValueError:
                    turn = 0
                if turn_min is not None and turn < turn_min:
                    continue
                if turn_max is not None and turn > turn_max:
                    continue
                yield row
