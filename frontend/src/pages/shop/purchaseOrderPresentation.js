export const PURCHASE_ORDER_STATUSES = ["DRAFT", "ORDERED", "RECEIVED", "CANCELLED"];

const STATUS_LABELS = {
  DRAFT: "Nháp",
  ORDERED: "Đã đặt hàng",
  RECEIVED: "Đã nhập kho",
  CANCELLED: "Đã hủy",
};

// Mirrors the purchase order transitions allowed by the backend (Planning C7).
const ACTIONS = {
  DRAFT: [
    { status: "ORDERED", label: "Đặt hàng" },
    { status: "CANCELLED", label: "Hủy" },
  ],
  ORDERED: [
    { status: "RECEIVED", label: "Đã nhận hàng" },
    { status: "CANCELLED", label: "Hủy" },
  ],
};

export function purchaseOrderStatusLabel(status) {
  return STATUS_LABELS[status] ?? status;
}

export function purchaseOrderActions(status) {
  return ACTIONS[status] ?? [];
}

export function variantLabel(variant) {
  return `${variant.product_name} — ${variant.color} / ${variant.size} (${variant.sku})`;
}
