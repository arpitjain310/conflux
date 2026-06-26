# conflux

[![ci](https://github.com/arpitjain310/conflux/actions/workflows/ci.yml/badge.svg)](https://github.com/arpitjain310/conflux/actions/workflows/ci.yml)

> A consolidation pipeline that pulls from mismatched sources, reconciles their
> schemas, and merges everything into one queryable store — with incremental
> sync, idempotent upserts, and last-write-wins conflict resolution.

**Status:** v0.1.0 scaffold. Source/Record contract, schema reconciliation,
idempotent per-field upsert with conflict resolution, incremental sync with a
persisted cursor, and a two-source demo, all against in-memory mocks.

---

## The problem

The interesting part of "pull data from everywhere into one place" is not the
pulling. It is everything that makes a second run safe:

- **Schema mismatch** — every source names and types the same field
  differently. They have to agree before they can merge.
- **Identity** — the same entity arrives from multiple sources and must land on
  one record, not three.
- **Conflicts** — two sources disagree on a field. Which one wins, and why.
- **Incremental, idempotent sync** — a re-run must pull only what changed and
  must not duplicate or corrupt what is already there.

The hard core is incremental sync plus schema reconciliation across sources that
do not agree on shape.

## What it does

```
source A ─┐  (native rows)
source B ─┤─▶ FieldMap (reconcile schema) ─▶ Record (entity-keyed)
source C ─┘                                      │
                                                 ▼
                          Store.upsert  ── idempotent, per-field
                                             last-write-wins merge
                                                 │
              SyncState cursor ◀── advance ──────┘
              (per source; persisted, so a re-run pulls only new rows)
```

- **Record + Source** (`record.py`) — one contract per connector. A source maps
  its native rows to entity-keyed Records; the engine never sees native schema.
- **Schema reconciliation** (`schema.py`) — a `FieldMap` renames and coerces
  native fields to a canonical schema before they become Records.
- **Store** (`store.py`) — one merged record per key. `upsert` is idempotent and
  resolves conflicts per field, newest `updated_at` winning a contested field.
- **Sync state** (`state.py`) — a per-source high-water cursor, persisted
  atomically, so incremental sync resumes across runs.
- **Pipeline** (`pipeline.py`) — fetch since cursor → upsert → advance cursor,
  reporting inserts, updates, and conflicts.

## Explicit non-goals

- Not a chatbot or a model — the hard part here is the data, not inference.
- No live external systems during development — sources are **mocked**; a real
  backend (SQL connector + on-disk store) is wired behind the same contract
  next, to prove it holds.
- Not a general ETL framework — it consolidates entity records, it does not run
  arbitrary transforms.

## Conflict resolution

Merge is **per field**, not per record. Each field carries the `updated_at` of
the write that set it:

- A newer write to a field overwrites it (and is flagged a conflict if the value
  actually changed).
- An older write to a field already set is ignored — this is what makes re-runs
  idempotent.
- An older source can still contribute a field no one else has set, without
  losing to a newer record's timestamp on other fields.

## Quickstart

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
conflux sync
conflux get customer:1
```
