import { Outlet } from "react-router";

import { useAuth } from "../auth/AuthContext.jsx";
import CreateShopForm from "./CreateShopForm.jsx";
import SidebarLayout from "./SidebarLayout.jsx";
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
    <SidebarLayout label="Quản lý shop" links={SHOP_LINKS}>
      <Outlet />
    </SidebarLayout>
  );
}
