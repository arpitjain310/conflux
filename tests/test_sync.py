from consolidate.pipeline import Pipeline
from consolidate.schema import FieldMap
from consolidate.sources.mock import MockSource
from consolidate.state import SyncState
from consolidate.store import InMemoryStore


def build(state=None):
    crm = MockSource("crm", FieldMap(rename={"name": "full_name", "email": "email"}),
                     key_field="id", entity="customer")
    crm.add({"id": 1, "full_name": "Ada", "email": "ada@old"}, updated_at=10.0)
    billing = MockSource("billing", FieldMap(rename={"email": "email_address", "plan": "plan"}),
                         key_field="customer_id", entity="customer")
    billing.add({"customer_id": 1, "email_address": "ada@new", "plan": "pro"}, updated_at=20.0)
    return crm, billing, Pipeline([crm, billing], InMemoryStore(), state)


def test_sync_merges_sources():
    _, _, pipeline = build()
    report = pipeline.sync()
    assert report.inserted == 1  # one entity
    merged = pipeline.store.get("customer:1").fields
    assert merged == {"name": "Ada", "email": "ada@new", "plan": "pro"}
    assert report.conflicts == 1  # billing's newer email overwrote crm's


def test_resync_with_no_new_rows_is_a_noop():
    state = SyncState()
    _, _, pipeline = build(state)
    pipeline.sync()
    report = pipeline.sync()
    assert report.inserted == 0 and report.updated == 0
    assert report.pulled_by_source == {"crm": 0, "billing": 0}


def test_incremental_picks_up_only_new_rows():
    state = SyncState()
    crm, billing, pipeline = build(state)
    pipeline.sync()
    crm.add({"id": 2, "full_name": "Alan", "email": "alan@x"}, updated_at=30.0)
    report = pipeline.sync()
    assert report.pulled_by_source == {"crm": 1, "billing": 0}
    assert report.inserted == 1
    assert state.cursor("crm") == 30.0


def test_cursor_persists_across_runs(tmp_path):
    path = str(tmp_path / "cursors.json")
    crm, billing, pipeline = build(SyncState.load(path))
    pipeline.sync()
    # A fresh state loaded from disk resumes from the persisted cursor.
    resumed = SyncState.load(path)
    assert resumed.cursor("crm") == 10.0
    assert resumed.cursor("billing") == 20.0
