import { useState } from "react";

import DashboardBody from "../../components/dashboard/DashboardBody.jsx";
import DashboardToolbar from "../../components/dashboard/DashboardToolbar.jsx";
import useDashboard from "../../components/dashboard/useDashboard.js";
import { lastDays } from "../../components/dateRange.js";

export default function ShopDashboardPage() {
  const [range, setRange] = useState(() => lastDays(30));
  const { data, loading, error, refresh } = useDashboard("/shop/stats/dashboard", range);
  return (
    <div className="dashboard-page">
      <h1>Tổng quan shop</h1>
      <DashboardToolbar range={range} onChange={setRange} loading={loading} onRefresh={refresh} />
      {loading && <p role="status">Đang tải số liệu...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!range.from || !range.to ? (
        <p className="dashboard-empty">Chọn đủ ngày bắt đầu và ngày kết thúc để xem số liệu.</p>
      ) : null}
      {!loading && data && <DashboardBody data={data} />}
    </div>
  );
}
