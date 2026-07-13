"""Consolidation engine: for each source, pull records changed since its
cursor, upsert them into the store, advance the cursor. A re-run with no new
source data changes nothing.

With a canonical Schema, records are coerced to declared types at ingest.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from .record import Record, Source
from .schema import Schema
from .state import Cursor, SyncState
from .store import Store


@dataclass
class Rejection:
    key: str
    source: str
    errors: tuple[str, ...]


@dataclass
class Incomplete:
    key: str
    missing: tuple[str, ...]


@dataclass
class SyncReport:
    inserted: int = 0
    updated: int = 0
    conflicts: int = 0
    deleted: int = 0
    rejected: int = 0
    pulled_by_source: dict[str, int] = field(default_factory=dict)
    rejects: list[Rejection] = field(default_factory=list)
    incomplete: list[Incomplete] = field(default_factory=list)


class Pipeline:
    def __init__(
        self,
        sources: Iterable[Source],
        store: Store,
        state: SyncState | None = None,
        schema: Schema | None = None,
    ):
        self.sources = list(sources)
        self.store = store
        self.state = state or SyncState()
        self.schema = schema

    def sync(self) -> SyncReport:
        report = SyncReport()
        for source in self.sources:
            cursor = self.state.cursor(source.name)
            high = cursor.watermark
            seen_at_high = set(cursor.seen)
            pulled = 0
            for record in source.fetch(cursor):
                pulled += 1

                if record.updated_at > high:
                    high = record.updated_at
                    seen_at_high = {record.key}
                elif record.updated_at == high:
                    seen_at_high.add(record.key)
                self._apply(record, report)
            report.pulled_by_source[source.name] = pulled
            # Advance only after the source drains, so a mid-source failure
            # re-pulls from the last committed cursor rather than skipping rows.
            self.state.advance(source.name, Cursor(high, frozenset(seen_at_high)))

        self._flag_incomplete(report)
        return report

    def _apply(self, record: Record, report: SyncReport) -> None:
        if self.schema is not None and not record.deleted:
            clean, errors = self.schema.coerce(record.fields)
            if errors:
                report.rejected += 1
                report.rejects.append(Rejection(record.key, record.source, tuple(errors)))
                return
            record = replace(record, fields=clean)
        result = self.store.upsert(record)
        report.inserted += int(result.inserted)
        report.updated += int(result.updated)
        report.conflicts += int(result.conflict)
        report.deleted += int(result.deleted)

    def _flag_incomplete(self, report: SyncReport) -> None:
        if self.schema is None:
            return
        for key in self.store.keys():
            record = self.store.get(key)
            missing = self.schema.missing_required(record.fields)
            if missing:
                report.incomplete.append(Incomplete(key, tuple(missing)))
