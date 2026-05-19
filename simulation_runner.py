"""Unified simulation runner abstraction for BOT8 system-stage development.

This module provides a stable RunResult interface for CLI tools, GUI prototypes,
RunManifest queues, and future accelerated engines. It intentionally keeps the
current Environment behavior unchanged.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
import copy
import json
import random
import time

import config
from model import Environment
from output import SUMMARY_HEADERS, validate_summary_headers
from event_stream import EventStreamWriter, write_event_stream
from entity_state_snapshot import EntitySnapshotWriter, write_entity_state_snapshots, write_entity_state_snapshots_csv


@dataclass
class RunResult:
    seed: int
    turns_completed: int
    requested_turns: int
    initial_population: int
    survived: bool
    extinction_turn: Optional[int]
    final_population: int
    peak_population: int
    tail_avg_population: float
    births: int
    deaths: int
    death_reasons: Dict[str, int]
    money_delta: float
    header_missing: List[str]
    resource_use_to_regen_tail_avg: float = 0.0
    labor_resource_unused_tail_avg: float = 0.0
    food_hard_satisfied_tail_avg: float = 0.0
    medical_hard_satisfied_tail_avg: float = 0.0
    reproduction_hard_satisfied_tail_avg: float = 0.0
    hard_need_blocked_no_stock_sum: float = 0.0
    food_hard_unsatisfied_sum: float = 0.0
    medical_hard_unsatisfied_sum: float = 0.0
    reproduction_hard_unsatisfied_sum: float = 0.0
    avg_health_index_tail: float = 0.0
    avg_education_capital_tail: float = 0.0
    avg_reproductive_security_tail: float = 0.0
    medical_recovery_sum: float = 0.0
    health_deterioration_sum: float = 0.0
    company_resilience_tail_avg: float = 0.0
    government_policy_pressure_tail_avg: float = 0.0
    runtime_seconds: float = 0.0
    avg_turn_seconds: float = 0.0
    phase_timing: Dict[str, float] = field(default_factory=dict)
    event_count: int = 0
    events_by_phase: Dict[str, int] = field(default_factory=dict)
    events_by_entity_type: Dict[str, int] = field(default_factory=dict)
    entity_snapshot_turns: int = 0
    latest_individual_snapshot_count: int = 0
    latest_company_snapshot_count: int = 0
    latest_government_snapshot_count: int = 0
    entity_snapshot_csv_files: Dict[str, str] = field(default_factory=dict)
    event_manifest_path: str = ""
    event_dir: str = ""
    event_chunk_count: int = 0
    snapshot_manifest_path: str = ""
    snapshot_dir: str = ""
    snapshot_chunk_count: int = 0
    output_dir: str = ""
    run_manifest_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def make_cfg(turns: int, pop: int, seed: int, base_settings=None, overrides=None) -> Dict[str, Any]:
    cfg = copy.deepcopy(base_settings or config.DEFAULT_SETTINGS)
    if overrides:
        from tools.preset_utils import apply_overrides
        cfg = apply_overrides(cfg, overrides)
    cfg["base"]["max_turns"] = int(turns)
    cfg["base"]["initial_population"] = int(pop)
    cfg["base"]["population_count"] = 1
    cfg["base"]["random_seed"] = int(seed)
    return cfg


def total_money(env: Environment) -> float:
    return (
        sum(ind.balance for pp in env.populations.values() for ind in pp)
        + sum(env.government_deposit.values())
        + sum(env.company_totals(p)["money"] for p in env.population_names)
    )


def run_simulation_case(
    seed: int,
    turns: int,
    pop: int,
    base_settings=None,
    overrides=None,
    collect_rows: bool = True,
    event_stream_out: Optional[str | Path] = None,
    event_stream_limit: int = 1000,
    entity_snapshot_out: Optional[str | Path] = None,
    entity_snapshot_limit: int = 200,
    entity_snapshot_csv_dir: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
    write_chunked_events: bool = False,
    event_chunk_size: int = 5000,
    write_chunked_snapshots: bool = False,
    snapshot_chunk_turns: int = 100,
) -> Dict[str, Any]:
    """Run one deterministic BOT8 case and return a RunResult-compatible dict."""
    random.seed(seed)
    env = Environment(make_cfg(turns, pop, seed, base_settings=base_settings, overrides=overrides))
    output_dir_path = Path(output_dir) if output_dir else None
    event_writer = None
    snapshot_writer = None
    if output_dir_path and write_chunked_events and hasattr(env, "event_stream"):
        event_writer = EventStreamWriter(output_dir_path / "events", chunk_size=event_chunk_size, write_csv=True)
        env.event_stream.set_writer(event_writer)
    if output_dir_path and write_chunked_snapshots and hasattr(env, "entity_state_snapshots"):
        snapshot_writer = EntitySnapshotWriter(output_dir_path / "snapshots", chunk_turns=snapshot_chunk_turns)
        env.entity_state_snapshots.set_writer(snapshot_writer)
    initial_money = total_money(env)
    rows: List[Dict[str, Any]] = []
    deaths: Counter = Counter()
    turn_durations: List[float] = []
    start = time.perf_counter()
    for _ in range(turns):
        t0 = time.perf_counter()
        ok = env.run_turn()
        turn_durations.append(time.perf_counter() - t0)
        for _, ind in env.dead_individuals_this_turn:
            deaths[ind.death_reason] += 1
        if collect_rows and env.current_summary_rows:
            rows.append(dict(env.current_summary_rows[0]))
        if not ok:
            break
    runtime = time.perf_counter() - start
    if event_writer is not None:
        event_writer.close()
    if snapshot_writer is not None:
        snapshot_writer.close()
    final_pop = sum(len(pp) for pp in env.populations.values())
    final_money = total_money(env)
    header_check = validate_summary_headers(env.summary_output_rows, SUMMARY_HEADERS)
    tail = rows[-min(200, len(rows)):] if rows else []

    def avg_tail(key: str) -> float:
        if not tail:
            return 0.0
        return round(sum(float(r.get(key, 0) or 0) for r in tail) / len(tail), 6)

    def sum_all(key: str) -> float:
        return round(sum(float(r.get(key, 0) or 0) for r in rows), 6) if rows else 0.0

    pops = [int(r.get("PopCount", 0) or 0) for r in rows]
    event_count = len(getattr(env.event_stream, "events", [])) if hasattr(env, "event_stream") else 0
    events_by_phase = env.event_stream.counts_by_phase() if hasattr(env, "event_stream") else {}
    events_by_entity_type = env.event_stream.counts_by_entity_type() if hasattr(env, "event_stream") else {}
    if event_stream_out and hasattr(env, "event_stream"):
        write_event_stream(env.event_stream.to_list(limit=event_stream_limit), event_stream_out)
    snapshot_list = env.entity_state_snapshots.to_list(limit=entity_snapshot_limit) if hasattr(env, "entity_state_snapshots") else []
    snapshot_csv_files = {}
    if entity_snapshot_out and hasattr(env, "entity_state_snapshots"):
        write_entity_state_snapshots(snapshot_list, entity_snapshot_out)
    if entity_snapshot_csv_dir and hasattr(env, "entity_state_snapshots"):
        snapshot_csv_files = write_entity_state_snapshots_csv(snapshot_list, entity_snapshot_csv_dir)
    latest_snapshot = env.entity_state_snapshots.latest() if hasattr(env, "entity_state_snapshots") else {}
    event_writer_paths = event_writer.paths() if event_writer is not None else {}
    snapshot_writer_paths = snapshot_writer.paths() if snapshot_writer is not None else {}
    result = RunResult(
        seed=int(seed),
        turns_completed=int(env.turn),
        requested_turns=int(turns),
        initial_population=int(pop),
        survived=bool(env.turn >= turns and final_pop > 0),
        extinction_turn=None if final_pop > 0 else int(env.turn),
        final_population=int(final_pop),
        peak_population=max(pops) if pops else int(pop),
        tail_avg_population=avg_tail("PopCount"),
        births=int(env.cumulative_birth_count.get("A", 0)),
        deaths=int(env.cumulative_death_count.get("A", 0)),
        death_reasons=dict(deaths),
        money_delta=round(final_money - initial_money, 6),
        header_missing=header_check["missing_headers"],
        resource_use_to_regen_tail_avg=avg_tail("ResourceUseToRegenRatio"),
        labor_resource_unused_tail_avg=avg_tail("LaborResourceUnusedRate"),
        food_hard_satisfied_tail_avg=avg_tail("FoodHardNeedSatisfiedRate"),
        medical_hard_satisfied_tail_avg=avg_tail("MedicalHardNeedSatisfiedRate"),
        reproduction_hard_satisfied_tail_avg=avg_tail("ReproductionHardNeedSatisfiedRate"),
        hard_need_blocked_no_stock_sum=sum_all("HardNeedBlockedByNoMarketStock"),
        food_hard_unsatisfied_sum=sum_all("FoodHardUnsatisfiedAmount"),
        medical_hard_unsatisfied_sum=sum_all("MedicalHardUnsatisfiedAmount"),
        reproduction_hard_unsatisfied_sum=sum_all("ReproductionHardUnsatisfiedAmount"),
        avg_health_index_tail=avg_tail("AvgHealthIndex"),
        avg_education_capital_tail=avg_tail("AvgEducationCapital"),
        avg_reproductive_security_tail=avg_tail("AvgReproductiveSecurity"),
        medical_recovery_sum=sum_all("MedicalRecoveryCount"),
        health_deterioration_sum=sum_all("HealthDeteriorationCount"),
        company_resilience_tail_avg=avg_tail("CompanyResilienceScore"),
        government_policy_pressure_tail_avg=avg_tail("GovernmentPolicyPressureScore"),
        runtime_seconds=round(runtime, 6),
        avg_turn_seconds=round(sum(turn_durations) / max(1, len(turn_durations)), 6),
        phase_timing={"run_turn_total_seconds": round(sum(turn_durations), 6)},
        event_count=event_count,
        events_by_phase=events_by_phase,
        events_by_entity_type=events_by_entity_type,
        entity_snapshot_turns=len(env.entity_state_snapshots.turns) if hasattr(env, "entity_state_snapshots") else 0,
        latest_individual_snapshot_count=len(latest_snapshot.get("individuals", [])) if latest_snapshot else 0,
        latest_company_snapshot_count=len(latest_snapshot.get("companies", [])) if latest_snapshot else 0,
        latest_government_snapshot_count=len(latest_snapshot.get("governments", [])) if latest_snapshot else 0,
        entity_snapshot_csv_files=snapshot_csv_files,
        event_manifest_path=str(event_writer_paths.get("event_manifest", "")),
        event_dir=str(event_writer_paths.get("event_dir", "")),
        event_chunk_count=int(len(event_writer_paths.get("event_chunks", []))),
        snapshot_manifest_path=str(snapshot_writer_paths.get("snapshot_manifest", "")),
        snapshot_dir=str(snapshot_writer_paths.get("snapshot_dir", "")),
        snapshot_chunk_count=int(len(snapshot_writer_paths.get("snapshot_chunks", []))),
        output_dir=str(output_dir_path or ""),
    )
    return result.to_dict()



def iter_simulation_steps(
    seed: int,
    turns: int,
    pop: int,
    base_settings=None,
    overrides=None,
    output_dir: Optional[str | Path] = None,
    write_chunked_events: bool = False,
    event_chunk_size: int = 5000,
    write_chunked_snapshots: bool = False,
    snapshot_chunk_turns: int = 100,
):
    """Yield per-turn simulation rows for GUI/runtime streaming.

    This helper is intentionally lightweight and does not change Environment
    behavior. Optional output writers are used by the GUI process backend so the
    model-observation pages can read events/snapshots from the latest GUI run.
    """
    random.seed(seed)
    env = Environment(make_cfg(turns, pop, seed, base_settings=base_settings, overrides=overrides))
    output_dir_path = Path(output_dir) if output_dir else None
    event_writer = None
    snapshot_writer = None
    if output_dir_path and write_chunked_events and hasattr(env, "event_stream"):
        event_writer = EventStreamWriter(output_dir_path / "events", chunk_size=event_chunk_size, write_csv=True)
        env.event_stream.set_writer(event_writer)
    if output_dir_path and write_chunked_snapshots and hasattr(env, "entity_state_snapshots"):
        snapshot_writer = EntitySnapshotWriter(output_dir_path / "snapshots", chunk_turns=snapshot_chunk_turns)
        env.entity_state_snapshots.set_writer(snapshot_writer)
    initial_money = total_money(env)
    try:
        for _ in range(turns):
            ok = env.run_turn()
            row = dict(env.current_summary_rows[0]) if env.current_summary_rows else {}
            row.setdefault("Turn", env.turn)
            row.setdefault("PopCount", sum(len(pp) for pp in env.populations.values()))
            row["__money_delta"] = round(total_money(env) - initial_money, 6)
            row["__ok"] = bool(ok)
            if output_dir_path:
                row["__output_dir"] = str(output_dir_path)
            yield row
            if not ok:
                break
    finally:
        if event_writer is not None:
            event_writer.close()
        if snapshot_writer is not None:
            snapshot_writer.close()


def row_to_ui_metrics(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map one summary row to stable GUI metric keys."""
    return {
        "population.total": row.get("PopCount", row.get("Population", 0)),
        "population.births": row.get("BirthCount", 0),
        "population.deaths": row.get("DeathCount", 0),
        "resources.use_to_regen": row.get("ResourceUseToRegenRatio", 0),
        "resources.unused_labor": row.get("LaborResourceUnusedRate", 0),
        "money.delta": row.get("__money_delta", row.get("MoneyDelta", 0)),
        "hard_need.food_satisfied": row.get("FoodHardNeedSatisfiedRate", 0),
        "hard_need.medical_satisfied": row.get("MedicalHardNeedSatisfiedRate", 0),
        "hard_need.reproduction_satisfied": row.get("ReproductionHardNeedSatisfiedRate", 0),
        "lifecycle.health": row.get("AvgHealthIndex", 0),
        "lifecycle.education": row.get("AvgEducationCapital", 0),
        "lifecycle.reproductive_security": row.get("AvgReproductiveSecurity", 0),
        "lifecycle.medical_recovery": row.get("MedicalRecoveryCount", 0),
        "lifecycle.health_deterioration": row.get("HealthDeteriorationCount", 0),
        "company.food_stock": row.get("FoodCompanyStock", row.get("CompanyFoodStock", 0)),
        "company.reproduction_stock": row.get("ReproductionCompanyStock", row.get("CompanyReproductionGoodsStock", 0)),
        "company.resilience": row.get("CompanyResilienceScore", 0),
        "government.food_stock": row.get("GovernmentFood", 0),
        "government.policy_pressure": row.get("GovernmentPolicyPressureScore", 0),
        "market.food_price": row.get("MarketFoodPrice", row.get("FoodPrice", 0)),
        "evolution.morality": row.get("AvgMorality", 0),
        "evolution.strength": row.get("AvgStrength", 0),
        "evolution.intelligence": row.get("AvgIntelligence", 0),
        "evolution.reproduce": row.get("AvgReproduceTendency", 0),
    }

def write_run_result(result: Dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
