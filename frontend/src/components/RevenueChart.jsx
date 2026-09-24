import { eachDay } from "./dateRange.js";
import { formatCurrency } from "./formatCurrency.js";

const WIDTH = 640;
const HEIGHT = 220;
const PADDING = 24;

// revenue-by-day omits days without DELIVERED orders; show them as 0 so the line keeps real spacing.
export function fillDailyRevenue(from, to, rows) {
  const revenueByDate = new Map(rows.map((row) => [row.date, row.revenue]));
  return eachDay(from, to).map((date) => ({ date, revenue: revenueByDate.get(date) ?? 0 }));
}

export default function RevenueChart({ from, to, rows }) {
  const points = fillDailyRevenue(from, to, rows);
  if (points.length === 0) return null;

  const maxRevenue = Math.max(...points.map((point) => point.revenue));
  const stepX = points.length > 1 ? (WIDTH - PADDING * 2) / (points.length - 1) : 0;
  const coordinates = points.map((point, index) => {
    const x = PADDING + index * stepX;
    const y =
      maxRevenue === 0
        ? HEIGHT - PADDING
        : HEIGHT - PADDING - (point.revenue / maxRevenue) * (HEIGHT - PADDING * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <figure className="revenue-chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Doanh thu theo ngày từ ${from} đến ${to}`}
      >
        <line
          className="chart-axis"
          x1={PADDING}
          y1={HEIGHT - PADDING}
          x2={WIDTH - PADDING}
          y2={HEIGHT - PADDING}
        />
        <polyline className="chart-line" points={coordinates.join(" ")} />
        {points.map((point, index) => {
          const [x, y] = coordinates[index].split(",");
          return (
            <circle className="chart-point" key={point.date} cx={x} cy={y} r="3">
              <title>{`${point.date}: ${formatCurrency(point.revenue)}`}</title>
            </circle>
          );
        })}
      </svg>
      <figcaption>
        <span>{from}</span>
        <span>Cao nhất: {formatCurrency(maxRevenue)}</span>
        <span>{to}</span>
      </figcaption>
    </figure>
  );
}
