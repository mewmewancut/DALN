import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import SiteLayout from "../components/SiteLayout.jsx";
import { formatCurrency } from "../components/formatCurrency.js";

export default function ProductDetailPage() {
  const { id } = useParams();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [color, setColor] = useState("");
  const [size, setSize] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setProduct(null);
    setColor("");
    setSize("");
    client
      .get(`/products/${id}`)
      .then((response) => {
        if (active) setProduct(response.data);
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
  }, [id]);

  const variants = product?.variants ?? [];
  const colors = [...new Set(variants.map((variant) => variant.color))];
  const sizes = variants
    .filter((variant) => variant.color === color)
    .map((variant) => variant.size);
  const selectedVariant = variants.find(
    (variant) => variant.color === color && variant.size === size,
  );

  return (
    <SiteLayout wide>
      <p>
        <Link to="/">← Danh sách sản phẩm</Link>
      </p>
      {loading && <p role="status">Đang tải sản phẩm...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {product && (
        <>
          <div className="product-detail">
            <div>
              {product.image_url ? (
                <img className="detail-image" src={product.image_url} alt={product.name} />
              ) : (
                <div className="product-image-placeholder">Chưa có ảnh</div>
              )}
            </div>
            <div>
              <p className="eyebrow">{product.shop_name}</p>
              <h1>{product.name}</h1>
              <p>{product.description}</p>
              <p className="detail-price">
                {selectedVariant
                  ? formatCurrency(selectedVariant.price)
                  : product.price_from == null
                    ? "Chưa có giá"
                    : `Từ ${formatCurrency(product.price_from)}`}
              </p>
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
              {selectedVariant && (
                <p role="status">
                  {selectedVariant.quantity > 0
                    ? `Còn ${selectedVariant.quantity} sản phẩm`
                    : "Hết hàng"}
                </p>
              )}
              <button type="button" disabled>
                Thêm vào giỏ
              </button>
              <p className="muted">Tính năng giỏ hàng đang được hoàn thiện.</p>
            </div>
          </div>
          <section className="reviews" aria-label="Đánh giá sản phẩm">
            <h2>Đánh giá</h2>
            <p>
              ★{" "}
              {product.rating_average == null
                ? "Chưa có đánh giá"
                : Number(product.rating_average).toFixed(1)}
            </p>
            <p className="muted">Danh sách đánh giá sẽ khả dụng khi API review được triển khai.</p>
          </section>
        </>
      )}
    </SiteLayout>
  );
}
