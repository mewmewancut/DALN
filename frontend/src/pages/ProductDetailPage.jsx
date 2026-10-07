import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import client from "../api/client.js";
import { addGuestItem } from "../cart/guestCart.js";
import { cartErrorMessage as errorMessage } from "../cart/errorMessage.js";
import { useAuth } from "../auth/AuthContext.jsx";
import SiteLayout from "../components/SiteLayout.jsx";
import ProductImage from "../components/ProductImage.jsx";
import WishlistButton from "../components/WishlistButton.jsx";
import { formatCurrency } from "../components/formatCurrency.js";
import { formatDateTime } from "../components/orderPresentation.js";
import useWishlist from "../components/useWishlist.js";

export default function ProductDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { session } = useAuth();
  const [product, setProduct] = useState(null);
  const [reviews, setReviews] = useState({ items: [], total: 0 });
  const [reviewsLoading, setReviewsLoading] = useState(true);
  const [reviewsError, setReviewsError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cartMessage, setCartMessage] = useState("");
  const [adding, setAdding] = useState(false);
  const [color, setColor] = useState("");
  const [size, setSize] = useState("");
  const { favoriteIds, busyIds, wishlistError, wishlistLoading, toggleWishlist } = useWishlist(
    session?.role === "BUYER",
  );

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setProduct(null);
    setReviews({ items: [], total: 0 });
    setReviewsLoading(true);
    setReviewsError("");
    setColor("");
    setSize("");
    async function loadProduct() {
      try {
        const response = await client.get(`/products/${id}`);
        if (!active) return;
        setProduct(response.data);
        setLoading(false);
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
          if (active) setReviewsError(`Không tải được đánh giá: ${errorMessage(requestError)}`);
        } finally {
          if (active) setReviewsLoading(false);
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
    setAdding(true);
    setError("");
    setCartMessage("");
    try {
      if (session) {
        await client.post("/cart/items", { variant_id: selectedVariant.id, quantity: 1 });
      } else {
        addGuestItem(selectedVariant);
      }
      setCartMessage("Đã thêm sản phẩm vào giỏ hàng.");
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
              <ProductImage
                src={product.image_url}
                alt={product.name}
                className="detail-image"
                loading="eager"
              />
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
              <WishlistButton
                className="detail-wishlist"
                productName={product.name}
                isFavorite={favoriteIds.has(product.id)}
                isBusy={wishlistLoading || busyIds.has(product.id)}
                onClick={() => {
                  if (!session) navigate("/login");
                  else toggleWishlist(product.id);
                }}
              />
              {wishlistError && (
                <p className="form-error" role="alert">
                  Không cập nhật được yêu thích: {wishlistError}
                </p>
              )}
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
                <h2>Đánh giá sản phẩm</h2>
              </div>
              <strong>
                ★ {product.rating_average == null ? "—" : Number(product.rating_average).toFixed(1)}
              </strong>
            </div>
            {reviewsLoading ? (
              <p role="status">Đang tải đánh giá...</p>
            ) : reviewsError ? (
              <p role="alert">{reviewsError}</p>
            ) : reviews.items.length === 0 ? (
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
    </SiteLayout>
  );
}
