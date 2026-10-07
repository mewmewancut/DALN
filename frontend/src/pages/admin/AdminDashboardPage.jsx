import { useState } from "react";

import { analyticsLinks } from "../../components/analyticsLinks.js";
import DashboardBody from "../../components/dashboard/DashboardBody.jsx";
import DashboardToolbar from "../../components/dashboard/DashboardToolbar.jsx";
import useDashboard from "../../components/dashboard/useDashboard.js";
import { lastDays } from "../../components/dateRange.js";

export default function AdminDashboardPage() {
  const [range, setRange] = useState(() => lastDays(30));
  const { data, loading, error, refresh } = useDashboard("/admin/stats/dashboard", range);
  return (
    <div className="dashboard-page">
      <h1>Quản trị hệ thống</h1>
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
      {!loading && data && <DashboardBody data={data} admin />}
      <details className="dashboard-external">
        <summary>Phân tích dữ liệu trên Databricks</summary>
        <ul className="analytics-links">
          {analyticsLinks().map((link) => (
            <li key={link.key}>
              {link.url ? (
                <a href={link.url} target="_blank" rel="noreferrer">
                  Mở {link.label}
                </a>
              ) : (
                <span className="muted">{link.label}: chưa được cấu hình</span>
              )}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
