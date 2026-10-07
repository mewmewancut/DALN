// @vitest-environment jsdom
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import {
  addGuestItem,
  finishGuestMerge,
  markGuestMerge,
  readCheckoutSelection,
  readGuestCart,
  saveCheckoutSelection,
  saveGuestItems,
} from "./guestCart.js";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

it("persists only variant quantities and keeps checkout choice separate", () => {
  addGuestItem({ id: 21, quantity: 3, price: 120000, size: "M", color: "Đỏ" });
  addGuestItem({ id: 21, quantity: 3, price: 999999 });
  addGuestItem({ id: 22, quantity: 2 });
  expect(readGuestCart().items).toEqual([
    { variant_id: 21, quantity: 2 },
    { variant_id: 22, quantity: 1 },
  ]);
  expect(JSON.parse(localStorage.getItem("fashion_guest_cart")).items[0]).toEqual({
    variant_id: 21,
    quantity: 2,
  });
  saveCheckoutSelection(2, true);
  expect(readCheckoutSelection()).toEqual({ shop_id: 2, resume: true });
  expect(() => addGuestItem({ id: 21, quantity: 2 })).toThrow("Không đủ hàng");
  expect(readGuestCart().items[0].quantity).toBe(2);
});

it("does not report success if browser storage is denied", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  expect(() => addGuestItem({ id: 21, quantity: 3 })).toThrow("Trình duyệt không cho lưu giỏ hàng");
  expect(readGuestCart().items).toEqual([]);
});

it("freezes uncertain imports and retains the same key for retry", () => {
  saveGuestItems([{ variant_id: 21, quantity: 1 }]);
  const snapshot = readGuestCart();
  markGuestMerge(snapshot);
  expect(readGuestCart().merge_id).toBe(snapshot.merge_id);
  expect(readGuestCart().pending).toBe(true);
  expect(() => addGuestItem({ id: 21, quantity: 3 })).toThrow("chờ xác nhận");
  expect(() => saveGuestItems([])).toThrow("chờ xác nhận");
  markGuestMerge(snapshot, false);
  saveGuestItems([{ variant_id: 21, quantity: 2 }]);
  expect(readGuestCart().merge_id).not.toBe(snapshot.merge_id);
  expect(finishGuestMerge(snapshot)).toBe(false);
  expect(readGuestCart().items[0].quantity).toBe(2);
});

it("only clears the successfully imported snapshot", () => {
  saveGuestItems([{ variant_id: 21, quantity: 1 }]);
  const snapshot = readGuestCart();
  expect(finishGuestMerge(snapshot)).toBe(true);
  expect(readGuestCart().items).toEqual([]);
});

it.each([
  "{broken",
  JSON.stringify({ version: 99, items: [] }),
  JSON.stringify({ version: 1, merge_id: "invalid", items: [] }),
  JSON.stringify({
    version: 1,
    merge_id: "00000000-0000-4000-8000-000000000001",
    items: [{ variant_id: 1, quantity: true }],
  }),
])("handles corrupt storage without trusting prices or crashing", (stored) => {
  localStorage.setItem("fashion_guest_cart", stored);
  expect(readGuestCart().items).toEqual([]);
});

it("keeps a confirmed snapshot if storage cannot remove it, so retry uses its original key", () => {
  saveGuestItems([{ variant_id: 21, quantity: 1 }]);
  const snapshot = readGuestCart();
  markGuestMerge(snapshot);
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
    throw new Error("denied");
  });
  expect(() => finishGuestMerge(snapshot)).toThrow("chưa xóa được giỏ tạm");
  expect(readGuestCart().merge_id).toBe(snapshot.merge_id);
  expect(readGuestCart().pending).toBe(true);
});
it("refuses a guest cart beyond the variant limit without replacing saved items", () => {
  saveGuestItems([{ variant_id: 21, quantity: 1 }]);
  expect(() =>
    saveGuestItems(Array.from({ length: 201 }, (_, id) => ({ variant_id: id + 1, quantity: 1 }))),
  ).toThrow("200");
  expect(readGuestCart().items).toEqual([{ variant_id: 21, quantity: 1 }]);
});
