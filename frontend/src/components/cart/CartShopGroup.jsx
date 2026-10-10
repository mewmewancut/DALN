import "./cart.css";
import ProductImage from "../ProductImage.jsx";
import ShopLink from "../ShopLink.jsx";
import { formatCurrency } from "../formatCurrency.js";

export default function CartShopGroup({
  group,
  quantities,
  onQuantity,
  onUpdate,
  onRemove,
  busy = false,
  selected = false,
  onSelect,
}) {
  return (
    <section
      className={`cart-shop-group${selected ? " is-selected" : ""}`}
      aria-label={`Giỏ của ${group.shop_name}`}
    >
      <header className="cart-shop-heading">
        <h2>
          <ShopLink shopId={group.shop_id}>{group.shop_name}</ShopLink>
        </h2>
        {onSelect && (
          <label>
            <input
              type="radio"
              name="checkout-shop"
              aria-label={`Thanh toán ${group.shop_name}`}
              checked={selected}
              disabled={busy || group.shop_id == null}
              onChange={onSelect}
            />
            Chọn shop này
          </label>
        )}
        <strong>{formatCurrency(group.total_amount)}</strong>
      </header>
      <div className="cart-list">
        {group.items.map((item) => {
          const quantity = Number(quantities[item.id] ?? item.quantity);
          const unavailable = item.is_available === false;
          const invalid =
            unavailable ||
            !Number.isInteger(quantity) ||
            quantity < 1 ||
            quantity > item.stock_quantity;
          return (
            <article className="cart-item" key={item.id}>
              <ProductImage
                src={item.image_url}
                alt={item.product_name}
                placeholderClassName="cart-image-placeholder"
              />
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
                    disabled={busy || unavailable}
                    value={quantities[item.id] ?? item.quantity}
                    onChange={(event) => onQuantity(item.id, event.target.value)}
                  />
                </label>
                {invalid && (
                  <span className="form-error">
                    {unavailable
                      ? "Sản phẩm đã ngừng bán. Hãy xóa khỏi giỏ."
                      : item.stock_quantity === 0
                        ? "Sản phẩm đã hết hàng. Hãy xóa khỏi giỏ."
                        : `Số lượng phải từ 1 đến ${item.stock_quantity}.`}
                  </span>
                )}
                <button
                  type="button"
                  disabled={busy || invalid || quantity === item.quantity}
                  onClick={() => onUpdate(item, quantity)}
                >
                  Cập nhật
                </button>
                <button type="button" disabled={busy} onClick={() => onRemove(item)}>
                  Xóa
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
