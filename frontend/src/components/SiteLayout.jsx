import { Link, NavLink } from "react-router";

import { useAuth } from "../auth/AuthContext.jsx";
import BackHomeButton from "./BackHomeButton.jsx";
import HeaderSearch from "./HeaderSearch.jsx";
import UiIcon from "./UiIcon.jsx";

export default function SiteLayout({ children, wide = false }) {
  const { session, logout } = useAuth();
  const management = ["ADMIN", "SHOP_OWNER"].includes(session?.role);

  const navClassName = ({ isActive }) => `site-nav-link${isActive ? " active" : ""}`;

  return (
    <div className={`site-frame${management ? " is-management" : " is-storefront"}`}>
      <a className="skip-link" href="#main-content">
        Đến nội dung chính
      </a>
      <header className="site-header">
        <Link to="/" className="brand" aria-label="Fashion Marketplace - Trang chủ">
          <span className="brand-mark" aria-hidden="true">
            F
          </span>

          <span>FASHION</span>
        </Link>

        {/* Catalog chỉ mở cho khách và buyer; role quản lý bị chuyển về dashboard. */}
        {!management && <HeaderSearch />}
        <nav className="site-nav" aria-label="Điều hướng tài khoản">
          {session ? (
            <>
              {session.role === "BUYER" && (
                <>
                  <NavLink to="/" end className={navClassName}>
                    <UiIcon name="grid" />
                    Sản phẩm
                  </NavLink>

                  <NavLink to="/cart" className={navClassName}>
                    <UiIcon name="bag" />
                    Giỏ hàng
                  </NavLink>

                  <NavLink to="/wishlist" className={navClassName}>
                    <UiIcon name="heart" />
                    Yêu thích
                  </NavLink>

                  <NavLink to="/account/preferences" className={navClassName}>
                    <UiIcon name="settings" />
                    Sở thích
                  </NavLink>

                  <NavLink to="/orders" className={navClassName}>
                    <UiIcon name="orders" />
                    Đơn hàng
                  </NavLink>
                </>
              )}
              {session.role === "SHOP_OWNER" && (
                <NavLink to="/shop" className={navClassName}>
                  <UiIcon name="store" />
                  Quản lý shop
                </NavLink>
              )}

              {session.role === "ADMIN" && (
                <NavLink to="/admin" className={navClassName}>
                  <UiIcon name="grid" />
                  Quản trị
                </NavLink>
              )}

              <NavLink to="/account/profile" className={navClassName}>
                <UiIcon name="user" />
                Hồ sơ
              </NavLink>

              <button type="button" className="site-nav-logout" onClick={logout}>
                Đăng xuất
              </button>
            </>
          ) : (
            <>
              <NavLink to="/cart" className={navClassName}>
                <UiIcon name="bag" /> Giỏ hàng
              </NavLink>
              <NavLink to="/login" className={navClassName}>
                Đăng nhập
              </NavLink>

              <NavLink to="/register" className={navClassName}>
                Đăng ký
              </NavLink>
            </>
          )}
        </nav>
      </header>
      <main className="shell" id="main-content" tabIndex={-1}>
        <section className={`card${wide ? " card-wide" : ""}`}>
          <BackHomeButton />
          {children}
        </section>
      </main>
      <footer className="fashion-footer">
        <div className="fashion-footer-inner">
          <div className="fashion-footer-brand">
            <h2>
              FASHION<span>.</span>
            </h2>
            <p>Khám phá thời trang hiện đại, thể hiện cá tính và phong cách riêng của bạn.</p>
          </div>

          {!management && (
            <div className="fashion-footer-column">
              <h3>Khám phá</h3>
              <Link to="/">Sản phẩm</Link>
              <Link to="/cart">Giỏ hàng</Link>
            </div>
          )}

          {!session && (
            <div className="fashion-footer-column">
              <h3>Tài khoản</h3>
              <Link to="/login">Đăng nhập</Link>
              <Link to="/register">Đăng ký</Link>
            </div>
          )}

          {session?.role === "BUYER" && (
            <div className="fashion-footer-column">
              <h3>Tài khoản</h3>
              <Link to="/orders">Đơn hàng</Link>
              <Link to="/account/profile">Hồ sơ</Link>
            </div>
          )}

          <div className="fashion-footer-column">
            <h3>FASHION</h3>
            <p>Thời trang dành cho mọi phong cách.</p>
            <p>Fashion Marketplace 2026</p>
          </div>
        </div>

        <div className="fashion-footer-bottom">
          © 2026 FASHION Marketplace. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
