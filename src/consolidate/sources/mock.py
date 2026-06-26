"""In-memory source for development and tests: seed native rows, normalize
them through a FieldMap, expose them as incremental Records.
"""
from __future__ import annotations

from collections.abc import Iterable

from ..record import Record, Source
from ..schema import FieldMap


class MockSource(Source):
    def __init__(
        self,
        name: str,
        field_map: FieldMap | None = None,
        key_field: str = "id",
        entity: str = "",
    ):
        self.name = name
        self.field_map = field_map or FieldMap()
        self.key_field = key_field
        # Shared entity namespace so the same real-world entity from two sources
        # lands on the same key and merges (e.g. "customer:42").
        self.entity = entity or name
        self._rows: list[tuple[float, dict]] = []

    def add(self, native: dict, updated_at: float) -> None:
        self._rows.append((updated_at, native))

    def fetch(self, since: float) -> Iterable[Record]:
        for updated_at, native in sorted(self._rows, key=lambda r: r[0]):
            if updated_at <= since:
                continue
            # Identity lives in the key, not the fields — drop the id column.
            payload = {k: v for k, v in native.items() if k != self.key_field}
            yield Record(
                key=f"{self.entity}:{native[self.key_field]}",
                fields=self.field_map.apply(payload),
                source=self.name,
                updated_at=updated_at,
            )
