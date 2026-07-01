"""Consolidated store: one merged record per key.

Provenance is the source of truth: every field keeps the write that set it
(value, source, time). upsert is idempotent, merges field-by-field across
sources — a Resolver decides who wins a contested field — and a delete is a
timestamped tombstone that masks fields older than it, so a later write from any
source revives just those fields.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .record import Record
from .resolve import FieldWrite, LastWriteWins, Resolver


@dataclass
class UpsertResult:
    inserted: bool = False
    updated: bool = False
    # An existing field was overwritten with a different value.
    conflict: bool = False
    deleted: bool = False


class Store(ABC):
    @abstractmethod
    def upsert(self, record: Record) -> UpsertResult: ...

    @abstractmethod
    def get(self, key: str) -> Record | None: ...


class InMemoryStore(Store):
    def __init__(self, resolver: Resolver | None = None) -> None:
        self.resolver = resolver or LastWriteWins()
        self._prov: dict[str, dict[str, FieldWrite]] = {}
        # Per-entity tombstone time. A field survives only if written after it.
        self._tombstone: dict[str, float] = {}

    def upsert(self, record: Record) -> UpsertResult:
        if record.deleted:
            return self._apply_delete(record)

        prov = self._prov.get(record.key)
        if prov is None:
            self._prov[record.key] = {
                name: FieldWrite(value, record.source, record.updated_at)
                for name, value in record.fields.items()
            }
            return UpsertResult(inserted=not self._is_deleted(record.key))

        changed = False
        conflict = False
        for name, value in record.fields.items():
            incoming = FieldWrite(value, record.source, record.updated_at)
            current = prov.get(name)
            if current is None or self.resolver.wins(incoming, current):
                if current is not None and current.value != value:
                    conflict = True
                prov[name] = incoming
                changed = True
            # Loser write to a field we already hold: ignore (idempotency).
        return UpsertResult(updated=changed, conflict=conflict)

    def get(self, key: str) -> Record | None:
        live = self._live_fields(key)
        if not live:
            return None
        latest = max(live.values(), key=lambda fw: fw.updated_at)
        return Record(
            key=key,
            fields={name: fw.value for name, fw in live.items()},
            source=latest.source,
            updated_at=latest.updated_at,
        )

    def keys(self) -> list[str]:
        return [key for key in self._prov if self._live_fields(key)]

    def _apply_delete(self, record: Record) -> UpsertResult:
        prior = self._tombstone.get(record.key, 0.0)
        if record.updated_at <= prior:
            return UpsertResult()  # stale or repeated delete: no-op
        had_live = bool(self._live_fields(record.key))
        self._tombstone[record.key] = record.updated_at
        return UpsertResult(deleted=had_live and not self._live_fields(record.key))

    def _live_fields(self, key: str) -> dict[str, FieldWrite]:
        tombstone = self._tombstone.get(key, 0.0)
        prov = self._prov.get(key, {})
        return {name: fw for name, fw in prov.items() if fw.updated_at > tombstone}

    def _is_deleted(self, key: str) -> bool:
        return not self._live_fields(key)
