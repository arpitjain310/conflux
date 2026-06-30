"""Conflict resolution policy
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FieldWrite:
    value: object
    source: str
    updated_at: float


class Resolver(Protocol):
    def wins(self, incoming: FieldWrite, current: FieldWrite) -> bool:
        """True if `incoming` should overwrite `current` for a contested field."""


class LastWriteWins:
    def wins(self, incoming: FieldWrite, current: FieldWrite) -> bool:
        return incoming.updated_at > current.updated_at


@dataclass
class SourcePriority:
    # Highest-trust source first.
    order: list[str]

    def _rank(self, source: str) -> int:
        try:
            return self.order.index(source)
        except ValueError:
            return len(self.order)

    def wins(self, incoming: FieldWrite, current: FieldWrite) -> bool:
        ri, rc = self._rank(incoming.source), self._rank(current.source)
        if ri != rc:
            return ri < rc  # lower index = higher trust
        return incoming.updated_at > current.updated_at  # same trust → newer wins