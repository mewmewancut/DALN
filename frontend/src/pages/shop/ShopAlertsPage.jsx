import { useEffect, useState } from "react";
import { Link } from "react-router";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { formatDateTime } from "../../components/orderPresentation.js";

export default function ShopAlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    client
      .get("/shop/alerts")
      .then((response) => {
        if (active) setAlerts(response.data);
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

  return (
    <>
      <p className="eyebrow">Chủ shop</p>
      <h1>Cảnh báo tồn kho</h1>
      {loading && <p role="status">Đang tải cảnh báo...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && alerts.length === 0 && (
        <p className="empty-state">Không có cảnh báo tồn kho nào đang mở.</p>
      )}
      {!loading && alerts.length > 0 && (
        <>
          <p>
            Cảnh báo tự đóng khi tồn kho được bổ sung trên ngưỡng.{" "}
            <Link to="/shop/purchase-orders">Tạo phiếu nhập hàng</Link>
          </p>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Sản phẩm</th>
                  <th>Size</th>
                  <th>Màu</th>
                  <th>Tồn kho lúc cảnh báo</th>
                  <th>Thời điểm</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.id} className="row-low">
                    <td>{alert.product_name}</td>
                    <td>{alert.size}</td>
                    <td>{alert.color}</td>
                    <td>{alert.quantity_at_alert}</td>
                    <td>{formatDateTime(alert.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
