import { Link, Navigate, Route, Routes } from "react-router";

import { useAuth } from "./auth/AuthContext.jsx";
import RequireRole from "./auth/RequireRole.jsx";
import { homeForRole } from "./auth/session.js";

function Page({ title, children }) {
  const { session, logout } = useAuth();
  return (
    <main className="shell">
      <section className="card">
        <header className="site-header">
          <Link to="/" className="brand">Fashion E-Commerce</Link>
          {session ? (
            <button type="button" onClick={logout}>Đăng xuất</button>
          ) : (
            <Link to="/login">Đăng nhập</Link>
          )}
        </header>
        <p className="eyebrow">Fashion E-Commerce Platform</p>
        <h1>{title}</h1>
        <p>{children}</p>
      </section>
    </main>
  );
}

function BuyerHome() {
  const { session } = useAuth();
  if (session && session.role !== "BUYER") {
    return <Navigate to={homeForRole(session.role)} replace />;
  }
  return <Page title="Khám phá thời trang">Danh sách sản phẩm đang được hoàn thiện.</Page>;
}

function GuestPage({ title }) {
  const { session } = useAuth();
  if (session) {
    return <Navigate to={homeForRole(session.role)} replace />;
  }
  return <Page title={title}>Trang này đang được hoàn thiện.</Page>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<BuyerHome />} />
      <Route path="/login" element={<GuestPage title="Đăng nhập" />} />
      <Route path="/register" element={<GuestPage title="Đăng ký" />} />
      <Route
        path="/shop/dashboard"
        element={
          <RequireRole role="SHOP_OWNER">
            <Page title="Tổng quan shop">Khu vực chủ shop đang được hoàn thiện.</Page>
          </RequireRole>
        }
      />
      <Route
        path="/admin/dashboard"
        element={
          <RequireRole role="ADMIN">
            <Page title="Quản trị hệ thống">Khu vực quản trị đang được hoàn thiện.</Page>
          </RequireRole>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
