import { useState } from "react";
import { Link, useLocation } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import SiteLayout from "../components/SiteLayout.jsx";

export default function VerificationPendingPage() {
  const location = useLocation();
  const [email, setEmail] = useState(location.state?.email ?? "");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function resend(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setPending(true);
    try {
      const response = await client.post("/auth/resend-verification", { email });
      setMessage(response.data.message);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPending(false);
    }
  }

  return (
    <SiteLayout>
      <p className="eyebrow">Xác minh tài khoản</p>
      <h1>Kiểm tra email của bạn</h1>
      {location.state?.deliveryFailed ? (
        <p role="status">
          Tài khoản đã được tạo nhưng email chưa gửi được. Hãy kiểm tra cấu hình Gmail rồi gửi lại.
        </p>
      ) : (
        <p>Chúng tôi đã gửi liên kết xác minh. Liên kết có hiệu lực trong 8 giờ.</p>
      )}
      <form className="form-stack" onSubmit={resend}>
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
          {pending ? "Đang gửi..." : "Gửi lại email xác minh"}
        </button>
      </form>
      <p>
        Đã xác minh? <Link to="/login">Đăng nhập</Link>
      </p>
    </SiteLayout>
  );
}
