import { useState } from "react";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { useAuth } from "../auth/AuthContext.jsx";

export default function CreateShopForm() {
  const { setShopId } = useAuth();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const response = await client.post("/shops", {
        name,
        description: description.trim() || null,
      });
      setShopId(response.data.id);
    } catch (requestError) {
      setError(errorMessage(requestError));
      setSubmitting(false);
    }
  }

  return (
    <>
      <p className="eyebrow">Chủ shop</p>
      <h1>Tạo shop của bạn</h1>
      <p>Tài khoản chưa có shop. Tạo shop để bắt đầu đăng sản phẩm và nhận đơn.</p>
      <form className="form-stack" onSubmit={handleSubmit}>
        <label>
          Tên shop
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Mô tả
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? "Đang tạo..." : "Tạo shop"}
        </button>
      </form>
    </>
  );
}
