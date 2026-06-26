"""Consolidated store: one merged record per key.

upsert is idempotent — re-applying a record the store has already seen changes
nothing — and merges field-by-field across sources, newest updated_at winning a
contested field.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .record import Record


@dataclass
class UpsertResult:
    inserted: bool = False
    updated: bool = False
    # An existing field was overwritten by a newer write with a different value.
    conflict: bool = False


class Store(ABC):
    @abstractmethod
    def upsert(self, record: Record) -> UpsertResult: ...

    @abstractmethod
    def get(self, key: str) -> Record | None: ...


class InMemoryStore(Store):
    def __init__(self) -> None:
        self._records: dict[str, Record] = {}
        # Per-field timestamp so conflict resolution is per field, not per record:
        # a stale source can still contribute a field no one else has set.
        self._field_ts: dict[str, dict[str, float]] = {}

    def upsert(self, record: Record) -> UpsertResult:
        existing = self._records.get(record.key)
        if existing is None:
            self._records[record.key] = record
            self._field_ts[record.key] = {f: record.updated_at for f in record.fields}
            return UpsertResult(inserted=True)

        merged = dict(existing.fields)
        ts = self._field_ts[record.key]
        changed = False
        conflict = False
        for name, value in record.fields.items():
            prior = ts.get(name)
            if prior is None:
                merged[name] = value
                ts[name] = record.updated_at
                changed = True
            elif record.updated_at > prior:
                if merged[name] != value:
                    conflict = True
                merged[name] = value
                ts[name] = record.updated_at
                changed = True
            # Older-or-equal write to a field we already have: ignore (idempotent).

        if changed:
            self._records[record.key] = Record(
                key=record.key,
                fields=merged,
                source=record.source,
                updated_at=max(existing.updated_at, record.updated_at),
            )
        return UpsertResult(updated=changed, conflict=conflict)

    def get(self, key: str) -> Record | None:
        return self._records.get(key)

    def keys(self) -> list[str]:
        return list(self._records)
