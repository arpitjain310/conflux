"""Schema reconciliation: sources name and type the same field differently.

FieldMap normalizes native field *names* (and per-source quirks) to canonical
ones. Schema declares the canonical *types* and which fields a complete entity
needs. Type coercion is per record.
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


@dataclass
class Field:
    name: str
    type: Callable = str
    required: bool = False


@dataclass
class Schema:
    fields: list[Field]

    def coerce(self, fields: dict) -> tuple[dict, list[str]]:
        declared = {f.name: f for f in self.fields}
        clean: dict = {}
        errors: list[str] = []
        for name, value in fields.items():
            f = declared.get(name)
            if f is None:
                clean[name] = value
                continue
            try:
                clean[name] = f.type(value)
            except (TypeError, ValueError):
                errors.append(f"{name}={value!r} is not {f.type.__name__}")
        return clean, errors

    def missing_required(self, fields: dict) -> list[str]:
        return [f.name for f in self.fields if f.required and f.name not in fields]
