"""Consolidated store: one merged record per key.

upsert is idempotent — re-applying a record the store has already seen changes
nothing — and merges field-by-field across sources. Each field keeps the write
that set it (value, source, time); a Resolver decides who wins a contested field.
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


class Store(ABC):
    @abstractmethod
    def upsert(self, record: Record) -> UpsertResult: ...

    @abstractmethod
    def get(self, key: str) -> Record | None: ...


class InMemoryStore(Store):
    def __init__(self, resolver: Resolver | None = None) -> None:
        self.resolver = resolver or LastWriteWins()
        self._records: dict[str, Record] = {}
        # Per-field provenance so resolution is per field, not per record: a
        # lesser source can still contribute a field no one else has set.
        self._prov: dict[str, dict[str, FieldWrite]] = {}

    def upsert(self, record: Record) -> UpsertResult:
        prov = self._prov.get(record.key)
        if prov is None:
            self._records[record.key] = record
            self._prov[record.key] = {
                name: FieldWrite(value, record.source, record.updated_at)
                for name, value in record.fields.items()
            }
            return UpsertResult(inserted=True)

        merged = dict(self._records[record.key].fields)
        changed = False
        conflict = False
        for name, value in record.fields.items():
            incoming = FieldWrite(value, record.source, record.updated_at)
            current = prov.get(name)
            if current is None:
                merged[name] = value
                prov[name] = incoming
                changed = True
            elif self.resolver.wins(incoming, current):
                if merged[name] != value:
                    conflict = True
                merged[name] = value
                prov[name] = incoming
                changed = True
            # Loser write to a field we already hold: ignore (idempotency).

        if changed:
            self._records[record.key] = Record(
                key=record.key,
                fields=merged,
                source=record.source,
                updated_at=max(self._records[record.key].updated_at, record.updated_at),
            )
        return UpsertResult(updated=changed, conflict=conflict)

    def get(self, key: str) -> Record | None:
        return self._records.get(key)

    def keys(self) -> list[str]:
        return list(self._records)
