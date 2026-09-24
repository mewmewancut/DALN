// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../../api/client.js";
import { fillDailyRevenue } from "../../components/RevenueChart.jsx";
import {
  alertText,
  button,
  buttonLabels,
  click,
  dialog,
  field,
  fill,
  mountContainer,
  renderAt,
  routeGet,
  rowContaining,
  setValue,
  signInAs,
  submit,
  unmountContainer,
} from "../../testing/appHarness.jsx";

let container;

beforeEach(() => {
  container = mountContainer();
});

afterEach(async () => {
  await unmountContainer();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const overview = {
  revenue: 1500000,
  order_count: 4,
  cancelled_count: 1,
  cancel_rate: 0.25,
  aov: 750000,
};

function dashboardRoutes(overrides = {}) {
  return {
    "/shop/stats/overview": overview,
    "/shop/stats/revenue-by-day": [],
    "/shop/alerts": [],
    ...overrides,
  };
}

const variants = [
  { id: 1, size: "M", color: "Đỏ", price: 120000, sku: "P5-M-Đỏ", is_active: true, quantity: 3 },
  { id: 2, size: "L", color: "Đỏ", price: 130000, sku: "P5-L-Đỏ", is_active: true, quantity: 4 },
];

const activeProduct = {
  id: 5,
  shop_id: 7,
  shop_name: "Shop A",
  category_id: 3,
  name: "Áo mẫu",
  description: "Mô tả",
  image_url: null,
  base_price: 90000,
  price_from: 120000,
  rating_average: null,
  is_active: true,
  variants,
};

const hiddenProduct = {
  ...activeProduct,
  id: 6,
  name: "Quần cũ",
  is_active: false,
  price_from: null,
  variants: [],
};

function productRoutes() {
  return {
    "/categories": [
      { id: 3, name: "Áo" },
      { id: 4, name: "Quần" },
    ],
    "/shop/products": (options) => ({
      items: [activeProduct, hiddenProduct],
      total: 2,
      page: options.params.page,
      page_size: 20,
    }),
  };
}

it("chủ shop chưa có shop phải tạo shop trước, sau đó vào khu quản lý", async () => {
  signInAs("SHOP_OWNER", null);
  routeGet(dashboardRoutes());
  const post = vi.spyOn(client, "post").mockResolvedValue({ data: { id: 11 } });
  await renderAt("/shop/products");
  expect(container.textContent).toContain("Tạo shop của bạn");
  expect(container.querySelector('nav[aria-label="Quản lý shop"]')).toBeNull();
  expect(client.get).not.toHaveBeenCalled();

  await fill("Tên shop", "Shop Mới");
  await submit(container.querySelector("form"));

  expect(post).toHaveBeenCalledWith("/shops", { name: "Shop Mới", description: null });
  expect(JSON.parse(localStorage.getItem("fashion_auth")).shop_id).toBe(11);
  expect(container.querySelector('nav[aria-label="Quản lý shop"]')).not.toBeNull();
});

it("giữ form tạo shop và hiện lỗi API khi tạo thất bại", async () => {
  signInAs("SHOP_OWNER", null);
  vi.spyOn(client, "post").mockRejectedValue({
    response: { data: { detail: "Bạn đã có shop" } },
  });
  await renderAt("/shop/dashboard");
  await fill("Tên shop", "Shop Mới");
  await submit(container.querySelector("form"));
  expect(alertText()).toBe("Bạn đã có shop");
  expect(JSON.parse(localStorage.getItem("fashion_auth")).shop_id).toBeNull();
  expect(container.textContent).toContain("Tạo shop của bạn");
});

it("dashboard gọi số liệu 30 ngày gần nhất, hiện 4 chỉ số, badge cảnh báo và biểu đồ theo ngày", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 24, 10, 0));
  signInAs("SHOP_OWNER", 7);
  const get = routeGet(
    dashboardRoutes({
      "/shop/stats/revenue-by-day": [{ date: "2026-09-20", revenue: 1500000, order_count: 2 }],
      "/shop/alerts": [{ id: 1 }, { id: 2 }],
    }),
  );
  await renderAt("/shop/dashboard");

  const params = { from: "2026-08-26", to: "2026-09-24" };
  expect(get).toHaveBeenCalledWith("/shop/stats/overview", { params });
  expect(get).toHaveBeenCalledWith("/shop/stats/revenue-by-day", { params });
  expect(container.textContent).toContain("1.500.000 ₫");
  expect(container.textContent).toContain("25%");
  expect(container.textContent).toContain("750.000 ₫");
  expect(container.querySelector(".alert-badge").textContent).toBe("Cảnh báo tồn kho: 2");
  expect(container.querySelector(".alert-badge").getAttribute("href")).toBe("/shop/alerts");
  expect(container.querySelectorAll(".chart-point")).toHaveLength(30);

  await fill("Từ ngày", "2026-09-20");
  expect(get).toHaveBeenCalledWith("/shop/stats/overview", {
    params: { from: "2026-09-20", to: "2026-09-24" },
  });
  expect(container.querySelectorAll(".chart-point")).toHaveLength(5);
});

it("dashboard hiện — khi chưa có mẫu số và báo lỗi API khi khoảng ngày sai", async () => {
  signInAs("SHOP_OWNER", 7);
  const get = routeGet(
    dashboardRoutes({
      "/shop/stats/overview": { ...overview, revenue: 0, cancel_rate: null, aov: null },
    }),
  );
  await renderAt("/shop/dashboard");
  const cards = [...container.querySelectorAll(".stat-card strong")].map(
    (item) => item.textContent,
  );
  expect(cards).toEqual(["0 ₫", "4", "—", "—"]);

  get.mockRejectedValue({
    response: { data: { detail: "Ngày bắt đầu phải trước ngày kết thúc" } },
  });
  await fill("Từ ngày", "2030-01-01");
  expect(alertText()).toBe("Ngày bắt đầu phải trước ngày kết thúc");
  expect(container.querySelector(".stat-grid")).toBeNull();
});

it("biểu đồ điền 0 cho ngày không có đơn giao, kể cả khi qua tháng mới", () => {
  expect(
    fillDailyRevenue("2026-08-30", "2026-09-02", [{ date: "2026-09-01", revenue: 500000 }]),
  ).toEqual([
    { date: "2026-08-30", revenue: 0 },
    { date: "2026-08-31", revenue: 0 },
    { date: "2026-09-01", revenue: 500000 },
    { date: "2026-09-02", revenue: 0 },
  ]);
});

it("danh sách sản phẩm của shop hiện cả sản phẩm đã ẩn, lọc trạng thái và bật/tắt hiển thị", async () => {
  signInAs("SHOP_OWNER", 7);
  const get = routeGet(productRoutes());
  const put = vi.spyOn(client, "put").mockResolvedValue({ data: {} });
  await renderAt("/shop/products");

  const activeRow = rowContaining("Áo mẫu");
  expect(activeRow.textContent).toContain("Áo");
  expect(activeRow.textContent).toContain("120.000 ₫");
  expect(activeRow.textContent).toContain("Đang bán");
  expect(activeRow.querySelectorAll("td")[4].textContent).toBe("7");
  expect(rowContaining("Quần cũ").textContent).toContain("Đã ẩn");

  await click(button("Ẩn", activeRow));
  expect(put).toHaveBeenCalledWith("/products/5", { is_active: false });
  await click(button("Hiện", rowContaining("Quần cũ")));
  expect(put).toHaveBeenCalledWith("/products/6", { is_active: true });

  await fill("Trạng thái", "false");
  expect(get).toHaveBeenLastCalledWith("/shop/products", {
    params: { page: 1, page_size: 20, is_active: "false" },
  });
});

it("tạo sản phẩm gửi thông tin và toàn bộ biến thể trong một request", async () => {
  signInAs("SHOP_OWNER", 7);
  const get = routeGet(productRoutes());
  const post = vi
    .spyOn(client, "post")
    .mockRejectedValueOnce({ response: { data: { detail: "Biến thể bị trùng" } } })
    .mockResolvedValueOnce({ data: { id: 9 } });
  await renderAt("/shop/products");
  await click(button("Thêm sản phẩm"));

  const scope = dialog();
  await fill("Danh mục", "3", { scope });
  await fill("Tên sản phẩm", "Áo mới", { scope });
  await fill("Giá cơ sở (₫)", "100000", { scope });
  await fill("Size", "M", { scope });
  await fill("Màu", "Đỏ", { scope });
  await fill("Giá (₫)", "120000", { scope });
  await fill("Tồn kho ban đầu", "5", { scope });
  await click(button("Thêm biến thể", scope));
  await fill("Size", "L", { scope, index: 1 });
  await fill("Màu", "Xanh", { scope, index: 1 });
  await fill("Giá (₫)", "130000", { scope, index: 1 });

  await submit(scope.querySelector("form"));
  expect(alertText()).toBe("Biến thể bị trùng");
  expect(dialog()).not.toBeNull();

  const callsBefore = get.mock.calls.filter(([url]) => url === "/shop/products").length;
  await submit(scope.querySelector("form"));
  expect(post).toHaveBeenLastCalledWith("/products", {
    category_id: 3,
    name: "Áo mới",
    description: null,
    image_url: null,
    base_price: 100000,
    variants: [
      { size: "M", color: "Đỏ", price: 120000, initial_quantity: 5 },
      { size: "L", color: "Xanh", price: 130000, initial_quantity: 0 },
    ],
  });
  expect(dialog()).toBeNull();
  expect(get.mock.calls.filter(([url]) => url === "/shop/products").length).toBe(callsBefore + 1);
});

it("sửa sản phẩm, giá và trạng thái từng biến thể, thêm biến thể mới", async () => {
  signInAs("SHOP_OWNER", 7);
  routeGet(productRoutes());
  const put = vi.spyOn(client, "put").mockImplementation(async (url, body) => {
    if (url === "/variants/1") return { data: { ...variants[0], ...body } };
    return { data: {} };
  });
  const post = vi.spyOn(client, "post").mockResolvedValue({
    data: {
      id: 3,
      size: "XL",
      color: "Đen",
      price: 140000,
      sku: "P5-XL-Đen",
      is_active: true,
      quantity: 0,
    },
  });
  await renderAt("/shop/products");
  await click(button("Sửa", rowContaining("Áo mẫu")));

  const scope = dialog();
  expect(field("Tên sản phẩm", { scope }).value).toBe("Áo mẫu");
  expect(field("Danh mục", { scope }).value).toBe("3");
  expect(scope.querySelectorAll(".variant-row")).toHaveLength(1);
  await fill("Tên sản phẩm", "Áo mẫu 2", { scope });
  await submit(scope.querySelector("form"));
  expect(put).toHaveBeenCalledWith("/products/5", {
    category_id: 3,
    name: "Áo mẫu 2",
    description: "Mô tả",
    image_url: null,
    base_price: 90000,
  });
  expect(scope.textContent).toContain("Đã lưu thông tin sản phẩm.");

  const variantRow = rowContaining("P5-M-Đỏ", scope);
  expect(button("Lưu giá", variantRow).disabled).toBe(true);
  await setValue(variantRow.querySelector("input"), "125000");
  await click(button("Lưu giá", variantRow));
  expect(put).toHaveBeenCalledWith("/variants/1", { price: 125000 });
  await click(button("Ẩn", variantRow));
  expect(put).toHaveBeenCalledWith("/variants/1", { is_active: false });
  expect(rowContaining("P5-M-Đỏ", scope).textContent).toContain("Đã ẩn");

  await fill("Size mới", "XL", { scope });
  await fill("Màu mới", "Đen", { scope });
  await fill("Giá mới (₫)", "140000", { scope });
  await submit(scope.querySelector('form[aria-label="Thêm biến thể mới"]'));
  expect(post).toHaveBeenCalledWith("/products/5/variants", {
    size: "XL",
    color: "Đen",
    price: 140000,
    initial_quantity: 0,
  });
  expect(rowContaining("P5-XL-Đen", scope)).toBeDefined();
  expect(buttonLabels(rowContaining("P5-XL-Đen", scope))).toEqual(["Lưu giá", "Ẩn"]);
});
