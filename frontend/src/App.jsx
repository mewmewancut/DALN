import { Navigate, Route, Routes } from "react-router";

import { useAuth } from "./auth/AuthContext.jsx";
import RequireRole from "./auth/RequireRole.jsx";
import { homeForRole } from "./auth/session.js";
import SiteLayout from "./components/SiteLayout.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import ProductDetailPage from "./pages/ProductDetailPage.jsx";
import ProductListPage from "./pages/ProductListPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";

function Page({ title, children }) {
  return (
    <SiteLayout>
      <p className="eyebrow">Fashion E-Commerce Platform</p>
      <h1>{title}</h1>
      <p>{children}</p>
    </SiteLayout>
  );
}

function BuyerRoute({ children }) {
  const { session } = useAuth();
  if (session && session.role !== "BUYER") {
    return <Navigate to={homeForRole(session.role)} replace />;
  }
  return children;
}

function GuestRoute({ children }) {
  const { session } = useAuth();
  if (session) {
    return <Navigate to={homeForRole(session.role)} replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <BuyerRoute>
            <ProductListPage />
          </BuyerRoute>
        }
      />
      <Route
        path="/products/:id"
        element={
          <BuyerRoute>
            <ProductDetailPage />
          </BuyerRoute>
        }
      />
      <Route
        path="/login"
        element={
          <GuestRoute>
            <LoginPage />
          </GuestRoute>
        }
      />
      <Route
        path="/register"
        element={
          <GuestRoute>
            <RegisterPage />
          </GuestRoute>
        }
      />
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
