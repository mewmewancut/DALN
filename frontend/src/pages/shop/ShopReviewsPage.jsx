import { useCallback, useEffect, useState } from "react";
import client from "../../api/client.js";

export default function ShopReviewsPage() {
  const [reviews, setReviews] = useState([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [drafts, setDrafts] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadReviews = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await client.get("/reviews/shop", {
        params: { page, page_size: pageSize },
      });

      setReviews(response.data.items);
      setTotal(response.data.total);
      setUnreadCount(response.data.unread_count);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Không thể tải danh sách đánh giá."
      );
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    loadReviews();
  }, [loadReviews]);

  async function markRead(reviewId) {
    setBusyId(reviewId);
    setError("");
    setMessage("");

    try {
      await client.patch(`/reviews/shop/${reviewId}/read`);
      await loadReviews();
      setMessage("Đã đánh dấu đánh giá là đã đọc.");
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể đánh dấu đã đọc.");
    } finally {
      setBusyId(null);
    }
  }

  async function sendReply(reviewId) {
    const reply = (drafts[reviewId] ?? "").trim();

    if (!reply) {
      setError("Vui lòng nhập nội dung phản hồi.");
      return;
    }

    if (reply.length > 2000) {
      setError("Phản hồi không được vượt quá 2000 ký tự.");
      return;
    }

    setBusyId(reviewId);
    setError("");
    setMessage("");

    try {
      await client.post(`/reviews/shop/${reviewId}/reply`, { reply });
      setDrafts((previous) => ({ ...previous, [reviewId]: "" }));
      await loadReviews();
      setMessage("Đã gửi phản hồi thành công.");
    } catch (err) {
      setError(err.response?.data?.detail || "Không thể gửi phản hồi.");
    } finally {
      setBusyId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section style={{ padding: "24px", maxWidth: "1100px", margin: "auto" }}>
      <h1>Đánh giá khách hàng</h1>
      <p>Quản lý đánh giá và phản hồi khách hàng về sản phẩm của shop.</p>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 20 }}>
        <div style={summaryStyle}>
          <strong>Tổng đánh giá</strong>
          <div style={numberStyle}>{total}</div>
        </div>
        <div style={summaryStyle}>
          <strong>Chưa đọc</strong>
          <div style={numberStyle}>{unreadCount}</div>
        </div>
      </div>

      <button type="button" onClick={loadReviews} disabled={loading}>
        Làm mới danh sách
      </button>

      {error && <p role="alert" style={{ color: "#b91c1c" }}>{String(error)}</p>}
      {message && <p role="status" style={{ color: "#166534" }}>{message}</p>}

      {loading ? (
        <p>Đang tải đánh giá...</p>
      ) : reviews.length === 0 ? (
        <p>Shop chưa có đánh giá nào.</p>
      ) : (
        <div style={{ display: "grid", gap: 16, marginTop: 20 }}>
          {reviews.map((review) => (
            <article key={review.id} style={cardStyle}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div>
                  <h3 style={{ marginTop: 0 }}>{review.product_name}</h3>
                  <p style={{ margin: "6px 0" }}>
                    {"★".repeat(review.rating)}
                    {"☆".repeat(5 - review.rating)}
                    {" "}({review.rating}/5)
                  </p>
                  <small>
                    {new Date(review.created_at).toLocaleString("vi-VN")}
                  </small>
                </div>
                <span>
                  {review.shop_review_read_at ? "Đã đọc" : "Chưa đọc"}
                </span>
              </div>

              <p>{review.comment || "Khách hàng không để lại bình luận."}</p>

              {!review.shop_review_read_at && (
                <button
                  type="button"
                  disabled={busyId === review.id}
                  onClick={() => markRead(review.id)}
                >
                  Đánh dấu đã đọc
                </button>
              )}

              {review.shop_reply && (
                <div style={replyStyle}>
                  <strong>Phản hồi của shop:</strong>
                  <p>{review.shop_reply}</p>
                </div>
              )}

              <div style={{ marginTop: 16 }}>
                <label htmlFor={`reply-${review.id}`}>
                  {review.shop_reply ? "Chỉnh sửa phản hồi" : "Viết phản hồi"}
                </label>
                <textarea
                  id={`reply-${review.id}`}
                  rows={3}
                  maxLength={2000}
                  value={drafts[review.id] ?? ""}
                  onChange={(event) =>
                    setDrafts((previous) => ({
                      ...previous,
                      [review.id]: event.target.value,
                    }))
                  }
                  placeholder="Nhập lời cảm ơn hoặc giải đáp cho khách hàng..."
                  style={{ width: "100%", padding: 10, marginTop: 8, boxSizing: "border-box" }}
                />
                <button
                  type="button"
                  disabled={busyId === review.id || loading}
                  onClick={() => sendReply(review.id)}
                  style={{ marginTop: 8 }}
                >
                  {busyId === review.id ? "Đang xử lý..." : "Gửi phản hồi"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 24 }}>
        <button
          type="button"
          disabled={page <= 1 || loading}
          onClick={() => setPage((current) => current - 1)}
        >
          Trang trước
        </button>
        <span>Trang {page}/{totalPages}</span>
        <button
          type="button"
          disabled={page >= totalPages || loading}
          onClick={() => setPage((current) => current + 1)}
        >
          Trang sau
        </button>
      </div>
    </section>
  );
}

const summaryStyle = {
  padding: 18,
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  minWidth: 160,
  background: "#fff",
};

const numberStyle = {
  fontSize: 28,
  fontWeight: 700,
  marginTop: 8,
};

const cardStyle = {
  padding: 20,
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  background: "#fff",
};

const replyStyle = {
  marginTop: 12,
  padding: 12,
  borderRadius: 8,
  background: "#f0fdf4",
};