// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../api/client.js";
import {
  mountContainer,
  renderAt,
  routeGet,
  signInAs,
  unmountContainer,
} from "../testing/appHarness.jsx";

let container;
beforeEach(() => {
  container = mountContainer();
});
afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

const product = {
  id: 31,
  shop_id: 7,
  shop_name: "Shop A",
  name: "Áo A",
  price_from: 100000,
  rating_average: 5,
  variants: [{ id: 21, color: "Đỏ", size: "M", quantity: 5, price: 100000 }],
};

function wishlistButtons() {
  return container.querySelectorAll('[aria-label*="danh sách yêu thích"]');
}

it("cho chủ shop xem catalog nhưng ẩn yêu thích và không gọi API của buyer", async () => {
  signInAs("SHOP_OWNER", 7);
  const get = routeGet({
    "/categories": [],
    "/products": { items: [product], total: 1, page: 1, page_size: 20 },
  });
  await renderAt("/");
  expect(container.textContent).toContain("Áo A");
  expect(container.querySelector(".header-search")).not.toBeNull();
  expect(wishlistButtons()).toHaveLength(0);
  expect(get.mock.calls.some(([url]) => url === "/wishlist" || url.startsWith("/recommend"))).toBe(
    false,
  );
});

it("cho chủ shop xem phản hồi đánh giá nhưng không có nút thêm vào giỏ", async () => {
  signInAs("SHOP_OWNER", 7);
  routeGet({
    "/products/31": product,
    "/products/31/reviews": {
      total: 1,
      items: [
        {
          id: 1,
          rating: 5,
          comment: "Áo đẹp",
          created_at: "2026-10-30T01:00:00Z",
          shop_reply: "Cảm ơn bạn đã ủng hộ shop!",
          shop_replied_at: "2026-10-30T02:00:00Z",
        },
      ],
    },
  });
  const post = vi.spyOn(client, "post");
  await renderAt("/products/31");
  expect(container.textContent).toContain("Phản hồi từ shop");
  expect(container.textContent).toContain("Cảm ơn bạn đã ủng hộ shop!");
  expect(container.textContent).toContain("Chỉ tài khoản người mua mới thêm được vào giỏ hàng.");
  expect(container.querySelector(".add-to-cart")).toBeNull();
  expect(wishlistButtons()).toHaveLength(0);
  expect(post).not.toHaveBeenCalled();
});

it("vẫn giữ nút thêm vào giỏ và yêu thích cho khách", async () => {
  routeGet({
    "/products/31": product,
    "/products/31/reviews": { items: [], total: 0 },
  });
  await renderAt("/products/31");
  expect(container.querySelector(".add-to-cart")).not.toBeNull();
  expect(wishlistButtons()).toHaveLength(1);
});
