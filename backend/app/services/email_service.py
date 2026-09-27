import html
import smtplib
import ssl
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol
from urllib.parse import quote

from app.config import Settings, get_settings


class EmailDeliveryError(RuntimeError):
    pass


class EmailSender(Protocol):
    def send_verification(self, recipient: str, token: str) -> None: ...

    def send_password_reset(self, recipient: str, token: str) -> None: ...

    def send_password_changed(self, recipient: str) -> None: ...


class GmailSmtpEmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _send(self, recipient: str, subject: str, text_body: str, html_body: str) -> None:
        if not self.settings.smtp_username or not self.settings.smtp_app_password:
            raise EmailDeliveryError("SMTP chưa được cấu hình")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"{self.settings.email_from_name} <{self.settings.smtp_username}>"
        message["To"] = recipient
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            ) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(self.settings.smtp_username, self.settings.smtp_app_password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError("Không gửi được email") from exc

    def send_verification(self, recipient: str, token: str) -> None:
        url = self._frontend_url("verify-email", token)
        self._send(
            recipient,
            "[Fashion E-Commerce] Xác nhận địa chỉ email",
            self._action_text(
                title="Xác nhận địa chỉ email",
                intro=(
                    "Cảm ơn bạn đã đăng ký tài khoản Fashion E-Commerce. "
                    "Hãy xác nhận địa chỉ email để hoàn tất đăng ký và bắt đầu sử dụng tài khoản."
                ),
                action_label="Xác nhận email",
                url=url,
                expiry="Liên kết này có hiệu lực trong 8 giờ và chỉ sử dụng được một lần.",
                security_note=(
                    "Nếu bạn không tạo tài khoản này, bạn có thể bỏ qua email; "
                    "chúng tôi sẽ không kích hoạt tài khoản khi chưa xác nhận."
                ),
            ),
            self._action_html(
                preheader="Hoàn tất đăng ký tài khoản Fashion E-Commerce.",
                title="Xác nhận địa chỉ email",
                intro=(
                    "Cảm ơn bạn đã đăng ký tài khoản Fashion E-Commerce. "
                    "Hãy xác nhận địa chỉ email để hoàn tất đăng ký và bắt đầu sử dụng tài khoản."
                ),
                action_label="Xác nhận email",
                url=url,
                expiry="Liên kết có hiệu lực trong 8 giờ và chỉ sử dụng được một lần.",
                security_note=(
                    "Nếu bạn không tạo tài khoản này, bạn có thể bỏ qua email. "
                    "Tài khoản sẽ không được kích hoạt khi chưa xác nhận."
                ),
            ),
        )

    def send_password_reset(self, recipient: str, token: str) -> None:
        url = self._frontend_url("reset-password", token)
        self._send(
            recipient,
            "[Fashion E-Commerce] Yêu cầu đặt lại mật khẩu",
            self._action_text(
                title="Đặt lại mật khẩu",
                intro=(
                    "Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn. "
                    "Nếu đây là yêu cầu của bạn, hãy sử dụng liên kết bên dưới."
                ),
                action_label="Đặt lại mật khẩu",
                url=url,
                expiry="Liên kết này có hiệu lực trong 30 phút và chỉ sử dụng được một lần.",
                security_note=(
                    "Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này. "
                    "Mật khẩu hiện tại của bạn sẽ không thay đổi."
                ),
            ),
            self._action_html(
                preheader="Liên kết đặt lại mật khẩu có hiệu lực trong 30 phút.",
                title="Đặt lại mật khẩu",
                intro=(
                    "Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn. "
                    "Nếu đây là yêu cầu của bạn, hãy sử dụng nút bên dưới."
                ),
                action_label="Đặt lại mật khẩu",
                url=url,
                expiry="Liên kết có hiệu lực trong 30 phút và chỉ sử dụng được một lần.",
                security_note=(
                    "Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này. "
                    "Mật khẩu hiện tại của bạn sẽ không thay đổi."
                ),
            ),
        )

    def send_password_changed(self, recipient: str) -> None:
        self._send(
            recipient,
            "[Fashion E-Commerce] Mật khẩu của bạn đã được thay đổi",
            self._notice_text(
                title="Mật khẩu đã được thay đổi",
                intro=(
                    "Mật khẩu tài khoản Fashion E-Commerce của bạn vừa được thay đổi thành công. "
                    "Tất cả phiên đăng nhập cũ đã hết hiệu lực."
                ),
                security_note=(
                    "Nếu bạn không thực hiện thay đổi này, hãy dùng chức năng Quên mật khẩu "
                    "ngay và liên hệ quản trị viên."
                ),
            ),
            self._notice_html(
                preheader="Thông báo bảo mật về thay đổi mật khẩu tài khoản.",
                title="Mật khẩu đã được thay đổi",
                intro=(
                    "Mật khẩu tài khoản Fashion E-Commerce của bạn vừa được thay đổi thành công. "
                    "Tất cả phiên đăng nhập cũ đã hết hiệu lực."
                ),
                security_note=(
                    "Nếu bạn không thực hiện thay đổi này, hãy dùng chức năng Quên mật khẩu "
                    "ngay và liên hệ quản trị viên."
                ),
            ),
        )

    def _frontend_url(self, path: str, token: str) -> str:
        base = self.settings.frontend_public_url.rstrip("/")
        return f"{base}/{path}#token={quote(token, safe='')}"

    def _action_text(
        self,
        *,
        title: str,
        intro: str,
        action_label: str,
        url: str,
        expiry: str,
        security_note: str,
    ) -> str:
        return (
            f"{self.settings.email_from_name}\n\n"
            f"{title}\n\n"
            "Xin chào,\n\n"
            f"{intro}\n\n"
            f"{action_label}:\n{url}\n\n"
            f"{expiry}\n\n"
            f"Lưu ý bảo mật: {security_note}\n\n"
            f"Trân trọng,\nĐội ngũ {self.settings.email_from_name}\n\n"
            "Đây là email tự động, vui lòng không trả lời email này."
        )

    def _notice_text(self, *, title: str, intro: str, security_note: str) -> str:
        return (
            f"{self.settings.email_from_name}\n\n"
            f"{title}\n\n"
            "Xin chào,\n\n"
            f"{intro}\n\n"
            f"Lưu ý bảo mật: {security_note}\n\n"
            f"Trân trọng,\nĐội ngũ {self.settings.email_from_name}\n\n"
            "Đây là email tự động, vui lòng không trả lời email này."
        )

    def _action_html(
        self,
        *,
        preheader: str,
        title: str,
        intro: str,
        action_label: str,
        url: str,
        expiry: str,
        security_note: str,
    ) -> str:
        safe_url = html.escape(url, quote=True)
        action_content = f"""
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:28px auto;">
            <tr>
              <td style="border-radius:8px;background:#c2410c;text-align:center;">
                <a href="{safe_url}" style="display:inline-block;padding:14px 28px;color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;">{html.escape(action_label)}</a>
              </td>
            </tr>
          </table>
          <p style="margin:0 0 8px;color:#64748b;font-size:13px;line-height:1.6;">Nếu nút không hoạt động, sao chép liên kết sau vào trình duyệt:</p>
          <p style="margin:0 0 24px;word-break:break-all;font-size:13px;line-height:1.6;"><a href="{safe_url}" style="color:#c2410c;">{safe_url}</a></p>
          <p style="margin:0;color:#475569;font-size:14px;line-height:1.6;"><strong>{html.escape(expiry)}</strong></p>
        """
        return self._email_html(preheader, title, intro, security_note, action_content)

    def _notice_html(
        self,
        *,
        preheader: str,
        title: str,
        intro: str,
        security_note: str,
    ) -> str:
        return self._email_html(preheader, title, intro, security_note, "")

    def _email_html(
        self,
        preheader: str,
        title: str,
        intro: str,
        security_note: str,
        content: str,
    ) -> str:
        brand = html.escape(self.settings.email_from_name)
        return f"""<!doctype html>
<html lang="vi">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{html.escape(title)}</title>
  </head>
  <body style="margin:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#1e293b;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{html.escape(preheader)}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 8px 28px rgba(15,23,42,.08);">
            <tr>
              <td style="padding:24px 32px;background:#0f172a;color:#ffffff;font-size:20px;font-weight:700;letter-spacing:.3px;">{brand}</td>
            </tr>
            <tr>
              <td style="padding:36px 32px;">
                <p style="margin:0 0 10px;color:#c2410c;font-size:12px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;">Bảo mật tài khoản</p>
                <h1 style="margin:0 0 20px;color:#0f172a;font-size:26px;line-height:1.3;">{html.escape(title)}</h1>
                <p style="margin:0 0 16px;font-size:16px;line-height:1.7;">Xin chào,</p>
                <p style="margin:0 0 20px;font-size:16px;line-height:1.7;">{html.escape(intro)}</p>
                {content}
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:28px;background:#fff7ed;border-left:4px solid #f97316;border-radius:6px;">
                  <tr>
                    <td style="padding:16px;color:#7c2d12;font-size:14px;line-height:1.6;"><strong>Lưu ý bảo mật:</strong> {html.escape(security_note)}</td>
                  </tr>
                </table>
                <p style="margin:28px 0 0;color:#475569;font-size:14px;line-height:1.7;">Trân trọng,<br><strong>Đội ngũ {brand}</strong></p>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;color:#64748b;font-size:12px;line-height:1.6;text-align:center;">Đây là email tự động, vui lòng không trả lời email này.</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


@lru_cache
def get_email_sender() -> GmailSmtpEmailSender:
    return GmailSmtpEmailSender(get_settings())
