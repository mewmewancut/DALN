import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { formatCurrency } from "../components/formatCurrency.js";
import { formatDateTime, orderStatusLabel } from "../components/orderPresentation.js";
import SiteLayout from "../components/SiteLayout.jsx";

export default function OrderDetailPage() {
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reviewItem, setReviewItem] = useState(null);
  const [rating, setRating] = useState("5");
  const [comment, setComment] = useState("");
  const [reviewing, setReviewing] = useState(false);

  useEffect(() => {
    let active = true;
    client
      .get(`/orders/${id}`)
      .then((response) => {
        if (active) setOrder(response.data);
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

  async function submitReview(event) {
    event.preventDefault();
    setReviewing(true);
    setError("");
    try {
      const response = await client.post("/reviews", {
        order_item_id: reviewItem.id,
        rating: Number(rating),
        comment: comment || null,
      });
      setOrder((current) => ({
        ...current,
        items: current.items.map((item) =>
          item.id === reviewItem.id ? { ...item, review_id: response.data.id } : item,
        ),
      }));
      setReviewItem(null);
      setRating("5");
      setComment("");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setReviewing(false);
    }
  }

  return (
    <SiteLayout wide>
      <p>
        <Link to="/orders">← Danh sách đơn hàng</Link>
      </p>
      {loading && <p role="status">Đang tải đơn hàng...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {order && (
        <>
          <div className="order-heading">
            <div>
              <p className="eyebrow">{formatDateTime(order.created_at)}</p>
              <h1>{order.code}</h1>
            </div>
            <span className={`status-badge status-${order.status.toLowerCase()}`}>
              {orderStatusLabel(order.status)}
            </span>
          </div>
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
                  {order.status === "DELIVERED" && item.review_id == null && (
                    <button
                      type="button"
                      onClick={() => {
                        setReviewItem(item);
                        setRating("5");
                        setComment("");
                      }}
                    >
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
                Thanh toán: {order.payment_method} — {order.payment_status}
              </p>
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
      )}
      {reviewItem && (
        <div className="dialog-backdrop">
          <section
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Đánh giá sản phẩm"
          >
            <h2>Đánh giá {reviewItem.product_name}</h2>
            <form className="form-stack" onSubmit={submitReview}>
              <label>
                Số sao
                <select value={rating} onChange={(event) => setRating(event.target.value)}>
                  {[5, 4, 3, 2, 1].map((value) => (
                    <option value={value} key={value}>
                      {value} sao
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Nhận xét
                <textarea
                  maxLength="2000"
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                />
              </label>
              <div className="dialog-actions">
                <button type="button" onClick={() => setReviewItem(null)}>
                  Đóng
                </button>
                <button type="submit" disabled={reviewing}>
                  {reviewing ? "Đang gửi..." : "Gửi đánh giá"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </SiteLayout>
  );
}
