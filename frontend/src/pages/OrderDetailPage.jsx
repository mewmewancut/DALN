import ModalDialog from "../components/ModalDialog.jsx";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import OrderSnapshot from "../components/orders/OrderSnapshot.jsx";
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
  const generation = useRef(null);

  useEffect(() => {
    let active = true;
    const current = Symbol("order-detail");
    generation.current = current;
    setOrder(null);
    setError("");
    setLoading(true);
    setReviewItem(null);
    setReviewing(false);
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
      if (generation.current === current) generation.current = null;
    };
  }, [id]);

  async function submitReview(event) {
    event.preventDefault();
    if (!reviewItem || reviewing) return;
    const current = generation.current;
    setReviewing(true);
    setError("");
    try {
      const response = await client.post("/reviews", {
        order_item_id: reviewItem.id,
        rating: Number(rating),
        comment: comment || null,
      });
      if (generation.current !== current) return;
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
      if (generation.current === current) setError(errorMessage(requestError));
    } finally {
      if (generation.current === current) setReviewing(false);
    }
  }

  return (
    <SiteLayout wide>
      <p>
        <Link to="/orders">← Danh sách đơn hàng</Link>
      </p>
      {loading && <p role="status">Đang tải đơn hàng...</p>}
      {error && !reviewItem && (
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
          <p>
            <Link className="shop-link" to={`/shops/${order.shop_id}`}>
              Xem shop
            </Link>
          </p>
          <OrderSnapshot
            order={order}
            onReview={(item) => {
              setReviewItem(item);
              setError("");
              setRating("5");
              setComment("");
            }}
          />
        </>
      )}
      {reviewItem && (
        <ModalDialog
          onClose={() => setReviewItem(null)}
          closeDisabled={reviewing}
          error={error}
          className="dialog"
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
        </ModalDialog>
      )}
    </SiteLayout>
  );
}
