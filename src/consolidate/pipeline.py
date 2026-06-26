"""Consolidation engine: for each source, pull records changed since its
cursor, upsert them into the store, advance the cursor. A re-run with no new
source data changes nothing.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .record import Source
from .state import SyncState
from .store import Store


@dataclass
class SyncReport:
    inserted: int = 0
    updated: int = 0
    conflicts: int = 0
    pulled_by_source: dict[str, int] = field(default_factory=dict)


class Pipeline:
    def __init__(self, sources: Iterable[Source], store: Store, state: SyncState | None = None):
        self.sources = list(sources)
        self.store = store
        self.state = state or SyncState()

    def sync(self) -> SyncReport:
        report = SyncReport()
        for source in self.sources:
            since = self.state.cursor(source.name)
            high = since
            pulled = 0
            for record in source.fetch(since):
                result = self.store.upsert(record)
                report.inserted += int(result.inserted)
                report.updated += int(result.updated)
                report.conflicts += int(result.conflict)
                high = max(high, record.updated_at)
                pulled += 1
            report.pulled_by_source[source.name] = pulled
            # Advance only after the source drains, so a mid-source failure
            # re-pulls from the last committed cursor rather than skipping rows.
            self.state.advance(source.name, high)
        return report
