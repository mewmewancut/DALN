import { formatCurrency } from "./formatCurrency.js";

export function formatRate(rate) {
  if (rate == null) return "—";
  return `${(rate * 100).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`;
}

// Renders the C9 overview metrics shared by the shop and admin dashboards.
function Comparison({ value, previous, rate = false }) {
  if (value == null || previous == null)
    return <small className="stat-comparison">Chưa đủ dữ liệu so sánh</small>;
  if (!rate && previous === 0)
    return (
      <small className="stat-comparison">
        {value === 0 ? "Không đổi so với kỳ trước" : "Phát sinh mới · kỳ trước bằng 0"}
      </small>
    );
  const change = rate ? (value - previous) * 100 : ((value - previous) * 100) / previous;
  const text = Math.abs(change).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
  return (
    <small className="stat-comparison">
      {change === 0 ? "Không đổi" : `${change > 0 ? "↑" : "↓"} ${text}${rate ? " điểm %" : "%"}`} so
      với kỳ trước
    </small>
  );
}

export default function StatCards({ overview, previous }) {
  return (
    <div className="stat-grid">
      <article className="stat-card">
        <span>Doanh thu</span>
        <strong>{formatCurrency(overview.revenue)}</strong>
        {previous && (
          <>
            <small>Đơn đã giao trong kỳ</small>
            <Comparison value={overview.revenue} previous={previous.revenue} />
          </>
        )}
      </article>
      <article className="stat-card">
        <span>Số đơn</span>
        <strong>{overview.order_count}</strong>
        {previous && (
          <>
            <small>Đơn được tạo trong kỳ</small>
            <Comparison value={overview.order_count} previous={previous.order_count} />
          </>
        )}
      </article>
      <article className="stat-card">
        <span>Tỷ lệ hủy</span>
        <strong>{formatRate(overview.cancel_rate)}</strong>
        {previous && (
          <>
            <small>
              {overview.cancelled_count} đơn hủy / {overview.order_count} đơn tạo
            </small>
            <Comparison value={overview.cancel_rate} previous={previous.cancel_rate} rate />
          </>
        )}
      </article>
      <article className="stat-card">
        <span>Giá trị đơn trung bình</span>
        <strong>{overview.aov == null ? "—" : formatCurrency(Math.round(overview.aov))}</strong>
        {previous && (
          <>
            <small>Trung bình đơn giao trong kỳ</small>
            <Comparison value={overview.aov} previous={previous.aov} />
          </>
        )}
      </article>
    </div>
  );
}
