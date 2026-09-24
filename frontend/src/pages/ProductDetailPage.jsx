import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { useAuth } from "../auth/AuthContext.jsx";
import SiteLayout from "../components/SiteLayout.jsx";
import { formatCurrency } from "../components/formatCurrency.js";
import { formatDateTime } from "../components/orderPresentation.js";

export default function ProductDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { session } = useAuth();
  const [product, setProduct] = useState(null);
  const [reviews, setReviews] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cartMessage, setCartMessage] = useState("");
  const [adding, setAdding] = useState(false);
  const [differentShop, setDifferentShop] = useState(null);
  const [color, setColor] = useState("");
  const [size, setSize] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setProduct(null);
    setColor("");
    setSize("");
    async function loadProduct() {
      try {
        const response = await client.get(`/products/${id}`);
        if (!active) return;
        setProduct(response.data);
        try {
          const reviewResponse = await client.get(`/products/${id}/reviews`, {
            params: { page: 1, page_size: 20 },
          });
          if (active) {
            setReviews({
              items: Array.isArray(reviewResponse.data.items) ? reviewResponse.data.items : [],
              total: Number(reviewResponse.data.total) || 0,
            });
          }
        } catch (requestError) {
          if (active) setError(`Không tải được đánh giá: ${errorMessage(requestError)}`);
        }
      } catch (requestError) {
        if (active) setError(errorMessage(requestError));
      } finally {
        if (active) setLoading(false);
      }
    }
    loadProduct();
    return () => {
      active = false;
    };
  }, [id]);

  const variants = product?.variants ?? [];
  const colors = [...new Set(variants.map((variant) => variant.color))];
  const sizes = variants
    .filter((variant) => variant.color === color)
    .map((variant) => variant.size);
  const selectedVariant = variants.find(
    (variant) => variant.color === color && variant.size === size,
  );

  async function addSelectedVariant() {
    if (!session) {
      navigate("/login");
      return;
    }
    setAdding(true);
    setError("");
    setCartMessage("");
    try {
      await client.post("/cart/items", { variant_id: selectedVariant.id, quantity: 1 });
      setCartMessage("Đã thêm sản phẩm vào giỏ hàng.");
    } catch (requestError) {
      if (requestError.response?.status === 409 && requestError.response?.data?.current_shop) {
        setDifferentShop({
          message: errorMessage(requestError),
          currentShop: requestError.response.data.current_shop,
        });
      } else {
        setError(errorMessage(requestError));
      }
    } finally {
      setAdding(false);
    }
  }

  async function replaceCart() {
    setAdding(true);
    setError("");
    try {
      await client.delete("/cart");
      await client.post("/cart/items", { variant_id: selectedVariant.id, quantity: 1 });
      setDifferentShop(null);
      setCartMessage("Đã thay giỏ hàng và thêm sản phẩm.");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setAdding(false);
    }
  }

  return (
    <SiteLayout wide>
      <nav className="breadcrumb" aria-label="Điều hướng sản phẩm">
        <Link to="/">Sản phẩm</Link>
        <span aria-hidden="true">/</span>
        <span>{product?.name ?? "Chi tiết"}</span>
      </nav>
      {loading && <p role="status">Đang tải sản phẩm...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {product && (
        <>
          <div className="product-detail">
            <div className="detail-media">
              {product.image_url ? (
                <img className="detail-image" src={product.image_url} alt={product.name} />
              ) : (
                <div className="product-image-placeholder">Chưa có ảnh</div>
              )}
            </div>
            <div className="detail-content">
              <div className="detail-meta">
                <p className="eyebrow">{product.shop_name}</p>
                <span className="rating-pill">
                  <span aria-hidden="true">★</span>{" "}
                  {product.rating_average == null
                    ? "Chưa có đánh giá"
                    : `${Number(product.rating_average).toFixed(1)} · ${reviews.total} đánh giá`}
                </span>
              </div>
              <h1>{product.name}</h1>
              <p className="detail-description">{product.description}</p>
              <p className="detail-price">
                {selectedVariant
                  ? formatCurrency(selectedVariant.price)
                  : product.price_from == null
                    ? "Chưa có giá"
                    : `Từ ${formatCurrency(product.price_from)}`}
              </p>
              <div className="purchase-panel">
                <div className="variant-options">
                  <fieldset>
                    <legend>Màu sắc</legend>
                    {colors.length ? (
                      colors.map((option) => (
                        <button
                          type="button"
                          aria-pressed={color === option}
                          key={option}
                          onClick={() => {
                            setColor(option);
                            setSize("");
                          }}
                        >
                          {option}
                        </button>
                      ))
                    ) : (
                      <span>Chưa có lựa chọn</span>
                    )}
                  </fieldset>
                  <fieldset>
                    <legend>Kích cỡ</legend>
                    {sizes.length ? (
                      sizes.map((option) => (
                        <button
                          type="button"
                          aria-pressed={size === option}
                          key={option}
                          onClick={() => setSize(option)}
                        >
                          {option}
                        </button>
                      ))
                    ) : (
                      <span>Chọn màu trước</span>
                    )}
                  </fieldset>
                </div>
                {selectedVariant ? (
                  <p
                    className={`stock-pill${selectedVariant.quantity <= 0 ? " is-out" : ""}`}
                    role="status"
                  >
                    {selectedVariant.quantity > 0
                      ? `Còn ${selectedVariant.quantity} sản phẩm`
                      : "Hết hàng"}
                  </p>
                ) : (
                  <p className="selection-hint">Chọn màu và kích cỡ để kiểm tra tồn kho.</p>
                )}
                <button
                  type="button"
                  className="primary-button add-to-cart"
                  disabled={!selectedVariant || selectedVariant.quantity <= 0 || adding}
                  onClick={addSelectedVariant}
                >
                  {adding ? "Đang thêm..." : "Thêm vào giỏ"}
                </button>
                {cartMessage && (
                  <p className="success-message" role="status">
                    {cartMessage}
                  </p>
                )}
              </div>
            </div>
          </div>
          <section className="reviews" aria-label="Đánh giá sản phẩm">
            <div className="review-heading">
              <div>
                <p className="eyebrow">Từ người mua</p>
                <h2>Đánh giá sản phẩm</h2>
              </div>
              <strong>
                ★ {product.rating_average == null ? "—" : Number(product.rating_average).toFixed(1)}
              </strong>
            </div>
            {reviews.items.length === 0 ? (
              <p className="muted">Chưa có nhận xét nào.</p>
            ) : (
              <div className="review-list">
                {reviews.items.map((review) => (
                  <article key={review.id}>
                    <strong>{review.rating}/5 sao</strong>
                    <span>{formatDateTime(review.created_at)}</span>
                    {review.comment && <p>{review.comment}</p>}
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
      {differentShop && (
        <div className="dialog-backdrop">
          <section
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Đổi shop trong giỏ"
          >
            <h2>Giỏ hàng đang có sản phẩm khác shop</h2>
            <p>{differentShop.message}</p>
            <p>Shop hiện tại: {differentShop.currentShop.name}</p>
            <div className="dialog-actions">
              <button type="button" onClick={() => setDifferentShop(null)}>
                Giữ giỏ hiện tại
              </button>
              <button type="button" disabled={adding} onClick={replaceCart}>
                Xóa giỏ và thêm
              </button>
            </div>
          </section>
        </div>
      )}
    </SiteLayout>
  );
}
