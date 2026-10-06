export const ORDER_STATUSES = [
  "PENDING",
  "CONFIRMED",
  "PREPARING",
  "SHIPPING",
  "DELIVERED",
  "CANCELLED",
];

const STATUS_LABELS = {
  PENDING: "Chờ xác nhận",
  CONFIRMED: "Đã xác nhận",
  PREPARING: "Đang chuẩn bị",
  SHIPPING: "Đang giao",
  DELIVERED: "Đã giao",
  CANCELLED: "Đã hủy",
};

export function orderStatusLabel(status) {
  return STATUS_LABELS[status] ?? status;
}

export function formatDateTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(new Date(value));
}

export function paymentMethodLabel(value) {
  return { COD: "Thanh toán khi nhận hàng", MOCK_CARD: "Thẻ mô phỏng" }[value] ?? value;
}

export function paymentStatusLabel(value) {
  return { PAID: "Đã thanh toán", UNPAID: "Chưa thanh toán" }[value] ?? value;
}
