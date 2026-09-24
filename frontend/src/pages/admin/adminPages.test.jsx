// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../../api/client.js";
import {
  alertText,
  button,
  click,
  field,
  fill,
  mountContainer,
  renderAt,
  routeGet,
  rowContaining,
  signInAs,
  unmountContainer,
} from "../../testing/appHarness.jsx";

let container;

beforeEach(() => {
  container = mountContainer();
  signInAs("ADMIN");
});

afterEach(async () => {
  await unmountContainer();
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

const overview = {
  revenue: 5000000,
  order_count: 20,
  cancelled_count: 2,
  cancel_rate: 0.1,
  aov: 625000,
};

const users = [
  {
    id: 1,
    email: "admin@shop.vn",
    full_name: "Quản trị",
    role: "ADMIN",
    is_active: true,
    created_at: "2026-09-01T00:00:00Z",
  },
  {
    id: 2,
    email: "buyer1@shop.vn",
    full_name: "Người mua 1",
    role: "BUYER",
    is_active: true,
    created_at: "2026-09-02T00:00:00Z",
  },
];

const shops = [
  {
    id: 13,
    owner_id: 4,
    name: "Shop 1",
    description: null,
    is_active: true,
    created_at: "2026-09-01T00:00:00Z",
  },
  {
    id: 14,
    owner_id: 5,
    name: "Shop 2",
    description: null,
    is_active: false,
    created_at: "2026-09-01T00:00:00Z",
  },
];

function page(items) {
  return (options) => ({ items, total: items.length, page: options.params.page, page_size: 20 });
}

it("chỉ admin vào được khu quản trị; vai trò khác bị đưa về trang của mình", async () => {
  signInAs("SHOP_OWNER", 7);
  routeGet({
    "/shop/stats/overview": overview,
    "/shop/stats/revenue-by-day": [],
    "/shop/alerts": [],
  });
  await renderAt("/admin/users");
  expect(container.textContent).toContain("Tổng quan shop");
  expect(container.querySelector('nav[aria-label="Quản trị"]')).toBeNull();
});

it("dashboard admin gọi số liệu toàn hệ thống 30 ngày gần nhất và báo lỗi API", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 24, 10, 0));
  const get = routeGet({ "/admin/stats/overview": overview });
  await renderAt("/admin");

  expect(container.textContent).toContain("Quản trị hệ thống");
  expect(get).toHaveBeenCalledWith("/admin/stats/overview", {
    params: { from: "2026-08-26", to: "2026-09-24" },
  });
  const cards = [...container.querySelectorAll(".stat-card strong")].map(
    (item) => item.textContent,
  );
  expect(cards).toEqual(["5.000.000 ₫", "20", "10%", "625.000 ₫"]);
  const navLinks = [...container.querySelectorAll('nav[aria-label="Quản trị"] a')];
  expect(navLinks.map((link) => link.getAttribute("href"))).toEqual([
    "/admin/dashboard",
    "/admin/users",
    "/admin/shops",
    "/admin/orders",
  ]);

  get.mockRejectedValue({ response: { data: { detail: "'from' phải nhỏ hơn hoặc bằng 'to'" } } });
  await fill("Từ ngày", "2030-01-01");
  expect(alertText()).toBe("'from' phải nhỏ hơn hoặc bằng 'to'");
  expect(container.querySelector(".stat-grid")).toBeNull();
});

it("không hiện link Databricks khi chưa cấu hình, hiện link mở tab mới khi đã cấu hình", async () => {
  vi.stubEnv("VITE_DATABRICKS_DASHBOARD_URL", "");
  vi.stubEnv("VITE_DATABRICKS_GENIE_URL", "");
  routeGet({ "/admin/stats/overview": overview });
  await renderAt("/admin/dashboard");
  const links = container.querySelector(".analytics-links");
  expect(links.querySelectorAll("a")).toHaveLength(0);
  expect(links.textContent).toContain("Databricks Dashboard: chưa được cấu hình");
  expect(links.textContent).toContain("Genie: chưa được cấu hình");

  await unmountContainer();
  container = mountContainer();
  signInAs("ADMIN");
  vi.stubEnv("VITE_DATABRICKS_DASHBOARD_URL", "https://example.cloud.databricks.com/dash");
  vi.stubEnv("VITE_DATABRICKS_GENIE_URL", "https://example.cloud.databricks.com/genie");
  await renderAt("/admin/dashboard");
  const anchors = [...container.querySelectorAll(".analytics-links a")];
  expect(anchors.map((anchor) => [anchor.textContent, anchor.getAttribute("href")])).toEqual([
    ["Mở Databricks Dashboard", "https://example.cloud.databricks.com/dash"],
    ["Mở Genie", "https://example.cloud.databricks.com/genie"],
  ]);
  expect(anchors.every((anchor) => anchor.target === "_blank" && anchor.rel === "noreferrer")).toBe(
    true,
  );
});

it("người dùng: lọc theo vai trò và từ khóa, khóa/mở theo response, hiện lỗi tự khóa", async () => {
  const get = routeGet({ "/admin/users": page(users) });
  const patch = vi
    .spyOn(client, "patch")
    .mockResolvedValueOnce({ data: { ...users[1], is_active: false } })
    .mockRejectedValueOnce({
      response: { data: { detail: "Không thể tự khóa tài khoản của chính mình" } },
    });
  await renderAt("/admin/users");

  expect(rowContaining("buyer1@shop.vn").textContent).toContain("Người mua");
  await fill("Vai trò", "BUYER");
  await fill("Tìm email hoặc họ tên", " buyer1 ");
  expect(get).toHaveBeenLastCalledWith("/admin/users", {
    params: { page: 1, page_size: 20, role: "BUYER", keyword: "buyer1" },
  });

  await click(button("Khóa", rowContaining("buyer1@shop.vn")));
  expect(patch).toHaveBeenCalledWith("/admin/users/2", { is_active: false });
  const lockedRow = rowContaining("buyer1@shop.vn");
  expect(lockedRow.textContent).toContain("Đã khóa");
  expect(button("Mở khóa", lockedRow)).toBeDefined();

  await click(button("Khóa", rowContaining("admin@shop.vn")));
  expect(patch).toHaveBeenLastCalledWith("/admin/users/1", { is_active: false });
  expect(alertText()).toBe("Không thể tự khóa tài khoản của chính mình");
  expect(rowContaining("admin@shop.vn").textContent).toContain("Hoạt động");

  get.mockRejectedValueOnce({ response: { data: { detail: "Không tải được người dùng" } } });
  await fill("Vai trò", "ADMIN");
  expect(alertText()).toBe("Không tải được người dùng");
  expect(rowContaining("admin@shop.vn")).toBeUndefined();
});

it("shop: khóa và mở khóa theo response, hiện lỗi từ API", async () => {
  const get = routeGet({ "/admin/shops": page(shops) });
  const patch = vi
    .spyOn(client, "patch")
    .mockResolvedValueOnce({ data: { ...shops[1], is_active: true } })
    .mockRejectedValueOnce({ response: { data: { detail: "Không tìm thấy shop" } } });
  await renderAt("/admin/shops");

  expect(rowContaining("Shop 2").textContent).toContain("Đã khóa");
  await fill("Tìm theo tên shop", " Shop 2 ");
  await fill("Trạng thái", "false");
  expect(get).toHaveBeenLastCalledWith("/admin/shops", {
    params: { page: 1, page_size: 20, keyword: "Shop 2", is_active: "false" },
  });
  await click(button("Xóa bộ lọc"));
  expect(get).toHaveBeenLastCalledWith("/admin/shops", {
    params: { page: 1, page_size: 20 },
  });

  await click(button("Mở khóa", rowContaining("Shop 2")));
  expect(patch).toHaveBeenCalledWith("/admin/shops/14", { is_active: true });
  expect(rowContaining("Shop 2").textContent).toContain("Hoạt động");

  await click(button("Khóa", rowContaining("Shop 1")));
  expect(patch).toHaveBeenLastCalledWith("/admin/shops/13", { is_active: false });
  expect(alertText()).toBe("Không tìm thấy shop");
  expect(rowContaining("Shop 1").textContent).toContain("Hoạt động");
});

it("shop không giữ dữ liệu trang cũ khi tải trang mới thất bại", async () => {
  let request = 0;
  vi.spyOn(client, "get").mockImplementation(async (url, options) => {
    if (url !== "/admin/shops") throw new Error(`GET ${url} chưa được mock`);
    request += 1;
    if (request > 1) {
      throw { response: { data: { detail: "Không tải được shop" } } };
    }
    return {
      data: { items: [shops[0]], total: 21, page: options.params.page, page_size: 20 },
    };
  });

  await renderAt("/admin/shops");
  expect(rowContaining("Shop 1")).not.toBeUndefined();
  await click(button("Trang sau"));

  expect(alertText()).toBe("Không tải được shop");
  expect(rowContaining("Shop 1")).toBeUndefined();
});

it("đơn toàn hệ thống: lọc theo shop, trạng thái, khoảng ngày và hiện tên shop", async () => {
  const get = routeGet({
    "/admin/shops": page(shops),
    "/admin/orders": page([
      {
        id: 1,
        code: "ORD-20260922-0001",
        buyer_id: 22,
        shop_id: 13,
        status: "DELIVERED",
        payment_method: "COD",
        payment_status: "PAID",
        total_amount: 878000,
        created_at: "2026-09-22T12:00:00Z",
      },
    ]),
  });
  await renderAt("/admin/orders");

  expect(get).toHaveBeenCalledWith("/admin/shops", { params: { page: 1, page_size: 100 } });
  expect(get).toHaveBeenCalledWith("/admin/orders", { params: { page: 1, page_size: 20 } });
  const row = rowContaining("ORD-20260922-0001");
  expect(row.textContent).toContain("Shop 1");
  expect(row.textContent).toContain("878.000 ₫");
  expect(row.textContent).toContain("Đã giao");
  expect([...field("Shop").options].map((option) => option.textContent)).toEqual([
    "Tất cả shop",
    "Shop 1",
    "Shop 2",
  ]);

  await fill("Shop", "13");
  await fill("Trạng thái", "DELIVERED");
  await fill("Từ ngày", "2026-09-01");
  await fill("Đến ngày", "2026-09-24");
  expect(get).toHaveBeenLastCalledWith("/admin/orders", {
    params: {
      page: 1,
      page_size: 20,
      shop_id: "13",
      status: "DELIVERED",
      from: "2026-09-01",
      to: "2026-09-24",
    },
  });

  await click(button("Xóa bộ lọc"));
  expect(field("Shop").value).toBe("");
  expect(field("Trạng thái").value).toBe("");
  expect(field("Từ ngày").value).toBe("");
  expect(field("Đến ngày").value).toBe("");
  expect(get).toHaveBeenLastCalledWith("/admin/orders", {
    params: { page: 1, page_size: 20 },
  });
});

it("bộ lọc đơn admin tải đủ shop qua nhiều trang", async () => {
  const firstPage = Array.from({ length: 100 }, (_, index) => ({
    id: index + 1,
    name: `Shop ${index + 1}`,
  }));
  const lastShop = { id: 101, name: "Shop 101" };
  const get = vi.spyOn(client, "get").mockImplementation(async (url, options) => {
    if (url === "/admin/orders") {
      return { data: { items: [], total: 0, page: 1, page_size: 20 } };
    }
    if (url === "/admin/shops" && options.params.page === 1) {
      return {
        data: { items: firstPage, total: 101, page: 1, page_size: 100 },
      };
    }
    if (url === "/admin/shops" && options.params.page === 2) {
      return {
        data: { items: [lastShop], total: 101, page: 2, page_size: 100 },
      };
    }
    throw new Error(`GET ${url} chưa được mock`);
  });

  await renderAt("/admin/orders");

  expect(get).toHaveBeenCalledWith("/admin/shops", { params: { page: 1, page_size: 100 } });
  expect(get).toHaveBeenCalledWith("/admin/shops", { params: { page: 2, page_size: 100 } });
  expect([...field("Shop").options]).toHaveLength(102);
  expect([...field("Shop").options].at(-1).textContent).toBe("Shop 101");
});

it("lỗi tải shop không bị request danh sách đơn ghi đè", async () => {
  vi.spyOn(client, "get").mockImplementation(async (url) => {
    if (url === "/admin/shops") {
      throw { response: { data: { detail: "Không tải được shop" } } };
    }
    return { data: { items: [], total: 0, page: 1, page_size: 20 } };
  });

  await renderAt("/admin/orders");

  expect(alertText()).toContain("Không tải được danh sách shop: Không tải được shop");
  expect(field("Shop").disabled).toBe(true);
  expect(container.textContent).toContain("Không có đơn hàng phù hợp");
});
