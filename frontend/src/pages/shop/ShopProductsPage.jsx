import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { formatCurrency } from "../../components/formatCurrency.js";
import ProductFormDialog from "./ProductFormDialog.jsx";

const PAGE_SIZE = 20;

export default function ShopProductsPage() {
  const [keyword, setKeyword] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE });
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingId, setPendingId] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    client
      .get("/categories")
      .then((response) => setCategories(response.data))
      .catch((requestError) => setError(errorMessage(requestError)));
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const params = { page, page_size: PAGE_SIZE };
    if (keyword.trim()) params.keyword = keyword.trim();
    if (activeFilter) params.is_active = activeFilter;
    client
      .get("/shop/products", { params })
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
  }, [activeFilter, keyword, page, refreshKey]);

  async function toggleActive(product) {
    setPendingId(product.id);
    setError("");
    try {
      await client.put(`/products/${product.id}`, { is_active: !product.is_active });
      setRefreshKey((value) => value + 1);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPendingId(null);
    }
  }

  function closeDialog() {
    setDialog(null);
    setRefreshKey((value) => value + 1);
  }

  const categoryName = (id) => categories.find((category) => category.id === id)?.name ?? "—";
  const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));

  return (
    <>
      <p className="eyebrow">Chủ shop</p>
      <h1>Sản phẩm</h1>
      <div className="toolbar">
        <label>
          Tìm theo tên
          <input
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          Trạng thái
          <select
            value={activeFilter}
            onChange={(event) => {
              setActiveFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Tất cả</option>
            <option value="true">Đang bán</option>
            <option value="false">Đã ẩn</option>
          </select>
        </label>
        <button type="button" onClick={() => setDialog({ product: null })}>
          Thêm sản phẩm
        </button>
      </div>
      {loading && <p role="status">Đang tải sản phẩm...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && result.items.length === 0 && <p>Chưa có sản phẩm phù hợp.</p>}
      {!loading && result.items.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Sản phẩm</th>
                <th>Danh mục</th>
                <th>Giá từ</th>
                <th>Biến thể</th>
                <th>Tồn kho</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((product) => (
                <tr key={product.id}>
                  <td>{product.name}</td>
                  <td>{categoryName(product.category_id)}</td>
                  <td>{formatCurrency(product.price_from)}</td>
                  <td>{product.variants.length}</td>
                  <td>{product.variants.reduce((sum, variant) => sum + variant.quantity, 0)}</td>
                  <td>{product.is_active ? "Đang bán" : "Đã ẩn"}</td>
                  <td className="table-actions">
                    <button type="button" onClick={() => setDialog({ product })}>
                      Sửa
                    </button>
                    <button
                      type="button"
                      disabled={pendingId === product.id}
                      onClick={() => toggleActive(product)}
                    >
                      {product.is_active ? "Ẩn" : "Hiện"}
                    </button>
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
      {dialog && (
        <ProductFormDialog categories={categories} product={dialog.product} onClose={closeDialog} />
      )}
    </>
  );
}
