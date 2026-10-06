import { formatCurrency } from "../formatCurrency.js";
import { formatRate } from "../StatCards.jsx";
import BarList from "./BarList.jsx";
import DashboardPanel from "./DashboardPanel.jsx";

export default function ShopPerformancePanel({ shops, revenue }) {
  const leadingShare = revenue > 0 && shops.length ? (100 * shops[0].revenue) / revenue : null;
  return (
    <DashboardPanel
      title="Shop đóng góp doanh thu"
      className="dashboard-wide"
      description="Top 10 theo doanh thu giao thành công trong kỳ. Tỷ lệ hủy giúp kiểm tra chất lượng xử lý đơn ở các shop này."
    >
      <div className="shop-performance-grid">
        <div>
          <BarList
            rows={shops.map((shop) => ({
              key: shop.shop_id,
              label: shop.shop_name,
              value: shop.revenue,
              formatted: formatCurrency(shop.revenue),
            }))}
            emptyMessage="Chưa có doanh thu giao thành công trong kỳ."
          />
          {leadingShare != null && (
            <p className="dashboard-footnote">
              Shop dẫn đầu đóng góp{" "}
              {leadingShare.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}% doanh thu toàn
              hệ thống trong kỳ.
            </p>
          )}
        </div>
        <div className="table-wrap">
          <table className="data-table dashboard-table">
            <thead>
              <tr>
                <th>Shop</th>
                <th className="numeric-cell">Đơn tạo</th>
                <th className="numeric-cell">Đơn hủy</th>
                <th className="numeric-cell">Tỷ lệ hủy</th>
                <th className="numeric-cell">AOV</th>
              </tr>
            </thead>
            <tbody>
              {shops.map((shop) => (
                <tr key={shop.shop_id}>
                  <td>{shop.shop_name}</td>
                  <td className="numeric-cell">{shop.order_count}</td>
                  <td className="numeric-cell">{shop.cancelled_count}</td>
                  <td className="numeric-cell">{formatRate(shop.cancel_rate)}</td>
                  <td className="numeric-cell">
                    {shop.aov == null ? "—" : formatCurrency(Math.round(shop.aov))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardPanel>
  );
}
