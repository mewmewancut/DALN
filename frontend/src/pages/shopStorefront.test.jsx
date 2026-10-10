// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../api/client.js";
import {
  mountContainer,
  unmountContainer,
  renderAt,
  routeGet,
  signInAs,
  click,
  button,
  fill,
} from "../testing/appHarness.jsx";

let container;
const shop = {
  id: 7,
  name: "Lụa Việt",
  description: "Chất liệu tự nhiên\nThiết kế Việt",
  created_at: "2026-09-30T20:00:00Z",
};
const product = {
  id: 31,
  shop_id: 7,
  shop_name: shop.name,
  name: "Áo linen",
  image_url: null,
  price_from: 180000,
  rating_average: null,
  variants: [{ id: 21, color: "Đen", size: "M", price: 180000, quantity: 3 }],
};
const page = { items: [product], total: 21, page: 1, page_size: 20 };
const order = {
  id: 9,
  code: "ORD-TEST-9",
  shop_id: 7,
  status: "DELIVERED",
  created_at: "2026-10-01T00:00:00Z",
  total_amount: 180000,
  receiver_name: "Người nhận",
  receiver_phone: "0900000000",
  shipping_address: "Địa chỉ mẫu",
  payment_method: "COD",
  payment_status: "PAID",
  items: [
    {
      id: 41,
      product_name: "Tên áo lúc mua",
      size: "M",
      color: "Đen",
      quantity: 1,
      unit_price: 180000,
      review_id: null,
    },
  ],
  status_history: [],
};

beforeEach(() => {
  container = mountContainer();
});
afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

function mockRoutes(extra = {}) {
  return routeGet({
    "/shops/7": shop,
    "/shops/8": { ...shop, id: 8, name: "Shop thứ hai" },
    "/categories": [{ id: 1, name: "Áo" }],
    "/products": page,
    "/wishlist": [],
    "/products/31": product,
    "/products/31/reviews": { items: [], total: 0 },
    "/orders/9": order,
    "/orders/my": { items: [order], total: 1, page: 1, page_size: 20 },
    ...extra,
  });
}

function deferred() {
  let resolve, reject;
  const promise = new Promise((success, failure) => {
    resolve = success;
    reject = failure;
  });
  return { promise, resolve, reject };
}

it.each([null, "BUYER"])(
  "opens the public shop as %s with safe profile, date in Vietnam and scoped products",
  async (role) => {
    if (role) signInAs(role);
    const get = mockRoutes({
      "/shops/7": { ...shop, description: "<img src=x onerror=alert(1)>" },
    });
    await renderAt("/shops/7");
    expect(container.querySelector("h1").textContent).toBe(shop.name);
    expect(container.textContent).toContain("Tham gia từ tháng 10, 2026");
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
    expect(container.querySelector(".shop-storefront-description img")).toBeNull();
    expect(container.textContent).toContain("180.000");
    expect(get).toHaveBeenCalledWith("/products", {
      params: { shop_id: 7, sort: "newest", page: 1, page_size: 20 },
    });
    expect(get.mock.calls.some(([url]) => url.includes("recommendations"))).toBe(false);
    expect(container.querySelector('.product-card a[href="/shops/7"]')).not.toBeNull();
    expect(container.querySelector("a a")).toBeNull();
  },
);

it("keeps all filters and pagination inside the shop, resets page and clears filters", async () => {
  const get = mockRoutes();
  await renderAt("/shops/7");
  await click(button("Trang sau"));
  expect(get.mock.calls.at(-1)[1].params).toMatchObject({ shop_id: 7, page: 2 });
  await fill("Tìm sản phẩm", "linen");
  await fill("Danh mục", "1");
  await fill("Giá từ (₫)", "100000");
  await fill("Giá đến (₫)", "250000");
  await fill("Sắp xếp", "price_asc");
  expect(get.mock.calls.at(-1)[1].params).toEqual({
    shop_id: 7,
    keyword: "linen",
    category_id: "1",
    min_price: "100000",
    max_price: "250000",
    sort: "price_asc",
    page: 1,
    page_size: 20,
  });
  await click(button("Xóa lọc"));
  expect(get.mock.calls.at(-1)[1].params).toEqual({
    shop_id: 7,
    sort: "newest",
    page: 1,
    page_size: 20,
  });
});

it("restores URL filters and ignores an attempted shop override", async () => {
  const get = mockRoutes();
  await renderAt(
    "/shops/7?shop_id=8&keyword=linen&category_id=1&min_price=100000&max_price=250000&sort=price_desc&page=2",
  );
  expect(get.mock.calls.at(-1)[1].params).toEqual({
    shop_id: 7,
    keyword: "linen",
    category_id: "1",
    min_price: "100000",
    max_price: "250000",
    sort: "price_desc",
    page: 2,
    page_size: 20,
  });
  expect(button("Trang trước").disabled).toBe(false);
});

it("normalizes invalid URL sort and page", async () => {
  const get = mockRoutes();
  await renderAt("/shops/7?sort=unsafe&page=-2");
  expect(get.mock.calls.at(-1)[1].params).toMatchObject({ sort: "newest", page: 1, shop_id: 7 });
});

it("shows shop loading before requesting any catalog", async () => {
  const pending = deferred();
  const get = mockRoutes();
  const original = get.getMockImplementation();
  get.mockImplementation((url, options) =>
    url === "/shops/7" ? pending.promise : original(url, options),
  );
  await renderAt("/shops/7");
  expect(container.querySelector('[role="status"]').textContent).toContain("Đang tải gian hàng");
  expect(get).not.toHaveBeenCalledWith("/products", expect.anything());
  await act(async () => pending.resolve({ data: shop }));
  expect(container.querySelector("h1").textContent).toBe(shop.name);
});

it("distinguishes empty shop from filtered empty results and supports mobile filters", async () => {
  mockRoutes({
    "/shops/7": { ...shop, description: null },
    "/products": { ...page, items: [], total: 0 },
  });
  await renderAt("/shops/7");
  expect(container.textContent).toContain("Shop chưa cập nhật phần giới thiệu");
  expect(container.textContent).toContain("Shop chưa có sản phẩm đang bán");
  expect(button("Trang sau").disabled).toBe(true);
  const toggle = container.querySelector(".filter-toggle");
  await click(toggle);
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(container.querySelector("#catalog-filters").classList.contains("is-open")).toBe(true);
  await fill("Tìm sản phẩm", "không có");
  expect(container.textContent).toContain("Không tìm thấy sản phẩm phù hợp");
  await click(button("Xóa bộ lọc"));
  expect(container.textContent).toContain("Shop chưa có sản phẩm đang bán");
});

it.each(["0", "-1", "abc", "1.5", "9007199254740992"])(
  "rejects invalid shop route %s without making requests",
  async (id) => {
    const get = mockRoutes();
    await renderAt(`/shops/${id}`);
    expect(container.textContent).toContain("Gian hàng không khả dụng");
    expect(get).not.toHaveBeenCalled();
  },
);

it("shows unavailable shop without catalog calls", async () => {
  const get = mockRoutes();
  get.mockRejectedValue({ response: { status: 404 } });
  await renderAt("/shops/7");
  expect(container.textContent).toContain("Gian hàng không khả dụng");
  expect(container.textContent).toContain("lịch sử đơn hàng");
  expect(get.mock.calls.map(([url]) => url)).toEqual(["/shops/7"]);
});

it("shows network failure and retries the profile", async () => {
  const get = mockRoutes();
  get.mockRejectedValueOnce({ response: { status: 503, data: { detail: "Tạm mất kết nối" } } });
  await renderAt("/shops/7");
  expect(container.querySelector('[role="alert"]').textContent).toContain("Tạm mất kết nối");
  expect(container.textContent).not.toContain("Gian hàng không khả dụng");
  await click(button("Thử lại"));
  expect(container.querySelector("h1").textContent).toBe(shop.name);
});

it("shows category failure independently and retries product failures without an empty success", async () => {
  const get = mockRoutes();
  const original = get.getMockImplementation();
  let fail = true;
  get.mockImplementation((url, options) => {
    if (url === "/categories")
      return Promise.reject({ response: { data: { detail: "Danh mục lỗi" } } });
    if (url === "/products" && fail)
      return Promise.reject({ response: { data: { detail: "Sản phẩm lỗi" } } });
    return original(url, options);
  });
  await renderAt("/shops/7");
  expect(container.textContent).toContain("Không tải được danh mục");
  expect(container.textContent).toContain("Sản phẩm lỗi");
  expect(container.textContent).not.toContain("Shop chưa có sản phẩm đang bán");
  expect(button("Trang sau").disabled).toBe(true);
  fail = false;
  await click(button("Thử lại"));
  expect(container.textContent).toContain("Áo linen");
});

it("drops late profile and product responses when navigating to another shop and resets filters", async () => {
  const pending = deferred();
  const get = mockRoutes();
  const original = get.getMockImplementation();
  get.mockImplementation((url, options) =>
    url === "/products" && options.params.shop_id === 7 ? pending.promise : original(url, options),
  );
  await renderAt("/shops/7?keyword=linen", ["/shops/8"]);
  await click(container.querySelector('[aria-label="Test navigation"] a'));
  expect(container.querySelector("h1").textContent).toBe("Shop thứ hai");
  expect(get.mock.calls.at(-1)[1].params).toMatchObject({ shop_id: 8, page: 1 });
  expect(get.mock.calls.at(-1)[1].params.keyword).toBeUndefined();
  await act(async () =>
    pending.resolve({ data: { ...page, items: [{ ...product, name: "Sản phẩm cũ trả trễ" }] } }),
  );
  expect(container.textContent).not.toContain("Sản phẩm cũ trả trễ");
});

it("ignores late profile failures from a previous shop", async () => {
  const pending = deferred();
  const get = mockRoutes();
  const original = get.getMockImplementation();
  get.mockImplementation((url, options) =>
    url === "/shops/7" ? pending.promise : original(url, options),
  );
  await renderAt("/shops/7", ["/shops/8"]);
  await click(container.querySelector('[aria-label="Test navigation"] a'));
  await act(async () => pending.reject({ response: { status: 404 } }));
  expect(container.querySelector("h1").textContent).toBe("Shop thứ hai");
  expect(container.textContent).not.toContain("Gian hàng không khả dụng");
});

it("toggles buyer favorites using the existing API", async () => {
  signInAs("BUYER");
  mockRoutes();
  const put = vi.spyOn(client, "put").mockResolvedValue({ data: {} });
  const remove = vi.spyOn(client, "delete").mockResolvedValue({ data: {} });
  await renderAt("/shops/7");
  const favorite = container.querySelector(".wishlist-button");
  await click(favorite);
  expect(put).toHaveBeenCalledWith("/wishlist/items/31");
  expect(favorite.classList.contains("is-favorite")).toBe(true);
  await click(favorite);
  expect(remove).toHaveBeenCalledWith("/wishlist/items/31");
});

it("takes guests to login from the favorite button", async () => {
  mockRoutes();
  await renderAt("/shops/7");
  await click(container.querySelector(".wishlist-button"));
  expect(container.querySelector("h1").textContent).toContain("Đăng nhập");
});

it("opens the correct shop from product details", async () => {
  mockRoutes();
  await renderAt("/products/31");
  await click(container.querySelector('.detail-meta a[href="/shops/7"]'));
  expect(container.querySelector("h1").textContent).toBe(shop.name);
});

it.each(["/orders/9", "/orders"])(
  "opens the shop from %s while preserving the order snapshot on return",
  async (path) => {
    signInAs("BUYER");
    const get = mockRoutes();
    const original = get.getMockImplementation();
    get.mockImplementation((url, options) =>
      url === "/shops/7" ? Promise.reject({ response: { status: 404 } }) : original(url, options),
    );
    await renderAt(path, ["/orders/9"]);
    expect(container.querySelector('a[href="/shops/7"]').textContent).toBe("Xem shop");
    await click(container.querySelector('a[href="/shops/7"]'));
    expect(container.textContent).toContain("Gian hàng không khả dụng");
    await click(container.querySelector('[aria-label="Test navigation"] a'));
    expect(container.textContent).toContain("Tên áo lúc mua");
    expect(container.textContent).toContain("180.000");
    expect(button("Đánh giá")).not.toBeNull();
  },
);

it("opens the correct shop from a cart group without writing to the cart", async () => {
  signInAs("BUYER");
  mockRoutes({
    "/cart": {
      shop_id: 7,
      shop_name: shop.name,
      total_amount: 180000,
      items: [
        {
          id: 1,
          variant_id: 21,
          product_name: "Áo linen",
          color: "Đen",
          size: "M",
          quantity: 1,
          stock_quantity: 3,
          unit_price: 180000,
        },
      ],
    },
  });
  const post = vi.spyOn(client, "post");
  await renderAt("/cart");
  await click(container.querySelector('.cart-shop-heading a[href="/shops/7"]'));
  expect(container.querySelector("h1").textContent).toBe(shop.name);
  expect(post).not.toHaveBeenCalled();
});
