// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import client from "../api/client.js";
import {
  mountContainer,
  renderAt,
  routeGet,
  click,
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
it("does not show another product's reviews or an empty success while reviews are unavailable", async () => {
  const product = { id: 1, name: "Áo A", variants: [], rating_average: 5 };
  routeGet({
    "/products/1": product,
    "/products/2": { ...product, id: 2, name: "Áo B" },
    "/products/1/reviews": {
      total: 1,
      items: [
        { id: 1, rating: 5, comment: "Nhận xét riêng Áo A", created_at: "2026-10-06T01:00:00Z" },
      ],
    },
  });
  const original = client.get.getMockImplementation();
  let reject;
  client.get.mockImplementation((url, options) =>
    url === "/products/2/reviews"
      ? new Promise((_, failure) => {
          reject = failure;
        })
      : original(url, options),
  );
  await renderAt("/products/1", ["/products/2"]);
  expect(container.textContent).toContain("Nhận xét riêng Áo A");
  await click(container.querySelector('[aria-label="Test navigation"] a'));
  expect(container.textContent).toContain("Áo B");
  expect(container.textContent).not.toContain("Nhận xét riêng Áo A");
  expect(container.textContent).toContain("Đang tải đánh giá");
  await act(async () => reject({ response: { data: { detail: "Tạm thời không kết nối được" } } }));
  expect(container.textContent).toContain("Không tải được đánh giá");
  expect(container.textContent).not.toContain("Chưa có nhận xét nào");
});
