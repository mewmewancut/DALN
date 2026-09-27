import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { tokenFromHash } from "../auth/emailToken.js";
import SiteLayout from "../components/SiteLayout.jsx";

export default function VerifyEmailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const token = useRef(tokenFromHash(location.hash));
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (location.hash) {
      navigate({ pathname: location.pathname, search: location.search }, { replace: true });
    }
  }, [location.hash, location.pathname, location.search, navigate]);

  async function verify() {
    if (!token.current) {
      setError("Liên kết xác minh không hợp lệ.");
      return;
    }
    setPending(true);
    setError("");
    try {
      const response = await client.post("/auth/verify-email", { token: token.current });
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
      <p className="eyebrow">Xác minh tài khoản</p>
      <h1>Xác nhận email</h1>
      {message ? (
        <>
          <p role="status">{message}</p>
          <Link to="/login">Đi tới đăng nhập</Link>
        </>
      ) : (
        <>
          <p>Nhấn nút bên dưới để hoàn tất xác minh tài khoản.</p>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="button" onClick={verify} disabled={pending}>
            {pending ? "Đang xác minh..." : "Xác nhận email"}
          </button>
        </>
      )}
    </SiteLayout>
  );
}
