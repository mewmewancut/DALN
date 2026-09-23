from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.cart import router as cart_router
from app.routers.inventory import router as inventory_router
from app.routers.orders import router as orders_router
from app.routers.orders import shop_router as shop_orders_router
from app.routers.products import category_router, product_router, variant_router
from app.routers.shops import router as shops_router

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(shop_orders_router)
app.include_router(inventory_router)
app.include_router(shops_router)
app.include_router(category_router)
app.include_router(product_router)
app.include_router(variant_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
