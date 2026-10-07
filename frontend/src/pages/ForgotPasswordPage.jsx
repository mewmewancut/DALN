import { useState } from "react";
import { Link } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import SiteLayout from "../components/SiteLayout.jsx";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const response = await client.post("/auth/forgot-password", { email });
      setMessage(response.data.message);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPending(false);
    }
  }

  return (
    <SiteLayout>
      <h1>Quên mật khẩu</h1>
      <p>Nhập email để nhận liên kết đặt lại mật khẩu có hiệu lực trong 30 phút.</p>
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
        {message && <p role="status">{message}</p>}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={pending}>
          {pending ? "Đang gửi..." : "Gửi liên kết đặt lại mật khẩu"}
        </button>
      </form>
      <Link to="/login">Quay lại đăng nhập</Link>
    </SiteLayout>
  );
}
