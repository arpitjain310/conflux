from consolidate.pipeline import Pipeline
from consolidate.schema import FieldMap
from consolidate.sources.sql import SqlSource, connect
from consolidate.state import SyncState
from consolidate.store import InMemoryStore


def make_source(conn, field_map=None):
    return SqlSource(
        "crm", conn, "customers", entity="customer",
        field_map=field_map or FieldMap(rename={"name": "full_name"}),
    )


def seed(conn):
    conn.execute(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, "
        "updated_at REAL, deleted INTEGER DEFAULT 0)"
    )
    conn.execute("INSERT INTO customers VALUES (1, 'Ada', 'ada@x', 10.0, 0)")
    conn.execute("INSERT INTO customers VALUES (2, 'Alan', 'alan@x', 11.0, 0)")
    conn.commit()


def test_reads_real_rows_and_reconciles_schema():
    conn = connect()
    seed(conn)
    state = SyncState()
    pipeline = Pipeline([make_source(conn)], InMemoryStore(), state)
    report = pipeline.sync()
    assert report.inserted == 2
    # id/updated_at/deleted are dropped; full_name renamed to name.
    assert pipeline.store.get("customer:1").fields == {"name": "Ada", "email": "ada@x"}


def test_incremental_pulls_only_changed_rows():
    conn = connect()
    seed(conn)
    state = SyncState()
    pipeline = Pipeline([make_source(conn)], InMemoryStore(), state)
    pipeline.sync()

    conn.execute("INSERT INTO customers VALUES (3, 'Grace', 'grace@x', 20.0, 0)")
    conn.commit()
    report = pipeline.sync()
    assert report.pulled_by_source == {"crm": 1}
    assert report.inserted == 1
    assert state.cursor("crm").watermark == 20.0


def test_soft_delete_becomes_a_tombstone():
    conn = connect()
    seed(conn)
    state = SyncState()
    pipeline = Pipeline([make_source(conn)], InMemoryStore(), state)
    pipeline.sync()

    conn.execute("UPDATE customers SET deleted = 1, updated_at = 30.0 WHERE id = 1")
    conn.commit()
    report = pipeline.sync()
    assert report.deleted == 1
    assert pipeline.store.get("customer:1") is None


def test_row_at_the_watermark_boundary_is_not_reprocessed():
    conn = connect()
    seed(conn)
    state = SyncState()
    pipeline = Pipeline([make_source(conn)], InMemoryStore(), state)
    pipeline.sync()
    
    report = pipeline.sync()
    assert report.pulled_by_source == {"crm": 0}
