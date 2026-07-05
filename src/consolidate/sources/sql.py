"""SqlSource: a real connector over a SQLite table.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from ..record import Record, Source
from ..schema import FieldMap
from ..state import Cursor


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # rows read as dicts
    return conn


class SqlSource(Source):
    def __init__(
        self,
        name: str,
        conn: sqlite3.Connection,
        table: str,
        *,
        key_field: str = "id",
        updated_field: str = "updated_at",
        deleted_field: str = "deleted",
        entity: str = "",
        field_map: FieldMap | None = None,
    ):
        self.name = name
        self.conn = conn
        self.table = table  # trusted identifier, not user input
        self.key_field = key_field
        self.updated_field = updated_field
        self.deleted_field = deleted_field
        self.entity = entity or name
        self.field_map = field_map or FieldMap()

    def fetch(self, cursor: Cursor) -> Iterable[Record]:
        rows = self.conn.execute(
            f"SELECT * FROM {self.table} WHERE {self.updated_field} >= ? "
            f"ORDER BY {self.updated_field}",
            (cursor.watermark,),
        ).fetchall()
        reserved = {self.key_field, self.updated_field, self.deleted_field}
        for row in rows:
            native = dict(row)
            updated_at = float(native[self.updated_field])
            key = f"{self.entity}:{native[self.key_field]}"
            if updated_at == cursor.watermark and key in cursor.seen:
                continue
            if native.get(self.deleted_field):
                yield Record(key=key, source=self.name, updated_at=updated_at, deleted=True)
                continue
            payload = {k: v for k, v in native.items() if k not in reserved}
            yield Record(
                key=key,
                fields=self.field_map.apply(payload),
                source=self.name,
                updated_at=updated_at,
            )
