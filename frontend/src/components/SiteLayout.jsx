import { Link, NavLink } from "react-router";

import { useAuth } from "../auth/AuthContext.jsx";

export default function SiteLayout({ children, wide = false }) {
  const { session, logout } = useAuth();

  const navClassName = ({ isActive }) =>
    `site-nav-link${isActive ? " active" : ""}`;

  return (
    <div className="site-frame">
      <div className="announcement-bar">
        <span>Marketplace thời trang Việt</span>
        <span>Giá và tồn kho theo từng biến thể</span>
      </div>

      <main className="shell">
        <section className={`card${wide ? " card-wide" : ""}`}>
          <header className="site-header">
            <Link to="/" className="brand" aria-label="Fashion Marketplace - Trang chủ">
              <span className="brand-mark" aria-hidden="true">
                F
              </span>

              <span>
                Fashion
                <small>Marketplace</small>
              </span>
            </Link>

            <nav className="site-nav" aria-label="Điều hướng tài khoản">
              {session ? (
                <>
                  {session.role === "BUYER" && (
                    <>
                      <NavLink to="/" end className={navClassName}>
                        Sản phẩm
                      </NavLink>

                      <NavLink to="/cart" className={navClassName}>
                        Giỏ hàng
                      </NavLink>

                      <NavLink to="/orders" className={navClassName}>
                        Đơn hàng
                      </NavLink>
                    </>
                  )}

                  {session.role === "SHOP_OWNER" && (
                    <NavLink to="/shop" className={navClassName}>
                      Quản lý shop
                    </NavLink>
                  )}

                  {session.role === "ADMIN" && (
                    <NavLink to="/admin" className={navClassName}>
                      Quản trị
                    </NavLink>
                  )}

                  <button
                    type="button"
                    className="site-nav-logout"
                    onClick={logout}
                  >
                    Đăng xuất
                  </button>
                </>
              ) : (
                <>
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

          {children}
        </section>
      </main>
    </div>
  );
}