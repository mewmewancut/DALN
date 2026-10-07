import { Link } from "react-router";

import { formatCurrency } from "../formatCurrency.js";
import { orderStatusLabel } from "../orderPresentation.js";
import RevenueChart from "../RevenueChart.jsx";
import StatCards from "../StatCards.jsx";
import BarList from "./BarList.jsx";
import DashboardPanel from "./DashboardPanel.jsx";
import ShopPerformancePanel from "./ShopPerformancePanel.jsx";
import StockPanel from "./StockPanel.jsx";
import "./dashboard.css";

export default function DashboardBody({ data, admin = false }) {
  const generated = new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(data.generated_at));
  return (
    <div className="dashboard-body">
      <p className="dashboard-period">
        So với {data.previous_from} → {data.previous_to}
      </p>
      <StatCards overview={data.overview} previous={data.previous} />
      <div className="dashboard-grid">
        <DashboardPanel
          title="Doanh thu theo ngày giao"
          className="dashboard-wide"
          description="Đơn đã giao thành công · VND"
        >
          <RevenueChart from={data.from_date} to={data.to_date} rows={data.revenue_daily} />
        </DashboardPanel>
        <DashboardPanel
          title="Trạng thái đơn tạo trong kỳ"
          description="Các đơn được tạo trong kỳ đã chọn"
        >
          <BarList
            rows={data.order_statuses.map((item) => ({
              key: item.status,
              label: orderStatusLabel(item.status),
              value: item.count,
              tone:
                item.status === "CANCELLED"
                  ? "warning"
                  : item.status === "DELIVERED"
                    ? "success"
                    : "neutral",
            }))}
            emptyMessage="Chưa có đơn được tạo trong kỳ."
          />
        </DashboardPanel>
        <DashboardPanel
          title="Sản phẩm bán chạy trong kỳ"
          description="Top 5 theo số lượng đã giao"
        >
          <BarList
            rows={data.top_products.map((item) => ({
              key: item.product_id,
              label: item.product_name,
              value: item.total_quantity_sold,
              formatted: `${item.total_quantity_sold.toLocaleString("vi-VN")} sản phẩm`,
              detail: `${admin ? `${item.shop_name} · ` : ""}${formatCurrency(item.total_revenue)} doanh thu`,
            }))}
            emptyMessage="Chưa có sản phẩm được giao thành công trong kỳ."
          />
        </DashboardPanel>
        {admin && <ShopPerformancePanel shops={data.shops} revenue={data.overview.revenue} />}
        <DashboardPanel
          title="Đơn cần tiếp tục xử lý"
          className="dashboard-wide"
          description={`Đơn chưa hoàn tất, gồm cả đơn được tạo trước kỳ · Cập nhật ${generated}`}
          action={<Link to={admin ? "/admin/orders" : "/shop/orders"}>Mở đơn hàng</Link>}
        >
          <div className="work-queue">
            {data.work_queue.map((item) => (
              <div key={item.status}>
                <span>{orderStatusLabel(item.status)}</span>
                <strong>{item.count.toLocaleString("vi-VN")}</strong>
              </div>
            ))}
          </div>
        </DashboardPanel>
        <StockPanel stock={data.stock} admin={admin} />
      </div>
    </div>
  );
}
