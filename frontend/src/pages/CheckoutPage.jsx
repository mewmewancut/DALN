import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { formatCurrency } from "../components/formatCurrency.js";
import SiteLayout from "../components/SiteLayout.jsx";

export default function CheckoutPage() {
  const navigate = useNavigate();
  const [cart, setCart] = useState(null);
  const [form, setForm] = useState({
    receiver_name: "",
    receiver_phone: "",
    shipping_address: "",
    payment_method: "COD",
  });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    client
      .get("/cart")
      .then((response) => {
        if (active) setCart(response.data);
      })
      .catch((requestError) => {
        if (active) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function changeField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const response = await client.post("/orders/checkout", form);
      navigate(`/orders/${response.data.id}`, { replace: true });
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  const hasItems = (cart?.items.length ?? 0) > 0;

  return (
    <SiteLayout wide>
      <p className="eyebrow">Hoàn tất đơn hàng</p>
      <h1>Thanh toán</h1>
      {loading && <p role="status">Đang kiểm tra giỏ hàng...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && !hasItems && (
        <div className="empty-state">
          <p>Giỏ hàng đang trống, chưa thể thanh toán.</p>
          <Link to="/cart">Quay lại giỏ hàng</Link>
        </div>
      )}
      {!loading && hasItems && (
        <div className="checkout-layout">
          <form className="form-stack" onSubmit={submit}>
            <label>
              Người nhận
              <input
                name="receiver_name"
                value={form.receiver_name}
                onChange={changeField}
                required
                maxLength="255"
              />
            </label>
            <label>
              Số điện thoại
              <input
                name="receiver_phone"
                type="tel"
                value={form.receiver_phone}
                onChange={changeField}
                required
                maxLength="20"
              />
            </label>
            <label>
              Địa chỉ giao hàng
              <textarea
                name="shipping_address"
                value={form.shipping_address}
                onChange={changeField}
                required
              />
            </label>
            <label>
              Phương thức thanh toán
              <select name="payment_method" value={form.payment_method} onChange={changeField}>
                <option value="COD">Thanh toán khi nhận hàng (COD)</option>
                <option value="MOCK_CARD">Thẻ mô phỏng</option>
              </select>
            </label>
            <button type="submit" disabled={submitting}>
              {submitting ? "Đang đặt hàng..." : "Đặt hàng"}
            </button>
          </form>
          <aside className="order-box">
            <h2>{cart.shop_name}</h2>
            {cart.items.map((item) => (
              <p key={item.id}>
                {item.product_name} ({item.color}/{item.size}) × {item.quantity}
              </p>
            ))}
            <strong>{formatCurrency(cart.total_amount)}</strong>
          </aside>
        </div>
      )}
    </SiteLayout>
  );
}
