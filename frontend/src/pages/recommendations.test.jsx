// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../api/client.js";
import {
  button,
  click,
  fill,
  mountContainer,
  renderAt,
  signInAs,
  unmountContainer,
} from "../testing/appHarness.jsx";

let container;
const product = {
  id: 5,
  shop_id: 2,
  shop_name: "Shop A",
  category_id: 3,
  name: "Áo gợi ý",
  image_url: null,
  base_price: 90000,
  price_from: 100000,
  rating_average: 4.5,
};

beforeEach(() => {
  container = mountContainer();
  signInAs("BUYER");
});

afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

function mockGet(recommendations = [product]) {
  return vi.spyOn(client, "get").mockImplementation(async (url) => {
    if (url === "/users/me/recommendations") return { data: recommendations };
    if (url === "/categories" || url === "/wishlist") return { data: [] };
    if (url === "/products") {
      return { data: { items: [product], total: 1, page: 1, page_size: 20 } };
    }
    throw new Error(`Unexpected GET ${url}`);
  });
}

function section() {
  return container.querySelector('section[aria-label="Dành cho bạn"]');
}

it("tải gợi ý theo thứ tự API, hiển thị giá và dẫn tới chi tiết/sở thích", async () => {
  const second = { ...product, id: 6, name: "Giày gợi ý", rating_average: null };
  const get = mockGet([second, product]);
  await renderAt("/");
  expect(get).toHaveBeenCalledWith("/users/me/recommendations", { params: { limit: 8 } });
  expect([...section().querySelectorAll("article h2")].map((item) => item.textContent)).toEqual([
    "Giày gợi ý",
    "Áo gợi ý",
  ]);
  expect(section().textContent).toContain("100.000 ₫");
  expect(section().textContent).toContain("Chưa có đánh giá");
  expect(section().querySelector("a.product-card-link").getAttribute("href")).toBe("/products/6");
  expect(section().querySelector("a.text-button").getAttribute("href")).toBe(
    "/account/preferences",
  );
  await fill("Tìm sản phẩm", "giày");
  expect(get.mock.calls.filter(([url]) => url === "/users/me/recommendations")).toHaveLength(1);
  expect(get).toHaveBeenLastCalledWith("/products", {
    params: expect.objectContaining({ keyword: "giày", page: 1 }),
  });
});

it("đồng bộ nút tim giữa gợi ý và catalog mà không tải lại dữ liệu", async () => {
  mockGet();
  const put = vi.spyOn(client, "put").mockResolvedValue({ data: {} });
  const remove = vi.spyOn(client, "delete").mockResolvedValue({ data: null });
  await renderAt("/");
  const recommendationHeart = section().querySelector("button[aria-pressed]");
  const catalogHeart = container.querySelector(".catalog-results button[aria-pressed]");
  expect(recommendationHeart.getAttribute("aria-pressed")).toBe("false");
  await click(recommendationHeart);
  expect(put).toHaveBeenCalledWith("/wishlist/items/5");
  expect(catalogHeart.getAttribute("aria-pressed")).toBe("true");
  await click(catalogHeart);
  expect(remove).toHaveBeenCalledWith("/wishlist/items/5");
  expect(recommendationHeart.getAttribute("aria-pressed")).toBe("false");
});

it("hiện trạng thái rỗng khi không còn sản phẩm phù hợp", async () => {
  mockGet([]);
  await renderAt("/");
  expect(section().textContent).toContain("Chưa có sản phẩm còn hàng để gợi ý");
  expect(section().querySelector("article")).toBeNull();
});

it("giữ trạng thái tim và báo lỗi ngay trong mục gợi ý khi lưu yêu thích thất bại", async () => {
  mockGet();
  vi.spyOn(client, "put").mockRejectedValue({
    response: { data: { detail: "Không lưu được yêu thích" } },
  });
  await renderAt("/");
  await click(section().querySelector("button[aria-pressed]"));
  expect(section().querySelector('[role="alert"]').textContent).toContain(
    "Không lưu được yêu thích",
  );
  expect(section().querySelector("button[aria-pressed]").getAttribute("aria-pressed")).toBe(
    "false",
  );
  expect(
    container.querySelector(".catalog-results button[aria-pressed]").getAttribute("aria-pressed"),
  ).toBe("false");
});

it("hiện đang tải rồi lỗi gợi ý trong khi catalog vẫn tìm kiếm được", async () => {
  let rejectRecommendations;
  const pending = new Promise((_, reject) => {
    rejectRecommendations = reject;
  });
  const get = mockGet();
  const original = get.getMockImplementation();
  get.mockImplementation((url, options) =>
    url === "/users/me/recommendations" ? pending : original(url, options),
  );
  await renderAt("/");
  expect(section().querySelector('[role="status"]').textContent).toBe("Đang tải gợi ý...");
  expect(container.querySelector(".catalog-results").textContent).toContain("Áo gợi ý");
  await act(async () => rejectRecommendations({ response: { data: { detail: "Lỗi gợi ý" } } }));
  expect(section().querySelector('[role="alert"]').textContent).toContain("Lỗi gợi ý");
  expect(section().querySelector("article")).toBeNull();
  await fill("Tìm sản phẩm", "áo");
  expect(get).toHaveBeenLastCalledWith("/products", {
    params: expect.objectContaining({ keyword: "áo" }),
  });
});

it.each([null, "SHOP_OWNER", "ADMIN"])("không gọi API gợi ý cho role %s", async (role) => {
  if (role) signInAs(role);
  else localStorage.clear();
  const get = mockGet();
  await renderAt("/");
  expect(section()).toBeNull();
  expect(get.mock.calls.some(([url]) => url === "/users/me/recommendations")).toBe(false);
});

it("bỏ response gợi ý cũ khi buyer đăng xuất", async () => {
  let resolveRecommendations;
  const pending = new Promise((resolve) => {
    resolveRecommendations = resolve;
  });
  const get = mockGet();
  const original = get.getMockImplementation();
  get.mockImplementation((url, options) =>
    url === "/users/me/recommendations" ? pending : original(url, options),
  );
  await renderAt("/");
  await click(button("Đăng xuất"));
  await act(async () => resolveRecommendations({ data: [product] }));
  expect(section()).toBeNull();
});
