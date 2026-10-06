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
  rowContaining,
  setValue,
  signInAs,
  unmountContainer,
} from "../testing/appHarness.jsx";

let container;
const first = {
  id: 1,
  product_name: "Áo A",
  color: "Đỏ",
  size: "M",
  quantity: 1,
  unit_price: 100000,
  stock_quantity: 5,
};
const second = { ...first, id: 2, product_name: "Áo B" };
const cart = { shop_id: 1, shop_name: "Shop A", items: [first, second], total_amount: 200000 };
beforeEach(() => {
  container = mountContainer();
  signInAs("BUYER");
});
afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

it("requires quantity drafts to be saved before checkout", async () => {
  routeGet({ "/cart": cart });
  await renderAt("/cart");
  expect(button("Thanh toán").disabled).toBe(false);
  await setValue(rowContaining("Áo A").querySelector("input"), "2");
  expect(button("Thanh toán").disabled).toBe(true);
  expect(container.textContent).toContain("Cập nhật số lượng trước khi thanh toán");
});

it("serializes cart mutations and preserves unsaved quantity in another row", async () => {
  routeGet({ "/cart": cart });
  let finish;
  const put = vi.spyOn(client, "put").mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await renderAt("/cart");
  await setValue(rowContaining("Áo A").querySelector("input"), "2");
  await setValue(rowContaining("Áo B").querySelector("input"), "3");
  await click(button("Cập nhật", rowContaining("Áo A")));
  expect(button("Xóa", rowContaining("Áo B")).disabled).toBe(true);
  expect(button("Thanh toán").disabled).toBe(true);
  await click(button("Cập nhật", rowContaining("Áo B")));
  expect(put).toHaveBeenCalledTimes(1);
  await act(async () =>
    finish({ data: { ...cart, items: [{ ...first, quantity: 2 }, second], total_amount: 300000 } }),
  );
  expect(rowContaining("Áo B").querySelector("input").value).toBe("3");
  expect(button("Thanh toán").disabled).toBe(true);
});

it("blocks checkout when stock falls below the saved cart quantity", async () => {
  routeGet({ "/cart": { ...cart, items: [{ ...first, stock_quantity: 0 }] } });
  await renderAt("/cart");
  expect(button("Thanh toán").disabled).toBe(true);
  expect(container.textContent).toContain("Sản phẩm đã hết hàng");
  expect(button("Xóa").disabled).toBe(false);
});
