from email.message import EmailMessage

import pytest

from app.config import Settings
from app.services.email_service import EmailDeliveryError, GmailSmtpEmailSender


class FakeSmtp:
    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.message: EmailMessage | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def starttls(self, *, context) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.message = message


def capture_sender(monkeypatch) -> tuple[GmailSmtpEmailSender, list[FakeSmtp]]:
    created: list[FakeSmtp] = []

    def smtp_factory(host: str, port: int, timeout: int) -> FakeSmtp:
        smtp = FakeSmtp(host, port, timeout)
        created.append(smtp)
        return smtp

    monkeypatch.setattr("app.services.email_service.smtplib.SMTP", smtp_factory)
    settings = Settings(
        _env_file=None,
        smtp_username="project@gmail.com",
        smtp_app_password="fake-app-password",
        frontend_public_url="http://localhost:5173",
    )
    return GmailSmtpEmailSender(settings), created


def test_verification_email_is_professional_and_uses_secure_fragment_link(monkeypatch) -> None:
    sender, created = capture_sender(monkeypatch)
    sender.send_verification("buyer@example.com", "raw token")

    smtp = created[0]
    assert (smtp.host, smtp.port) == ("smtp.gmail.com", 587)
    assert smtp.started_tls is True
    assert smtp.login_args == ("project@gmail.com", "fake-app-password")
    assert smtp.message is not None
    assert str(smtp.message["Subject"]) == "[Fashion E-Commerce] Xác nhận địa chỉ email"
    plain_body = smtp.message.get_body(preferencelist=("plain",)).get_content()
    html_body = smtp.message.get_body(preferencelist=("html",)).get_content()
    verification_url = "http://localhost:5173/verify-email#token=raw%20token"
    assert verification_url in plain_body
    assert "có hiệu lực trong 8 giờ" in plain_body
    assert "Nếu bạn không tạo tài khoản" in plain_body
    assert "Xác nhận email" in html_body
    assert verification_url in html_body
    assert "Lưu ý bảo mật" in html_body
    assert "Đây là email tự động" in html_body
    assert "?token=" not in smtp.message.as_string()
    assert "fake-app-password" not in smtp.message.as_string()


def test_password_reset_email_has_expiry_cta_and_security_guidance(monkeypatch) -> None:
    sender, created = capture_sender(monkeypatch)
    sender.send_password_reset("buyer@example.com", "reset-token")

    message = created[0].message
    assert message is not None
    assert str(message["Subject"]) == "[Fashion E-Commerce] Yêu cầu đặt lại mật khẩu"
    plain_body = message.get_body(preferencelist=("plain",)).get_content()
    html_body = message.get_body(preferencelist=("html",)).get_content()
    assert "http://localhost:5173/reset-password#token=reset-token" in plain_body
    assert "có hiệu lực trong 30 phút" in plain_body
    assert "Mật khẩu hiện tại của bạn sẽ không thay đổi" in plain_body
    assert "Đặt lại mật khẩu" in html_body
    assert "sao chép liên kết sau vào trình duyệt" in html_body


def test_password_changed_email_confirms_revoked_sessions_and_next_steps(monkeypatch) -> None:
    sender, created = capture_sender(monkeypatch)
    sender.send_password_changed("buyer@example.com")

    message = created[0].message
    assert message is not None
    assert str(message["Subject"]) == "[Fashion E-Commerce] Mật khẩu của bạn đã được thay đổi"
    plain_body = message.get_body(preferencelist=("plain",)).get_content()
    html_body = message.get_body(preferencelist=("html",)).get_content()
    assert "Tất cả phiên đăng nhập cũ đã hết hiệu lực" in plain_body
    assert "Quên mật khẩu" in plain_body
    assert "Mật khẩu đã được thay đổi" in html_body
    assert "Lưu ý bảo mật" in html_body


def test_gmail_sender_requires_credentials() -> None:
    sender = GmailSmtpEmailSender(Settings(_env_file=None, smtp_username="", smtp_app_password=""))
    with pytest.raises(EmailDeliveryError):
        sender.send_password_reset("buyer@example.com", "token")
