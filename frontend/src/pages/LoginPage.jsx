import { useState } from "react";
import { Link } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { useAuth } from "../auth/AuthContext.jsx";
import SiteLayout from "../components/SiteLayout.jsx";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [unverified, setUnverified] = useState(false);
  const [pending, setPending] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setUnverified(false);
    setPending(true);

    try {
      const response = await client.post("/auth/login", { email, password });
      login(response.data);
    } catch (requestError) {
      setError(errorMessage(requestError));
      setUnverified(requestError.response?.data?.detail === "Email chưa được xác nhận");
    } finally {
      setPending(false);
    }
  }

  return (
    <SiteLayout>
      <div className="fashion-auth">
        <aside className="fashion-auth-visual fashion-auth-visual-login">
          <div className="fashion-auth-visual-copy">
            <span className="fashion-auth-eyebrow">FASHION MARKETPLACE</span>
            <h2>Phong cách của bạn. Thế giới của bạn.</h2>
            <p>Khám phá những lựa chọn thời trang dành riêng cho bạn.</p>
          </div>
          <span className="fashion-auth-visual-bottom">DISCOVER YOUR STYLE</span>
        </aside>

        <div className="fashion-auth-panel">
          <div className="fashion-auth-heading">
            <span className="fashion-auth-kicker">CHÀO MỪNG TRỞ LẠI</span>
            <h1>Đăng nhập</h1>
            <p>Đăng nhập để tiếp tục hành trình phong cách của bạn.</p>
          </div>

          <form className="form-stack fashion-auth-form" onSubmit={submit}>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="ban@email.com"
                required
                autoComplete="email"
              />
            </label>

            <label>
              Mật khẩu
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Nhập mật khẩu"
                required
                minLength={8}
                autoComplete="current-password"
              />
            </label>

            <div className="fashion-auth-forgot">
              <Link to="/forgot-password">Quên mật khẩu?</Link>
            </div>

            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}

            {unverified && (
              <Link to="/verify-email-sent" state={{ email }}>
                Gửi lại email xác minh
              </Link>
            )}

            <button className="fashion-auth-submit" type="submit" disabled={pending}>
              {pending ? "Đang đăng nhập..." : "Đăng nhập"}
              {!pending && <span aria-hidden="true"> →</span>}
            </button>
          </form>

          <p className="fashion-auth-switch">
            Chưa có tài khoản? <Link to="/register">Đăng ký ngay</Link>
          </p>

          <p className="fashion-auth-note">FASHION — Thể hiện phong cách riêng của bạn.</p>
        </div>
      </div>
    </SiteLayout>
  );
}
