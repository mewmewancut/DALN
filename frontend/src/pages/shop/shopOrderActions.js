// Mirrors the shop transitions allowed by the backend state machine (Planning C5).
const SHOP_ORDER_ACTIONS = {
  PENDING: [
    { status: "CONFIRMED", label: "Xác nhận" },
    { status: "CANCELLED", label: "Hủy" },
  ],
  CONFIRMED: [
    { status: "PREPARING", label: "Chuẩn bị" },
    { status: "CANCELLED", label: "Hủy" },
  ],
  PREPARING: [{ status: "SHIPPING", label: "Giao hàng" }],
  SHIPPING: [{ status: "DELIVERED", label: "Đã giao" }],
};

export function shopOrderActions(status) {
  return SHOP_ORDER_ACTIONS[status] ?? [];
}
