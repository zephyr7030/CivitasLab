"""Structured event stream for CivitasLab runtime inspection.

This module provides both a bounded in-memory stream for the live UI and a
chunked writer for long-running simulations. The writer is optional and does not
change simulation behavior; it only mirrors emitted events to disk so that high
volume runtime windows can read event pages without keeping everything in memory.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import csv
import json


@dataclass
class EventRecord:
    turn: int
    phase: str
    message: str
    entity_type: str = "unknown"
    entity_id: str = ""
    population: str = ""
    event_type: str = "text_log"
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EventStreamWriter:
    """Chunked on-disk writer for structured events.

    JSONL is the canonical streaming format. A compact CSV mirror can also be
    enabled for quick spreadsheet-style inspection; nested ``data`` is stored as
    JSON text in the CSV file.
    """

    def __init__(
        self,
        output_dir: str | Path,
        chunk_size: int = 5000,
        write_csv: bool = True,
        manifest_name: str = "event_manifest.json",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_size = max(1, int(chunk_size))
        self.write_csv = bool(write_csv)
        self.manifest_path = self.output_dir / manifest_name
        self.chunk_index = 0
        self.current_count = 0
        self.total_events = 0
        self.chunks: List[Dict[str, Any]] = []
        self._jsonl_file = None
        self._csv_file = None
        self._csv_writer = None
        self._open_next_chunk()

    def _chunk_paths(self, index: int) -> Dict[str, Path]:
        return {
            "jsonl": self.output_dir / f"events_{index:06d}.jsonl",
            "csv": self.output_dir / f"events_{index:06d}.csv",
        }

    def _open_next_chunk(self) -> None:
        self.close_current()
        self.chunk_index += 1
        self.current_count = 0
        paths = self._chunk_paths(self.chunk_index)
        self._jsonl_file = paths["jsonl"].open("w", encoding="utf-8")
        if self.write_csv:
            self._csv_file = paths["csv"].open("w", newline="", encoding="utf-8-sig")
            fieldnames = ["turn", "phase", "entity_type", "entity_id", "population", "event_type", "message", "data"]
            self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=fieldnames)
            self._csv_writer.writeheader()
        else:
            self._csv_file = None
            self._csv_writer = None
        self.chunks.append({
            "chunk_index": self.chunk_index,
            "jsonl": str(paths["jsonl"]),
            "csv": str(paths["csv"]) if self.write_csv else None,
            "event_count": 0,
            "first_turn": None,
            "last_turn": None,
        })
        self.write_manifest()

    def close_current(self) -> None:
        if self._jsonl_file:
            self._jsonl_file.flush()
            self._jsonl_file.close()
            self._jsonl_file = None
        if self._csv_file:
            self._csv_file.flush()
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None

    def append(self, event: EventRecord | Dict[str, Any]) -> None:
        event_dict = event.to_dict() if isinstance(event, EventRecord) else dict(event)
        if self.current_count >= self.chunk_size:
            self._open_next_chunk()
        if not self._jsonl_file:
            self._open_next_chunk()
        self._jsonl_file.write(json.dumps(event_dict, ensure_ascii=False) + "\n")
        if self._csv_writer:
            row = {
                "turn": event_dict.get("turn", ""),
                "phase": event_dict.get("phase", ""),
                "entity_type": event_dict.get("entity_type", ""),
                "entity_id": event_dict.get("entity_id", ""),
                "population": event_dict.get("population", ""),
                "event_type": event_dict.get("event_type", ""),
                "message": event_dict.get("message", ""),
                "data": json.dumps(event_dict.get("data", {}), ensure_ascii=False, sort_keys=True),
            }
            self._csv_writer.writerow(row)
        self.current_count += 1
        self.total_events += 1
        chunk = self.chunks[-1]
        chunk["event_count"] += 1
        turn = event_dict.get("turn")
        if chunk["first_turn"] is None:
            chunk["first_turn"] = turn
        chunk["last_turn"] = turn

    def write_manifest(self) -> None:
        manifest = {
            "schema_version": 1,
            "format": "jsonl_chunks",
            "chunk_size": self.chunk_size,
            "total_events": self.total_events,
            "chunk_count": len(self.chunks),
            "chunks": self.chunks,
        }
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def close(self) -> None:
        self.close_current()
        # Remove trailing empty chunk if no event ever landed in it.
        self.chunks = [chunk for chunk in self.chunks if chunk.get("event_count", 0) > 0]
        self.write_manifest()

    def paths(self) -> Dict[str, Any]:
        return {
            "event_manifest": str(self.manifest_path),
            "event_dir": str(self.output_dir),
            "event_chunks": self.chunks,
            "event_count": self.total_events,
        }


class EventStream:
    """Bounded in-memory structured event stream with optional disk writer."""

    def __init__(self, max_events: int = 5000, writer: Optional[EventStreamWriter] = None):
        self.max_events = int(max_events)
        self.events: List[EventRecord] = []
        self.writer = writer

    def set_writer(self, writer: Optional[EventStreamWriter]) -> None:
        self.writer = writer

    def append(
        self,
        turn: int,
        phase: str,
        message: str,
        entity_type: str = "unknown",
        entity_id: str = "",
        population: str = "",
        event_type: str = "text_log",
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        record = EventRecord(
            turn=int(turn),
            phase=str(phase),
            message=str(message),
            entity_type=str(entity_type or "unknown"),
            entity_id=str(entity_id or ""),
            population=str(population or ""),
            event_type=str(event_type or "text_log"),
            data=dict(data or {}),
        )
        self.events.append(record)
        if self.writer is not None:
            self.writer.append(record)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events :]

    def to_list(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        source = self.events if limit is None else self.events[-int(limit) :]
        return [event.to_dict() for event in source]

    def counts_by_phase(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for event in self.events:
            counts[event.phase] = counts.get(event.phase, 0) + 1
        return counts

    def counts_by_entity_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for event in self.events:
            counts[event.entity_type] = counts.get(event.entity_type, 0) + 1
        return counts


def write_event_stream(events: Iterable[Dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(events), ensure_ascii=False, indent=2), encoding="utf-8")


def iter_event_chunks(manifest_path: str | Path, event_type: str | None = None, entity_type: str | None = None, entity_id: str | None = None, turn_min: int | None = None, turn_max: int | None = None):
    """Yield events from a chunked event manifest with optional filters."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for chunk in manifest.get("chunks", []):
        path = Path(chunk.get("jsonl", ""))
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                turn = int(event.get("turn", 0) or 0)
                if event_type and event.get("event_type") != event_type:
                    continue
                if entity_type and event.get("entity_type") != entity_type:
                    continue
                if entity_id and event.get("entity_id") != entity_id:
                    continue
                if turn_min is not None and turn < turn_min:
                    continue
                if turn_max is not None and turn > turn_max:
                    continue
                yield event
