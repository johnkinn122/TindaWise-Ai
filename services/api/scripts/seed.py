"""Seed a demo organization with SAMPLE products for local development.

Usage (from services/api):  python -m scripts.seed

Everything created here is sample data for building and testing the UI. Prices are rough,
illustrative shelf prices, not real supplier quotes. Safe to run more than once: existing
records are left alone, and missing demo accounts are added.

The demo accounts below are for local development and CI only. Their passwords are public
(they're in this file), so never create them on a server that real people use.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Category, Membership, Organization, Role, User
from app.schemas.product import ProductCreate
from app.services.products import create_product

# Fixed id so the web app's .env can point at the demo store.
DEMO_ORG_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")

# Emails use example.com, a domain reserved for documentation (RFC 2606).
DEMO_ACCOUNTS = [
    ("Nena Santos", "owner@example.com", Role.OWNER),
    ("Joy Reyes", "manager@example.com", Role.MANAGER),
    ("Carlo Dizon", "cashier@example.com", Role.CASHIER),
]
DEMO_PASSWORD = "tindawise-demo"

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


def seed_accounts(db) -> None:
    for full_name, email, role in DEMO_ACCOUNTS:
        if db.scalar(select(User).where(User.email == email)):
            continue
        user = User(email=email, full_name=full_name, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=DEMO_ORG_ID, role=role.value))
        print(f"Added demo {role.value}: {email}")
    db.commit()


def main() -> None:
    with SessionLocal() as db:
        if db.get(Organization, DEMO_ORG_ID):
            print(f"Demo organization already exists ({DEMO_ORG_ID}). Products left as they are.")
            seed_accounts(db)
            print_logins()
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
        seed_accounts(db)
        print_logins()


def print_logins() -> None:
    print(f"Demo sign-ins (password for all: {DEMO_PASSWORD}):")
    for _, email, role in DEMO_ACCOUNTS:
        print(f"  {role.value:<8} {email}")


if __name__ == "__main__":
    main()
