// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../../api/client.js";
import {
  button,
  click,
  fill,
  mountContainer,
  renderAt,
  routeGet,
  signInAs,
  unmountContainer,
} from "../../testing/appHarness.jsx";
import { dashboardFixture } from "../../testing/dashboardFixture.js";
import { revenueSeries } from "./revenueSeries.js";

let container;
beforeEach(() => {
  container = mountContainer();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 24, 10));
});
afterEach(async () => {
  await unmountContainer();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const overview = {
  revenue: 1000000,
  order_count: 4,
  cancelled_count: 1,
  cancel_rate: 0.25,
  aov: 500000,
};
const stock = {
  tracked_variants: 12,
  out_of_stock: 1,
  low_stock: 2,
  priorities: [
    {
      variant_id: 1,
      product_name: "Áo cần nhập",
      shop_name: "Shop A",
      size: "M",
      color: "Đỏ",
      quantity: 0,
      threshold: 5,
      sold_quantity: 7,
    },
  ],
};

function mockDashboard(role, overrides = {}) {
  signInAs(role, role === "SHOP_OWNER" ? 7 : null);
  return routeGet({
    [role === "ADMIN" ? "/admin/stats/dashboard" : "/shop/stats/dashboard"]: ({ params }) =>
      dashboardFixture(params, overrides),
  });
}

it("shop sees period sales, current backlog and actionable stock without admin ranking", async () => {
  mockDashboard("SHOP_OWNER", {
    overview,
    stock,
    order_statuses: [
      { status: "PENDING", count: 1 },
      { status: "DELIVERED", count: 3 },
    ],
    work_queue: [{ status: "PENDING", count: 9 }],
    top_products: [
      {
        product_id: 1,
        product_name: "Áo bán chạy",
        shop_name: "Shop A",
        total_quantity_sold: 10,
        total_revenue: 800000,
      },
    ],
  });
  await renderAt("/shop/dashboard");
  expect(container.textContent).toContain("2026-07-27 → 2026-08-25");
  expect(container.textContent).toContain("Trạng thái đơn tạo trong kỳ");
  expect(container.textContent).toContain("gồm cả đơn được tạo trước kỳ");
  expect(container.querySelector(".work-queue strong").textContent).toBe("9");
  expect(container.textContent).toContain("10 sản phẩm");
  expect(container.textContent).toContain("800.000 ₫ doanh thu");
  expect(container.querySelector(".stock-summary").textContent).toContain(
    "12 biến thể đang theo dõi",
  );
  expect(container.querySelector(".dashboard-table tbody tr").textContent).toContain(
    "Áo cần nhậpM · ĐỏHết hàng57",
  );
  expect(container.querySelector('a[href="/shop/inventory"]')).not.toBeNull();
  expect(container.querySelector('a[href="/shop/orders"]')).not.toBeNull();
  expect(container.textContent).not.toContain("Shop đóng góp doanh thu");
});

it("admin ranking uses all-system revenue for contribution and shows each shop's quality", async () => {
  mockDashboard("ADMIN", {
    overview,
    stock,
    shops: [
      {
        shop_id: 7,
        shop_name: "Shop A",
        revenue: 600000,
        order_count: 4,
        cancelled_count: 1,
        cancel_rate: 0.25,
        aov: 300000,
      },
    ],
  });
  await renderAt("/admin/dashboard");
  expect(container.textContent).toMatch(/60% doanh thu toàn\s+hệ thống/);
  const ranking = container.querySelector(".shop-performance-grid");
  expect(ranking.textContent).toContain("600.000 ₫");
  expect(ranking.querySelector("tbody tr").textContent).toBe("Shop A4125%300.000 ₫");
  expect(container.querySelector('a[href="/admin/orders"]')).not.toBeNull();
  expect(container.querySelector('a[href="/admin/shops"]')).not.toBeNull();
  expect(container.querySelector('a[href="/shop/inventory"]')).toBeNull();
});

it("compares percentage points for cancellations and handles zero/null denominators", async () => {
  mockDashboard("SHOP_OWNER", {
    overview,
    previous: { revenue: 0, order_count: 2, cancelled_count: 1, cancel_rate: 0.5, aov: null },
  });
  await renderAt("/shop/dashboard");
  const cards = [...container.querySelectorAll(".stat-card")];
  expect(cards[0].textContent).toContain("Phát sinh mới · kỳ trước bằng 0");
  expect(cards[1].textContent).toContain("↑ 100%");
  expect(cards[2].textContent).toContain("↓ 25 điểm %");
  expect(cards[3].textContent).toContain("Chưa đủ dữ liệu so sánh");
  expect(container.textContent).not.toContain("Infinity");
});

it("presets and refresh fetch the selected period; incomplete dates hide stale data", async () => {
  const get = mockDashboard("SHOP_OWNER", { overview });
  await renderAt("/shop/dashboard");
  await click(button("7 ngày"));
  expect(get).toHaveBeenLastCalledWith("/shop/stats/dashboard", {
    params: { from: "2026-09-18", to: "2026-09-24" },
  });
  const count = get.mock.calls.length;
  await click(button("Làm mới số liệu"));
  expect(get.mock.calls.length).toBe(count + 1);
  await click(button("90 ngày"));
  expect(get).toHaveBeenLastCalledWith("/shop/stats/dashboard", {
    params: { from: "2026-06-27", to: "2026-09-24" },
  });
  const beforeClear = get.mock.calls.length;
  await fill("Từ ngày", "");
  expect(get.mock.calls.length).toBe(beforeClear);
  expect(container.querySelector(".stat-grid")).toBeNull();
  expect(container.textContent).toContain("Chọn đủ ngày");
});

it("ignores an old request that resolves after the selected period has changed", async () => {
  signInAs("SHOP_OWNER", 7);
  let resolveOld;
  vi.spyOn(client, "get")
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
    )
    .mockImplementation(async (_, { params }) => ({
      data: dashboardFixture(params, { overview }),
    }));
  await renderAt("/shop/dashboard");
  expect(container.textContent).toContain("Đang tải");
  expect(button("Làm mới số liệu").disabled).toBe(true);
  await click(button("7 ngày"));
  expect(container.querySelector(".stat-card strong").textContent).toBe("1.000.000 ₫");
  await act(async () =>
    resolveOld({ data: dashboardFixture({ from: "2026-08-26", to: "2026-09-24" }) }),
  );
  expect(container.querySelector(".stat-card strong").textContent).toBe("1.000.000 ₫");
  expect(container.textContent).toContain("2026-09-11 → 2026-09-17");
});

it("indicates the selected preset and clears it when the dates become custom", async () => {
  mockDashboard("SHOP_OWNER");
  await renderAt("/shop/dashboard");
  expect(button("30 ngày").getAttribute("aria-pressed")).toBe("true");
  await click(button("7 ngày"));
  expect(button("7 ngày").getAttribute("aria-pressed")).toBe("true");
  expect(button("30 ngày").getAttribute("aria-pressed")).toBe("false");
  await fill("Từ ngày", "2026-09-01");
  expect(
    [...container.querySelectorAll(".dashboard-presets button")].every(
      (node) => node.getAttribute("aria-pressed") === "false",
    ),
  ).toBe(true);
});

it("empty data shows zero totals, undefined ratios and explanations without a fake chart", async () => {
  mockDashboard("ADMIN");
  await renderAt("/admin/dashboard");
  expect(
    [...container.querySelectorAll(".stat-card strong")].map((node) => node.textContent),
  ).toEqual(["0 ₫", "0", "—", "—"]);
  expect(container.querySelector(".revenue-chart")).toBeNull();
  expect(container.textContent).toContain("Chưa có doanh thu giao thành công trong kỳ.");
  expect(container.textContent).toContain("Chưa có đơn được tạo trong kỳ.");
  expect(container.textContent).toContain("Chưa có sản phẩm được giao thành công trong kỳ.");
});

it("chart exposes VND values, zero days and an accessible data table", async () => {
  mockDashboard("SHOP_OWNER", { revenue_daily: [{ date: "2026-09-24", revenue: 1234567 }] });
  await renderAt("/shop/dashboard");
  const chart = container.querySelector(".revenue-chart");
  expect(chart.querySelector("svg").textContent).toContain("VND");
  expect(chart.querySelectorAll(".chart-point")).toHaveLength(30);
  expect(chart.querySelector('.chart-point[aria-label="2026-09-24: 1.234.567 ₫"]')).not.toBeNull();
  expect(chart.querySelector("tbody tr").textContent).toBe("2026-08-260 ₫");
  expect(chart.querySelector("summary").textContent).toBe("Xem số liệu biểu đồ");
});

it("monthly grouping includes only selected days and fills months without deliveries", () => {
  expect(
    revenueSeries("2026-08-20", "2026-12-02", [
      { date: "2026-08-19", revenue: 100 },
      { date: "2026-08-20", revenue: 20 },
      { date: "2026-08-31", revenue: 30 },
      { date: "2026-12-02", revenue: 40 },
      { date: "2026-12-03", revenue: 100 },
    ]),
  ).toEqual({
    unit: "month",
    points: [
      { date: "2026-08-01", revenue: 50 },
      { date: "2026-09-01", revenue: 0 },
      { date: "2026-10-01", revenue: 0 },
      { date: "2026-11-01", revenue: 0 },
      { date: "2026-12-01", revenue: 40 },
    ],
  });
});

it("wide ranges use yearly totals and keep zero years including leap years", () => {
  const result = revenueSeries("2023-12-31", "2027-01-01", [{ date: "2024-02-29", revenue: 10 }]);
  expect(result.unit).toBe("year");
  expect(result.points).toEqual(
    [2023, 2024, 2025, 2026, 2027].map((year) => ({
      date: `${year}-01-01`,
      revenue: year === 2024 ? 10 : 0,
    })),
  );
});
