import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { formatCurrency } from "../components/formatCurrency.js";
import SiteLayout from "../components/SiteLayout.jsx";

export default function CheckoutPage() {
  const navigate = useNavigate();
  const [cart, setCart] = useState(null);
  const [addresses, setAddresses] = useState([]);
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const [form, setForm] = useState({
    receiver_name: "",
    receiver_phone: "",
    shipping_address: "",
    payment_method: "COD",
  });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      client.get("/cart"),
      client.get("/users/me/profile"),
      client.get("/users/me/addresses"),
    ])
      .then(([cartResponse, profileResponse, addressResponse]) => {
        if (!active) return;
        setCart(cartResponse.data);
        setAddresses(addressResponse.data);
        const preferred =
          addressResponse.data.find((address) => address.is_default) ?? addressResponse.data[0];
        if (preferred) {
          setSelectedAddressId(String(preferred.id));
          setForm((current) => ({
            ...current,
            receiver_name: preferred.receiver_name,
            receiver_phone: preferred.receiver_phone,
            shipping_address: `${preferred.address_detail}, ${preferred.commune_name}, ${preferred.province_name}`,
          }));
        } else {
          setForm((current) => ({
            ...current,
            receiver_name: profileResponse.data.full_name ?? "",
            receiver_phone: profileResponse.data.phone ?? "",
          }));
        }
      })
      .catch((requestError) => {
        if (active) setLoadError(errorMessage(requestError));
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

  function chooseAddress(event) {
    const nextId = event.target.value;
    setSelectedAddressId(nextId);
    const address = addresses.find((item) => String(item.id) === nextId);
    if (!address) return;
    setForm((current) => ({
      ...current,
      receiver_name: address.receiver_name,
      receiver_phone: address.receiver_phone,
      shipping_address: `${address.address_detail}, ${address.commune_name}, ${address.province_name}`,
    }));
  }

  async function submit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      const response = await client.post("/orders/checkout", form);
      navigate(`/orders/${response.data.id}`, { replace: true });
    } catch (requestError) {
      setSubmitError(errorMessage(requestError));
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
      {loadError && (
        <p className="form-error" role="alert">
          {loadError}
        </p>
      )}
      {!loading && !loadError && !hasItems && (
        <div className="empty-state">
          <p>Giỏ hàng đang trống, chưa thể thanh toán.</p>
          <Link to="/cart">Quay lại giỏ hàng</Link>
        </div>
      )}
      {!loading && !loadError && hasItems && (
        <div className="checkout-layout">
          <form className="form-stack" onSubmit={submit}>
            {addresses.length > 0 && (
              <label>
                Địa chỉ đã lưu
                <select value={selectedAddressId} onChange={chooseAddress}>
                  {addresses.map((address) => (
                    <option value={address.id} key={address.id}>
                      {address.label}
                      {address.is_default ? " (Mặc định)" : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
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
            {submitError && (
              <p className="form-error" role="alert">
                {submitError}
              </p>
            )}
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
