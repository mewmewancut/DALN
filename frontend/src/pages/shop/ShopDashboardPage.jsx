import { useEffect, useState } from "react";
import { Link } from "react-router";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import DateRangeFields from "../../components/DateRangeFields.jsx";
import { lastDays } from "../../components/dateRange.js";
import RevenueChart from "../../components/RevenueChart.jsx";
import StatCards from "../../components/StatCards.jsx";

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
        <DateRangeFields range={range} onChange={setRange} />
      </div>
      {loading && <p role="status">Đang tải số liệu...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && data && (
        <>
          <StatCards overview={data.overview} />
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
