"""Schema reconciliation: sources name and type the same field differently.

A FieldMap normalizes a native row to canonical field names (and optional type
coercion) before it becomes a Record, so everything downstream sees one schema.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class FieldMap:
    # canonical name -> native name
    rename: dict[str, str] = field(default_factory=dict)
    # canonical name -> coercion applied after rename (e.g. int, parse date)
    coerce: dict[str, Callable] = field(default_factory=dict)

    def apply(self, native: dict) -> dict:
        out: dict = {}
        mapped_natives = set(self.rename.values())
        for canon, nat in self.rename.items():
            if nat in native:
                value = native[nat]
                if canon in self.coerce:
                    value = self.coerce[canon](value)
                out[canon] = value
        # Fields already canonical (not renamed) pass through untouched.
        for k, v in native.items():
            if k not in mapped_natives and k not in out:
                out[k] = v
        return out
