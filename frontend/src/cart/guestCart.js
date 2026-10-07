const GUEST_KEY = "fashion_guest_cart";
const CHECKOUT_KEY = "fashion_checkout_shop";
export const MAX_GUEST_ITEMS = 200;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function readGuestCart() {
  try {
    const cart = JSON.parse(localStorage.getItem(GUEST_KEY));
    if (
      cart?.version === 1 &&
      UUID.test(cart.merge_id) &&
      Array.isArray(cart.items) &&
      cart.items.length <= MAX_GUEST_ITEMS &&
      cart.items.every(
        (item) =>
          Number.isSafeInteger(item.variant_id) &&
          item.variant_id > 0 &&
          Number.isInteger(item.quantity) &&
          item.quantity > 0 &&
          item.quantity <= 2147483647,
      ) &&
      new Set(cart.items.map((item) => item.variant_id)).size === cart.items.length
    ) {
      return {
        pending: cart.pending === true,
        merge_id: cart.merge_id,
        items: cart.items.map(({ variant_id, quantity }) => ({ variant_id, quantity })),
      };
    }
  } catch {
    /* Invalid or unavailable storage is an empty guest cart. */
  }
  return { pending: false, merge_id: null, items: [] };
}

export function saveGuestItems(items) {
  if (readGuestCart().pending)
    throw new Error("Giỏ tạm đang chờ xác nhận chuyển. Hãy thử đồng bộ lại trước khi sửa.");
  if (items.length > MAX_GUEST_ITEMS) throw new Error("Giỏ tạm chỉ lưu tối đa 200 biến thể.");
  const next = { version: 1, merge_id: crypto.randomUUID(), items };
  try {
    localStorage.setItem(GUEST_KEY, JSON.stringify(next));
  } catch {
    throw new Error(
      "Trình duyệt không cho lưu giỏ hàng. Hãy cho phép lưu dữ liệu hoặc đăng nhập để thêm hàng.",
    );
  }
  window.dispatchEvent(new Event("fashion:guest-cart-changed"));
  return next;
}

export function addGuestItem(variant) {
  const current = readGuestCart();
  const previous = current.items.find((item) => item.variant_id === variant.id);
  const quantity = (previous?.quantity ?? 0) + 1;
  if (quantity > variant.quantity) throw new Error("Không đủ hàng");
  return saveGuestItems(
    previous
      ? current.items.map((item) => (item.variant_id === variant.id ? { ...item, quantity } : item))
      : [...current.items, { variant_id: variant.id, quantity }],
  );
}

export function finishGuestMerge(snapshot) {
  if (readGuestCart().merge_id !== snapshot.merge_id) return false;
  try {
    localStorage.removeItem(GUEST_KEY);
  } catch {
    throw new Error(
      "Giỏ đã chuyển thành công nhưng chưa xóa được giỏ tạm. Hãy thử lại để đồng bộ.",
    );
  }
  window.dispatchEvent(new Event("fashion:guest-cart-changed"));
  return true;
}

export function readCheckoutSelection() {
  try {
    const value = JSON.parse(localStorage.getItem(CHECKOUT_KEY));
    if (Number.isSafeInteger(value?.shop_id) && value.shop_id > 0)
      return { shop_id: value.shop_id, resume: value.resume === true };
  } catch {
    /* Ignore invalid selection metadata. */
  }
  return { shop_id: null, resume: false };
}

export function saveCheckoutSelection(shopId, resume = false) {
  try {
    localStorage.setItem(CHECKOUT_KEY, JSON.stringify({ shop_id: shopId, resume }));
  } catch {
    throw new Error("Không lưu được shop đã chọn. Hãy cho phép trình duyệt lưu dữ liệu.");
  }
}

export function clearCheckoutSelection() {
  try {
    localStorage.removeItem(CHECKOUT_KEY);
  } catch {
    /* The order is already created. */
  }
}

export function markGuestMerge(snapshot, pending = true) {
  const current = readGuestCart();
  if (current.merge_id !== snapshot.merge_id)
    throw new Error("Giỏ tạm vừa thay đổi. Hãy tải lại giỏ hàng.");
  try {
    localStorage.setItem(GUEST_KEY, JSON.stringify({ version: 1, ...current, pending }));
  } catch {
    throw new Error("Không lưu được trạng thái chuyển giỏ. Hãy cho phép trình duyệt lưu dữ liệu.");
  }
}
