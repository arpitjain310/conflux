"""conflux: pull from mismatched sources, reconcile schemas, and merge into one
queryable store with incremental sync and idempotent upserts."""

from .pipeline import Incomplete, Pipeline, Rejection, SyncReport
from .record import Record, Source
from .resolve import FieldWrite, LastWriteWins, Resolver, SourcePriority
from .schema import Field, FieldMap, Schema
from .state import Cursor, SyncState
from .store import InMemoryStore, Store, UpsertResult

__all__ = [
    "Pipeline",
    "SyncReport",
    "Rejection",
    "Incomplete",
    "Record",
    "Source",
    "FieldWrite",
    "LastWriteWins",
    "Resolver",
    "SourcePriority",
    "Field",
    "FieldMap",
    "Schema",
    "Cursor",
    "SyncState",
    "InMemoryStore",
    "Store",
    "UpsertResult",
]
