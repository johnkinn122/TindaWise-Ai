"""Export a store's daily demand table as CSV, for services/ml.

    python -m scripts.export_demand --org <organization id> --out demand.csv
    python -m scripts.export_demand --org <id> --start 2025-01-01 --end 2025-12-31 --out demand.csv

Defaults: from the day the store's first active product was created to yesterday (store time;
today isn't over yet). Reads the database directly, so it runs where the API's DATABASE_URL
points, outside any sign-in. The output holds sales volumes per product, so treat it like other
business data: don't commit it or share it.

Then, from services/ml: python -m tindawise_ml backtest --csv demand.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Organization, Product
from app.services.demand_history import daily_demand


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.export_demand")
    parser.add_argument("--org", type=uuid.UUID, required=True, help="organization id")
    parser.add_argument("--start", type=date.fromisoformat, help="first store day (YYYY-MM-DD)")
    parser.add_argument("--end", type=date.fromisoformat, help="last store day (YYYY-MM-DD)")
    parser.add_argument("--out", required=True, help="CSV file to write")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        org = db.get(Organization, args.org)
        if org is None:
            print(f"No organization {args.org}.", file=sys.stderr)
            return 1
        today = datetime.now(ZoneInfo(org.timezone)).date()
        end = args.end or today - timedelta(days=1)
        start = args.start
        if start is None:
            first = db.scalar(
                select(func.min(Product.created_at)).where(
                    Product.organization_id == org.id, Product.is_active.is_(True)
                )
            )
            if first is None:
                print(f"{org.name} has no active products.", file=sys.stderr)
                return 1
            start = first.astimezone(ZoneInfo(org.timezone)).date()
        if end < start:
            print(f"The end ({end}) is before the start ({start}).", file=sys.stderr)
            return 1
        rows = daily_demand(db, org, start, end)

    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "sku", "units_sold", "stockout"])
        for row in rows:
            writer.writerow([row.day.isoformat(), row.sku, row.units_sold, row.stockout])

    products = len({row.sku for row in rows})
    stockouts = sum(row.stockout for row in rows)
    print(
        f"Wrote {len(rows):,} rows to {args.out}: {org.name}, {products} products, {start} to {end}"
    )
    print(
        f"Units sold: {sum(row.units_sold for row in rows):,}. Stockout product-days: {stockouts:,}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
