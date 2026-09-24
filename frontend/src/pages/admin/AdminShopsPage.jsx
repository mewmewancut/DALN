import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { formatDateTime } from "../../components/orderPresentation.js";
import Pagination from "../../components/Pagination.jsx";

const PAGE_SIZE = 20;

export default function AdminShopsPage() {
  const [filters, setFilters] = useState({ keyword: "", is_active: "" });
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [pendingId, setPendingId] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError("");
    setActionError("");
    const params = { page, page_size: PAGE_SIZE };
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim();
    if (filters.is_active) params.is_active = filters.is_active;
    client
      .get("/admin/shops", { params })
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
  }, [filters, page]);

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function resetFilters() {
    setFilters({ keyword: "", is_active: "" });
    setPage(1);
  }

  async function toggleActive(shop) {
    setPendingId(shop.id);
    setActionError("");
    try {
      const response = await client.patch(`/admin/shops/${shop.id}`, {
        is_active: !shop.is_active,
      });
      setResult((current) => ({
        ...current,
        items: current.items.map((item) => (item.id === shop.id ? response.data : item)),
      }));
    } catch (requestError) {
      setActionError(errorMessage(requestError));
    } finally {
      setPendingId(null);
    }
  }

  return (
    <>
      <p className="eyebrow">Admin</p>
      <h1>Shop</h1>
      <p className="muted">
        Shop bị khóa sẽ không còn sản phẩm nào hiển thị trong catalog công khai.
      </p>
      <div className="toolbar">
        <label>
          Tìm theo tên shop
          <input
            type="search"
            value={filters.keyword}
            onChange={(event) => updateFilter("keyword", event.target.value)}
          />
        </label>
        <label>
          Trạng thái
          <select
            value={filters.is_active}
            onChange={(event) => updateFilter("is_active", event.target.value)}
          >
            <option value="">Tất cả</option>
            <option value="true">Hoạt động</option>
            <option value="false">Đã khóa</option>
          </select>
        </label>
        {(filters.keyword || filters.is_active) && (
          <button type="button" className="text-button" onClick={resetFilters}>
            Xóa bộ lọc
          </button>
        )}
      </div>
      {loading && <p role="status">Đang tải shop...</p>}
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
      {!loading && !loadError && result.items.length === 0 && (
        <p>Không có shop phù hợp với bộ lọc.</p>
      )}
      {!loading && !loadError && result.items.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Tên shop</th>
                <th>Mã chủ shop</th>
                <th>Ngày tạo</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((shop) => (
                <tr key={shop.id}>
                  <td>{shop.name}</td>
                  <td>#{shop.owner_id}</td>
                  <td>{formatDateTime(shop.created_at)}</td>
                  <td>
                    <span
                      className={`status-badge ${shop.is_active ? "status-active" : "status-inactive"}`}
                    >
                      {shop.is_active ? "Hoạt động" : "Đã khóa"}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      disabled={pendingId === shop.id}
                      onClick={() => toggleActive(shop)}
                    >
                      {shop.is_active ? "Khóa" : "Mở khóa"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
