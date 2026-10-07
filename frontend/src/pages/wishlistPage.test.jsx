// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../api/client.js";
import {
  button,
  click,
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
  name: "Áo mẫu",
  image_url: null,
  base_price: 90000,
  price_from: 100000,
  rating_average: 4.5,
};

const wishlistItem = {
  id: 7,
  product_id: 5,
  name: "Áo mẫu",
  image_url: null,
  shop_name: "Shop A",
  price_from: 100000,
  rating_average: 4.5,
  is_available: true,
  has_stock: true,
  created_at: "2026-09-29T01:00:00Z",
};

beforeEach(() => {
  container = mountContainer();
  signInAs("BUYER");
});

afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

it("hiện trạng thái tim ở catalog và bỏ yêu thích không tải lại trang", async () => {
  vi.spyOn(client, "get").mockImplementation(async (url) => {
    if (url === "/categories") return { data: [] };
    if (url === "/wishlist") return { data: [wishlistItem] };
    if (url === "/users/me/recommendations") return { data: [] };
    if (url === "/products") {
      return { data: { items: [product], total: 1, page: 1, page_size: 20 } };
    }
    throw new Error(`Unexpected GET ${url}`);
  });
  const remove = vi.spyOn(client, "delete").mockResolvedValue({ data: null });

  await renderAt("/");
  const favorite = container.querySelector('button[aria-label*="Áo mẫu"]');
  expect(favorite.getAttribute("aria-pressed")).toBe("true");
  expect(container.textContent).toContain("Yêu thích");

  await click(favorite);
  expect(remove).toHaveBeenCalledWith("/wishlist/items/5");
  expect(favorite.getAttribute("aria-pressed")).toBe("false");
});

it("thêm sản phẩm vào yêu thích từ trang chi tiết", async () => {
  vi.spyOn(client, "get").mockImplementation(async (url) => {
    if (url === "/wishlist") return { data: [] };
    if (url === "/products/5/reviews") {
      return { data: { items: [], total: 0, page: 1, page_size: 20 } };
    }
    if (url === "/products/5") {
      return {
        data: {
          ...product,
          description: "Mô tả",
          variants: [{ id: 21, color: "Đỏ", size: "M", price: 120000, quantity: 3 }],
        },
      };
    }
    throw new Error(`Unexpected GET ${url}`);
  });
  const add = vi.spyOn(client, "put").mockResolvedValue({ data: wishlistItem });

  await renderAt("/products/5");
  const favorite = container.querySelector('button[aria-label*="Áo mẫu"]');
  expect(favorite.getAttribute("aria-pressed")).toBe("false");
  await click(favorite);
  expect(add).toHaveBeenCalledWith("/wishlist/items/5");
  expect(favorite.getAttribute("aria-pressed")).toBe("true");
});

it("hiện sản phẩm tạm ẩn trong wishlist và vẫn cho xóa", async () => {
  vi.spyOn(client, "get").mockResolvedValue({
    data: [{ ...wishlistItem, is_available: false, has_stock: false }],
  });
  const remove = vi.spyOn(client, "delete").mockResolvedValue({ data: null });

  await renderAt("/wishlist");
  expect(container.textContent).toContain("Sản phẩm tạm ẩn");
  expect(container.textContent).not.toContain("Mua hàng");
  expect(container.querySelector('a[href="/products/5"]')).toBeNull();
  await click(button("Bỏ yêu thích"));
  expect(remove).toHaveBeenCalledWith("/wishlist/items/5");
  expect(container.textContent).toContain("Chưa có sản phẩm yêu thích");
});

it("hiện đúng trạng thái rỗng và lỗi tải wishlist", async () => {
  const get = vi.spyOn(client, "get").mockResolvedValue({ data: [] });
  await renderAt("/wishlist");
  expect(container.textContent).toContain("Chưa có sản phẩm yêu thích");

  await act(async () => {
    await unmountContainer();
    container = mountContainer();
    signInAs("BUYER");
  });
  get.mockRejectedValue({ response: { data: { detail: "Không tải được wishlist" } } });
  await renderAt("/wishlist");
  expect(container.querySelector('[role="alert"]').textContent).toBe("Không tải được wishlist");
});
