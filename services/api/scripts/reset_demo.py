"""Reset the public demo: delete EVERY record, then seed the demo store again.

Usage (from services/api, with DATABASE_URL pointing at the demo database):

    python -m scripts.reset_demo --yes-delete-everything

Visitors on the public demo share the demo accounts and can change anything, so this puts the
demo back to its starting point. It empties every table (the schema stays), including the
activity log: TRUNCATE isn't blocked by the log's append-only trigger, which guards rows
against UPDATE and DELETE. Then it runs `scripts.seed`. The sample history store, if you want
it again, is a separate step (docs/DEPLOYMENT.md).

Refuses without the flag, and in production unless DEMO_MODE is on, so it can never wipe a
store with real data.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from scripts import seed

CONFIRM = "--yes-delete-everything"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.reset_demo")
    parser.add_argument(CONFIRM, dest="confirmed", action="store_true", help="required")
    args = parser.parse_args(argv)

    if not args.confirmed:
        print(f"This deletes every record. Run again with {CONFIRM} to go ahead.", file=sys.stderr)
        return 1
    if not get_settings().sample_data_allowed:
        print("Refusing to reset a production database (DEMO_MODE is off).", file=sys.stderr)
        return 1

    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    print(f"Emptied {len(Base.metadata.sorted_tables)} tables.")
    return seed.main()


if __name__ == "__main__":
    sys.exit(main())
