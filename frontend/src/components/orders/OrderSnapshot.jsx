import { formatCurrency } from "../formatCurrency.js";
import {
  formatDateTime,
  orderStatusLabel,
  paymentMethodLabel,
  paymentStatusLabel,
} from "../orderPresentation.js";

export default function OrderSnapshot({ order, onReview }) {
  return (
    <>
      <div className="order-detail-grid">
        <section>
          <h2>Sản phẩm</h2>
          {order.items.map((item) => (
            <article className="order-item" key={item.id}>
              <div>
                <strong>{item.product_name}</strong>
                <p>
                  {item.color}/{item.size} × {item.quantity}
                </p>
              </div>
              <strong>{formatCurrency(item.unit_price * item.quantity)}</strong>
              {onReview && order.status === "DELIVERED" && item.review_id == null && (
                <button type="button" onClick={() => onReview(item)}>
                  Đánh giá
                </button>
              )}
              {item.review_id != null && <span className="muted">Đã đánh giá</span>}
            </article>
          ))}
          <p className="order-total">Tổng cộng: {formatCurrency(order.total_amount)}</p>
        </section>
        <aside className="order-box">
          <h2>Giao hàng</h2>
          <p>{order.receiver_name}</p>
          <p>{order.receiver_phone}</p>
          <p>{order.shipping_address}</p>
          <p>
            Thanh toán: {paymentMethodLabel(order.payment_method)} —{" "}
            {paymentStatusLabel(order.payment_status)}
          </p>
          {order.cancel_reason && <p>Lý do hủy: {order.cancel_reason}</p>}
        </aside>
      </div>
      <section className="order-history">
        <h2>Lịch sử trạng thái</h2>
        <ol>
          {order.status_history.map((entry) => (
            <li key={entry.id}>
              <strong>{orderStatusLabel(entry.to_status)}</strong>
              <span>{formatDateTime(entry.created_at)}</span>
              {entry.note && <p>{entry.note}</p>}
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
