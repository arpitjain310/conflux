from consolidate.pipeline import Pipeline
from consolidate.schema import Field, FieldMap, Schema
from consolidate.sources.mock import MockSource
from consolidate.store import InMemoryStore

SCHEMA = Schema([
    Field("name", str, required=True),
    Field("email", str),
    Field("mrr", int),
])


def test_coerce_casts_declared_fields():
    clean, errors = SCHEMA.coerce({"name": "Ada", "mrr": "4900"})
    assert clean == {"name": "Ada", "mrr": 4900}
    assert errors == []


def test_coerce_reports_uncoercible_value():
    clean, errors = SCHEMA.coerce({"mrr": "lots"})
    assert clean == {}
    assert len(errors) == 1 and "mrr" in errors[0]


def test_coerce_passes_through_undeclared_fields():
    clean, _ = SCHEMA.coerce({"nickname": "Countess"})
    assert clean == {"nickname": "Countess"}


def test_missing_required_is_per_entity():
    assert SCHEMA.missing_required({"email": "a@b"}) == ["name"]
    assert SCHEMA.missing_required({"name": "Ada"}) == []


def source(name, rows, key="id"):
    src = MockSource(name, FieldMap(), key_field=key, entity="customer")
    for native, ts in rows:
        src.add(native, ts)
    return src


def test_mismatched_types_merge_after_coercion():
    a = source("a", [({"id": 1, "mrr": 4900}, 10.0)])
    b = source("b", [({"id": 1, "mrr": "4900"}, 20.0)])
    pipeline = Pipeline([a, b], InMemoryStore(), schema=SCHEMA)
    report = pipeline.sync()
    assert report.conflicts == 0
    assert pipeline.store.get("customer:1").fields["mrr"] == 4900


def test_uncoercible_record_is_quarantined_not_stored():
    src = source("a", [({"id": 1, "name": "Ada", "mrr": "lots"}, 10.0)])
    pipeline = Pipeline([src], InMemoryStore(), schema=SCHEMA)
    report = pipeline.sync()
    assert report.rejected == 1
    assert report.rejects[0].key == "customer:1"
    assert pipeline.store.get("customer:1") is None  # nothing partial leaked in


def test_incomplete_entity_is_flagged_after_merge():
    src = source("billing", [({"id": 4, "email": "team@x"}, 13.0)])
    pipeline = Pipeline([src], InMemoryStore(), schema=SCHEMA)
    report = pipeline.sync()
    assert [(i.key, i.missing) for i in report.incomplete] == [("customer:4", ("name",))]


def test_partial_source_records_are_not_rejected_for_missing_required():
    crm = source("crm", [({"id": 1, "name": "Ada"}, 10.0)])
    billing = source("billing", [({"id": 1, "email": "ada@b"}, 20.0)])
    pipeline = Pipeline([crm, billing], InMemoryStore(), schema=SCHEMA)
    report = pipeline.sync()
    assert report.rejected == 0
    assert report.incomplete == []
    assert pipeline.store.get("customer:1").fields == {"name": "Ada", "email": "ada@b"}
