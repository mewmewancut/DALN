import { Link } from "react-router";

import { useAuth } from "../auth/AuthContext.jsx";

export default function SiteLayout({ children, wide = false }) {
  const { session, logout } = useAuth();

  return (
    <div className="site-frame">
      <div className="announcement-bar">
        <span>Marketplace thời trang Việt</span>
        <span>Giá và tồn kho theo từng biến thể</span>
      </div>
      <main className="shell">
        <section className={`card${wide ? " card-wide" : ""}`}>
          <header className="site-header">
            <Link to="/" className="brand">
              <span className="brand-mark" aria-hidden="true">
                F
              </span>
              <span>
                Fashion
                <small>Marketplace</small>
              </span>
            </Link>
            <nav aria-label="Tài khoản">
              {session ? (
                <>
                  {session.role === "BUYER" && (
                    <>
                      <Link to="/">Sản phẩm</Link>
                      <Link to="/cart">Giỏ hàng</Link>
                      <Link to="/orders">Đơn hàng</Link>
                    </>
                  )}
                  {session.role === "SHOP_OWNER" && <Link to="/shop/dashboard">Quản lý shop</Link>}
                  {session.role === "ADMIN" && <Link to="/admin/dashboard">Quản trị</Link>}
                  <button type="button" onClick={logout}>
                    Đăng xuất
                  </button>
                </>
              ) : (
                <>
                  <Link to="/login">Đăng nhập</Link>
                  <Link to="/register">Đăng ký</Link>
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
