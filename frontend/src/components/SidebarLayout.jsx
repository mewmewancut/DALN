import { NavLink } from "react-router";

import SiteLayout from "./SiteLayout.jsx";

export default function SidebarLayout({ label, links, children }) {
  return (
    <SiteLayout wide>
      <div className="shop-layout">
        <nav className="shop-sidebar" aria-label={label}>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="shop-content">{children}</div>
      </div>
    </SiteLayout>
  );
}
