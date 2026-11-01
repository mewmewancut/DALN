from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import Product
from app.models.order import Order, OrderItem
from app.models.review import Review
from app.models.shop import Shop
from app.models.user import User
from app.schemas.review import (
    ReviewCreate,
    ReviewPage,
    ReviewResponse,
    ShopReviewPage,
    ShopReviewReply,
    ShopReviewResponse,
)


def _response(review: Review) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        order_item_id=review.order_item_id,
        product_id=review.product_id,
        buyer_id=review.buyer_id,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
        shop_reply=review.shop_reply,
        shop_replied_at=review.shop_replied_at,
    )


def create_review(db: Session, buyer: User, request: ReviewCreate) -> ReviewResponse:
    order_item = db.get(OrderItem, request.order_item_id)
    if order_item is None:
        raise HTTPException(status_code=404, detail="Order item không tồn tại")
    order = db.get(Order, order_item.order_id)
    if order is None or order.buyer_id != buyer.id:
        raise HTTPException(status_code=403, detail="Order item không thuộc đơn hàng của bạn")
    if order.status != "DELIVERED":
        raise HTTPException(status_code=400, detail="Chỉ đánh giá sau khi nhận hàng")
    existing = db.scalar(select(Review.id).where(Review.order_item_id == order_item.id))
    if existing is not None:
        raise HTTPException(status_code=400, detail="Order item này đã được đánh giá")

    review = Review(
        order_item_id=order_item.id,
        product_id=order_item.variant.product_id,
        buyer_id=buyer.id,
        rating=request.rating,
        comment=request.comment,
    )
    try:
        db.add(review)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Order item này đã được đánh giá") from None
    except Exception:
        db.rollback()
        raise
    db.refresh(review)
    return _response(review)


def list_product_reviews(db: Session, product_id: int, *, page: int, page_size: int) -> ReviewPage:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")

    filters = [Review.product_id == product_id]
    total = db.scalar(select(func.count()).select_from(Review).where(*filters)) or 0
    rating_average = db.scalar(select(func.avg(Review.rating)).where(*filters))
    reviews = list(
        db.scalars(
            select(Review)
            .where(*filters)
            .order_by(Review.created_at.desc(), Review.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return ReviewPage(
        items=[_response(review) for review in reviews],
        total=total,
        page=page,
        page_size=page_size,
        rating_average=float(rating_average) if rating_average is not None else None,
    )


def _shop_review_response(review: Review, product_name: str) -> ShopReviewResponse:
    return ShopReviewResponse(
        **_response(review).model_dump(),
        product_name=product_name,
        shop_review_read_at=review.shop_review_read_at,
    )


def _get_shop_review(db: Session, shop: Shop, review_id: int) -> tuple[Review, Product]:
    result = db.execute(
        select(Review, Product)
        .join(Product, Review.product_id == Product.id)
        .where(
            Review.id == review_id,
            Product.shop_id == shop.id,
        )
    ).first()

    if result is None:
        raise HTTPException(status_code=404, detail="Đánh giá không tồn tại trong shop")

    return result


def list_shop_reviews(
    db: Session,
    shop: Shop,
    *,
    page: int,
    page_size: int,
) -> ShopReviewPage:
    filters = [Product.shop_id == shop.id]

    total = (
        db.scalar(
            select(func.count())
            .select_from(Review)
            .join(Product, Review.product_id == Product.id)
            .where(*filters)
        )
        or 0
    )

    unread_count = (
        db.scalar(
            select(func.count())
            .select_from(Review)
            .join(Product, Review.product_id == Product.id)
            .where(*filters, Review.shop_review_read_at.is_(None))
        )
        or 0
    )

    results = db.execute(
        select(Review, Product.name)
        .join(Product, Review.product_id == Product.id)
        .where(*filters)
        .order_by(Review.created_at.desc(), Review.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ShopReviewPage(
        items=[_shop_review_response(review, product_name) for review, product_name in results],
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
    )


def reply_to_shop_review(
    db: Session,
    shop: Shop,
    review_id: int,
    request: ShopReviewReply,
) -> ShopReviewResponse:
    review, product = _get_shop_review(db, shop, review_id)

    reply = request.reply.strip()
    if not reply:
        raise HTTPException(status_code=422, detail="Phản hồi không được để trống")

    review.shop_reply = reply
    review.shop_replied_at = datetime.now(timezone.utc)
    review.shop_review_read_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(review)

    return _shop_review_response(review, product.name)


def mark_shop_review_read(
    db: Session,
    shop: Shop,
    review_id: int,
) -> ShopReviewResponse:
    review, product = _get_shop_review(db, shop, review_id)

    if review.shop_review_read_at is None:
        review.shop_review_read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(review)

    return _shop_review_response(review, product.name)
