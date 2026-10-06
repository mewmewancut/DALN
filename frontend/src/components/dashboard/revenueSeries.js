import { eachDay } from "../dateRange.js";

export function revenueSeries(from, to, rows) {
  const start = new Date(`${from}T00:00:00Z`);
  const end = new Date(`${to}T00:00:00Z`);
  const days = (end - start) / 86400000 + 1;
  const unit = days <= 93 ? "day" : days <= 1096 ? "month" : "year";
  const key = (value) =>
    unit === "day"
      ? value
      : unit === "month"
        ? `${value.slice(0, 7)}-01`
        : `${value.slice(0, 4)}-01-01`;
  const totals = new Map();
  for (const row of rows) {
    if (row.date >= from && row.date <= to)
      totals.set(key(row.date), (totals.get(key(row.date)) ?? 0) + row.revenue);
  }
  const dates = [];
  if (unit === "day") dates.push(...eachDay(from, to));
  else {
    const cursor = new Date(`${key(from)}T00:00:00Z`);
    while (cursor <= end) {
      dates.push(cursor.toISOString().slice(0, 10));
      if (unit === "month") cursor.setUTCMonth(cursor.getUTCMonth() + 1);
      else cursor.setUTCFullYear(cursor.getUTCFullYear() + 1);
    }
  }
  return { unit, points: dates.map((date) => ({ date, revenue: totals.get(date) ?? 0 })) };
}
