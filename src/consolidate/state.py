"""Sync state: a per-source high-water cursor so a re-run pulls only what
changed. Persisted (atomically) so incremental sync survives across runs.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class SyncState:
    path: str | None = None
    cursors: dict[str, float] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | None) -> SyncState:
        if path and os.path.exists(path):
            with open(path) as f:
                return cls(path=path, cursors=json.load(f))
        return cls(path=path)

    def cursor(self, source: str) -> float:
        return self.cursors.get(source, 0.0)

    def advance(self, source: str, to: float) -> None:
        if to > self.cursors.get(source, 0.0):
            self.cursors[source] = to
            self._flush()

    def _flush(self) -> None:
        if not self.path:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.cursors, f)
        os.replace(tmp, self.path)  # atomic: a crash mid-write can't corrupt the cursor file
