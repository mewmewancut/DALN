from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.config import get_settings
from app.database import Base
from app.services.auth_rate_limiter import get_auth_rate_limiter


class FakeEmailSender:
    def __init__(self) -> None:
        self.verifications: list[tuple[str, str]] = []
        self.password_resets: list[tuple[str, str]] = []
        self.password_changes: list[str] = []

    def send_verification(self, recipient: str, token: str) -> None:
        self.verifications.append((recipient, token))

    def send_password_reset(self, recipient: str, token: str) -> None:
        self.password_resets.append((recipient, token))

    def send_password_changed(self, recipient: str) -> None:
        self.password_changes.append(recipient)


test_engine = create_engine(get_settings().test_database_url, pool_pre_ping=True)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    test_engine.dispose()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def fake_email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture(autouse=True)
def reset_auth_rate_limiter() -> Generator[None, None, None]:
    limiter = get_auth_rate_limiter()
    limiter.reset()
    yield
    limiter.reset()
