"""Natural language examples without customer data or hardcoded calendar years."""


def examples(tables, *, shop=False):
    day = "DATE(from_utc_timestamp(current_timestamp(), 'Asia/Ho_Chi_Minh'))"
    rd = tables["revenue_daily"]
    od = tables["orders_summary_daily"]
    result = [
        (
            "Tháng này bán được bao nhiêu tiền?",
            f"SELECT COALESCE(SUM(revenue),0) AS revenue_vnd FROM {rd} WHERE date >= "
            f"date_trunc('MONTH', {day}) AND date <= {day}",
        ),
        (
            "doanh thu thang 9",
            f"SELECT COALESCE(SUM(revenue),0) AS revenue_vnd, year({day}) AS year, 9 "
            f"AS month FROM {rd} WHERE date >= make_date(year({day}),9,1) AND date < "
            f"add_months(make_date(year({day}),9,1),1) GROUP BY year({day})",
        ),
        (
            "Doanh thu tháng 9 năm 2025",
            f"SELECT COALESCE(SUM(revenue),0) AS revenue_vnd FROM {rd} WHERE date >= "
            f"DATE '2025-09-01' AND date < DATE '2025-10-01'",
        ),
        (
            "Hôm qua kiếm được bao nhiêu?",
            f"SELECT COALESCE(SUM(revenue),0) AS revenue_vnd FROM {rd} WHERE date = "
            f"date_sub({day},1)",
        ),
        (
            "7 ngày gần đây thu được bao nhiêu?",
            f"SELECT COALESCE(SUM(revenue),0) AS revenue_vnd FROM {rd} WHERE date "
            f"BETWEEN date_sub({day},6) AND {day}",
        ),
        (
            "Tuần này doanh thu thế nào?",
            f"SELECT date, SUM(revenue) AS revenue_vnd FROM {rd} WHERE date BETWEEN "
            f"date_trunc('WEEK', {day}) AND {day} GROUP BY date ORDER BY date",
        ),
        (
            "Còn tháng trước thì sao?",
            f"SELECT COALESCE(SUM(revenue),0) AS revenue_vnd FROM {rd} WHERE date >= "
            f"add_months(date_trunc('MONTH', {day}),-1) AND date < "
            f"date_trunc('MONTH', {day})",
        ),
        (
            "So doanh thu tháng này với tháng trước",
            f"SELECT CASE WHEN date >= date_trunc('MONTH', {day}) THEN 'Tháng này' "
            f"ELSE 'Tháng trước' END AS period, SUM(revenue) AS revenue_vnd FROM {rd} "
            f"WHERE date >= add_months(date_trunc('MONTH', {day}),-1) AND date <= "
            f"{day} GROUP BY period",
        ),
        (
            "Ngày nào bán tốt nhất tháng này?",
            f"SELECT date, SUM(revenue) AS revenue_vnd FROM {rd} WHERE date BETWEEN "
            f"date_trunc('MONTH', {day}) AND {day} GROUP BY date ORDER BY revenue_vnd "
            f"DESC,date LIMIT 1",
        ),
        (
            "Tháng này có bao nhiêu đơn?",
            f"SELECT COALESCE(SUM(total_orders),0) AS total_orders FROM {od} WHERE "
            f"date BETWEEN date_trunc('MONTH', {day}) AND {day}",
        ),
        (
            "Tỷ lệ hủy tháng này bao nhiêu phần trăm?",
            f"SELECT SUM(cancelled)/NULLIF(SUM(total_orders),0) AS cancel_rate FROM "
            f"{od} WHERE date BETWEEN date_trunc('MONTH', {day}) AND {day}",
        ),
        (
            "Trung bình mỗi đơn giao thành công bao nhiêu tiền?",
            f"SELECT SUM(revenue)/NULLIF(SUM(delivered_orders),0) AS aov_vnd FROM {rd}",
        ),
        (
            "How much revenue did we make last month?",
            f"SELECT COALESCE(SUM(revenue),0) AS revenue_vnd FROM {rd} WHERE date >= "
            f"add_months(date_trunc('MONTH', {day}),-1) AND date < "
            f"date_trunc('MONTH', {day})",
        ),
        (
            "Mặt hàng nào bán chạy nhất?",
            f"SELECT product_name,total_quantity_sold,total_revenue FROM "
            f"{tables['top_products']} ORDER BY total_quantity_sold DESC,product_id "
            f"LIMIT 10",
        ),
        (
            "Hàng nào sắp hết để tôi nhập thêm?",
            f"SELECT product_name,size,color,quantity,threshold FROM "
            f"{tables['low_stock_current']} ORDER BY quantity,product_name LIMIT 100",
        ),
        (
            "Có bao nhiêu mẫu hàng đang thiếu tồn kho?",
            f"SELECT COUNT(*) AS low_stock_variants FROM {tables['low_stock_current']}",
        ),
        (
            "Sản phẩm được đánh giá tốt nhất?",
            f"SELECT product_name,avg_rating FROM {tables['top_products']} WHERE "
            f"avg_rating IS NOT NULL ORDER BY avg_rating DESC,product_id LIMIT 10",
        ),
    ]
    if shop:
        result.append(
            (
                "Shop tôi có bao nhiêu sản phẩm?",
                f"SELECT shop_name,product_count FROM {tables['shop_performance']}",
            )
        )
    else:
        result.append(
            (
                "Shop nào bán tốt nhất?",
                f"SELECT shop_name,revenue FROM {tables['shop_performance']} ORDER BY "
                f"revenue DESC,shop_id LIMIT 10",
            )
        )
    return result
