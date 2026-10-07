import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { tokenFromHash } from "../auth/emailToken.js";
import SiteLayout from "../components/SiteLayout.jsx";

export default function ResetPasswordPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const token = useRef(tokenFromHash(location.hash));
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (location.hash) {
      navigate({ pathname: location.pathname, search: location.search }, { replace: true });
    }
  }, [location.hash, location.pathname, location.search, navigate]);

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!token.current) {
      setError("Liên kết đặt lại mật khẩu không hợp lệ.");
      return;
    }
    if (password !== confirmation) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }
    setPending(true);
    try {
      const response = await client.post("/auth/reset-password", {
        token: token.current,
        new_password: password,
      });
      token.current = "";
      setMessage(response.data.message);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPending(false);
    }
  }

  return (
    <SiteLayout>
      <h1>Đặt mật khẩu mới</h1>
      {message ? (
        <>
          <p role="status">{message}</p>
          <Link to="/login">Đăng nhập bằng mật khẩu mới</Link>
        </>
      ) : (
        <form className="form-stack" onSubmit={submit}>
          <label>
            Mật khẩu mới
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </label>
          <label>
            Xác nhận mật khẩu mới
            <input
              type="password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </label>
          <small>Mật khẩu phải có ít nhất 8 ký tự.</small>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" disabled={pending}>
            {pending ? "Đang cập nhật..." : "Đổi mật khẩu"}
          </button>
        </form>
      )}
    </SiteLayout>
  );
}
