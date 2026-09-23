from datetime import date

from fastapi import HTTPException
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.models.catalog import Product, ProductVariant
from app.models.order import Order, OrderItem
from app.schemas.shop_stats import RevenueByDayItem, ShopStatsOverview, TopProductItem

# 📌 Định nghĩa metric dùng chung C9/Gold/Dashboard/Genie (Planning C9): doanh thu
# tính theo ngày delivered_at quy đổi sang giờ Việt Nam, không được lệch giữa các nơi.
VN_TIMEZONE = "Asia/Ho_Chi_Minh"


def _vn_date(column):
    return cast(func.timezone(VN_TIMEZONE, column), Date)


def _validate_range(from_date: date, to_date: date) -> None:
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="'from' phải nhỏ hơn hoặc bằng 'to'")


def get_overview(db: Session, shop_id: int, from_date: date, to_date: date) -> ShopStatsOverview:
    _validate_range(from_date, to_date)
    delivered_date = _vn_date(Order.delivered_at)
    revenue, delivered_count = db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0), func.count()).where(
            Order.shop_id == shop_id,
            Order.status == "DELIVERED",
            delivered_date >= from_date,
            delivered_date <= to_date,
        )
    ).one()

    created_date = _vn_date(Order.created_at)
    order_count = (
        db.scalar(
            select(func.count()).where(
                Order.shop_id == shop_id,
                created_date >= from_date,
                created_date <= to_date,
            )
        )
        or 0
    )
    cancelled_count = (
        db.scalar(
            select(func.count()).where(
                Order.shop_id == shop_id,
                Order.status == "CANCELLED",
                created_date >= from_date,
                created_date <= to_date,
            )
        )
        or 0
    )

    return ShopStatsOverview(
        revenue=int(revenue),
        order_count=order_count,
        cancelled_count=cancelled_count,
        cancel_rate=(cancelled_count / order_count) if order_count > 0 else None,
        aov=(float(revenue) / delivered_count) if delivered_count > 0 else None,
    )


def get_revenue_by_day(
    db: Session, shop_id: int, from_date: date, to_date: date
) -> list[RevenueByDayItem]:
    _validate_range(from_date, to_date)
    delivered_date = _vn_date(Order.delivered_at)
    rows = db.execute(
        select(delivered_date.label("date"), func.sum(Order.total_amount), func.count())
        .where(
            Order.shop_id == shop_id,
            Order.status == "DELIVERED",
            delivered_date >= from_date,
            delivered_date <= to_date,
        )
        .group_by(delivered_date)
        .order_by(delivered_date)
    ).all()
    return [RevenueByDayItem(date=row[0], revenue=int(row[1]), order_count=row[2]) for row in rows]


def get_top_products(db: Session, shop_id: int, limit: int) -> list[TopProductItem]:
    total_quantity = func.sum(OrderItem.quantity)
    rows = db.execute(
        select(
            Product.id,
            Product.name,
            total_quantity,
            func.sum(OrderItem.unit_price * OrderItem.quantity),
        )
        .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.shop_id == shop_id, Order.status == "DELIVERED")
        .group_by(Product.id, Product.name)
        .order_by(total_quantity.desc())
        .limit(limit)
    ).all()
    return [
        TopProductItem(
            product_id=row[0],
            product_name=row[1],
            total_quantity_sold=int(row[2]),
            total_revenue=int(row[3]),
        )
        for row in rows
    ]
