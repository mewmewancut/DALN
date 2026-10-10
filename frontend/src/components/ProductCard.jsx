import { Link } from "react-router";

import WishlistButton from "./WishlistButton.jsx";
import ProductImage from "./ProductImage.jsx";
import ShopLink from "./ShopLink.jsx";
import { formatCurrency } from "./formatCurrency.js";

export default function ProductCard({ product, isFavorite, isBusy, onToggleFavorite }) {
  return (
    <article className="product-card">
      <div className="product-card-link">
        <Link
          to={`/products/${product.id}`}
          className="product-card-media"
          aria-label={`Xem ${product.name}`}
        >
          <ProductImage src={product.image_url} alt={product.name} />
          <span className="view-product">Xem chi tiết</span>
        </Link>
        <div className="product-card-body">
          <p className="product-shop">
            <ShopLink shopId={product.shop_id}>{product.shop_name}</ShopLink>
          </p>
          <h2>
            <Link className="product-title-link" to={`/products/${product.id}`}>
              {product.name}
            </Link>
          </h2>
          <strong className="product-price">
            {product.price_from == null
              ? "Chưa có giá"
              : `Từ ${formatCurrency(product.price_from)}`}
          </strong>
          <p className="product-rating">
            <span aria-hidden="true">★</span>{" "}
            {product.rating_average == null
              ? "Chưa có đánh giá"
              : Number(product.rating_average).toFixed(1)}
          </p>
        </div>
      </div>
      <WishlistButton
        className="product-card-wishlist"
        productName={product.name}
        isFavorite={isFavorite}
        isBusy={isBusy}
        onClick={(event) => onToggleFavorite(event, product.id)}
      />
    </article>
  );
}
