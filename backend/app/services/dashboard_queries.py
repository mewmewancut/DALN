"""Read-only dashboard aggregates; aggregate sales before joining inventory or shops."""

from sqlalchemy import case, func, select

from app.models.catalog import Product, ProductVariant
from app.models.inventory import Inventory
from app.models.order import Order, OrderItem
from app.models.shop import Shop
from app.schemas.dashboard import (
    DashboardProduct,
    ShopPerformance,
    StatusCount,
    StockPriority,
    StockSummary,
)
from app.schemas.shop_stats import RevenueByDayItem
from app.services.shop_stats_service import _vn_date

STATUSES = ("PENDING", "CONFIRMED", "PREPARING", "SHIPPING", "DELIVERED", "CANCELLED")


def scope(query, shop_id):
    return query.where(Order.shop_id == shop_id) if shop_id is not None else query


def delivered_in(from_date, to_date):
    return (Order.status == "DELIVERED", _vn_date(Order.delivered_at).between(from_date, to_date))


def revenue_daily(db, from_date, to_date, shop_id):
    day = _vn_date(Order.delivered_at)
    query = (
        select(day, func.sum(Order.total_amount), func.count())
        .where(*delivered_in(from_date, to_date))
        .group_by(day)
        .order_by(day)
    )
    return [
        RevenueByDayItem(date=day, revenue=int(total), order_count=count)
        for day, total, count in db.execute(scope(query, shop_id))
    ]


def status_counts(db, shop_id, from_date=None, to_date=None):
    query = select(Order.status, func.count()).group_by(Order.status)
    if from_date is not None:
        query = query.where(_vn_date(Order.created_at).between(from_date, to_date))
    counts = dict(db.execute(scope(query, shop_id)).all())
    statuses = STATUSES if from_date is not None else STATUSES[:4]
    return [StatusCount(status=status, count=counts.get(status, 0)) for status in statuses]


def top_products(db, from_date, to_date, shop_id):
    quantity = func.sum(OrderItem.quantity)
    query = (
        select(
            Product.id,
            Product.name,
            Shop.name,
            quantity,
            func.sum(OrderItem.unit_price * OrderItem.quantity),
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .join(Shop, Order.shop_id == Shop.id)
        .where(*delivered_in(from_date, to_date))
        .group_by(Product.id, Product.name, Shop.name)
        .order_by(quantity.desc(), Product.id)
        .limit(5)
    )
    return [
        DashboardProduct(
            product_id=key,
            product_name=name,
            shop_name=shop,
            total_quantity_sold=int(qty),
            total_revenue=int(total),
        )
        for key, name, shop, qty, total in db.execute(scope(query, shop_id))
    ]


def stock_summary(db, from_date, to_date, shop_id):
    sellable = (
        Shop.is_active.is_(True),
        Product.is_active.is_(True),
        ProductVariant.is_active.is_(True),
    )
    base = (
        select(Inventory)
        .join(ProductVariant, Inventory.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .join(Shop, Inventory.shop_id == Shop.id)
        .where(*sellable)
    )
    if shop_id is not None:
        base = base.where(Inventory.shop_id == shop_id)
    tracked, zero, low = db.execute(
        base.with_only_columns(
            func.count(),
            func.count().filter(Inventory.quantity == 0),
            func.count().filter(
                (Inventory.quantity > 0) & (Inventory.quantity < Inventory.low_stock_threshold)
            ),
        )
    ).one()
    sales = scope(
        select(OrderItem.variant_id, func.sum(OrderItem.quantity).label("sold"))
        .join(Order, OrderItem.order_id == Order.id)
        .where(*delivered_in(from_date, to_date))
        .group_by(OrderItem.variant_id),
        shop_id,
    ).subquery()
    sold = func.coalesce(sales.c.sold, 0)
    priority = (
        base.with_only_columns(
            Inventory.variant_id,
            Product.name,
            Shop.name,
            ProductVariant.size,
            ProductVariant.color,
            Inventory.quantity,
            Inventory.low_stock_threshold,
            sold,
        )
        .outerjoin(sales, Inventory.variant_id == sales.c.variant_id)
        .where((Inventory.quantity == 0) | (Inventory.quantity < Inventory.low_stock_threshold))
        .order_by(
            case((Inventory.quantity == 0, 0), else_=1),
            sold.desc(),
            (Inventory.low_stock_threshold - Inventory.quantity).desc(),
            Inventory.variant_id,
        )
        .limit(8)
    )
    return StockSummary(
        tracked_variants=tracked,
        out_of_stock=zero,
        low_stock=low,
        priorities=[
            StockPriority(
                variant_id=key,
                product_name=name,
                shop_name=shop,
                size=size,
                color=color,
                quantity=qty,
                threshold=threshold,
                sold_quantity=int(sales_qty),
            )
            for key, name, shop, size, color, qty, threshold, sales_qty in db.execute(priority)
        ],
    )


def shop_performance(db, from_date, to_date):
    created = _vn_date(Order.created_at).between(from_date, to_date)
    delivered = (Order.status == "DELIVERED") & _vn_date(Order.delivered_at).between(
        from_date, to_date
    )
    totals = (
        select(
            Order.shop_id,
            func.sum(Order.total_amount).filter(delivered).label("revenue"),
            func.count().filter(delivered).label("delivered"),
            func.count().filter(created).label("orders"),
            func.count().filter(created & (Order.status == "CANCELLED")).label("cancelled"),
        )
        .group_by(Order.shop_id)
        .subquery()
    )
    query = (
        select(
            Shop.id,
            Shop.name,
            func.coalesce(totals.c.revenue, 0),
            func.coalesce(totals.c.delivered, 0),
            func.coalesce(totals.c.orders, 0),
            func.coalesce(totals.c.cancelled, 0),
        )
        .outerjoin(totals, Shop.id == totals.c.shop_id)
        .order_by(func.coalesce(totals.c.revenue, 0).desc(), Shop.id)
        .limit(10)
    )
    return [
        ShopPerformance(
            shop_id=key,
            shop_name=name,
            revenue=int(revenue),
            order_count=orders,
            cancelled_count=cancelled,
            cancel_rate=cancelled / orders if orders else None,
            aov=float(revenue) / delivered if delivered else None,
        )
        for key, name, revenue, delivered, orders, cancelled in db.execute(query)
    ]
