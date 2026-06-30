from consolidate.record import Record
from consolidate.resolve import FieldWrite, LastWriteWins, SourcePriority
from consolidate.store import InMemoryStore


def rec(key, fields, source, updated_at):
    return Record(key=key, fields=fields, source=source, updated_at=updated_at)


def test_last_write_wins_by_time_ignoring_source():
    r = LastWriteWins()
    assert r.wins(FieldWrite("b", "billing", 20.0), FieldWrite("a", "crm", 10.0))
    assert not r.wins(FieldWrite("a", "crm", 10.0), FieldWrite("b", "billing", 20.0))


def test_source_priority_beats_a_newer_lesser_source():
    # billing is authoritative; a later crm write must not clobber it.
    r = SourcePriority(["billing", "crm"])
    assert not r.wins(FieldWrite("crm-late", "crm", 30.0), FieldWrite("billed", "billing", 20.0))
    assert r.wins(FieldWrite("billed", "billing", 20.0), FieldWrite("crm-late", "crm", 30.0))


def test_source_priority_breaks_ties_by_time_within_a_source():
    r = SourcePriority(["billing", "crm"])
    assert r.wins(FieldWrite("new", "crm", 30.0), FieldWrite("old", "crm", 10.0))


def test_store_source_priority_keeps_authoritative_field():
    store = InMemoryStore(resolver=SourcePriority(["billing", "crm"]))
    store.upsert(rec("customer:1", {"email": "ada@billing"}, "billing", 20.0))
    res = store.upsert(rec("customer:1", {"email": "ada@crm-late"}, "crm", 30.0))
    assert not res.updated  # the newer-but-lesser source lost
    assert store.get("customer:1").fields["email"] == "ada@billing"


def test_store_last_write_wins_takes_the_newer_email():
    store = InMemoryStore()  # default LastWriteWins
    store.upsert(rec("customer:1", {"email": "ada@billing"}, "billing", 20.0))
    store.upsert(rec("customer:1", {"email": "ada@crm-late"}, "crm", 30.0))
    assert store.get("customer:1").fields["email"] == "ada@crm-late"
