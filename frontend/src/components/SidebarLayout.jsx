import { NavLink } from "react-router";

import SiteLayout from "./SiteLayout.jsx";
import UiIcon from "./UiIcon.jsx";

const icons = {
  dashboard: "grid",
  products: "bag",
  orders: "orders",
  inventory: "box",
  alerts: "alert",
  suppliers: "truck",
  "purchase-orders": "orders",
  users: "user",
  shops: "store",
};

export default function SidebarLayout({ label, links, children }) {
  return (
    <SiteLayout wide>
      <div className="shop-layout">
        <nav className="shop-sidebar" aria-label={label}>
          <p className="sidebar-label">{label}</p>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to}>
              <UiIcon name={icons[link.to.split("/").at(-1)]} />
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="shop-content">{children}</div>
      </div>
    </SiteLayout>
  );
}
