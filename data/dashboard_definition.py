"""Build a reproducible AI/BI dashboard with dated KPI/status widgets and snapshot rankings."""

from dashboard_queries import queries


def build_dashboard(catalog="fashion"):
    datasets = [
        {"name": name, "displayName": name, "queryLines": [sql]}
        for name, sql in queries(catalog).items()
    ]
    # Widget expressions accept a single aggregation or MEASURE reference.
    # Inline multi-field formulas can silently render only the numerator.
    datasets[0]["columns"] = [
        {
            "displayName": "Cancellation ratio",
            "expression": "SUM(`cancelled`)/NULLIF(SUM(`total_orders`),0)",
        },
        {
            "displayName": "Delivered AOV",
            "expression": "SUM(`revenue`)/NULLIF(SUM(`delivered_orders`),0)",
        },
    ]
    layout = []

    def widget(name, dataset, fields, spec, x, y, width, height, *, aggregate=False):
        layout.append(
            {
                "widget": {
                    "name": name,
                    "queries": [
                        {
                            "name": "main_query",
                            "query": {
                                "datasetName": dataset,
                                "fields": [
                                    {"name": field, "expression": expression}
                                    for field, expression in fields.items()
                                ],
                                "disaggregated": not aggregate,
                            },
                        }
                    ],
                    "spec": spec,
                },
                "position": {"x": x, "y": y, "width": width, "height": height},
            }
        )

    def frame(title, description):
        return {
            "showTitle": True,
            "title": title,
            "showDescription": True,
            "description": description,
        }

    money = {
        "type": "number-currency",
        "currencyCode": "VND",
        "abbreviation": "none",
        "decimalPlaces": {"type": "exact", "places": 0},
    }
    counters = [
        ("revenue", "Doanh thu đã giao", "SUM(`revenue`)", money, "Theo ngày giao tại Việt Nam"),
        (
            "orders",
            "Đơn được tạo",
            "SUM(`total_orders`)",
            {
                "type": "number-plain",
                "abbreviation": "none",
                "decimalPlaces": {"type": "exact", "places": 0},
            },
            "Mọi trạng thái; theo ngày tạo tại Việt Nam",
        ),
        (
            "cancel_rate",
            "Tỷ lệ hủy",
            "MEASURE(`Cancellation ratio`)",
            {"type": "number-percent", "decimalPlaces": {"type": "exact", "places": 2}},
            "Đơn đã hủy / đơn được tạo trong kỳ",
        ),
        (
            "aov",
            "Giá trị đơn trung bình",
            "MEASURE(`Delivered AOV`)",
            money,
            "Doanh thu / số đơn đã giao trong kỳ",
        ),
    ]
    for index, (name, title, expression, formatting, description) in enumerate(counters):
        widget(
            name,
            "daily",
            {name: expression},
            {
                "version": 2,
                "widgetType": "counter",
                "encodings": {
                    "value": {"fieldName": name, "displayName": title, "format": formatting}
                },
                "data": {"queryName": "main_query"},
                "frame": frame(title, description),
            },
            (index % 2) * 6,
            2 + (index // 2) * 3,
            6,
            3,
            aggregate=True,
        )

    widget(
        "revenue_trend",
        "daily",
        {"date": "`date`", "revenue": "SUM(`revenue`)"},
        {
            "version": 3,
            "widgetType": "line",
            "encodings": {
                "x": {"fieldName": "date", "scale": {"type": "temporal"}},
                "y": {"fieldName": "revenue", "scale": {"type": "quantitative"}, "format": money},
            },
            "frame": frame("Doanh thu theo ngày", "Chỉ đơn đã giao; ngày giao tại Việt Nam"),
        },
        0,
        8,
        8,
        5,
        aggregate=True,
    )
    widget(
        "order_statuses",
        "statuses",
        {"status": "`status`", "order_count": "SUM(`order_count`)"},
        {
            "version": 3,
            "widgetType": "bar",
            "encodings": {
                "x": {"fieldName": "status", "scale": {"type": "categorical"}},
                "y": {"fieldName": "order_count", "scale": {"type": "quantitative"}},
            },
            "frame": frame("Phân bố trạng thái đơn", "Trạng thái hiện tại của đơn tạo trong kỳ"),
        },
        8,
        8,
        4,
        5,
        aggregate=True,
    )
    for index, (name, dimension, value, title, description) in enumerate(
        [
            (
                "shops",
                "shop_label",
                "revenue",
                "Top 10 shop theo doanh thu",
                "Toàn thời gian; không chịu bộ lọc ngày",
            ),
            (
                "products",
                "product_label",
                "total_quantity_sold",
                "Top 10 sản phẩm bán chạy",
                "Toàn thời gian; cộng mọi biến thể từ đơn đã giao",
            ),
        ]
    ):
        widget(
            f"top_{name}",
            name,
            {dimension: f"`{dimension}`", value: f"`{value}`"},
            {
                "version": 3,
                "widgetType": "bar",
                "encodings": {
                    "y": {
                        "fieldName": dimension,
                        "scale": {"type": "categorical", "sort": {"by": "value"}},
                    },
                    "x": {
                        "fieldName": value,
                        "scale": {"type": "quantitative"},
                        **({"format": money} if value == "revenue" else {}),
                    },
                },
                "frame": frame(title, description),
            },
            index * 6,
            13,
            6,
            5,
        )
    stock_fields = {
        "shop_id": "Shop ID",
        "shop_name": "Shop",
        "product_name": "Sản phẩm",
        "size": "Size",
        "color": "Màu",
        "quantity": "Tồn kho",
        "threshold": "Ngưỡng",
    }
    widget(
        "low_stock",
        "stock",
        {f: f"`{f}`" for f in stock_fields},
        {
            "version": 2,
            "widgetType": "table",
            "encodings": {
                "columns": [
                    {"fieldName": f, "displayName": label} for f, label in stock_fields.items()
                ]
            },
            "frame": frame(
                "Biến thể cần nhập thêm", "Snapshot pipeline gần nhất; tồn kho thấp hơn ngưỡng"
            ),
        },
        0,
        18,
        12,
        6,
    )
    layout.insert(
        0,
        {
            "widget": {
                "name": "date_range",
                "queries": [
                    {
                        "name": name,
                        "query": {
                            "datasetName": name,
                            "fields": [{"name": "date", "expression": "`date`"}],
                            "disaggregated": False,
                        },
                    }
                    for name in ("daily", "statuses")
                ],
                "spec": {
                    "version": 2,
                    "widgetType": "filter-date-range-picker",
                    "encodings": {
                        "fields": [
                            {"fieldName": "date", "queryName": name}
                            for name in ("daily", "statuses")
                        ]
                    },
                    "frame": frame(
                        "Khoảng ngày Việt Nam",
                        "Áp dụng cho KPI, doanh thu theo ngày và trạng thái đơn",
                    ),
                },
            },
            "position": {"x": 0, "y": 0, "width": 12, "height": 2},
        },
    )
    return {
        "datasets": datasets,
        "pages": [
            {
                "name": "overview",
                "displayName": "Fashion Platform Overview",
                "pageType": "PAGE_TYPE_CANVAS",
                "layoutVersion": "GRID_V1",
                "layout": layout,
            }
        ],
    }
