from fastapi import APIRouter

from app.api.v1 import (
    auth,
    categories,
    members,
    overview,
    products,
    purchase_orders,
    sales,
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
