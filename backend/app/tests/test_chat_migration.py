import runpy
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock

from alembic import context
from alembic.config import Config

from app.config import get_settings


def test_migration_accepts_percent_encoded_email_and_password_without_interpolation(monkeypatch):
    url = "postgresql+psycopg://demo%40example.com:FAKE%25PASSWORD@db/fashion"
    monkeypatch.setattr(get_settings(), "database_url", url)
    monkeypatch.setattr(context, "config", Config(), raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: True)
    configure = Mock()
    monkeypatch.setattr(context, "configure", configure)
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", Mock())
    runpy.run_path(str(Path(__file__).resolve().parents[2] / "alembic" / "env.py"))
    assert configure.call_args.kwargs["url"] == url
