"""Sync state: a per-source cursor so a re-run pulls only what changed.

A cursor is a high-water timestamp plus the keys already seen *at* that exact
timestamp. The boundary set is what makes incremental sync correct: rows that
share the watermark and arrive in a later run are still pulled instead of being
silently skipped. Persisted atomically so sync resumes across runs.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Cursor:
    watermark: float = 0.0
    seen: frozenset[str] = frozenset()


@dataclass
class SyncState:
    path: str | None = None
    cursors: dict[str, Cursor] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | None) -> SyncState:
        if path and os.path.exists(path):
            with open(path) as f:
                raw = json.load(f)
            cursors = {
                src: Cursor(c["watermark"], frozenset(c["seen"])) for src, c in raw.items()
            }
            return cls(path=path, cursors=cursors)
        return cls(path=path)

    def cursor(self, source: str) -> Cursor:
        return self.cursors.get(source, Cursor())

    def advance(self, source: str, cursor: Cursor) -> None:
        self.cursors[source] = cursor
        self._flush()

    def _flush(self) -> None:
        if not self.path:
            return
        raw = {
            src: {"watermark": c.watermark, "seen": sorted(c.seen)}
            for src, c in self.cursors.items()
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(raw, f)
        os.replace(tmp, self.path)  # atomic: a crash mid-write can't corrupt the cursor file
