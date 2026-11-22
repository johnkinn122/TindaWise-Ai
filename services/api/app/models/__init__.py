"""All ORM models, imported here so Alembic autogenerate sees every table."""

from app.models.audit_event import AuditAction, AuditEvent
from app.models.category import Category
from app.models.organization import Organization
from app.models.product import Product
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderReceipt,
    PurchaseOrderStatus,
)
from app.models.refund import Refund, RefundLine, RefundReason
from app.models.sale import PaymentMethod, Sale, SaleLine
from app.models.stock_movement import MovementReason, StockMovement
from app.models.supplier import Supplier
from app.models.user import AuthSession, Membership, Role, User

__all__ = [
    "AuditAction",
    "AuditEvent",
    "AuthSession",
    "Category",
    "Membership",
    "MovementReason",
    "Organization",
    "PaymentMethod",
    "Product",
    "PurchaseOrder",
    "PurchaseOrderLine",
    "PurchaseOrderReceipt",
    "PurchaseOrderStatus",
    "Refund",
    "RefundLine",
    "RefundReason",
    "Role",
    "Sale",
    "SaleLine",
    "StockMovement",
    "Supplier",
    "User",
]
