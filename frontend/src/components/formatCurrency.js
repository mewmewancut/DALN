export function formatCurrency(amount) {
  if (amount == null) {
    return "—";
  }
  return `${Number(amount).toLocaleString("vi-VN")} ₫`;
}
