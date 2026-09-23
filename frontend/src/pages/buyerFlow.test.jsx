// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import App from "../App.jsx";
import client from "../api/client.js";
import { AuthProvider } from "../auth/AuthContext.jsx";

let container;
let root;

const cart = {
  shop_id: 2,
  shop_name: "Shop A",
  items: [
    {
      id: 11,
      variant_id: 21,
      product_id: 31,
      product_name: "Áo mẫu",
      image_url: null,
      size: "M",
      color: "Đỏ",
      quantity: 1,
      unit_price: 120000,
      stock_quantity: 3,
    },
  ],
  total_amount: 120000,
};

const deliveredOrder = {
  id: 9,
  code: "ORD-20260923-0009",
  buyer_id: 1,
  shop_id: 2,
  status: "DELIVERED",
  receiver_name: "Nguyễn An",
  receiver_phone: "0900000000",
  shipping_address: "Quận 1",
  payment_method: "COD",
  payment_status: "PAID",
  total_amount: 120000,
  created_at: "2026-09-23T01:00:00Z",
  updated_at: "2026-09-23T02:00:00Z",
  delivered_at: "2026-09-23T02:00:00Z",
  cancelled_at: null,
  cancel_reason: null,
  items: [
    {
      id: 41,
      variant_id: 21,
      product_name: "Áo mẫu",
      size: "M",
      color: "Đỏ",
      unit_price: 120000,
      quantity: 1,
      review_id: null,
    },
  ],
  status_history: [
    {
      id: 51,
      from_status: "SHIPPING",
      to_status: "DELIVERED",
      changed_by: 2,
      note: null,
      created_at: "2026-09-23T02:00:00Z",
    },
  ],
};

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem(
    "fashion_auth",
    JSON.stringify({ token: "buyer-token", role: "BUYER", shop_id: null }),
  );
  container = document.createElement("div");
  document.body.appendChild(container);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  root = null;
  container.remove();
  vi.restoreAllMocks();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

async function renderAt(path) {
  root = createRoot(container);
  await act(async () =>
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    ),
  );
}

function button(text) {
  return [...container.querySelectorAll("button")].find((item) => item.textContent.trim() === text);
}

async function click(text) {
  await act(async () => button(text).click());
}

async function fill(labelText, value) {
  const label = [...container.querySelectorAll("label")].find((item) =>
    item.textContent.includes(labelText),
  );
  const field = label.querySelector("input, select, textarea");
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(field.constructor.prototype, "value").set;
    setter.call(field, value);
    field.dispatchEvent(
      new Event(field.tagName === "SELECT" ? "change" : "input", { bubbles: true }),
    );
  });
}

async function submitVisibleForm() {
  const form =
    [...container.querySelectorAll("form")].find((item) => item.offsetParent !== null) ??
    container.querySelector("form");
  await act(async () =>
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
  );
}

it("thêm đúng variant vào giỏ và xử lý xác nhận đổi shop", async () => {
  vi.spyOn(client, "get").mockImplementation(async (url) => {
    if (url.endsWith("/reviews")) {
      return { data: { items: [], total: 0, page: 1, page_size: 20, rating_average: null } };
    }
    return {
      data: {
        id: 5,
        shop_name: "Shop B",
        name: "Áo mới",
        description: "Mô tả",
        image_url: null,
        price_from: 120000,
        rating_average: null,
        variants: [{ id: 21, color: "Đỏ", size: "M", price: 120000, quantity: 3 }],
      },
    };
  });
  const post = vi
    .spyOn(client, "post")
    .mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: "Giỏ hàng đang chứa sản phẩm của shop khác",
          current_shop: { name: "Shop A" },
        },
      },
    })
    .mockResolvedValueOnce({ data: cart });
  const remove = vi.spyOn(client, "delete").mockResolvedValue({ data: {} });

  await renderAt("/products/5");
  await click("Đỏ");
  await click("M");
  expect(button("Thêm vào giỏ").disabled).toBe(false);
  await click("Thêm vào giỏ");
  expect(container.querySelector('[role="dialog"]').textContent).toContain("Shop A");
  await click("Xóa giỏ và thêm");

  expect(remove).toHaveBeenCalledWith("/cart");
  expect(post).toHaveBeenLastCalledWith("/cart/items", { variant_id: 21, quantity: 1 });
  expect(container.textContent).toContain("Đã thay giỏ hàng và thêm sản phẩm");
});

it("sửa và xóa item trong giỏ, đồng thời chặn số lượng vượt tồn kho", async () => {
  vi.spyOn(client, "get").mockResolvedValue({ data: cart });
  const put = vi.spyOn(client, "put").mockResolvedValue({
    data: {
      ...cart,
      items: [{ ...cart.items[0], quantity: 2 }],
      total_amount: 240000,
    },
  });
  const remove = vi.spyOn(client, "delete").mockResolvedValue({
    data: { shop_id: null, shop_name: null, items: [], total_amount: 0 },
  });

  await renderAt("/cart");
  await fill("Số lượng", "4");
  expect(container.textContent).toContain("Số lượng phải từ 1 đến 3");
  expect(button("Cập nhật").disabled).toBe(true);
  await fill("Số lượng", "2");
  await click("Cập nhật");
  expect(put).toHaveBeenCalledWith("/cart/items/11", { quantity: 2 });
  expect(container.textContent).toContain("240.000 ₫");
  await click("Xóa");
  expect(remove).toHaveBeenCalledWith("/cart/items/11");
  expect(container.textContent).toContain("Giỏ hàng đang trống");
});

it("hiện lỗi thiếu hàng từ checkout rồi chuyển tới chi tiết đơn khi thử lại thành công", async () => {
  const get = vi.spyOn(client, "get").mockImplementation(async (url) => {
    if (url === "/cart") return { data: cart };
    if (url === "/orders/9") return { data: deliveredOrder };
    throw new Error(`Unexpected GET ${url}`);
  });
  const post = vi
    .spyOn(client, "post")
    .mockRejectedValueOnce({ response: { status: 409, data: { detail: "Áo mẫu không đủ hàng" } } })
    .mockResolvedValueOnce({ data: { id: 9 } });

  await renderAt("/checkout");
  await fill("Người nhận", "Nguyễn An");
  await fill("Số điện thoại", "0900000000");
  await fill("Địa chỉ giao hàng", "Quận 1");
  await fill("Phương thức thanh toán", "MOCK_CARD");
  await submitVisibleForm();
  expect(container.querySelector('[role="alert"]').textContent).toBe("Áo mẫu không đủ hàng");
  await submitVisibleForm();

  expect(post).toHaveBeenLastCalledWith("/orders/checkout", {
    receiver_name: "Nguyễn An",
    receiver_phone: "0900000000",
    shipping_address: "Quận 1",
    payment_method: "MOCK_CARD",
  });
  expect(get).toHaveBeenCalledWith("/orders/9");
  expect(container.textContent).toContain("ORD-20260923-0009");
});

it("lọc đơn theo trạng thái và chỉ cho hủy đơn PENDING với lý do", async () => {
  const pending = {
    id: 7,
    code: "ORD-PENDING",
    buyer_id: 1,
    shop_id: 2,
    status: "PENDING",
    payment_method: "COD",
    payment_status: "UNPAID",
    total_amount: 120000,
    created_at: "2026-09-23T01:00:00Z",
  };
  const delivered = { ...pending, id: 8, code: "ORD-DELIVERED", status: "DELIVERED" };
  const get = vi.spyOn(client, "get").mockResolvedValue({
    data: { items: [pending, delivered], total: 2, page: 1, page_size: 20 },
  });
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValue({ data: { ...pending, status: "CANCELLED" } });

  await renderAt("/orders");
  expect(
    [...container.querySelectorAll("button")].filter((item) => item.textContent === "Hủy đơn"),
  ).toHaveLength(1);
  await click("Đã giao");
  expect(get).toHaveBeenLastCalledWith("/orders/my", {
    params: { page: 1, page_size: 20, status: "DELIVERED" },
  });
  await click("Tất cả");
  await click("Hủy đơn");
  await fill("Lý do hủy", "Đổi ý");
  await click("Xác nhận hủy");
  expect(post).toHaveBeenCalledWith("/orders/7/cancel", { reason: "Đổi ý" });
});

it("chỉ hiện form đánh giá cho item DELIVERED chưa review và cập nhật sau khi gửi", async () => {
  vi.spyOn(client, "get").mockResolvedValue({ data: deliveredOrder });
  const post = vi.spyOn(client, "post").mockResolvedValue({ data: { id: 88 } });

  await renderAt("/orders/9");
  await click("Đánh giá");
  await fill("Số sao", "4");
  await fill("Nhận xét", "Sản phẩm đẹp");
  await click("Gửi đánh giá");

  expect(post).toHaveBeenCalledWith("/reviews", {
    order_item_id: 41,
    rating: 4,
    comment: "Sản phẩm đẹp",
  });
  expect(container.textContent).toContain("Đã đánh giá");
  expect(button("Đánh giá")).toBeUndefined();
});
