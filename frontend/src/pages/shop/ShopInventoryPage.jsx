import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import Pagination from "../../components/Pagination.jsx";
import useClientPagination, { matchesSearch } from "../../components/useClientPagination.js";

export default function ShopInventoryPage() {
  const [items, setItems] = useState([]);
  const [thresholds, setThresholds] = useState({});
  const [keyword, setKeyword] = useState("");
  const [stockFilter, setStockFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    let active = true;
    client
      .get("/shop/inventory")
      .then((response) => {
        if (!active) return;
        setItems(response.data);
        setThresholds(
          Object.fromEntries(
            response.data.map((item) => [item.variant_id, String(item.low_stock_threshold)]),
          ),
        );
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
  }, []);

  async function saveThreshold(item) {
    setPendingId(item.variant_id);
    setActionError("");
    try {
      const response = await client.put(`/shop/inventory/${item.variant_id}/threshold`, {
        low_stock_threshold: Number(thresholds[item.variant_id]),
      });
      setItems((current) =>
        current.map((row) => (row.variant_id === item.variant_id ? response.data : row)),
      );
      setThresholds((current) => ({
        ...current,
        [item.variant_id]: String(response.data.low_stock_threshold),
      }));
    } catch (requestError) {
      setActionError(errorMessage(requestError));
    } finally {
      setPendingId(null);
    }
  }

  const filteredItems = items.filter(
    (item) =>
      matchesSearch(keyword, item.product_name, item.sku, item.size, item.color) &&
      (stockFilter === "" || (stockFilter === "low" ? item.is_low : !item.is_low)),
  );
  const { page, pageItems, pageSize, setPage, total } = useClientPagination(filteredItems);

  function updateKeyword(value) {
    setKeyword(value);
    setPage(1);
  }

  function updateStockFilter(value) {
    setStockFilter(value);
    setPage(1);
  }

  return (
    <>
      <p className="eyebrow">Chủ shop</p>
      <h1>Tồn kho</h1>
      <div className="toolbar">
        <label>
          Tìm sản phẩm hoặc SKU
          <input
            type="search"
            value={keyword}
            onChange={(event) => updateKeyword(event.target.value)}
          />
        </label>
        <label>
          Mức tồn kho
          <select value={stockFilter} onChange={(event) => updateStockFilter(event.target.value)}>
            <option value="">Tất cả</option>
            <option value="low">Sắp hết</option>
            <option value="ok">Còn đủ</option>
          </select>
        </label>
      </div>
      {loading && <p role="status">Đang tải tồn kho...</p>}
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
      {!loading && !loadError && items.length === 0 && <p>Shop chưa có biến thể nào.</p>}
      {!loading && !loadError && items.length > 0 && filteredItems.length === 0 && (
        <p className="empty-state">Không tìm thấy biến thể phù hợp.</p>
      )}
      {!loading && !loadError && filteredItems.length > 0 && (
        <>
          <p className="list-summary">Tìm thấy {total} biến thể.</p>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Sản phẩm</th>
                  <th>Size</th>
                  <th>Màu</th>
                  <th>SKU</th>
                  <th>Tồn kho</th>
                  <th>Ngưỡng cảnh báo</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((item) => {
                  const threshold = thresholds[item.variant_id] ?? "";
                  const invalid = !/^\d+$/.test(threshold);
                  return (
                    <tr key={item.variant_id} className={item.is_low ? "row-low" : undefined}>
                      <td>{item.product_name}</td>
                      <td>{item.size}</td>
                      <td>{item.color}</td>
                      <td>{item.sku}</td>
                      <td>
                        {item.quantity}
                        {item.is_low && <span className="low-label"> Sắp hết</span>}
                      </td>
                      <td>
                        <input
                          aria-label={`Ngưỡng ${item.sku}`}
                          type="number"
                          min="0"
                          value={threshold}
                          onChange={(event) =>
                            setThresholds((current) => ({
                              ...current,
                              [item.variant_id]: event.target.value,
                            }))
                          }
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          disabled={
                            invalid ||
                            pendingId === item.variant_id ||
                            Number(threshold) === item.low_stock_threshold
                          }
                          onClick={() => saveThreshold(item)}
                        >
                          Lưu ngưỡng
                        </button>
                      </td>
                    </tr>
                  );
                })}
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
    </>
  );
}
