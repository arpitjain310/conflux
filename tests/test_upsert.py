from consolidate.record import Record
from consolidate.store import InMemoryStore


def rec(key, fields, source, updated_at):
    return Record(key=key, fields=fields, source=source, updated_at=updated_at)


def test_first_upsert_inserts():
    store = InMemoryStore()
    res = store.upsert(rec("customer:1", {"name": "Ada"}, "crm", 10.0))
    assert res.inserted and not res.updated
    assert store.get("customer:1").fields == {"name": "Ada"}


def test_reapply_is_idempotent():
    store = InMemoryStore()
    store.upsert(rec("customer:1", {"name": "Ada"}, "crm", 10.0))
    res = store.upsert(rec("customer:1", {"name": "Ada"}, "crm", 10.0))
    assert not res.inserted and not res.updated and not res.conflict


def test_newer_write_wins_and_flags_conflict():
    store = InMemoryStore()
    store.upsert(rec("customer:1", {"email": "ada@old"}, "crm", 10.0))
    res = store.upsert(rec("customer:1", {"email": "ada@new"}, "billing", 20.0))
    assert res.updated and res.conflict
    assert store.get("customer:1").fields["email"] == "ada@new"


def test_older_write_does_not_overwrite():
    store = InMemoryStore()
    store.upsert(rec("customer:1", {"email": "ada@new"}, "billing", 20.0))
    res = store.upsert(rec("customer:1", {"email": "ada@old"}, "crm", 10.0))
    assert not res.updated and not res.conflict
    assert store.get("customer:1").fields["email"] == "ada@new"


def test_stale_source_still_adds_a_missing_field():
    # Conflict resolution is per field: an older source contributes a field no
    # newer write has set, without losing to the newer record's timestamp.
    store = InMemoryStore()
    store.upsert(rec("customer:1", {"email": "ada@new"}, "billing", 20.0))
    res = store.upsert(rec("customer:1", {"plan": "free"}, "crm", 10.0))
    assert res.updated and not res.conflict
    assert store.get("customer:1").fields == {"email": "ada@new", "plan": "free"}
