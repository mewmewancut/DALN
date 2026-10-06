"""Anchor relative dates to the server's Vietnam clock without rewriting user intent."""

from datetime import datetime
from zoneinfo import ZoneInfo


def prompt(question, *, now=None):
    local = (now or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))).astimezone(
        ZoneInfo("Asia/Ho_Chi_Minh")
    )
    return (
        f"Server calendar context: today is {local.date().isoformat()} in Vietnam "
        f"(Asia/Ho_Chi_Minh). A named month without a year defaults to {local.year}, "
        "unless the conversation explicitly established a different year. State the "
        "interpreted month and year. Preserve explicit dates/years and follow-up context.\n"
        f"User question: {question}"
    )
