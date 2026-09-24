import { useEffect, useState } from "react";
import { Link } from "react-router";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { formatCurrency } from "../../components/formatCurrency.js";
import { formatDateTime } from "../../components/orderPresentation.js";
import PurchaseOrderForm from "./PurchaseOrderForm.jsx";
import {
  PURCHASE_ORDER_STATUSES,
  purchaseOrderActions,
  purchaseOrderStatusLabel,
  variantLabel,
} from "./purchaseOrderPresentation.js";

const PAGE_SIZE = 20;

export default function ShopPurchaseOrdersPage() {
  const [suppliers, setSuppliers] = useState([]);
  const [variants, setVariants] = useState([]);
  const [referencesLoading, setReferencesLoading] = useState(true);
  const [referencesError, setReferencesError] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [pendingId, setPendingId] = useState(null);
  const [receivedId, setReceivedId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    setReferencesLoading(true);
    setReferencesError("");
    Promise.all([client.get("/shop/suppliers"), client.get("/shop/inventory")])
      .then(([supplierResponse, inventoryResponse]) => {
        if (active) {
          setSuppliers(supplierResponse.data);
          setVariants(inventoryResponse.data);
        }
      })
      .catch((requestError) => {
        if (active) setReferencesError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setReferencesLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError("");
    setActionError("");
    const params = { page, page_size: PAGE_SIZE };
    if (status) params.status = status;
    client
      .get("/shop/purchase-orders", { params })
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

  async function changeStatus(purchaseOrder, nextStatus) {
    setPendingId(purchaseOrder.id);
    setActionError("");
    setReceivedId(null);
    try {
      await client.patch(`/shop/purchase-orders/${purchaseOrder.id}/status`, {
        status: nextStatus,
      });
      if (nextStatus === "RECEIVED") setReceivedId(purchaseOrder.id);
      setRefreshKey((value) => value + 1);
    } catch (requestError) {
      setActionError(errorMessage(requestError));
    } finally {
      setPendingId(null);
    }
  }

  function selectStatus(value) {
    setStatus(value);
    setPage(1);
  }

  const supplierName = (id) => suppliers.find((supplier) => supplier.id === id)?.name ?? `#${id}`;
  const itemLabel = (variantId) => {
    const variant = variants.find((row) => row.variant_id === variantId);
    return variant ? variantLabel(variant) : `Biến thể #${variantId}`;
  };
  const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));

  return (
    <>
      <p className="eyebrow">Chủ shop</p>
      <h1>Nhập hàng</h1>
      {referencesLoading && <p role="status">Đang tải nhà cung cấp và biến thể...</p>}
      {referencesError && (
        <p className="form-error" role="alert">
          Không thể mở form nhập hàng: {referencesError}
        </p>
      )}
      {!referencesLoading && !referencesError && (
        <PurchaseOrderForm
          suppliers={suppliers}
          variants={variants}
          onCreated={() => {
            setReceivedId(null);
            setRefreshKey((value) => value + 1);
          }}
        />
      )}
      <h2>Phiếu nhập</h2>
      <div className="status-tabs" aria-label="Lọc trạng thái phiếu nhập">
        <button type="button" aria-pressed={status === ""} onClick={() => selectStatus("")}>
          Tất cả
        </button>
        {PURCHASE_ORDER_STATUSES.map((value) => (
          <button
            type="button"
            aria-pressed={status === value}
            key={value}
            onClick={() => selectStatus(value)}
          >
            {purchaseOrderStatusLabel(value)}
          </button>
        ))}
      </div>
      {receivedId && (
        <p role="status">
          Đã nhận hàng phiếu #{receivedId} và cộng tồn kho.{" "}
          <Link to="/shop/inventory">Xem tồn kho</Link>
        </p>
      )}
      {loading && <p role="status">Đang tải phiếu nhập...</p>}
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
      {!loading && !loadError && result.items.length === 0 && <p>Chưa có phiếu nhập phù hợp.</p>}
      {!loading && !loadError && result.items.length > 0 && (
        <div className="order-list">
          {result.items.map((purchaseOrder) => (
            <article className="order-box" key={purchaseOrder.id}>
              <div className="order-heading">
                <strong>
                  Phiếu #{purchaseOrder.id} · {supplierName(purchaseOrder.supplier_id)}
                </strong>
                <span className="status-badge">
                  {purchaseOrderStatusLabel(purchaseOrder.status)}
                </span>
              </div>
              <p className="muted">
                Tạo lúc {formatDateTime(purchaseOrder.created_at)}
                {purchaseOrder.received_at &&
                  ` · Nhận lúc ${formatDateTime(purchaseOrder.received_at)}`}
              </p>
              {purchaseOrder.note && <p>Ghi chú: {purchaseOrder.note}</p>}
              <ul>
                {purchaseOrder.items.map((item) => (
                  <li key={item.id}>
                    {itemLabel(item.variant_id)} × {item.quantity} @{" "}
                    {formatCurrency(item.unit_cost)}
                  </li>
                ))}
              </ul>
              <p>
                Tổng giá nhập:{" "}
                {formatCurrency(
                  purchaseOrder.items.reduce(
                    (sum, item) => sum + item.quantity * item.unit_cost,
                    0,
                  ),
                )}
              </p>
              <div className="table-actions">
                {purchaseOrderActions(purchaseOrder.status).map((action) => (
                  <button
                    type="button"
                    key={action.status}
                    disabled={pendingId === purchaseOrder.id}
                    onClick={() => changeStatus(purchaseOrder, action.status)}
                  >
                    {action.label}
                  </button>
                ))}
                {purchaseOrder.status === "RECEIVED" && (
                  <Link to="/shop/inventory">Xem tồn kho</Link>
                )}
              </div>
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
    </>
  );
}
