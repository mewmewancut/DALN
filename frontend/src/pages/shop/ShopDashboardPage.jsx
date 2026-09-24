import { useEffect, useState } from "react";
import { Link } from "react-router";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { lastDays } from "../../components/dateRange.js";
import { formatCurrency } from "../../components/formatCurrency.js";
import RevenueChart from "../../components/RevenueChart.jsx";

function formatRate(rate) {
  if (rate == null) return "—";
  return `${(rate * 100).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`;
}

export default function ShopDashboardPage() {
  const [range, setRange] = useState(() => lastDays(30));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setError("");
    if (!range.from || !range.to) {
      setData(null);
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    const params = { from: range.from, to: range.to };
    Promise.all([
      client.get("/shop/stats/overview", { params }),
      client.get("/shop/stats/revenue-by-day", { params }),
      client.get("/shop/alerts"),
    ])
      .then(([overview, revenue, alerts]) => {
        if (active) {
          setData({
            overview: overview.data,
            revenue: revenue.data,
            alertCount: alerts.data.length,
            range: params,
          });
        }
      })
      .catch((requestError) => {
        if (active) {
          setData(null);
          setError(errorMessage(requestError));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [range]);

  return (
    <>
      <p className="eyebrow">Chủ shop</p>
      <h1>Tổng quan shop</h1>
      <div className="toolbar">
        <label>
          Từ ngày
          <input
            type="date"
            value={range.from}
            onChange={(event) => setRange((current) => ({ ...current, from: event.target.value }))}
            required
          />
        </label>
        <label>
          Đến ngày
          <input
            type="date"
            value={range.to}
            onChange={(event) => setRange((current) => ({ ...current, to: event.target.value }))}
            required
          />
        </label>
      </div>
      {loading && <p role="status">Đang tải số liệu...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && data && (
        <>
          <div className="stat-grid">
            <article className="stat-card">
              <span>Doanh thu</span>
              <strong>{formatCurrency(data.overview.revenue)}</strong>
            </article>
            <article className="stat-card">
              <span>Số đơn</span>
              <strong>{data.overview.order_count}</strong>
            </article>
            <article className="stat-card">
              <span>Tỷ lệ hủy</span>
              <strong>{formatRate(data.overview.cancel_rate)}</strong>
            </article>
            <article className="stat-card">
              <span>Giá trị đơn trung bình</span>
              <strong>
                {data.overview.aov == null ? "—" : formatCurrency(Math.round(data.overview.aov))}
              </strong>
            </article>
          </div>
          <Link to="/shop/alerts" className="alert-badge">
            Cảnh báo tồn kho: <strong>{data.alertCount}</strong>
          </Link>
          <h2>Doanh thu theo ngày giao</h2>
          <RevenueChart from={data.range.from} to={data.range.to} rows={data.revenue} />
        </>
      )}
    </>
  );
}
