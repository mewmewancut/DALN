import { formatCurrency } from "../formatCurrency.js";
import ChatText from "./ChatText.jsx";

const LABELS = {
  revenue: "Doanh thu",
  revenue_vnd: "Doanh thu",
  total_revenue: "Doanh thu",
  total_revenue_vnd: "Tổng doanh thu",
  aov: "Giá trị đơn trung bình",
  aov_vnd: "Giá trị đơn trung bình",
  shop_id: "Mã shop",
  shop_name: "Shop",
  product_id: "Mã sản phẩm",
  product_name: "Sản phẩm",
  total_orders: "Số đơn",
  total_orders_created_this_month: "Số đơn tạo tháng này",
  delivered_orders: "Số đơn đã giao",
  delivered: "Số đơn đã giao",
  cancelled: "Số đơn đã hủy",
  cancel_rate: "Tỷ lệ hủy",
  total_quantity_sold: "Số lượng đã bán",
  avg_rating: "Điểm đánh giá",
  product_count: "Số sản phẩm",
  date: "Ngày",
  month: "Tháng",
  year: "Năm",
  size: "Kích cỡ",
  color: "Màu",
  quantity: "Tồn kho",
  threshold: "Ngưỡng cảnh báo",
};

function cell(value, column) {
  if (value == null) return "—";
  const name = column.name
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
  if (/revenue|aov|amount|doanh.?thu/.test(name) && Number.isFinite(Number(value))) {
    return formatCurrency(value);
  }
  if (/cancel_rate|ty.?le.?huy/.test(name) && Number.isFinite(Number(value))) {
    return `${(Number(value) * 100).toLocaleString("vi-VN", { maximumFractionDigits: 2 })}%`;
  }
  return value;
}

export default function ChatResult({ message }) {
  return (
    <article className="genie-turn">
      <div className="genie-question">
        <strong>Bạn</strong>
        <p>{message.question}</p>
      </div>
      <div className="genie-answer">
        <strong>Genie</strong>
        {message.status === "PENDING" ? (
          <p role="status">Genie đang phân tích dữ liệu…</p>
        ) : (
          <>
            <ChatText text={message.text} />
            {message.tables?.map((table, index) => (
              <div key={index}>
                <p>{table.description}</p>
                {table.rows.length ? (
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          {table.columns.map((column, i) => (
                            <th key={i} scope="col">
                              {LABELS[column.name.toLowerCase()] ??
                                column.name.replaceAll("_", " ")}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {table.rows.map((row, i) => (
                          <tr key={i}>
                            {table.columns.map((column, j) => (
                              <td key={j}>{cell(row[j], column)}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p>Không có dữ liệu phù hợp với câu hỏi.</p>
                )}
                {table.truncated && (
                  <p className="genie-note">
                    Đang hiển thị tối đa 100 dòng của phần kết quả đầu tiên. Hãy thu hẹp câu hỏi để
                    xem đủ dữ liệu.
                  </p>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </article>
  );
}
