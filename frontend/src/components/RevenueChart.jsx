import { eachDay } from "./dateRange.js";
import { revenueSeries } from "./dashboard/revenueSeries.js";
import { formatCurrency } from "./formatCurrency.js";

const WIDTH = 760;
const HEIGHT = 280;
const LEFT = 78;
const RIGHT = 20;
const TOP = 22;
const BOTTOM = 40;

// revenue-by-day omits days without DELIVERED orders; show them as 0 so the line keeps real spacing.
export function fillDailyRevenue(from, to, rows) {
  const revenueByDate = new Map(rows.map((row) => [row.date, row.revenue]));
  return eachDay(from, to).map((date) => ({ date, revenue: revenueByDate.get(date) ?? 0 }));
}

export default function RevenueChart({ from, to, rows }) {
  const { points, unit } = revenueSeries(from, to, rows);
  if (points.length === 0) return null;

  const maxRevenue = Math.max(...points.map((point) => point.revenue));
  if (maxRevenue === 0)
    return <p className="dashboard-empty">Chưa có doanh thu giao thành công trong kỳ.</p>;
  const magnitude = 10 ** Math.floor(Math.log10(maxRevenue / 4));
  const tick = Math.ceil(maxRevenue / 4 / magnitude) * magnitude;
  const ceiling = tick * 4;
  const stepX = points.length > 1 ? (WIDTH - LEFT - RIGHT) / (points.length - 1) : 0;
  const coordinates = points.map((point, index) => {
    const x = LEFT + index * stepX;
    const y = HEIGHT - BOTTOM - (point.revenue / ceiling) * (HEIGHT - TOP - BOTTOM);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const label = (date) =>
    unit === "year"
      ? date.slice(0, 4)
      : unit === "month"
        ? `${date.slice(5, 7)}/${date.slice(0, 4)}`
        : `${date.slice(8, 10)}/${date.slice(5, 7)}`;
  const axisValue = (value) =>
    value >= 1000000
      ? `${(value / 1000000).toLocaleString("vi-VN")} tr`
      : value >= 1000
        ? `${(value / 1000).toLocaleString("vi-VN")} nghìn`
        : value;
  const labels = [...new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])];

  return (
    <figure className="revenue-chart">
      <div className="chart-scroll" tabIndex="0" aria-label="Biểu đồ doanh thu có thể cuộn ngang">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={`Doanh thu theo ${unit === "day" ? "ngày" : unit === "month" ? "tháng" : "năm"} từ ${from} đến ${to}`}
        >
          <text className="chart-label" x="8" y="15">
            VND
          </text>
          {[0, 1, 2, 3, 4].map((index) => {
            const y = HEIGHT - BOTTOM - (index / 4) * (HEIGHT - TOP - BOTTOM);
            return (
              <g key={index}>
                <line className="chart-axis" x1={LEFT} y1={y} x2={WIDTH - RIGHT} y2={y} />
                <text className="chart-label" x={LEFT - 10} y={y + 4} textAnchor="end">
                  {axisValue(tick * index)}
                </text>
              </g>
            );
          })}
          {labels.map((index) => (
            <text
              key={index}
              className="chart-label"
              x={LEFT + index * stepX}
              y={HEIGHT - 12}
              textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"}
            >
              {label(points[index].date)}
            </text>
          ))}
          <polyline className="chart-line" points={coordinates.join(" ")} />
          {points.map((point, index) => {
            const [x, y] = coordinates[index].split(",");
            return (
              <circle
                className="chart-point"
                key={point.date}
                cx={x}
                cy={y}
                r="3"
                tabIndex="0"
                aria-label={`${point.date}: ${formatCurrency(point.revenue)}`}
              >
                <title>{`${point.date}: ${formatCurrency(point.revenue)}`}</title>
              </circle>
            );
          })}
        </svg>
      </div>
      <p className="dashboard-footnote chart-scroll-hint">
        Vuốt ngang để xem đủ biểu đồ, hoặc mở bảng số liệu bên dưới.
      </p>
      <figcaption>
        <span>{from}</span>
        <span>Cao nhất: {formatCurrency(maxRevenue)}</span>
        <span>{to}</span>
      </figcaption>
      {unit !== "day" && (
        <p className="dashboard-footnote">
          Gộp theo {unit === "month" ? "tháng" : "năm"}; chỉ tính các ngày nằm trong kỳ đã chọn.
        </p>
      )}
      <details className="chart-data">
        <summary>Xem số liệu biểu đồ</summary>
        <div className="table-wrap">
          <table className="data-table dashboard-table">
            <thead>
              <tr>
                <th>{unit === "day" ? "Ngày" : unit === "month" ? "Tháng" : "Năm"}</th>
                <th>Doanh thu</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.date}>
                  <td>{point.date}</td>
                  <td>{formatCurrency(point.revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
