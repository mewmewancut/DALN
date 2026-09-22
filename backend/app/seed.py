"""Create deterministic demo data without duplicating rows on repeated runs."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from random import Random

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Category,
    Inventory,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductVariant,
    Shop,
    Supplier,
    User,
)

CATEGORY_NAMES = ("Áo", "Quần", "Váy", "Giày", "Túi xách", "Phụ kiện")
CATEGORY_BASE_PRICES = {
    "Áo": 199_000,
    "Quần": 299_000,
    "Váy": 399_000,
    "Giày": 499_000,
    "Túi xách": 599_000,
    "Phụ kiện": 149_000,
}
CATEGORY_SIZES = {
    "Áo": ("S", "M", "L"),
    "Quần": ("S", "M", "L"),
    "Váy": ("S", "M", "L"),
    "Giày": ("38", "39", "40"),
    "Túi xách": ("MINI", "MEDIUM", "LARGE"),
    "Phụ kiện": ("SMALL", "MEDIUM", "LARGE"),
}
VARIANT_COLORS = ("Đen", "Trắng", "Xanh")
ORDER_STATUSES = (
    "PENDING",
    "CONFIRMED",
    "PREPARING",
    "SHIPPING",
    "DELIVERED",
    "DELIVERED",
    "DELIVERED",
    "SHIPPING",
    "CANCELLED",
)
ORDER_PATHS = {
    "PENDING": (),
    "CONFIRMED": ("CONFIRMED",),
    "PREPARING": ("CONFIRMED", "PREPARING"),
    "SHIPPING": ("CONFIRMED", "PREPARING", "SHIPPING"),
    "DELIVERED": ("CONFIRMED", "PREPARING", "SHIPPING", "DELIVERED"),
    "CANCELLED": ("CANCELLED",),
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def get_or_create_user(
    session: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role: str,
    created: dict[str, int],
) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is not None:
        return user

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
    )
    session.add(user)
    session.flush()
    created["users"] += 1
    return user


def get_or_create_category(
    session: Session,
    name: str,
    created: dict[str, int],
) -> Category:
    category = session.scalar(select(Category).where(Category.name == name))
    if category is not None:
        return category

    category = Category(name=name)
    session.add(category)
    session.flush()
    created["categories"] += 1
    return category


def get_or_create_shop(
    session: Session,
    *,
    owner: User,
    name: str,
    description: str,
    created: dict[str, int],
) -> Shop:
    shop = session.scalar(select(Shop).where(Shop.owner_id == owner.id))
    if shop is not None:
        return shop

    shop = Shop(owner=owner, name=name, description=description)
    session.add(shop)
    session.flush()
    created["shops"] += 1
    return shop


def get_or_create_product(
    session: Session,
    *,
    shop: Shop,
    category: Category,
    name: str,
    image_url: str,
    base_price: Decimal,
    created: dict[str, int],
) -> Product:
    product = session.scalar(
        select(Product).where(Product.shop_id == shop.id, Product.name == name)
    )
    if product is not None:
        return product

    product = Product(
        shop=shop,
        category=category,
        name=name,
        description=f"Sản phẩm mẫu {name} dùng cho môi trường demo.",
        image_url=image_url,
        base_price=base_price,
    )
    session.add(product)
    session.flush()
    created["products"] += 1
    return product


def get_or_create_variant(
    session: Session,
    *,
    product: Product,
    size: str,
    color: str,
    price: Decimal,
    sku: str,
    created: dict[str, int],
) -> ProductVariant:
    variant = session.scalar(
        select(ProductVariant).where(
            ProductVariant.product_id == product.id,
            ProductVariant.size == size,
            ProductVariant.color == color,
        )
    )
    if variant is not None:
        variant.sku = sku
        return variant

    sku_owner = session.scalar(select(ProductVariant).where(ProductVariant.sku == sku))
    if sku_owner is not None:
        raise ValueError(f"SKU {sku} đã thuộc về một biến thể khác")

    variant = ProductVariant(
        product=product,
        size=size,
        color=color,
        price=price,
        sku=sku,
    )
    session.add(variant)
    session.flush()
    created["variants"] += 1
    return variant


def get_or_create_inventory(
    session: Session,
    *,
    variant: ProductVariant,
    shop: Shop,
    quantity: int,
    created: dict[str, int],
) -> Inventory:
    inventory = session.scalar(select(Inventory).where(Inventory.variant_id == variant.id))
    if inventory is not None:
        return inventory

    inventory = Inventory(variant=variant, shop=shop, quantity=quantity)
    session.add(inventory)
    session.flush()
    created["inventory"] += 1
    return inventory


def get_or_create_supplier(
    session: Session,
    *,
    shop: Shop,
    name: str,
    phone: str,
    address: str,
    created: dict[str, int],
) -> Supplier:
    supplier = session.scalar(
        select(Supplier).where(Supplier.shop_id == shop.id, Supplier.name == name)
    )
    if supplier is not None:
        return supplier

    supplier = Supplier(
        shop=shop,
        name=name,
        phone=phone,
        address=address,
    )
    session.add(supplier)
    session.flush()
    created["suppliers"] += 1
    return supplier


def create_catalog(
    session: Session,
    *,
    shops: Sequence[Shop],
    categories: Sequence[Category],
    created: dict[str, int],
) -> dict[int, list[ProductVariant]]:
    random = Random(20260922)
    variants_by_shop: dict[int, list[ProductVariant]] = {}

    for shop_number, shop in enumerate(shops, start=1):
        shop_variants: list[ProductVariant] = []
        for product_number in range(1, 16):
            category = categories[(product_number - 1) % len(categories)]
            base_price = Decimal(CATEGORY_BASE_PRICES[category.name] + product_number * 10_000)
            product = get_or_create_product(
                session,
                shop=shop,
                category=category,
                name=f"{category.name} mẫu {product_number:02d} - Shop {shop_number}",
                image_url=(
                    f"https://placehold.co/600x800?text=shop-{shop_number}-product-{product_number}"
                ),
                base_price=base_price,
                created=created,
            )

            sizes = CATEGORY_SIZES[category.name]
            for variant_number, (size, color) in enumerate(
                zip(sizes, VARIANT_COLORS, strict=True),
                start=1,
            ):
                sku = f"P{product.id}-{size}-{color}"
                variant = get_or_create_variant(
                    session,
                    product=product,
                    size=size,
                    color=color,
                    price=base_price + Decimal((variant_number - 1) * 20_000),
                    sku=sku,
                    created=created,
                )
                shop_variants.append(variant)

                sequence = (shop_number - 1) * 45 + (product_number - 1) * 3
                sequence += variant_number
                if sequence % 17 == 0:
                    quantity = 0
                elif sequence % 11 == 0:
                    quantity = random.randint(1, 4)
                else:
                    quantity = random.randint(6, 50)
                get_or_create_inventory(
                    session,
                    variant=variant,
                    shop=shop,
                    quantity=quantity,
                    created=created,
                )

        variants_by_shop[shop.id] = shop_variants

    return variants_by_shop


def create_order_history(
    session: Session,
    *,
    order: Order,
    buyer: User,
    owner: User,
    created_at: datetime,
) -> None:
    session.add(
        OrderStatusHistory(
            order=order,
            from_status=None,
            to_status="PENDING",
            changed_by_user=buyer,
            created_at=created_at,
        )
    )
    previous_status = "PENDING"
    for step, next_status in enumerate(ORDER_PATHS[order.status], start=1):
        session.add(
            OrderStatusHistory(
                order=order,
                from_status=previous_status,
                to_status=next_status,
                changed_by_user=owner,
                created_at=created_at + timedelta(hours=step),
            )
        )
        previous_status = next_status


def create_orders(
    session: Session,
    *,
    buyers: Sequence[User],
    shops: Sequence[Shop],
    owners: Sequence[User],
    variants_by_shop: dict[int, list[ProductVariant]],
    reference_time: datetime,
    created: dict[str, int],
) -> None:
    order_number = 0
    for shop_index, (shop, owner) in enumerate(zip(shops, owners, strict=True)):
        shop_variants = variants_by_shop[shop.id]
        for shop_order_number in range(12):
            order_number += 1
            created_at = reference_time - timedelta(
                days=(order_number - 1) % 30,
                hours=shop_order_number % 6,
            )
            receiver_phone = f"090{order_number:07d}"
            shipping_address = f"{order_number} Nguyễn Huệ, TP.HCM"
            code = f"ORD-{created_at:%Y%m%d}-{order_number:04d}"
            existing_order = session.scalar(
                select(Order.id).where(
                    Order.shop_id == shop.id,
                    Order.receiver_phone == receiver_phone,
                    Order.shipping_address == shipping_address,
                )
            )
            if existing_order is not None:
                continue

            buyer = buyers[(order_number + shop_index) % len(buyers)]
            status = ORDER_STATUSES[(order_number - 1) % len(ORDER_STATUSES)]
            first_variant = shop_variants[(order_number * 3) % len(shop_variants)]
            second_variant = shop_variants[(order_number * 3 + 7) % len(shop_variants)]
            selected_variants = (first_variant, second_variant)
            quantities = (1, 2 if order_number % 4 == 0 else 1)
            total_amount = sum(
                (
                    variant.price * quantity
                    for variant, quantity in zip(
                        selected_variants,
                        quantities,
                        strict=True,
                    )
                ),
                Decimal(0),
            )
            finished_at = created_at + timedelta(hours=4)
            payment_method = "MOCK_CARD" if order_number % 3 == 0 else "COD"
            order = Order(
                code=code,
                buyer=buyer,
                shop=shop,
                status=status,
                shipping_address=shipping_address,
                receiver_name=buyer.full_name,
                receiver_phone=receiver_phone,
                payment_method=payment_method,
                payment_status=(
                    "PAID" if payment_method == "MOCK_CARD" or status == "DELIVERED" else "UNPAID"
                ),
                total_amount=total_amount,
                delivered_at=finished_at if status == "DELIVERED" else None,
                cancelled_at=finished_at if status == "CANCELLED" else None,
                cancel_reason="Người mua đổi ý" if status == "CANCELLED" else None,
                created_at=created_at,
                updated_at=finished_at,
            )
            session.add(order)
            for variant, quantity in zip(
                selected_variants,
                quantities,
                strict=True,
            ):
                session.add(
                    OrderItem(
                        order=order,
                        variant=variant,
                        product_name=variant.product.name,
                        size=variant.size,
                        color=variant.color,
                        unit_price=variant.price,
                        quantity=quantity,
                        created_at=created_at,
                    )
                )
            create_order_history(
                session,
                order=order,
                buyer=buyer,
                owner=owner,
                created_at=created_at,
            )
            created["orders"] += 1

    session.flush()


def seed_database(
    session: Session,
    *,
    reference_time: datetime | None = None,
) -> dict[str, int]:
    if reference_time is None:
        reference_time = datetime.now(timezone.utc).replace(
            hour=12,
            minute=0,
            second=0,
            microsecond=0,
        )
    elif reference_time.tzinfo is None:
        raise ValueError("reference_time phải có timezone")
    else:
        reference_time = reference_time.astimezone(timezone.utc)

    created = {
        "users": 0,
        "shops": 0,
        "categories": 0,
        "products": 0,
        "variants": 0,
        "inventory": 0,
        "suppliers": 0,
        "orders": 0,
    }

    get_or_create_user(
        session,
        email="admin@shop.vn",
        password="Admin@123",
        full_name="Quản trị viên",
        role="ADMIN",
        created=created,
    )
    owners = [
        get_or_create_user(
            session,
            email=f"shop{number}@shop.vn",
            password="Shop@123",
            full_name=f"Chủ shop {number}",
            role="SHOP_OWNER",
            created=created,
        )
        for number in range(1, 4)
    ]
    buyers = [
        get_or_create_user(
            session,
            email=f"buyer{number}@shop.vn",
            password="Buyer@123",
            full_name=f"Người mua {number}",
            role="BUYER",
            created=created,
        )
        for number in range(1, 6)
    ]
    categories = [get_or_create_category(session, name, created) for name in CATEGORY_NAMES]
    shops = [
        get_or_create_shop(
            session,
            owner=owner,
            name=f"Thời trang Shop {number}",
            description=f"Cửa hàng thời trang mẫu số {number}.",
            created=created,
        )
        for number, owner in enumerate(owners, start=1)
    ]
    variants_by_shop = create_catalog(
        session,
        shops=shops,
        categories=categories,
        created=created,
    )
    for shop_number, shop in enumerate(shops, start=1):
        for supplier_number in range(1, 3):
            get_or_create_supplier(
                session,
                shop=shop,
                name=f"Nhà cung cấp {shop_number}-{supplier_number}",
                phone=f"028{shop_number}{supplier_number}000000",
                address=f"Quận {shop_number + supplier_number}, TP.HCM",
                created=created,
            )
    create_orders(
        session,
        buyers=buyers,
        shops=shops,
        owners=owners,
        variants_by_shop=variants_by_shop,
        reference_time=reference_time,
        created=created,
    )
    return created


def main() -> None:
    with SessionLocal() as session:
        try:
            created = seed_database(session)
            session.commit()
        except Exception:
            session.rollback()
            raise

    total_created = sum(created.values())
    detail = ", ".join(f"{name}={count}" for name, count in created.items())
    print(f"Seed hoàn tất: created={total_created} ({detail})")


if __name__ == "__main__":
    main()
