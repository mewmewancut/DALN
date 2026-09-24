import { NavLink, Outlet } from "react-router";

import { useAuth } from "../auth/AuthContext.jsx";
import CreateShopForm from "./CreateShopForm.jsx";
import SiteLayout from "./SiteLayout.jsx";

const SHOP_LINKS = [
  { to: "/shop/dashboard", label: "Tổng quan" },
  { to: "/shop/products", label: "Sản phẩm" },
  { to: "/shop/orders", label: "Đơn hàng" },
  { to: "/shop/inventory", label: "Tồn kho" },
  { to: "/shop/alerts", label: "Cảnh báo" },
  { to: "/shop/suppliers", label: "Nhà cung cấp" },
  { to: "/shop/purchase-orders", label: "Nhập hàng" },
];

export default function ShopLayout() {
  const { session } = useAuth();

  if (session.shop_id == null) {
    return (
      <SiteLayout>
        <CreateShopForm />
      </SiteLayout>
    );
  }

  return (
    <SiteLayout wide>
      <div className="shop-layout">
        <nav className="shop-sidebar" aria-label="Quản lý shop">
          {SHOP_LINKS.map((link) => (
            <NavLink key={link.to} to={link.to}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="shop-content">
          <Outlet />
        </div>
      </div>
    </SiteLayout>
  );
}
