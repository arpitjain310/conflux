# conflux

[![ci](https://github.com/arpitjain310/conflux/actions/workflows/ci.yml/badge.svg)](https://github.com/arpitjain310/conflux/actions/workflows/ci.yml)

> A consolidation pipeline that pulls from mismatched sources, reconciles their
> schemas, and merges everything into one queryable store — with incremental
> sync, idempotent upserts, and last-write-wins conflict resolution.

**Status:** v0.1.0 scaffold. Source/Record contract, schema reconciliation,
idempotent per-field upsert with pluggable conflict resolution (last-write-wins
or source priority), incremental sync with a boundary-correct persisted cursor,
and a two-source demo, all against in-memory mocks.

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
  merges per field; a `Resolver` decides who wins a contested field.
- **Resolver** (`resolve.py`) — the trust model, separate from the merge
  mechanics: last-write-wins, or source priority for a field a given source owns.
- **Sync state** (`state.py`) — a per-source cursor (watermark + boundary keys),
  persisted atomically, so incremental sync resumes across runs without losing
  rows that share the watermark.
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

Merge is **per field**, not per record — each field remembers the write that set
it (value, source, time) — and the *decision* of who wins is a swappable policy,
kept separate from the merge mechanics:

- **Last-write-wins** (default): newest `updated_at` wins a contested field.
- **Source priority**: a source you trust for a field wins regardless of edit
  time — a stale clock or a bulk re-import from a lesser source can't clobber the
  system of record. Ties within a trust level fall back to time.

An older write to a field already held is ignored either way (idempotency), and
an older source can still contribute a field no one else has set.

## Incremental sync

The cursor is a high-water timestamp **plus the keys already seen at exactly that
timestamp**. A naive `updated_at > watermark` cursor silently drops a row that
shares the watermark and arrives in a later run; carrying the boundary set fixes
that while still pulling only new work. The cursor advances only after a source
drains, so a mid-source failure re-pulls rather than skips. State is persisted
atomically, so sync resumes across processes.

## Quickstart

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
conflux sync
conflux get customer:1
conflux --trust billing,crm get customer:1
```
