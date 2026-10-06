// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import client from "../../api/client.js";
import {
  button,
  click,
  mountContainer,
  renderAt,
  routeGet,
  signInAs,
  unmountContainer,
} from "../../testing/appHarness.jsx";

let container;
const order = {
  id: 7,
  code: "ORD-FAKE-7",
  buyer_id: 4,
  shop_id: 1,
  status: "SHIPPING",
  payment_method: "COD",
  payment_status: "UNPAID",
  total_amount: 120000,
  created_at: "2026-10-06T01:00:00Z",
  receiver_name: "FAKE người nhận",
  receiver_phone: "0900000000",
  shipping_address: "FAKE địa chỉ giao",
  items: [
    {
      id: 1,
      product_name: "Tên snapshot đã mua",
      color: "Đen",
      size: "M",
      quantity: 2,
      unit_price: 60000,
      review_id: null,
    },
  ],
  status_history: [
    { id: 1, to_status: "SHIPPING", created_at: "2026-10-06T01:00:00Z", note: "Đang giao" },
  ],
};
beforeEach(() => {
  container = mountContainer();
});
afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

it.each([
  ["SHOP_OWNER", "/shop/orders", "/shop/orders"],
  ["ADMIN", "/admin/orders", "/admin/orders"],
])(
  "%s opens recipient, item snapshots and timeline from the authorized detail API",
  async (role, path, listUrl) => {
    signInAs(role, 1);
    routeGet({
      [listUrl]: { items: [order], total: 1, page_size: 20 },
      "/admin/shops": { items: [{ id: 1, name: "Shop A" }], total: 1, page_size: 20 },
      "/orders/7": order,
    });
    await renderAt(path);
    await click(button(order.code));
    expect(container.querySelector("dialog").open).toBe(true);
    expect(container.textContent).toContain("FAKE địa chỉ giao");
    expect(container.textContent).toContain("Tên snapshot đã mua");
    expect(container.textContent).toContain("Chưa thanh toán");
    expect(container.textContent).toContain("120.000 ₫");
    expect(container.querySelector("dialog").textContent).not.toContain("Đánh giá");
    await click(button("Đóng chi tiết"));
    expect(container.querySelector("dialog")).toBeNull();
  },
);

it("shows permission failure and retries without inventing order details", async () => {
  signInAs("SHOP_OWNER", 1);
  routeGet({ "/shop/orders": { items: [order], total: 1, page_size: 20 } });
  const original = client.get.getMockImplementation();
  let attempts = 0;
  client.get.mockImplementation((url, options) => {
    if (url !== "/orders/7") return original(url, options);
    if (++attempts === 1)
      return Promise.reject({ response: { data: { detail: "Đơn không thuộc shop" } } });
    return Promise.resolve({ data: order });
  });
  await renderAt("/shop/orders");
  await click(button(order.code));
  expect(container.textContent).toContain("Đơn không thuộc shop");
  expect(container.textContent).not.toContain("FAKE địa chỉ giao");
  await click(button("Tải lại chi tiết"));
  expect(container.textContent).toContain("FAKE địa chỉ giao");
  const modal = container.querySelector("dialog");
  await act(async () =>
    modal.dispatchEvent(new Event("cancel", { bubbles: true, cancelable: true })),
  );
  expect(container.querySelector("dialog")).toBeNull();
});
