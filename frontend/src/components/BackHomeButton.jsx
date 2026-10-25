import { Link, useLocation } from "react-router";
import { useAuth } from "../auth/AuthContext.jsx";

export default function BackHomeButton() {
  const { session } = useAuth();
  const { pathname } = useLocation();

  let destination = "/";
  let label = "Về trang chủ";

  if (session?.role === "ADMIN") {
    destination = "/admin/dashboard";
    label = "Về trang quản trị";
  } else if (session?.role === "SHOP_OWNER") {
    destination = "/shop/dashboard";
    label = "Về trang quản lý shop";
  }

  if (pathname === destination) return null;

  return (
    <div className="back-home-wrap">
      <Link className="back-home-button" to={destination}>
        <span aria-hidden="true">←</span>
        {label}
      </Link>
    </div>
  );
}
