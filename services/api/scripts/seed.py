"""Seed a demo organization with SAMPLE products for local development.

Usage (from services/api):  python -m scripts.seed

Everything created here is sample data for building and testing the UI. Prices are rough,
illustrative shelf prices, not real supplier quotes. Safe to run more than once: if the demo
organization already exists, nothing is changed.
"""

import uuid
from decimal import Decimal

from app.db.session import SessionLocal
from app.models import Category, Organization
from app.schemas.product import ProductCreate
from app.services.products import create_product

# Fixed id so the web app's .env can point at the demo store.
DEMO_ORG_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")

CATEGORIES = ["Beverages", "Canned goods", "Condiments", "Dairy", "Household", "Noodles", "Snacks"]

# Barcodes use the GS1 "20" prefix, reserved for in-store/internal codes, so they can never
# collide with a real product's barcode.
# name, sku, barcode, category, unit, price, cost, reorder_level, initial_stock
PRODUCTS = [
    ("Lucky Me Pancit Canton (Original)", "NDL-001", "2000000000015", "Noodles", "pcs", "16.00", "13.50", 24, 6),
    ("Lucky Me Instant Mami Beef", "NDL-002", "2000000000022", "Noodles", "pcs", "11.00", "9.25", 24, 40),
    ("Nissin Cup Noodles Seafood", "NDL-003", "2000000000039", "Noodles", "pcs", "28.00", "23.00", 12, 18),
    ("Coca-Cola 1.5L", "BEV-001", "2000000000046", "Beverages", "btl", "80.00", "68.00", 12, 0),
    ("Royal Tru-Orange 1L", "BEV-002", "2000000000053", "Beverages", "btl", "55.00", "46.00", 12, 20),
    ("Nescafé Classic 25g", "BEV-003", "2000000000060", "Beverages", "pcs", "32.00", "27.00", 10, 15),
    ("Bear Brand Swak 33g", "DRY-001", "2000000000077", "Dairy", "pcs", "17.00", "15.25", 24, 4),
    ("Alaska Evaporada 370ml", "DRY-002", "2000000000084", "Dairy", "can", "38.00", "32.00", 12, 30),
    ("Datu Puti Vinegar 1L", "CND-001", "2000000000091", "Condiments", "btl", "48.00", "40.00", 6, 38),
    ("Silver Swan Soy Sauce 1L", "CND-002", "2000000000107", "Condiments", "btl", "52.00", "44.00", 6, 22),
    ("UFC Banana Catsup 320g", "CND-003", "2000000000114", "Condiments", "pcs", "36.00", "30.00", 6, 5),
    ("555 Sardines Tomato Sauce 155g", "CAN-001", "2000000000121", "Canned goods", "can", "24.00", "20.00", 24, 60),
    ("Argentina Corned Beef 150g", "CAN-002", "2000000000138", "Canned goods", "can", "45.00", "38.50", 12, 14),
    ("Piattos Cheese 40g", "SNK-001", "2000000000145", "Snacks", "pcs", "20.00", "16.50", 20, 35),
    ("SkyFlakes Crackers 10-pack", "SNK-002", "2000000000152", "Snacks", "pack", "62.00", "53.00", 6, 9),
    ("Safeguard Soap 85g", "HSE-001", "2000000000169", "Household", "pcs", "45.00", "38.00", 6, 0),
    ("Surf Powder Detergent 65g", "HSE-002", None, "Household", "pcs", "9.00", "7.50", 30, 120),
]


def main() -> None:
    with SessionLocal() as db:
        if db.get(Organization, DEMO_ORG_ID):
            print(f"Demo organization already exists ({DEMO_ORG_ID}). Nothing to do.")
            return

        org = Organization(id=DEMO_ORG_ID, name="Aling Nena's Mini-Mart (sample)", currency="PHP")
        db.add(org)
        db.flush()  # insert the organization first: categories reference it
        categories = {name: Category(organization_id=org.id, name=name) for name in CATEGORIES}
        db.add_all(categories.values())
        db.commit()

        for name, sku, barcode, category, unit, price, cost, reorder, stock in PRODUCTS:
            create_product(
                db,
                org,
                ProductCreate(
                    name=name,
                    sku=sku,
                    barcode=barcode,
                    category_id=categories[category].id,
                    unit=unit,
                    price=Decimal(price),
                    cost=Decimal(cost),
                    reorder_level=reorder,
                    initial_stock=stock,
                ),
            )
        print(f"Seeded demo organization {DEMO_ORG_ID} with {len(PRODUCTS)} sample products.")


if __name__ == "__main__":
    main()
