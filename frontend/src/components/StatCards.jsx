import { formatCurrency } from "./formatCurrency.js";

function formatRate(rate) {
  if (rate == null) return "—";
  return `${(rate * 100).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`;
}

// Renders the C9 overview metrics shared by the shop and admin dashboards.
export default function StatCards({ overview }) {
  return (
    <div className="stat-grid">
      <article className="stat-card">
        <span>Doanh thu</span>
        <strong>{formatCurrency(overview.revenue)}</strong>
      </article>
      <article className="stat-card">
        <span>Số đơn</span>
        <strong>{overview.order_count}</strong>
      </article>
      <article className="stat-card">
        <span>Tỷ lệ hủy</span>
        <strong>{formatRate(overview.cancel_rate)}</strong>
      </article>
      <article className="stat-card">
        <span>Giá trị đơn trung bình</span>
        <strong>{overview.aov == null ? "—" : formatCurrency(Math.round(overview.aov))}</strong>
      </article>
    </div>
  );
}
