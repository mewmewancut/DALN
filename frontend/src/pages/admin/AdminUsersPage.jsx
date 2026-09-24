import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { formatDateTime } from "../../components/orderPresentation.js";
import Pagination from "../../components/Pagination.jsx";

const PAGE_SIZE = 20;
const ROLE_LABELS = { BUYER: "Người mua", SHOP_OWNER: "Chủ shop", ADMIN: "Admin" };

export default function AdminUsersPage() {
  const [role, setRole] = useState("");
  const [keyword, setKeyword] = useState("");
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
    if (role) params.role = role;
    if (keyword.trim()) params.keyword = keyword.trim();
    client
      .get("/admin/users", { params })
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
  }, [keyword, page, role]);

  async function toggleActive(user) {
    setPendingId(user.id);
    setActionError("");
    try {
      const response = await client.patch(`/admin/users/${user.id}`, {
        is_active: !user.is_active,
      });
      setResult((current) => ({
        ...current,
        items: current.items.map((item) => (item.id === user.id ? response.data : item)),
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
      <h1>Người dùng</h1>
      <div className="toolbar">
        <label>
          Vai trò
          <select
            value={role}
            onChange={(event) => {
              setRole(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Tất cả</option>
            {Object.entries(ROLE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Tìm email hoặc họ tên
          <input
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
          />
        </label>
      </div>
      {loading && <p role="status">Đang tải người dùng...</p>}
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
      {!loading && !loadError && result.items.length === 0 && <p>Không có người dùng phù hợp.</p>}
      {!loading && !loadError && result.items.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Họ tên</th>
                <th>Vai trò</th>
                <th>Ngày tạo</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((user) => (
                <tr key={user.id}>
                  <td>{user.email}</td>
                  <td>{user.full_name}</td>
                  <td>{ROLE_LABELS[user.role] ?? user.role}</td>
                  <td>{formatDateTime(user.created_at)}</td>
                  <td>
                    <span
                      className={`status-badge ${user.is_active ? "status-active" : "status-inactive"}`}
                    >
                      {user.is_active ? "Hoạt động" : "Đã khóa"}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      disabled={pendingId === user.id}
                      onClick={() => toggleActive(user)}
                    >
                      {user.is_active ? "Khóa" : "Mở khóa"}
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
