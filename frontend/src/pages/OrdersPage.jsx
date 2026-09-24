import { useEffect, useState } from "react";
import { Link } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { formatCurrency } from "../components/formatCurrency.js";
import {
  formatDateTime,
  ORDER_STATUSES,
  orderStatusLabel,
} from "../components/orderPresentation.js";
import SiteLayout from "../components/SiteLayout.jsx";

const PAGE_SIZE = 20;

export default function OrdersPage() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [cancelOrder, setCancelOrder] = useState(null);
  const [reason, setReason] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError("");
    setActionError("");
    const params = { page, page_size: PAGE_SIZE };
    if (status) params.status = status;
    client
      .get("/orders/my", { params })
      .then((response) => {
        if (active) setResult(response.data);
      })
      .catch((requestError) => {
        if (active) setLoadError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [page, refreshKey, status]);

  async function confirmCancel(event) {
    event.preventDefault();
    if (cancelling) return;
    setCancelling(true);
    setActionError("");
    try {
      await client.post(`/orders/${cancelOrder.id}/cancel`, { reason });
      setCancelOrder(null);
      setReason("");
      setRefreshKey((value) => value + 1);
    } catch (requestError) {
      setActionError(errorMessage(requestError));
    } finally {
      setCancelling(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));

  return (
    <SiteLayout wide>
      <p className="eyebrow">Tài khoản</p>
      <h1>Đơn hàng của tôi</h1>
      <div className="status-tabs" aria-label="Lọc trạng thái đơn hàng">
        <button
          type="button"
          aria-pressed={status === ""}
          onClick={() => {
            setStatus("");
            setPage(1);
          }}
        >
          Tất cả
        </button>
        {ORDER_STATUSES.map((value) => (
          <button
            type="button"
            aria-pressed={status === value}
            key={value}
            onClick={() => {
              setStatus(value);
              setPage(1);
            }}
          >
            {orderStatusLabel(value)}
          </button>
        ))}
      </div>
      {loading && <p role="status">Đang tải đơn hàng...</p>}
      {loadError && (
        <p className="form-error" role="alert">
          {loadError}
        </p>
      )}
      {actionError && (
        <p className="form-error" role="alert">
          {actionError}
        </p>
      )}
      {!loading && !loadError && result.items.length === 0 && <p>Chưa có đơn hàng phù hợp.</p>}
      {!loading && !loadError && (
        <div className="order-list">
          {result.items.map((order) => (
            <article className="order-card" key={order.id}>
              <div>
                <Link to={`/orders/${order.id}`}>
                  <strong>{order.code}</strong>
                </Link>
                <p>{formatDateTime(order.created_at)}</p>
              </div>
              <span className={`status-badge status-${order.status.toLowerCase()}`}>
                {orderStatusLabel(order.status)}
              </span>
              <strong>{formatCurrency(order.total_amount)}</strong>
              {order.status === "PENDING" && (
                <button
                  type="button"
                  onClick={() => {
                    setCancelOrder(order);
                    setReason("");
                    setActionError("");
                  }}
                >
                  Hủy đơn
                </button>
              )}
            </article>
          ))}
        </div>
      )}
      <div className="pagination">
        <button type="button" disabled={loading || page <= 1} onClick={() => setPage(page - 1)}>
          Trang trước
        </button>
        <span>
          Trang {page}/{totalPages}
        </span>
        <button
          type="button"
          disabled={loading || page >= totalPages}
          onClick={() => setPage(page + 1)}
        >
          Trang sau
        </button>
      </div>
      {cancelOrder && (
        <div className="dialog-backdrop">
          <section className="dialog" role="dialog" aria-modal="true" aria-label="Hủy đơn hàng">
            <h2>Hủy {cancelOrder.code}</h2>
            <form className="form-stack" onSubmit={confirmCancel}>
              <label>
                Lý do hủy
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  required
                />
              </label>
              <div className="dialog-actions">
                <button type="button" disabled={cancelling} onClick={() => setCancelOrder(null)}>
                  Giữ đơn
                </button>
                <button type="submit" disabled={cancelling}>
                  {cancelling ? "Đang hủy..." : "Xác nhận hủy"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </SiteLayout>
  );
}
