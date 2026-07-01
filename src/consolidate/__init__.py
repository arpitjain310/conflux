"""conflux: pull from mismatched sources, reconcile schemas, and merge into one
queryable store with incremental sync and idempotent upserts."""

from .pipeline import Pipeline, SyncReport
from .record import Record, Source
from .resolve import FieldWrite, LastWriteWins, Resolver, SourcePriority
from .schema import FieldMap
from .state import Cursor, SyncState
from .store import InMemoryStore, Store, UpsertResult

__all__ = [
    "Pipeline",
    "SyncReport",
    "Record",
    "Source",
    "FieldWrite",
    "LastWriteWins",
    "Resolver",
    "SourcePriority",
    "FieldMap",
    "Cursor",
    "SyncState",
    "InMemoryStore",
    "Store",
    "UpsertResult",
]
