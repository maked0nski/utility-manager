"""Merge consecutive ConnectionChargeLine rows that only differ by date.

Some connections accumulate one charge-line row per month even when the
price never actually changed (e.g. someone re-submits the same tariff via
the "Змінити тарифний план" wizard every month out of habit, or a manual
"Редагувати" edit re-saves an unchanged line with a new effective_from).
Each of those rows is functionally identical to its predecessor - same
label/meter/price/unit/quantity settings - and contiguous in time, so they
carry no extra billing information; they just clutter the connection's
history list.

This script finds, for each (connection_id, meter_register) group, runs of
adjacent rows that are byte-identical except for id/effective_from/
effective_to and directly contiguous (no gap, no overlap), and collapses
each run into its earliest row by extending that row's effective_to to
the run's last effective_to and deleting the rest.

It never changes any price, date range coverage, or which row is "active"
for a given month - only removes rows that were redundant. Safe to verify
by comparing billing totals before/after for any affected month (they must
be identical, since the merged rows shared the same price for their whole
combined date range).

Usage:
    python -m scripts.dedupe_charge_line_history            # dry run, prints what would change
    python -m scripts.dedupe_charge_line_history --apply    # actually merge and commit
    python -m scripts.dedupe_charge_line_history --apply --connection-id 12
"""

from __future__ import annotations

import argparse
from datetime import timedelta
from itertools import groupby

from app.db.session import SessionLocal
from app.models.entities import ConnectionChargeLine

MERGE_FIELDS = (
    "line_kind",
    "label",
    "meter_id",
    "derived_from_line_id",
    "unit_name",
    "price_per_unit",
    "quantity_source",
    "quantity_multiplier",
    "is_active",
)


def _same_terms(a: ConnectionChargeLine, b: ConnectionChargeLine) -> bool:
    return all(getattr(a, field) == getattr(b, field) for field in MERGE_FIELDS)


def _contiguous(a: ConnectionChargeLine, b: ConnectionChargeLine) -> bool:
    if a.effective_to is None:
        return False
    return b.effective_from == a.effective_to + timedelta(days=1)


def find_merge_runs(lines: list[ConnectionChargeLine]) -> list[list[ConnectionChargeLine]]:
    ordered = sorted(lines, key=lambda row: row.effective_from)
    runs: list[list[ConnectionChargeLine]] = []
    current: list[ConnectionChargeLine] = []
    for row in ordered:
        if current and _same_terms(current[-1], row) and _contiguous(current[-1], row):
            current.append(row)
        else:
            if len(current) > 1:
                runs.append(current)
            current = [row]
    if len(current) > 1:
        runs.append(current)
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually merge and commit (default: dry run).")
    parser.add_argument("--connection-id", type=int, default=None, help="Limit to one connection.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(ConnectionChargeLine)
        if args.connection_id is not None:
            query = query.filter(ConnectionChargeLine.connection_id == args.connection_id)
        all_lines = query.all()

        keyfunc = lambda row: (row.connection_id, row.meter_register or "total")  # noqa: E731
        grouped = groupby(sorted(all_lines, key=keyfunc), key=keyfunc)

        total_deleted = 0
        for (connection_id, register), rows in grouped:
            runs = find_merge_runs(list(rows))
            for run in runs:
                keep = run[0]
                drop = run[1:]
                new_effective_to = run[-1].effective_to
                action = "WOULD MERGE" if not args.apply else "MERGING"
                print(
                    f"[{action}] connection={connection_id} register={register}: "
                    f"keep id={keep.id} ({keep.effective_from} -> {new_effective_to}), "
                    f"drop ids={[row.id for row in drop]}"
                )
                if args.apply:
                    keep.effective_to = new_effective_to
                    for row in drop:
                        db.delete(row)
                total_deleted += len(drop)

        if total_deleted == 0:
            print("No redundant rows found.")
        elif args.apply:
            db.commit()
            print(f"Merged and deleted {total_deleted} redundant row(s).")
        else:
            print(f"Dry run: {total_deleted} row(s) would be deleted. Re-run with --apply to commit.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
