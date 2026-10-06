// Complete API response shared by dashboard and role-routing tests.
export function dashboardFixture(params, overrides = {}) {
  const overview = { revenue: 0, order_count: 0, cancelled_count: 0, cancel_rate: null, aov: null };
  const start = new Date(`${params.from}T00:00:00Z`);
  const days = (new Date(`${params.to}T00:00:00Z`) - start) / 86400000 + 1;
  const dateAt = (offset) => new Date(+start + offset * 86400000).toISOString().slice(0, 10);
  return {
    from_date: params.from,
    to_date: params.to,
    previous_from: dateAt(-days),
    previous_to: dateAt(-1),
    generated_at: "2026-09-24T03:00:00Z",
    overview,
    previous: overview,
    revenue_daily: [],
    order_statuses: ["PENDING", "CONFIRMED", "PREPARING", "SHIPPING", "DELIVERED", "CANCELLED"].map(
      (status) => ({ status, count: 0 }),
    ),
    work_queue: ["PENDING", "CONFIRMED", "PREPARING", "SHIPPING"].map((status) => ({
      status,
      count: 0,
    })),
    top_products: [],
    stock: { tracked_variants: 0, out_of_stock: 0, low_stock: 0, priorities: [] },
    shops: [],
    ...overrides,
  };
}
