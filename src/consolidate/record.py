"""Record and Source: the two contracts the engine is built on.

A Record is one entity, identity-keyed so the same entity arriving from
different sources merges instead of duplicating. A Source is a connector that
pulls native rows and maps them onto Records — native schema stays behind the
connector, the engine sees only Records.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field

from .state import Cursor


@dataclass(frozen=True)
class Record:
    key: str
    fields: dict = field(default_factory=dict)
    source: str = ""
    # Source's last-modified time. Drives incremental sync (the cursor) and
    # conflict resolution (newest write wins per field).
    updated_at: float = 0.0


class Source(ABC):
    name: str

    @abstractmethod
    def fetch(self, cursor: Cursor) -> Iterable[Record]:
        """Records at or after the cursor watermark, excluding keys already seen
        at exactly that watermark.

        Native-row → Record mapping happens here, so a re-fetch from the current
        cursor pulls only new work without dropping rows on the boundary.
        """
