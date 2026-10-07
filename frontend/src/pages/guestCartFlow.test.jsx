// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import client from "../api/client.js";
import { readGuestCart, saveGuestItems } from "../cart/guestCart.js";
import {
  button,
  click,
  fill,
  mountContainer,
  renderAt,
  routeGet,
  rowContaining,
  setValue,
  signInAs,
  submit,
  unmountContainer,
} from "../testing/appHarness.jsx";

let container;
const first = {
  id: 11,
  variant_id: 21,
  product_id: 31,
  shop_id: 1,
  shop_name: "Shop A",
  is_available: true,
  product_name: "Áo A",
  image_url: null,
  color: "Đỏ",
  size: "M",
  quantity: 1,
  unit_price: 100000,
  stock_quantity: 5,
};
const second = {
  ...first,
  id: 12,
  variant_id: 22,
  product_id: 32,
  shop_id: 2,
  shop_name: "Shop B",
  product_name: "Áo B",
  unit_price: 200000,
};
const empty = { shop_id: null, shop_name: null, items: [], total_amount: 0 };
function responseCart(items) {
  const single = items.length && items.every((item) => item.shop_id === items[0].shop_id);
  return {
    ...empty,
    shop_id: single ? items[0].shop_id : null,
    shop_name: single ? items[0].shop_name : null,
    items,
    total_amount: items.reduce((sum, item) => sum + item.quantity * item.unit_price, 0),
  };
}
function selectShop(name) {
  return click(container.querySelector(`input[aria-label="Thanh toán ${name}"]`));
}
beforeEach(() => {
  container = mountContainer();
});
afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

it("adds a guest variant without login and keeps it across navigation", async () => {
  routeGet({
    "/products/31": {
      id: 31,
      shop_id: 1,
      shop_name: "Shop A",
      name: "Áo A",
      variants: [{ id: 21, color: "Đỏ", size: "M", quantity: 5, price: 100000 }],
    },
    "/products/31/reviews": { items: [], total: 0 },
  });
  const post = vi.spyOn(client, "post").mockImplementation(async (url, body) => {
    if (url === "/cart/preview")
      return {
        data: responseCart(body.items.map((item) => ({ ...first, ...item, id: item.variant_id }))),
      };
    throw new Error("unexpected POST " + url);
  });
  await renderAt("/products/31", ["/cart", "/login"]);
  await click(button("Đỏ"));
  await click(button("M"));
  await click(button("Thêm vào giỏ"));
  expect(container.textContent).toContain("Đã thêm sản phẩm vào giỏ hàng");
  expect(post).not.toHaveBeenCalled();
  expect(readGuestCart().items).toEqual([{ variant_id: 21, quantity: 1 }]);
  await click(container.querySelector('[aria-label="Test navigation"] a[href="/cart"]'));
  expect(container.textContent).toContain("Áo A");
  await click(container.querySelector('[aria-label="Test navigation"] a[href="/login"]'));
  await click(container.querySelector('[aria-label="Test navigation"] a[href="/cart"]'));
  expect(container.textContent).toContain("Áo A");
  expect(readGuestCart().items).toHaveLength(1);
});

it("requires exactly one selected shop and ignores unavailable items in other shops", async () => {
  signInAs("BUYER");
  routeGet({
    "/cart": responseCart([{ ...first, stock_quantity: 0 }, second]),
    "/users/me/profile": { full_name: "Buyer", phone: "0900000000" },
    "/users/me/addresses": [],
  });
  await renderAt("/cart");
  expect(button("Thanh toán").disabled).toBe(true);
  await selectShop("Shop A");
  expect(button("Thanh toán").disabled).toBe(true);
  await selectShop("Shop B");
  const radios = [...container.querySelectorAll('input[name="checkout-shop"]')];
  expect(radios.filter((input) => input.checked)).toHaveLength(1);
  expect(container.querySelector(".cart-summary").textContent).toContain("200.000 ₫");
  expect(button("Thanh toán").disabled).toBe(false);
  await click(button("Thanh toán"));
  const summary = container.querySelector(".order-box");
  expect(summary.textContent).toContain("Áo B");
  expect(summary.textContent).not.toContain("Áo A");
});

it("keeps the guest cart through registration, verification and login, then checks out one shop", async () => {
  saveGuestItems([
    { variant_id: 21, quantity: 1 },
    { variant_id: 22, quantity: 1 },
  ]);
  let server = empty;
  const get = vi.spyOn(client, "get").mockImplementation(async (url) => {
    if (url === "/cart") return { data: server };
    if (url === "/users/me/profile") return { data: { full_name: "An", phone: "0900000000" } };
    if (url === "/users/me/addresses") return { data: [] };
    if (url === "/orders/9")
      return {
        data: {
          id: 9,
          code: "ORD-TEST-9",
          status: "PENDING",
          total_amount: 200000,
          payment_method: "COD",
          payment_status: "UNPAID",
          items: [{ ...second, review_id: null }],
          status_history: [],
        },
      };
    throw new Error("unexpected GET " + url);
  });
  const post = vi.spyOn(client, "post").mockImplementation(async (url, body) => {
    if (url === "/cart/preview")
      return {
        data: responseCart([first, second].map((item) => ({ ...item, id: item.variant_id }))),
      };
    if (url === "/auth/register") return { data: { id: 8 } };
    if (url === "/auth/verify-email") return { data: { message: "Đã xác nhận email" } };
    if (url === "/auth/login")
      return { data: { access_token: "buyer-token", role: "BUYER", shop_id: null } };
    if (url === "/cart/merge") {
      expect(body.items).toEqual([
        { variant_id: 21, quantity: 1 },
        { variant_id: 22, quantity: 1 },
      ]);
      server = responseCart([first, second]);
      return { data: server };
    }
    if (url === "/orders/checkout") {
      expect(body.shop_id).toBe(2);
      server = responseCart([first]);
      return { data: { id: 9 } };
    }
    throw new Error("unexpected POST " + url);
  });
  await renderAt("/cart", ["/verify-email#token=fake-verification-token", "/login", "/cart"]);
  await selectShop("Shop B");
  await click(button("Thanh toán"));
  expect(container.querySelector("h1").textContent).toBe("Đăng nhập");
  await click(container.querySelector('a[href="/register"]'));
  await fill("Họ và tên", "Nguyễn An");
  await fill("Email", "an@example.com");
  await fill("Mật khẩu", "secret123");
  await submit(container.querySelector("form"));
  expect(container.textContent).toContain("Kiểm tra email");
  expect(readGuestCart().items).toHaveLength(2);
  await click(container.querySelector('[aria-label="Test navigation"] a[href^="/verify-email#"]'));
  await click(button("Xác nhận email"));
  expect(readGuestCart().items).toHaveLength(2);
  await click(container.querySelector('[aria-label="Test navigation"] a[href="/login"]'));
  await fill("Email", "an@example.com");
  await fill("Mật khẩu", "secret123");
  await submit(container.querySelector("form"));
  expect(container.querySelector("h1").textContent).toBe("Thanh toán");
  expect(readGuestCart().items).toEqual([]);
  expect(container.querySelector("h1").textContent).toBe("Thanh toán");
  expect(container.querySelector(".order-box").textContent).toContain("Áo B");
  expect(container.querySelector(".order-box").textContent).not.toContain("Áo A");
  await fill("Địa chỉ giao hàng", "Địa chỉ thử nghiệm");
  await submit(container.querySelector("form"));
  expect(post).toHaveBeenLastCalledWith(
    "/orders/checkout",
    expect.objectContaining({ shop_id: 2 }),
  );
  expect(get).toHaveBeenCalledWith("/orders/9");
  await click(container.querySelector('[aria-label="Test navigation"] a[href="/cart"]'));
  expect(container.textContent).toContain("Áo A");
  expect(container.textContent).not.toContain("Áo B");
});

it("retains the same import key after network failure and clears it only after retry succeeds", async () => {
  saveGuestItems([{ variant_id: 21, quantity: 1 }]);
  const initial = readGuestCart();
  signInAs("BUYER");
  routeGet({ "/cart": empty });
  const post = vi.spyOn(client, "post").mockImplementation(async (url) => {
    if (url === "/cart/preview") return { data: responseCart([{ ...first, id: 21 }]) };
    throw new Error("Mất kết nối");
  });
  await renderAt("/cart");
  expect(readGuestCart().items).toEqual(initial.items);
  expect(readGuestCart().pending).toBe(true);
  expect(container.textContent).toContain("Mất kết nối");
  expect(button("Xóa", container.querySelector(".guest-cart-recovery")).disabled).toBe(true);
  post.mockImplementation(async () => ({ data: responseCart([first]) }));
  await click(button("Thử chuyển giỏ tạm"));
  expect(post).toHaveBeenLastCalledWith(
    "/cart/merge",
    { merge_id: initial.merge_id, items: initial.items },
    expect.anything(),
  );
  expect(readGuestCart().items).toEqual([]);
  expect(container.textContent).toContain("Áo A");
});

it("allows rejected guest items to be corrected and retries with a fresh key", async () => {
  saveGuestItems([{ variant_id: 21, quantity: 1 }]);
  const initial = readGuestCart();
  signInAs("BUYER");
  routeGet({ "/cart": empty });
  const post = vi.spyOn(client, "post").mockImplementation(async (url) => {
    if (url === "/cart/merge")
      throw { response: { status: 404, data: { detail: "Sản phẩm đã ngừng bán" } } };
    return { data: responseCart([{ ...first, id: 21, is_available: false, stock_quantity: 0 }]) };
  });
  await renderAt("/cart");
  expect(readGuestCart().pending).toBe(false);
  await click(button("Xóa", container.querySelector(".guest-cart-recovery")));
  expect(readGuestCart().items).toEqual([]);
  expect(readGuestCart().merge_id).not.toBe(initial.merge_id);
  post.mockResolvedValue({ data: empty });
  await click(button("Thử chuyển giỏ tạm"));
  expect(container.querySelector(".guest-cart-recovery")).toBeNull();
});

it("shows preview failure without displaying a false empty cart", async () => {
  saveGuestItems([{ variant_id: 21, quantity: 1 }]);
  vi.spyOn(client, "post").mockRejectedValue(new Error("Không tải được giỏ tạm"));
  await renderAt("/cart");
  expect(container.textContent).toContain("Không tải được giỏ tạm");
  expect(container.textContent).not.toContain("Giỏ hàng đang trống");
  expect(readGuestCart().items).toHaveLength(1);
});

it("blocks direct checkout when a multi-shop cart has no selection", async () => {
  signInAs("BUYER");
  routeGet({
    "/cart": responseCart([first, second]),
    "/users/me/profile": {},
    "/users/me/addresses": [],
  });
  const post = vi.spyOn(client, "post");
  await renderAt("/checkout");
  expect(container.textContent).toContain("Chọn một shop");
  expect(container.querySelector("form")).toBeNull();
  expect(post).not.toHaveBeenCalled();
});

it("does not import a guest cart for a shop owner", async () => {
  saveGuestItems([{ variant_id: 21, quantity: 1 }]);
  const post = vi.spyOn(client, "post").mockResolvedValue({
    data: { access_token: "owner-token", role: "SHOP_OWNER", shop_id: null },
  });
  await renderAt("/login");
  await fill("Email", "owner@example.com");
  await fill("Mật khẩu", "secret123");
  await submit(container.querySelector("form"));
  expect(post).toHaveBeenCalledTimes(1);
  expect(readGuestCart().items).toHaveLength(1);
  expect(container.textContent).toContain("Tạo shop");
});

it("shows a storage failure when adding as a guest without claiming the item was saved", async () => {
  routeGet({
    "/products/31": {
      id: 31,
      name: "Áo A",
      variants: [{ id: 21, color: "Đỏ", size: "M", quantity: 5, price: 100000 }],
    },
    "/products/31/reviews": { items: [], total: 0 },
  });
  await renderAt("/products/31");
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  await click(button("Đỏ"));
  await click(button("M"));
  await click(button("Thêm vào giỏ"));
  expect(container.textContent).toContain("Trình duyệt không cho lưu giỏ hàng");
  expect(container.textContent).not.toContain("Đã thêm sản phẩm");
});

it("reloads a changed guest cart when preview fails instead of checking out stale rows", async () => {
  saveGuestItems([
    { variant_id: 21, quantity: 1 },
    { variant_id: 22, quantity: 1 },
  ]);
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValueOnce({ data: responseCart([first, second]) })
    .mockRejectedValue(new Error("Mất kết nối khi kiểm tra giỏ"));
  await renderAt("/cart");
  await selectShop("Shop B");
  await click(button("Xóa", rowContaining("Áo A")));
  expect(readGuestCart().items).toEqual([{ variant_id: 22, quantity: 1 }]);
  expect(container.textContent).toContain("Mất kết nối");
  expect(container.querySelector(".cart-summary")).toBeNull();
  expect(container.textContent).not.toContain("Giỏ hàng đang trống");
  post.mockResolvedValue({ data: responseCart([second]) });
  await click(button("Tải lại giỏ hàng"));
  expect(container.textContent).toContain("Áo B");
  expect(container.textContent).not.toContain("Áo A");
  expect(button("Thanh toán").disabled).toBe(false);
});

it("can retry corrected guest quantities when recovery preview loses connection", async () => {
  saveGuestItems([{ variant_id: 21, quantity: 1 }]);
  signInAs("BUYER");
  routeGet({ "/cart": empty });
  let previews = 0;
  let imports = 0;
  vi.spyOn(client, "post").mockImplementation(async (url) => {
    if (url === "/cart/merge") {
      if (++imports === 1) throw { response: { status: 409, data: { detail: "Không đủ hàng" } } };
      return { data: responseCart([{ ...first, quantity: 2 }]) };
    }
    if (++previews === 1) return { data: responseCart([{ ...first, id: 21 }]) };
    throw new Error("Mất kết nối khi kiểm tra giỏ");
  });
  await renderAt("/cart");
  const recovery = container.querySelector(".guest-cart-recovery");
  await setValue(recovery.querySelector('input[type="number"]'), "2");
  await click(button("Cập nhật", recovery));
  expect(readGuestCart().items[0].quantity).toBe(2);
  expect(button("Thử chuyển giỏ tạm").disabled).toBe(false);
  await click(button("Thử chuyển giỏ tạm"));
  expect(readGuestCart().items).toEqual([]);
  expect(container.querySelector(".guest-cart-recovery")).toBeNull();
  expect(container.querySelector('input[type="number"]').value).toBe("2");
});
