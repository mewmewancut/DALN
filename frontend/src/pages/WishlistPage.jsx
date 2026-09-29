import { useEffect, useState } from "react";
import { Link } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import SiteLayout from "../components/SiteLayout.jsx";
import { formatCurrency } from "../components/formatCurrency.js";

export default function WishlistPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [removingId, setRemovingId] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    client
      .get("/wishlist")
      .then((response) => {
        if (active) setItems(response.data);
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

  async function remove(productId) {
    setRemovingId(productId);
    setError("");
    try {
      await client.delete(`/wishlist/items/${productId}`);
      setItems((current) => current.filter((item) => item.product_id !== productId));
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <SiteLayout wide>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Bộ sưu tập cá nhân</p>
          <h1>Sản phẩm yêu thích</h1>
        </div>
        <Link to="/">Tiếp tục mua sắm</Link>
      </header>
      {loading && <p role="status">Đang tải danh sách yêu thích...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <h2>Chưa có sản phẩm yêu thích</h2>
          <p>Lưu lại những món bạn quan tâm để xem nhanh vào lần sau.</p>
          <Link to="/">Khám phá sản phẩm</Link>
        </div>
      )}
      {!loading && items.length > 0 && (
        <div className="wishlist-grid">
          {items.map((item) => (
            <article className="wishlist-item" key={item.id}>
              {item.image_url ? (
                <img src={item.image_url} alt={item.name} />
              ) : (
                <div className="wishlist-image-placeholder">Chưa có ảnh</div>
              )}
              <div className="wishlist-item-content">
                <p className="product-shop">{item.shop_name}</p>
                <h2>{item.name}</h2>
                <strong className="product-price">
                  {item.price_from == null
                    ? "Chưa có giá"
                    : `Từ ${formatCurrency(item.price_from)}`}
                </strong>
                <p className={`wishlist-status${!item.is_available ? " is-unavailable" : ""}`}>
                  {!item.is_available
                    ? "Sản phẩm tạm ẩn"
                    : item.has_stock
                      ? "Đang còn hàng"
                      : "Tạm hết hàng"}
                </p>
                <div className="wishlist-actions">
                  {item.is_available && (
                    <Link to={`/products/${item.product_id}`} className="primary-button">
                      Chọn phân loại
                    </Link>
                  )}
                  <button
                    type="button"
                    disabled={removingId === item.product_id}
                    onClick={() => remove(item.product_id)}
                  >
                    {removingId === item.product_id ? "Đang xóa..." : "Bỏ yêu thích"}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </SiteLayout>
  );
}
