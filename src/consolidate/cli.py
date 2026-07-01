"""conflux CLI.

`sync` runs the pipeline and prints a report; `get KEY` prints the merged
record. The demo wires two sources with mismatched schemas onto one entity
(customer). Both touch customer 1's email, with crm editing it later than
billing — so `--trust billing crm` (source priority) resolves it differently
than the default last-write-wins.
"""
from __future__ import annotations

import argparse
import json

from .pipeline import Pipeline
from .resolve import LastWriteWins, SourcePriority
from .schema import FieldMap
from .sources.mock import MockSource
from .store import InMemoryStore


def build_demo(trust: list[str] | None = None) -> Pipeline:
    # A CRM-style source: full_name/email under its own names.
    crm = MockSource(
        "crm",
        field_map=FieldMap(rename={"name": "full_name", "email": "email"}),
        key_field="id",
        entity="customer",
    )
    crm.add({"id": 1, "full_name": "Ada Lovelace", "email": "ada@crm"}, updated_at=10.0)
    crm.add({"id": 1, "email": "ada@crm-late"}, updated_at=30.0)
    crm.add({"id": 2, "full_name": "Alan Turing"}, updated_at=11.0)

    # A billing-style source: same customers, different field names.
    billing = MockSource(
        "billing",
        field_map=FieldMap(rename={"email": "email_address", "plan": "plan"}),
        key_field="customer_id",
        entity="customer",
    )
    billing.add({"customer_id": 1, "email_address": "ada@billing", "plan": "pro"}, updated_at=20.0)
    billing.add({"customer_id": 2, "plan": "free"}, updated_at=12.0)

    resolver = SourcePriority(trust) if trust else LastWriteWins()
    return Pipeline([crm, billing], InMemoryStore(resolver))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="conflux")
    parser.add_argument(
        "--trust",
        metavar="SOURCE,SOURCE",
        help="comma-separated source priority (highest-trust first); "
        "resolves conflicts by trust instead of last-write-wins",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync", help="consolidate all sources into the store")
    get = sub.add_parser("get", help="print the merged record for a key")
    get.add_argument("key")

    args = parser.parse_args(argv)
    trust = args.trust.split(",") if args.trust else None
    pipeline = build_demo(trust=trust)
    report = pipeline.sync()

    if args.command == "sync":
        print(
            f"inserted={report.inserted} updated={report.updated} "
            f"conflicts={report.conflicts} pulled={report.pulled_by_source}"
        )
        return 0

    record = pipeline.store.get(args.key)
    if record is None:
        print(f"no record for {args.key}")
        return 1
    print(json.dumps({"key": record.key, "fields": record.fields}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
