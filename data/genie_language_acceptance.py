"""Compare natural-language web chatbot results with independent Gold SQL."""

import argparse
import json
import os
import time
from decimal import Decimal
from pathlib import Path

import requests
from databricks.sdk import WorkspaceClient

from warehouse_sql import WarehouseSQL


def cases(shop_id=None):
    scope = "" if shop_id is None else f" AND shop_id = {int(shop_id)}"
    daily = "fashion.gold.revenue_daily"
    day = "DATE(from_utc_timestamp(current_timestamp(), 'Asia/Ho_Chi_Minh'))"
    september = f"date >= make_date(year({day}),9,1) AND date < make_date(year({day}),10,1)"
    august = f"date >= make_date(year({day}),8,1) AND date < make_date(year({day}),9,1)"
    month = f"date BETWEEN date_trunc('MONTH',{day}) AND {day}"
    previous = (
        f"date >= add_months(date_trunc('MONTH',{day}),-1) AND date < date_trunc('MONTH',{day})"
    )

    def revenue(window):
        return f"SELECT COALESCE(SUM(revenue),0) FROM {daily} WHERE {window}{scope}"

    return [
        ("Doanh thu tháng 9", revenue(september), False),
        ("Còn tháng 8 thì sao?", revenue(august), True),
        ("doanh thu thang 9", revenue(september), False),
        ("Tháng này bán được bao nhiêu tiền?", revenue(month), False),
        ("Còn tháng trước?", revenue(previous), True),
        ("How much revenue did we make last month?", revenue(previous), False),
        (
            "Doanh thu tháng 9 năm 2023",
            revenue("date >= DATE '2023-09-01' AND date < DATE '2023-10-01'"),
            False,
        ),
        (
            "7 ngày gần đây kiếm được bao nhiêu?",
            revenue(f"date BETWEEN date_sub({day},6) AND {day}"),
            False,
        ),
        (
            "Có bao nhiêu đơn được tạo tháng này?",
            f"SELECT COALESCE(SUM(total_orders),0) FROM fashion.gold.orders_summary_daily "
            f"WHERE {month}{scope}",
            False,
        ),
        (
            "Hàng nào sắp hết, có bao nhiêu biến thể cần nhập thêm?",
            f"SELECT COUNT(*) FROM fashion.gold.low_stock_current WHERE TRUE{scope}",
            False,
        ),
        ("Doanh thu hôm nay là bao nhiêu?", revenue(f"date = {day}"), False),
        (
            "Có bao nhiêu đơn hàng đang giao?",
            "SELECT COALESCE(SUM(shipping),0) FROM fashion.gold.orders_summary_daily "
            f"WHERE TRUE{scope}",
            False,
        ),
    ]


def numbers(message):
    values = []
    for table in message.get("tables", []):
        metric_columns = [
            index
            for index, column in enumerate(table["columns"])
            if any(
                name in column["name"].lower()
                for name in (
                    "revenue",
                    "total_orders",
                    "order_count",
                    "low_stock_variants",
                    "shipping_orders",
                )
            )
        ]
        for row in table["rows"]:
            for index in metric_columns:
                value = row[index]
                if value is not None:
                    try:
                        values.append(Decimal(value))
                    except Exception:
                        pass
    return values


def verify(session, base, sql, *, shop_id=None, report=print, output=None):
    results, saved = [], set()
    token = None
    try:
        for question, statement, followup in cases(shop_id):
            expected = Decimal(sql.execute(statement)[0][0])
            payload = {"question": question}
            if followup and token:
                payload["conversation_token"] = token
            response = session.post(f"{base}/analytics/chat/messages", json=payload, timeout=40)
            response.raise_for_status()
            message = response.json()
            token = message["conversation_token"]
            if message.get("conversation_id"):
                saved.add(message["conversation_id"])
            deadline = time.monotonic() + 180
            while message["status"] == "PENDING":
                if time.monotonic() >= deadline:
                    raise TimeoutError("Genie language acceptance timed out")
                time.sleep(2)
                response = session.post(
                    f"{base}/analytics/chat/messages/{message['message_id']}",
                    json={"conversation_token": token},
                    timeout=40,
                )
                response.raise_for_status()
                message = response.json()
            passed = message["status"] == "COMPLETED" and expected in numbers(message)
            record = {
                "question": question,
                "passed": passed,
                "expected": str(expected),
                "text": message["text"],
                "tables": message["tables"],
            }
            results.append(record)
            report(f"{'PASS' if passed else 'FAIL'} {question}: expected {expected}", flush=True)
    finally:
        # Delete only conversations created by this acceptance run.
        for conversation_id in saved:
            response = session.delete(
                f"{base}/analytics/chat/conversations/{conversation_id}", timeout=30
            )
            response.raise_for_status()
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            Path(output).write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    if not results or not all(r["passed"] for r in results):
        raise ValueError("Natural language results differ from Gold")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password-env", default="GENIE_ACCEPTANCE_PASSWORD")
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--shop-id", type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        config = json.loads(Path("backend/.env.genie.json").read_text())
        identity = config["admin"]
        w = WorkspaceClient(
            host=config["host"],
            client_id=identity["client_id"],
            client_secret=identity["client_secret"],
            auth_type="oauth-m2m",
        )
        session = requests.Session()
        response = session.post(
            f"{args.base}/auth/login",
            json={"email": args.email, "password": os.environ[args.password_env]},
            timeout=30,
        )
        response.raise_for_status()
        session.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
        verify(
            session,
            args.base,
            WarehouseSQL(w.statement_execution, args.warehouse_id),
            shop_id=args.shop_id,
            output=args.output,
        )
    except Exception as error:
        parser.exit(1, f"Language acceptance failed ({type(error).__name__})\n")


if __name__ == "__main__":
    main()
