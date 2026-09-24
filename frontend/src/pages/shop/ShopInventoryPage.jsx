import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";

export default function ShopInventoryPage() {
  const [items, setItems] = useState([]);
  const [thresholds, setThresholds] = useState({});
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState(null);
  const [error, setError] = useState("");

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
        if (active) setError(errorMessage(requestError));
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
    setError("");
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
      setError(errorMessage(requestError));
    } finally {
      setPendingId(null);
    }
  }

  return (
    <>
      <p className="eyebrow">Chủ shop</p>
      <h1>Tồn kho</h1>
      {loading && <p role="status">Đang tải tồn kho...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && items.length === 0 && <p>Shop chưa có biến thể nào.</p>}
      {!loading && items.length > 0 && (
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
              {items.map((item) => {
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
      )}
    </>
  );
}
