import { useState } from "react";
import { Link, useNavigate } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import SiteLayout from "../components/SiteLayout.jsx";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("BUYER");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event) {
    event.preventDefault();

    const normalizedFullName = fullName.trim();
    const normalizedEmail = email.trim();

    setError("");

    if (normalizedFullName.length < 2) {
      setError("Họ và tên phải có ít nhất 2 ký tự.");
      return;
    }

    setPending(true);

    try {
      await client.post("/auth/register", {
        full_name: normalizedFullName,
        email: normalizedEmail,
        password,
        role,
      });

      navigate("/verify-email-sent", {
        replace: true,
        state: { email: normalizedEmail },
      });
    } catch (requestError) {
      if (requestError.response?.status === 503) {
        navigate("/verify-email-sent", {
          replace: true,
          state: {
            email: normalizedEmail,
            deliveryFailed: true,
          },
        });
        return;
      }

      setError(errorMessage(requestError));
    } finally {
      setPending(false);
    }
  }

  return (
    <SiteLayout>
      <div className="fashion-auth fashion-auth-register">
        <aside className="fashion-auth-visual fashion-auth-visual-register">
          <div className="fashion-auth-visual-copy">
            <span className="fashion-auth-eyebrow">YOUR STYLE JOURNEY</span>
            <h2>Bắt đầu câu chuyện phong cách của bạn.</h2>
            <p>Tham gia cộng đồng và khám phá thế giới thời trang đa dạng.</p>
          </div>
          <span className="fashion-auth-visual-bottom">WELCOME TO FASHION</span>
        </aside>

        <div className="fashion-auth-panel">
          <div className="fashion-auth-heading">
            <span className="fashion-auth-kicker">THÀNH VIÊN MỚI</span>
            <h1>Tạo tài khoản</h1>
            <p>Chỉ mất một phút để bắt đầu.</p>
          </div>

          <form className="form-stack fashion-auth-form" onSubmit={submit}>
            <label>
              Họ và tên
              <input
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Nguyễn Văn A"
                required
                autoComplete="name"
              />
            </label>

            <label>
              Địa chỉ email
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
                placeholder="Ít nhất 8 ký tự"
                required
                minLength={8}
                autoComplete="new-password"
              />
            </label>

            <small className="fashion-auth-hint">
              Mật khẩu phải có ít nhất 8 ký tự.
            </small>

            <label>
              Bạn muốn tham gia với vai trò
              <select
                value={role}
                onChange={(event) => setRole(event.target.value)}
              >
                <option value="BUYER">Người mua</option>
                <option value="SHOP_OWNER">Chủ shop</option>
              </select>
            </label>

            {error && (
              <p className="form-error" role="alert">{error}</p>
            )}

            <button
              className="fashion-auth-submit"
              type="submit"
              disabled={pending}
            >
              {pending ? "Đang đăng ký..." : "Tạo tài khoản"}
              {!pending && <span aria-hidden="true"> →</span>}
            </button>
          </form>

          <p className="fashion-auth-switch">
            Đã có tài khoản? <Link to="/login">Đăng nhập</Link>
          </p>

          <p className="fashion-auth-note">
            FASHION — Thể hiện phong cách riêng của bạn.
          </p>
        </div>
      </div>
    </SiteLayout>
  );
}
