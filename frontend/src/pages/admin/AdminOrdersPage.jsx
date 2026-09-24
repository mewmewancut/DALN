import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import DateRangeFields from "../../components/DateRangeFields.jsx";
import { formatCurrency } from "../../components/formatCurrency.js";
import {
  formatDateTime,
  ORDER_STATUSES,
  orderStatusLabel,
} from "../../components/orderPresentation.js";
import Pagination from "../../components/Pagination.jsx";
import { loadAllAdminShops } from "./loadAllAdminShops.js";

const PAGE_SIZE = 20;

export default function AdminOrdersPage() {
  const [filters, setFilters] = useState({ shop_id: "", status: "", from: "", to: "" });
  const [page, setPage] = useState(1);
  const [shops, setShops] = useState([]);
  const [shopsLoading, setShopsLoading] = useState(true);
  const [shopsError, setShopsError] = useState("");
  const [result, setResult] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE });
  const [loading, setLoading] = useState(true);
  const [ordersError, setOrdersError] = useState("");

  useEffect(() => {
    let active = true;
    setShopsLoading(true);
    setShopsError("");
    loadAllAdminShops(client)
      .then((items) => {
        if (active) setShops(items);
      })
      .catch((requestError) => {
        if (active) setShopsError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setShopsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setOrdersError("");
    const params = { page, page_size: PAGE_SIZE };
    for (const [key, value] of Object.entries(filters)) {
      if (value) params[key] = value;
    }
    client
      .get("/admin/orders", { params })
      .then((response) => {
        if (active) setResult(response.data);
      })
      .catch((requestError) => {
        if (active) setOrdersError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters, page]);

  function updateFilters(next) {
    setFilters(next);
    setPage(1);
  }

  function resetFilters() {
    setFilters({ shop_id: "", status: "", from: "", to: "" });
    setPage(1);
  }

  const hasFilters = Object.values(filters).some(Boolean);

  const shopName = (id) => shops.find((shop) => shop.id === id)?.name ?? `Shop #${id}`;

  return (
    <>
      <p className="eyebrow">Admin</p>
      <h1>Đơn hàng toàn hệ thống</h1>
      <div className="toolbar">
        <label>
          Shop
          <select
            value={filters.shop_id}
            disabled={shopsLoading || !!shopsError}
            onChange={(event) => updateFilters({ ...filters, shop_id: event.target.value })}
          >
            <option value="">{shopsLoading ? "Đang tải shop..." : "Tất cả shop"}</option>
            {shops.map((shop) => (
              <option key={shop.id} value={shop.id}>
                {shop.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Trạng thái
          <select
            value={filters.status}
            onChange={(event) => updateFilters({ ...filters, status: event.target.value })}
          >
            <option value="">Tất cả</option>
            {ORDER_STATUSES.map((value) => (
              <option key={value} value={value}>
                {orderStatusLabel(value)}
              </option>
            ))}
          </select>
        </label>
        <DateRangeFields
          range={{ from: filters.from, to: filters.to }}
          onChange={(range) => updateFilters({ ...filters, ...range })}
          required={false}
        />
        {hasFilters && (
          <button type="button" className="text-button" onClick={resetFilters}>
            Xóa bộ lọc
          </button>
        )}
      </div>
      {shopsError && (
        <p className="form-error" role="alert">
          Không tải được danh sách shop: {shopsError}
        </p>
      )}
      {loading && <p role="status">Đang tải đơn hàng...</p>}
      {ordersError && (
        <p className="form-error" role="alert">
          {ordersError}
        </p>
      )}
      {!loading && !ordersError && result.items.length === 0 && <p>Không có đơn hàng phù hợp.</p>}
      {!loading && !ordersError && result.items.length > 0 && (
        <>
          <p className="muted">Tổng cộng {result.total} đơn.</p>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Mã đơn</th>
                  <th>Shop</th>
                  <th>Người mua</th>
                  <th>Ngày đặt</th>
                  <th>Tổng tiền</th>
                  <th>Thanh toán</th>
                  <th>Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {result.items.map((order) => (
                  <tr key={order.id}>
                    <td>{order.code}</td>
                    <td>{shopName(order.shop_id)}</td>
                    <td>#{order.buyer_id}</td>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <Pagination
        page={page}
        total={result.total}
        pageSize={result.page_size}
        loading={loading}
        onChange={setPage}
      />
    </>
  );
}
