import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { analyticsLinks } from "../../components/analyticsLinks.js";
import DateRangeFields from "../../components/DateRangeFields.jsx";
import { lastDays } from "../../components/dateRange.js";
import StatCards from "../../components/StatCards.jsx";

export default function AdminDashboardPage() {
  const [range, setRange] = useState(() => lastDays(30));
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setError("");
    if (!range.from || !range.to) {
      setOverview(null);
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    client
      .get("/admin/stats/overview", { params: { from: range.from, to: range.to } })
      .then((response) => {
        if (active) setOverview(response.data);
      })
      .catch((requestError) => {
        if (active) {
          setOverview(null);
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
      <p className="eyebrow">Admin</p>
      <h1>Quản trị hệ thống</h1>
      <div className="toolbar">
        <DateRangeFields range={range} onChange={setRange} />
      </div>
      {loading && <p role="status">Đang tải số liệu...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading && overview && <StatCards overview={overview} />}
      <h2>Phân tích dữ liệu</h2>
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
    </>
  );
}
