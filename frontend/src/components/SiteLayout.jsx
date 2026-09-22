import { Link } from "react-router";

import { useAuth } from "../auth/AuthContext.jsx";

export default function SiteLayout({ children, wide = false }) {
  const { session, logout } = useAuth();

  return (
    <main className="shell">
      <section className={`card${wide ? " card-wide" : ""}`}>
        <header className="site-header">
          <Link to="/" className="brand">
            Fashion E-Commerce
          </Link>
          <nav aria-label="Tài khoản">
            {session ? (
              <button type="button" onClick={logout}>
                Đăng xuất
              </button>
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
  );
}
