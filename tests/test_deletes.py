from consolidate.pipeline import Pipeline
from consolidate.record import Record
from consolidate.schema import FieldMap
from consolidate.sources.mock import MockSource
from consolidate.state import SyncState
from consolidate.store import InMemoryStore


def rec(key, fields, source, updated_at):
    return Record(key=key, fields=fields, source=source, updated_at=updated_at)


def tomb(key, source, updated_at):
    return Record(key=key, source=source, updated_at=updated_at, deleted=True)


def test_delete_tombstones_entity():
    store = InMemoryStore()
    store.upsert(rec("customer:1", {"name": "Ada"}, "crm", 10.0))
    res = store.upsert(tomb("customer:1", "crm", 20.0))
    assert res.deleted
    assert store.get("customer:1") is None
    assert store.keys() == []


def test_field_newer_than_delete_survives():
    store = InMemoryStore()
    store.upsert(rec("customer:1", {"email": "ada@x"}, "crm", 30.0))
    res = store.upsert(tomb("customer:1", "billing", 20.0))
    assert not res.deleted  # nothing live was actually removed
    assert store.get("customer:1").fields == {"email": "ada@x"}


def test_write_after_delete_revives_only_newer_fields():
    store = InMemoryStore()
    store.upsert(rec("customer:1", {"name": "Ada", "plan": "free"}, "crm", 10.0))
    store.upsert(tomb("customer:1", "crm", 20.0))
    store.upsert(rec("customer:1", {"plan": "pro"}, "billing", 30.0))
    # The pre-delete fields stay masked; only the post-delete write survives.
    assert store.get("customer:1").fields == {"plan": "pro"}


def test_delete_is_idempotent():
    store = InMemoryStore()
    store.upsert(rec("customer:1", {"name": "Ada"}, "crm", 10.0))
    store.upsert(tomb("customer:1", "crm", 20.0))
    res = store.upsert(tomb("customer:1", "crm", 20.0))
    assert not res.deleted
    assert store.get("customer:1") is None


def test_delete_propagates_through_sync_and_is_incremental():
    state = SyncState()
    crm = MockSource("crm", FieldMap(rename={"name": "full_name"}), key_field="id", entity="customer")
    crm.add({"id": 3, "full_name": "Grace"}, updated_at=15.0)
    billing = MockSource("billing", key_field="customer_id", entity="customer")
    pipeline = Pipeline([crm, billing], InMemoryStore(), state)
    pipeline.sync()
    assert pipeline.store.get("customer:3") is not None

    billing.remove(3, updated_at=25.0)
    report = pipeline.sync()
    assert report.deleted == 1
    assert report.pulled_by_source == {"crm": 0, "billing": 1}
    assert pipeline.store.get("customer:3") is None
