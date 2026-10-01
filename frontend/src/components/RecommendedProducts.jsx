import { useEffect, useState } from "react";
import { Link } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import ProductCard from "./ProductCard.jsx";

export default function RecommendedProducts({
  favoriteIds,
  busyIds,
  wishlistLoading,
  wishlistError,
  onToggleFavorite,
}) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    client
      .get("/users/me/recommendations", { params: { limit: 8 } })
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

  return (
    <section className="recommendations" aria-label="Dành cho bạn">
      <div className="recommendations-heading">
        <div>
          <p className="eyebrow">Khám phá thêm</p>
          <h2>Dành cho bạn</h2>
          <p className="muted">Ưu tiên sở thích đã lưu, sau đó là sản phẩm mới còn hàng.</p>
        </div>
        <Link to="/account/preferences" className="text-button">
          Chỉnh sở thích
        </Link>
      </div>
      {loading && <p role="status">Đang tải gợi ý...</p>}
      {error && (
        <p className="form-error" role="alert">
          Không tải được gợi ý: {error}
        </p>
      )}
      {wishlistError && (
        <p className="form-error" role="alert">
          Không cập nhật được yêu thích: {wishlistError}
        </p>
      )}
      {!loading &&
        !error &&
        (items.length === 0 ? (
          <p>Chưa có sản phẩm còn hàng để gợi ý.</p>
        ) : (
          <div className="product-grid">
            {items.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                isFavorite={favoriteIds.has(product.id)}
                isBusy={wishlistLoading || busyIds.has(product.id)}
                onToggleFavorite={onToggleFavorite}
              />
            ))}
          </div>
        ))}
    </section>
  );
}
