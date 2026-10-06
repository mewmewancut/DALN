// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import client from "../api/client.js";
import {
  button,
  click,
  mountContainer,
  renderAt,
  routeGet,
  signInAs,
  submit,
  unmountContainer,
} from "../testing/appHarness.jsx";

let container;
beforeEach(() => {
  container = mountContainer();
  signInAs("BUYER");
});

it("ignores a review response after navigating to a different order", async () => {
  const first = {
    id: 1,
    code: "FIRST",
    created_at: "2026-10-06T00:00:00Z",
    status: "DELIVERED",
    total_amount: 100000,
    payment_method: "COD",
    payment_status: "PAID",
    status_history: [],
    items: [{ id: 11, product_name: "Áo A", unit_price: 100000, quantity: 1, review_id: null }],
  };
  const second = {
    ...first,
    id: 2,
    code: "SECOND",
    items: [{ ...first.items[0], product_name: "Áo B" }],
  };
  routeGet({ "/orders/1": first, "/orders/2": second });
  let finish;
  vi.spyOn(client, "post").mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await renderAt("/orders/1", ["/orders/2"]);
  await click(button("Đánh giá"));
  await submit(container.querySelector('[role="dialog"] form'));
  await click(container.querySelector('[aria-label="Test navigation"] a'));
  await act(async () => finish({ data: { id: 99 } }));
  expect(container.textContent).toContain("SECOND");
  expect(container.textContent).not.toContain("Đã đánh giá");
  expect(button("Đánh giá").disabled).toBe(false);
});
afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

it("clears the previous order and review dialog while loading a different order", async () => {
  const order = {
    id: 1,
    code: "OWN-ORDER-1",
    created_at: "2026-10-06T01:00:00Z",
    status: "DELIVERED",
    payment_method: "COD",
    payment_status: "PAID",
    total_amount: 100000,
    receiver_name: "Người nhận",
    receiver_phone: "0900000000",
    shipping_address: "Địa chỉ cũ",
    items: [
      {
        id: 11,
        product_name: "Áo",
        unit_price: 100000,
        quantity: 1,
        color: "Đỏ",
        size: "M",
        review_id: null,
      },
    ],
    status_history: [],
  };
  routeGet({ "/orders/1": order });
  const original = client.get.getMockImplementation();
  let reject;
  client.get.mockImplementation((url, options) =>
    url === "/orders/2"
      ? new Promise((_, failure) => {
          reject = failure;
        })
      : original(url, options),
  );
  await renderAt("/orders/1", ["/orders/2"]);
  await click(button("Đánh giá"));
  await click(container.querySelector('[aria-label="Test navigation"] a'));
  expect(container.textContent).not.toContain("OWN-ORDER-1");
  expect(container.querySelector('[role="dialog"]')).toBeNull();
  expect(container.textContent).toContain("Đang tải đơn hàng");
  await act(async () => reject({ response: { data: { detail: "Không có quyền truy cập" } } }));
  expect(container.textContent).toContain("Không có quyền truy cập");
  expect(container.textContent).not.toContain("Địa chỉ cũ");
});
