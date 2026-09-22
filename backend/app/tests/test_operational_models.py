from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Cart,
    CartItem,
    Category,
    LowStockAlert,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductVariant,
    PurchaseOrder,
    PurchaseOrderItem,
    Review,
    Shop,
    Supplier,
    User,
)


def create_catalog(
    db_session: Session,
) -> tuple[User, User, Shop, Product, ProductVariant]:
    owner = User(
        email="owner-operational@example.com",
        password_hash="hashed-password",
        full_name="Shop Owner",
        role="SHOP_OWNER",
    )
    buyer = User(
        email="buyer-operational@example.com",
        password_hash="hashed-password",
        full_name="Buyer",
        role="BUYER",
    )
    shop = Shop(owner=owner, name="Operational Shop")
    category = Category(name="Phụ kiện")
    product = Product(
        shop=shop,
        category=category,
        name="Túi đeo chéo",
        base_price=Decimal("250000"),
    )
    variant = ProductVariant(
        product=product,
        size="ONE_SIZE",
        color="Đen",
        price=Decimal("250000"),
        sku="OPERATIONAL-BAG-BLACK",
    )
    db_session.add_all([owner, buyer, shop, category, product, variant])
    db_session.flush()
    return owner, buyer, shop, product, variant


def create_order(
    db_session: Session,
) -> tuple[User, User, Shop, Product, ProductVariant, Order, OrderItem]:
    owner, buyer, shop, product, variant = create_catalog(db_session)
    order = Order(
        code="ORD-20260922-0001",
        buyer=buyer,
        shop=shop,
        shipping_address="1 Nguyễn Huệ, TP.HCM",
        receiver_name="Người mua",
        receiver_phone="0900000000",
        payment_method="COD",
        total_amount=Decimal("250000"),
    )
    item = OrderItem(
        order=order,
        variant=variant,
        product_name=product.name,
        size=variant.size,
        color=variant.color,
        unit_price=variant.price,
        quantity=1,
    )
    db_session.add_all([order, item])
    db_session.flush()
    return owner, buyer, shop, product, variant, order, item


def test_supplier_and_purchase_order_defaults(db_session: Session) -> None:
    _, _, shop, _, _ = create_catalog(db_session)
    supplier = Supplier(shop=shop, name="Nhà cung cấp A")
    purchase_order = PurchaseOrder(shop=shop, supplier=supplier)
    db_session.add(purchase_order)
    db_session.flush()

    assert supplier.is_active is True
    assert purchase_order.status == "DRAFT"
    assert purchase_order.received_at is None
    assert purchase_order.created_at.tzinfo is not None


def test_purchase_order_status_is_constrained(db_session: Session) -> None:
    _, _, shop, _, _ = create_catalog(db_session)
    supplier = Supplier(shop=shop, name="Nhà cung cấp A")
    db_session.add(PurchaseOrder(shop=shop, supplier=supplier, status="INVALID"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_purchase_order_item_quantity_must_be_positive(db_session: Session) -> None:
    _, _, shop, _, variant = create_catalog(db_session)
    supplier = Supplier(shop=shop, name="Nhà cung cấp A")
    purchase_order = PurchaseOrder(shop=shop, supplier=supplier)
    db_session.add(
        PurchaseOrderItem(
            purchase_order=purchase_order,
            variant=variant,
            quantity=0,
            unit_cost=Decimal("100000"),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_purchase_order_cannot_repeat_variant(db_session: Session) -> None:
    _, _, shop, _, variant = create_catalog(db_session)
    supplier = Supplier(shop=shop, name="Nhà cung cấp A")
    purchase_order = PurchaseOrder(shop=shop, supplier=supplier)
    db_session.add_all(
        [
            PurchaseOrderItem(
                purchase_order=purchase_order,
                variant=variant,
                quantity=5,
                unit_cost=Decimal("100000"),
            ),
            PurchaseOrderItem(
                purchase_order=purchase_order,
                variant=variant,
                quantity=10,
                unit_cost=Decimal("90000"),
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_buyer_has_only_one_cart(db_session: Session) -> None:
    _, buyer, shop, _, _ = create_catalog(db_session)
    db_session.add_all([Cart(buyer=buyer), Cart(buyer=buyer, shop=shop)])

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_empty_cart_can_have_no_shop(db_session: Session) -> None:
    _, buyer, _, _, _ = create_catalog(db_session)
    cart = Cart(buyer=buyer)
    db_session.add(cart)
    db_session.flush()

    assert cart.shop_id is None


def test_cart_item_quantity_must_be_positive(db_session: Session) -> None:
    _, buyer, shop, _, variant = create_catalog(db_session)
    cart = Cart(buyer=buyer, shop=shop)
    db_session.add(CartItem(cart=cart, variant=variant, quantity=0))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_cart_cannot_repeat_variant(db_session: Session) -> None:
    _, buyer, shop, _, variant = create_catalog(db_session)
    cart = Cart(buyer=buyer, shop=shop)
    db_session.add_all(
        [
            CartItem(cart=cart, variant=variant, quantity=1),
            CartItem(cart=cart, variant=variant, quantity=2),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_order_defaults_and_item_snapshot(db_session: Session) -> None:
    _, _, _, _, _, order, item = create_order(db_session)

    assert order.status == "PENDING"
    assert order.payment_status == "UNPAID"
    assert order.created_at.tzinfo is not None
    assert order.updated_at.tzinfo is not None
    assert item.product_name == "Túi đeo chéo"
    assert item.size == "ONE_SIZE"
    assert item.color == "Đen"
    assert item.unit_price == Decimal("250000")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "INVALID"),
        ("payment_method", "BANK_TRANSFER"),
        ("payment_status", "REFUNDED"),
    ],
)
def test_order_enums_are_constrained(
    db_session: Session,
    field: str,
    value: str,
) -> None:
    _, buyer, shop, _, _ = create_catalog(db_session)
    values = {
        "code": "ORD-20260922-0001",
        "buyer": buyer,
        "shop": shop,
        "shipping_address": "1 Nguyễn Huệ, TP.HCM",
        "receiver_name": "Người mua",
        "receiver_phone": "0900000000",
        "payment_method": "COD",
        "total_amount": Decimal("250000"),
    }
    values[field] = value
    db_session.add(Order(**values))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_order_code_is_unique(db_session: Session) -> None:
    _, buyer, shop, _, _ = create_catalog(db_session)
    common = {
        "code": "ORD-20260922-0001",
        "buyer": buyer,
        "shop": shop,
        "shipping_address": "1 Nguyễn Huệ, TP.HCM",
        "receiver_name": "Người mua",
        "receiver_phone": "0900000000",
        "payment_method": "COD",
        "total_amount": Decimal("250000"),
    }
    db_session.add_all([Order(**common), Order(**common)])

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_order_item_quantity_must_be_positive(db_session: Session) -> None:
    _, buyer, shop, product, variant = create_catalog(db_session)
    order = Order(
        code="ORD-20260922-0001",
        buyer=buyer,
        shop=shop,
        shipping_address="1 Nguyễn Huệ, TP.HCM",
        receiver_name="Người mua",
        receiver_phone="0900000000",
        payment_method="COD",
        total_amount=Decimal("250000"),
    )
    db_session.add(
        OrderItem(
            order=order,
            variant=variant,
            product_name=product.name,
            size=variant.size,
            color=variant.color,
            unit_price=variant.price,
            quantity=0,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_initial_order_history_allows_null_from_status(db_session: Session) -> None:
    _, buyer, _, _, _, order, _ = create_order(db_session)
    history = OrderStatusHistory(
        order=order,
        from_status=None,
        to_status="PENDING",
        changed_by_user=buyer,
    )
    db_session.add(history)
    db_session.flush()

    assert history.from_status is None
    assert history.to_status == "PENDING"


@pytest.mark.parametrize("rating", [0, 6])
def test_review_rating_must_be_between_one_and_five(
    db_session: Session,
    rating: int,
) -> None:
    _, buyer, _, product, _, _, item = create_order(db_session)
    db_session.add(
        Review(
            order_item=item,
            product=product,
            buyer=buyer,
            rating=rating,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_order_item_can_be_reviewed_only_once(db_session: Session) -> None:
    _, buyer, _, product, _, _, item = create_order(db_session)
    db_session.add_all(
        [
            Review(order_item=item, product=product, buyer=buyer, rating=4),
            Review(order_item=item, product=product, buyer=buyer, rating=5),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_low_stock_alert_defaults_to_unresolved(db_session: Session) -> None:
    _, _, shop, _, variant = create_catalog(db_session)
    alert = LowStockAlert(
        variant=variant,
        shop=shop,
        quantity_at_alert=3,
    )
    db_session.add(alert)
    db_session.flush()

    assert alert.is_resolved is False
    assert alert.created_at.tzinfo is not None
