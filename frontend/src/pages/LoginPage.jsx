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
      <h1>Đăng nhập</h1>
      <form className="form-stack" onSubmit={submit}>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
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
            required
            minLength={8}
            autoComplete="current-password"
          />
        </label>
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
        <button type="submit" disabled={pending}>
          {pending ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>
      </form>
      <p>
        <Link to="/forgot-password">Quên mật khẩu?</Link>
      </p>
      <p>
        Chưa có tài khoản? <Link to="/register">Đăng ký</Link>
      </p>
    </SiteLayout>
  );
}
