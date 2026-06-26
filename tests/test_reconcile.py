from consolidate.schema import FieldMap
from consolidate.sources.mock import MockSource


def test_fieldmap_renames_and_coerces():
    fm = FieldMap(rename={"id": "customer_id", "email": "email_address"}, coerce={"id": int})
    out = fm.apply({"customer_id": "42", "email_address": "a@b", "extra": "kept"})
    assert out == {"id": 42, "email": "a@b", "extra": "kept"}


def test_unmapped_canonical_fields_pass_through():
    fm = FieldMap(rename={"name": "full_name"})
    out = fm.apply({"full_name": "Ada", "plan": "pro"})
    assert out == {"name": "Ada", "plan": "pro"}


def test_two_sources_merge_onto_one_entity():
    crm = MockSource("crm", FieldMap(rename={"name": "full_name"}), key_field="id", entity="customer")
    crm.add({"id": 1, "full_name": "Ada"}, updated_at=10.0)
    billing = MockSource("billing", key_field="customer_id", entity="customer")
    billing.add({"customer_id": 1, "plan": "pro"}, updated_at=11.0)

    keys = {r.key for r in list(crm.fetch(0.0)) + list(billing.fetch(0.0))}
    assert keys == {"customer:1"}
