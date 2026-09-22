export function errorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((item) => item.msg)
      .filter(Boolean)
      .join("; ");
  return "Không thể kết nối tới máy chủ. Vui lòng thử lại.";
}
