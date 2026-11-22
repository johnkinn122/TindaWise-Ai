from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    categories,
    inventory,
    members,
    overview,
    products,
    purchase_orders,
    reports,
    sales,
    store,
    suppliers,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(members.router)
api_router.include_router(categories.router)
api_router.include_router(products.router)
api_router.include_router(sales.router)
api_router.include_router(overview.router)
api_router.include_router(suppliers.router)
api_router.include_router(purchase_orders.router)
api_router.include_router(reports.router)
api_router.include_router(inventory.router)
api_router.include_router(store.router)
api_router.include_router(audit.router)
