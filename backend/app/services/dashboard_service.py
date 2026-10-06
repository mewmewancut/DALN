from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.schemas.dashboard import DashboardResponse
from app.services import dashboard_queries as queries
from app.services.shop_stats_service import _validate_range, get_overview


def get_dashboard(db, from_date, to_date, *, shop_id=None):
    _validate_range(from_date, to_date)
    try:
        previous_to = from_date - timedelta(days=1)
        previous_from = from_date - timedelta(days=(to_date - from_date).days + 1)
    except OverflowError:
        raise HTTPException(
            status_code=400, detail="Khoảng ngày quá xa để so sánh kỳ trước"
        ) from None
    return DashboardResponse(
        from_date=from_date,
        to_date=to_date,
        previous_from=previous_from,
        previous_to=previous_to,
        generated_at=datetime.now(timezone.utc),
        overview=get_overview(db, from_date, to_date, shop_id=shop_id),
        previous=get_overview(db, previous_from, previous_to, shop_id=shop_id),
        revenue_daily=queries.revenue_daily(db, from_date, to_date, shop_id),
        order_statuses=queries.status_counts(db, shop_id, from_date, to_date),
        top_products=queries.top_products(db, from_date, to_date, shop_id),
        work_queue=queries.status_counts(db, shop_id),
        stock=queries.stock_summary(db, from_date, to_date, shop_id),
        shops=queries.shop_performance(db, from_date, to_date) if shop_id is None else [],
    )
