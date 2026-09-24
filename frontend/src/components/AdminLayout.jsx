import { Outlet } from "react-router";

import SidebarLayout from "./SidebarLayout.jsx";

const ADMIN_LINKS = [
  { to: "/admin/dashboard", label: "Tổng quan" },
  { to: "/admin/users", label: "Người dùng" },
  { to: "/admin/shops", label: "Shop" },
  { to: "/admin/orders", label: "Đơn hàng" },
];

export default function AdminLayout() {
  return (
    <SidebarLayout label="Quản trị" links={ADMIN_LINKS}>
      <Outlet />
    </SidebarLayout>
  );
}
