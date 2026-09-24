import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { formatCurrency } from "../../components/formatCurrency.js";
import {
  formatDateTime,
  ORDER_STATUSES,
  orderStatusLabel,
} from "../../components/orderPresentation.js";
import { shopOrderActions } from "./shopOrderActions.js";

const PAGE_SIZE = 20;

export default function ShopOrdersPage() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingId, setPendingId] = useState(null);
  const [cancelOrder, setCancelOrder] = useState(null);
  const [reason, setReason] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const params = { page, page_size: PAGE_SIZE };
    if (status) params.status = status;
    client
      .get("/shop/orders", { params })
      .then((response) => {
        if (active) setResult(response.data);
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
  }, [page, refreshKey, status]);

  async function changeStatus(order, nextStatus, note) {
    setPendingId(order.id);
    setError("");
    try {
      const body = { status: nextStatus };
      if (note) body.note = note;
      await client.patch(`/orders/${order.id}/status`, body);
      setCancelOrder(null);
      setRefreshKey((value) => value + 1);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPendingId(null);
    }
  }

  function selectStatus(value) {
    setStatus(value);
    setPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));

  return (
    <>
      <p className="eyebrow">Chủ shop</p>
      <h1>Đơn hàng</h1>
      <div className="status-tabs" aria-label="Lọc trạng thái đơn hàng">
        <button type="button" aria-pressed={status === ""} onClick={() => selectStatus("")}>
          Tất cả
        </button>
        {ORDER_STATUSES.map((value) => (
          <button
            type="button"
            aria-pressed={status === value}
            key={value}
            onClick={() => selectStatus(value)}
          >
            {orderStatusLabel(value)}
          </button>
        ))}
      </div>
      {loading && <p role="status">Đang tải đơn hàng...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && result.items.length === 0 && <p>Chưa có đơn hàng phù hợp.</p>}
      {!loading && result.items.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Mã đơn</th>
                <th>Ngày đặt</th>
                <th>Tổng tiền</th>
                <th>Thanh toán</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((order) => (
                <tr key={order.id}>
                  <td>{order.code}</td>
                  <td>{formatDateTime(order.created_at)}</td>
                  <td>{formatCurrency(order.total_amount)}</td>
                  <td>
                    {order.payment_method} · {order.payment_status}
                  </td>
                  <td>
                    <span className={`status-badge status-${order.status.toLowerCase()}`}>
                      {orderStatusLabel(order.status)}
                    </span>
                  </td>
                  <td className="table-actions">
                    {shopOrderActions(order.status).map((action) => (
                      <button
                        type="button"
                        key={action.status}
                        disabled={pendingId === order.id}
                        onClick={() => {
                          if (action.status === "CANCELLED") {
                            setCancelOrder(order);
                            setReason("");
                          } else {
                            changeStatus(order, action.status);
                          }
                        }}
                      >
                        {action.label}
                      </button>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
            <form
              className="form-stack"
              onSubmit={(event) => {
                event.preventDefault();
                changeStatus(cancelOrder, "CANCELLED", reason.trim());
              }}
            >
              <label>
                Lý do hủy
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  required
                />
              </label>
              <div className="dialog-actions">
                <button type="button" onClick={() => setCancelOrder(null)}>
                  Giữ đơn
                </button>
                <button type="submit" disabled={pendingId === cancelOrder.id}>
                  Xác nhận hủy
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
