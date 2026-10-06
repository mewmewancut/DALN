import { useEffect, useRef, useState } from "react";
import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { orderStatusLabel } from "../orderPresentation.js";
import OrderSnapshot from "./OrderSnapshot.jsx";
import "./orderDetails.css";

export default function OrderDetailDialog({ orderId, onClose }) {
  const dialog = useRef(null);
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const node = dialog.current;
    if (node.showModal) node.showModal();
    else node.setAttribute("open", "");
    return () => node.close?.();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setOrder(null);
    setError("");
    setLoading(true);
    client
      .get(`/orders/${orderId}`, { signal: controller.signal })
      .then(({ data }) => {
        if (!controller.signal.aborted) setOrder(data);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [orderId, retry]);
  return (
    <dialog
      className="dialog dialog-wide order-preview"
      ref={dialog}
      aria-label="Chi tiết đơn hàng"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="page-heading">
        <h2>{order?.code ?? "Chi tiết đơn hàng"}</h2>
        <button type="button" onClick={onClose} autoFocus>
          Đóng chi tiết
        </button>
      </div>
      {loading && <p role="status">Đang tải chi tiết đơn hàng...</p>}
      {error && (
        <>
          <p role="alert">{error}</p>
          <button onClick={() => setRetry((n) => n + 1)}>Tải lại chi tiết</button>
        </>
      )}
      {order && (
        <>
          <p>
            <strong>Trạng thái: {orderStatusLabel(order.status)}</strong>
          </p>
          <OrderSnapshot order={order} />
        </>
      )}
    </dialog>
  );
}
