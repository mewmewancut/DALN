import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import Pagination from "../../components/Pagination.jsx";
import useClientPagination, { matchesSearch } from "../../components/useClientPagination.js";

const EMPTY_FORM = { name: "", phone: "", address: "" };

function supplierPayload(form) {
  return {
    name: form.name.trim(),
    phone: form.phone.trim() || null,
    address: form.address.trim() || null,
  };
}

function SupplierFields({ form, onChange }) {
  return (
    <>
      <label>
        Tên nhà cung cấp
        <input
          value={form.name}
          onChange={(event) => onChange({ ...form, name: event.target.value })}
          required
        />
      </label>
      <label>
        Số điện thoại
        <input
          value={form.phone}
          maxLength={20}
          onChange={(event) => onChange({ ...form, phone: event.target.value })}
        />
      </label>
      <label>
        Địa chỉ
        <input
          value={form.address}
          onChange={(event) => onChange({ ...form, address: event.target.value })}
        />
      </label>
    </>
  );
}

export default function ShopSuppliersPage() {
  const [suppliers, setSuppliers] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(null);
  const [pending, setPending] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError("");
    client
      .get("/shop/suppliers")
      .then((response) => {
        if (active) setSuppliers(response.data);
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
  }, [refreshKey]);

  async function run(key, request) {
    setPending(key);
    setActionError("");
    try {
      await request();
      setRefreshKey((value) => value + 1);
      return true;
    } catch (requestError) {
      setActionError(errorMessage(requestError));
      return false;
    } finally {
      setPending(null);
    }
  }

  async function createSupplier(event) {
    event.preventDefault();
    const ok = await run("new", () => client.post("/shop/suppliers", supplierPayload(form)));
    if (ok) setForm(EMPTY_FORM);
  }

  async function saveEdit(event) {
    event.preventDefault();
    const ok = await run(editing.id, () =>
      client.put(`/shop/suppliers/${editing.id}`, supplierPayload(editing.form)),
    );
    if (ok) setEditing(null);
  }

  const filteredSuppliers = suppliers.filter(
    (supplier) =>
      matchesSearch(keyword, supplier.name, supplier.phone, supplier.address) &&
      (activeFilter === "" || (activeFilter === "true" ? supplier.is_active : !supplier.is_active)),
  );
  const { page, pageItems, pageSize, setPage, total } = useClientPagination(filteredSuppliers);

  function updateKeyword(value) {
    setKeyword(value);
    setPage(1);
  }

  function updateActiveFilter(value) {
    setActiveFilter(value);
    setPage(1);
  }

  return (
    <>
      <p className="eyebrow">Chủ shop</p>
      <h1>Nhà cung cấp</h1>
      <section className="management-form">
        <h2>Thêm nhà cung cấp</h2>
        <form className="inline-form" onSubmit={createSupplier} aria-label="Thêm nhà cung cấp">
          <SupplierFields form={form} onChange={setForm} />
          <button type="submit" disabled={pending === "new" || loading || !!loadError}>
            Thêm nhà cung cấp
          </button>
        </form>
      </section>
      <div className="section-heading">
        <div>
          <p className="eyebrow">Danh sách</p>
          <h2>Nhà cung cấp hiện có</h2>
        </div>
      </div>
      <div className="toolbar">
        <label>
          Tìm nhà cung cấp
          <input
            type="search"
            value={keyword}
            onChange={(event) => updateKeyword(event.target.value)}
          />
        </label>
        <label>
          Trạng thái
          <select value={activeFilter} onChange={(event) => updateActiveFilter(event.target.value)}>
            <option value="">Tất cả</option>
            <option value="true">Đang hợp tác</option>
            <option value="false">Ngừng hợp tác</option>
          </select>
        </label>
      </div>
      {loading && <p role="status">Đang tải nhà cung cấp...</p>}
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
      {!loading && !loadError && suppliers.length === 0 && <p>Chưa có nhà cung cấp.</p>}
      {!loading && !loadError && suppliers.length > 0 && filteredSuppliers.length === 0 && (
        <p className="empty-state">Không tìm thấy nhà cung cấp phù hợp.</p>
      )}
      {!loading && !loadError && filteredSuppliers.length > 0 && (
        <>
          <p className="list-summary">Tìm thấy {total} nhà cung cấp.</p>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tên</th>
                  <th>Số điện thoại</th>
                  <th>Địa chỉ</th>
                  <th>Trạng thái</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((supplier) => (
                  <tr key={supplier.id}>
                    <td>{supplier.name}</td>
                    <td>{supplier.phone ?? "—"}</td>
                    <td>{supplier.address ?? "—"}</td>
                    <td>
                      <span
                        className={`status-badge ${
                          supplier.is_active ? "status-active" : "status-inactive"
                        }`}
                      >
                        {supplier.is_active ? "Đang hợp tác" : "Ngừng hợp tác"}
                      </span>
                    </td>
                    <td>
                      <div className="table-actions">
                        <button
                          type="button"
                          onClick={() =>
                            setEditing({
                              id: supplier.id,
                              form: {
                                name: supplier.name,
                                phone: supplier.phone ?? "",
                                address: supplier.address ?? "",
                              },
                            })
                          }
                        >
                          Sửa
                        </button>
                        {supplier.is_active ? (
                          <button
                            type="button"
                            disabled={pending === supplier.id}
                            onClick={() =>
                              run(supplier.id, () =>
                                client.delete(`/shop/suppliers/${supplier.id}`),
                              )
                            }
                          >
                            Ngừng hợp tác
                          </button>
                        ) : (
                          <button
                            type="button"
                            disabled={pending === supplier.id}
                            onClick={() =>
                              run(supplier.id, () =>
                                client.put(`/shop/suppliers/${supplier.id}`, { is_active: true }),
                              )
                            }
                          >
                            Khôi phục
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            total={total}
            pageSize={pageSize}
            loading={loading}
            onChange={setPage}
          />
        </>
      )}
      {editing && (
        <div className="dialog-backdrop">
          <section className="dialog" role="dialog" aria-modal="true" aria-label="Sửa nhà cung cấp">
            <h2>Sửa nhà cung cấp</h2>
            <form className="form-stack" onSubmit={saveEdit}>
              <SupplierFields
                form={editing.form}
                onChange={(next) => setEditing({ ...editing, form: next })}
              />
              <div className="dialog-actions">
                <button type="button" onClick={() => setEditing(null)}>
                  Đóng
                </button>
                <button type="submit" disabled={pending === editing.id}>
                  Lưu
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
