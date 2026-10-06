import { Link } from "react-router";

import DashboardPanel from "./DashboardPanel.jsx";

export default function StockPanel({ stock, admin }) {
  return (
    <DashboardPanel
      title="Ưu tiên nhập hàng"
      className="dashboard-wide"
      description="Tồn kho hiện tại của các biến thể đang bán. Ưu tiên hết hàng, sau đó sức bán trong kỳ; không phải dự báo lượng cần nhập."
      action={
        <Link to={admin ? "/admin/shops" : "/shop/inventory"}>
          {admin ? "Quản lý shop" : "Mở tồn kho"}
        </Link>
      }
    >
      <div className="stock-summary">
        <span>
          <strong>{stock.out_of_stock}</strong> biến thể hết hàng
        </span>
        <span>
          <strong>{stock.low_stock}</strong> còn hàng dưới ngưỡng
        </span>
        <span>{stock.tracked_variants} biến thể đang theo dõi</span>
      </div>
      {!stock.priorities.length ? (
        <p className="dashboard-empty">Không có biến thể đang bán cần ưu tiên nhập hàng.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table dashboard-table">
            <thead>
              <tr>
                {admin && <th>Shop</th>}
                <th>Sản phẩm / biến thể</th>
                <th>Còn lại</th>
                <th>Ngưỡng</th>
                <th>Đã bán trong kỳ</th>
              </tr>
            </thead>
            <tbody>
              {stock.priorities.map((item) => (
                <tr key={item.variant_id}>
                  {admin && <td>{item.shop_name}</td>}
                  <td>
                    {item.product_name}
                    <small>
                      {item.size} · {item.color}
                    </small>
                  </td>
                  <td>
                    <span className={item.quantity === 0 ? "stock-zero" : "stock-low"}>
                      {item.quantity === 0 ? "Hết hàng" : item.quantity}
                    </span>
                  </td>
                  <td>{item.threshold}</td>
                  <td>{item.sold_quantity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="dashboard-footnote">
        Hiển thị tối đa 8 biến thể cần ưu tiên. Sức bán chỉ tính đơn đã giao thành công trong kỳ.
      </p>
    </DashboardPanel>
  );
}
