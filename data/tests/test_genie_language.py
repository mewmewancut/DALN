from unittest.mock import Mock

import pytest

from genie_language_acceptance import verify


def test_language_acceptance_compares_sql_and_cleans_only_its_created_history(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("genie_language_acceptance.cases", lambda _: [("tháng 9", "sql", False)])
    sql = Mock()
    sql.execute.return_value = [[123]]
    session = Mock()
    session.post.return_value.json.return_value = {
        "status": "COMPLETED",
        "conversation_id": 42,
        "conversation_token": "FAKE-TOKEN",
        "text": "123",
        "tables": [{"columns": [{"name": "revenue_vnd"}], "rows": [["123"]]}],
    }
    path = tmp_path / "results.json"
    result = verify(session, "http://local", sql, output=path, report=Mock())
    assert result[0]["passed"]
    session.delete.assert_called_once_with(
        "http://local/analytics/chat/conversations/42", timeout=30
    )
    assert "FAKE-TOKEN" not in path.read_text()
    session.post.return_value.json.return_value["tables"] = [
        {"columns": [{"name": "revenue_vnd"}], "rows": [["999"]]}
    ]
    with pytest.raises(ValueError):
        verify(session, "http://local", sql, report=Mock())


def test_acceptance_does_not_mistake_year_month_or_stock_quantity_for_the_metric(monkeypatch):
    monkeypatch.setattr("genie_language_acceptance.cases", lambda _: [("tháng 9", "sql", False)])
    session, sql = Mock(), Mock()
    sql.execute.return_value = [[9]]
    session.post.return_value.json.return_value = {
        "status": "COMPLETED",
        "conversation_token": "FAKE-TOKEN",
        "text": "Wrong metric",
        "tables": [
            {
                "columns": [{"name": "revenue_vnd"}, {"name": "month"}, {"name": "quantity"}],
                "rows": [["0", "9", "9"]],
            }
        ],
    }
    with pytest.raises(ValueError):
        verify(session, "http://local", sql, report=Mock())
