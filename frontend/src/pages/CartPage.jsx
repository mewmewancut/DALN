import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { formatCurrency } from "../components/formatCurrency.js";
import SiteLayout from "../components/SiteLayout.jsx";

const EMPTY_CART = { shop_id: null, shop_name: null, items: [], total_amount: 0 };

export default function CartPage() {
  const navigate = useNavigate();
  const [cart, setCart] = useState(EMPTY_CART);
  const [quantities, setQuantities] = useState({});
  const [loading, setLoading] = useState(true);
  const [pendingItem, setPendingItem] = useState(null);
  const [error, setError] = useState("");

  const applyCart = useCallback((nextCart) => {
    setCart(nextCart);
    setQuantities(
      Object.fromEntries(nextCart.items.map((item) => [item.id, String(item.quantity)])),
    );
  }, []);

  useEffect(() => {
    let active = true;
    client
      .get("/cart")
      .then((response) => {
        if (active) applyCart(response.data);
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
  }, [applyCart]);

  async function updateItem(item) {
    const quantity = Number(quantities[item.id]);
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > item.stock_quantity) return;
    setPendingItem(item.id);
    setError("");
    try {
      const response = await client.put(`/cart/items/${item.id}`, { quantity });
      applyCart(response.data);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPendingItem(null);
    }
  }

  async function removeItem(itemId) {
    setPendingItem(itemId);
    setError("");
    try {
      const response = await client.delete(`/cart/items/${itemId}`);
      applyCart(response.data);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPendingItem(null);
    }
  }

  return (
    <SiteLayout wide>
      <p className="eyebrow">Mua sắm</p>
      <h1>Giỏ hàng</h1>
      {loading && <p role="status">Đang tải giỏ hàng...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && cart.items.length === 0 && (
        <div className="empty-state">
          <p>Giỏ hàng đang trống.</p>
          <Link to="/">Tiếp tục mua sắm</Link>
        </div>
      )}
      {!loading && cart.items.length > 0 && (
        <>
          <h2>{cart.shop_name}</h2>
          <div className="cart-list">
            {cart.items.map((item) => {
              const quantity = Number(quantities[item.id]);
              const invalidQuantity =
                !Number.isInteger(quantity) || quantity < 1 || quantity > item.stock_quantity;
              return (
                <article className="cart-item" key={item.id}>
                  {item.image_url ? (
                    <img src={item.image_url} alt={item.product_name} />
                  ) : (
                    <div className="cart-image-placeholder">Chưa có ảnh</div>
                  )}
                  <div>
                    <h3>{item.product_name}</h3>
                    <p>
                      {item.color} / {item.size}
                    </p>
                    <p>{formatCurrency(item.unit_price)}</p>
                    <p className="muted">Tồn kho: {item.stock_quantity}</p>
                  </div>
                  <div className="cart-actions">
                    <label>
                      Số lượng
                      <input
                        aria-label={`Số lượng ${item.product_name}`}
                        type="number"
                        min="1"
                        max={item.stock_quantity}
                        value={quantities[item.id] ?? item.quantity}
                        onChange={(event) =>
                          setQuantities((current) => ({
                            ...current,
                            [item.id]: event.target.value,
                          }))
                        }
                      />
                    </label>
                    {invalidQuantity && (
                      <span className="form-error">
                        Số lượng phải từ 1 đến {item.stock_quantity}.
                      </span>
                    )}
                    <button
                      type="button"
                      disabled={
                        invalidQuantity || quantity === item.quantity || pendingItem === item.id
                      }
                      onClick={() => updateItem(item)}
                    >
                      Cập nhật
                    </button>
                    <button
                      type="button"
                      disabled={pendingItem === item.id}
                      onClick={() => removeItem(item.id)}
                    >
                      Xóa
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
          <div className="cart-summary">
            <strong>Tổng cộng: {formatCurrency(cart.total_amount)}</strong>
            <button type="button" onClick={() => navigate("/checkout")}>
              Thanh toán
            </button>
          </div>
        </>
      )}
    </SiteLayout>
  );
}
