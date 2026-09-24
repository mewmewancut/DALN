import { Navigate, Route, Routes } from "react-router";

import { useAuth } from "./auth/AuthContext.jsx";
import RequireRole from "./auth/RequireRole.jsx";
import { homeForRole } from "./auth/session.js";
import ShopLayout from "./components/ShopLayout.jsx";
import SiteLayout from "./components/SiteLayout.jsx";
import CartPage from "./pages/CartPage.jsx";
import CheckoutPage from "./pages/CheckoutPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import OrderDetailPage from "./pages/OrderDetailPage.jsx";
import OrdersPage from "./pages/OrdersPage.jsx";
import ProductDetailPage from "./pages/ProductDetailPage.jsx";
import ProductListPage from "./pages/ProductListPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";
import ShopAlertsPage from "./pages/shop/ShopAlertsPage.jsx";
import ShopDashboardPage from "./pages/shop/ShopDashboardPage.jsx";
import ShopInventoryPage from "./pages/shop/ShopInventoryPage.jsx";
import ShopOrdersPage from "./pages/shop/ShopOrdersPage.jsx";
import ShopProductsPage from "./pages/shop/ShopProductsPage.jsx";
import ShopPurchaseOrdersPage from "./pages/shop/ShopPurchaseOrdersPage.jsx";
import ShopSuppliersPage from "./pages/shop/ShopSuppliersPage.jsx";

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
        path="/cart"
        element={
          <RequireRole role="BUYER">
            <CartPage />
          </RequireRole>
        }
      />
      <Route
        path="/checkout"
        element={
          <RequireRole role="BUYER">
            <CheckoutPage />
          </RequireRole>
        }
      />
      <Route
        path="/orders"
        element={
          <RequireRole role="BUYER">
            <OrdersPage />
          </RequireRole>
        }
      />
      <Route
        path="/orders/:id"
        element={
          <RequireRole role="BUYER">
            <OrderDetailPage />
          </RequireRole>
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
        path="/shop"
        element={
          <RequireRole role="SHOP_OWNER">
            <ShopLayout />
          </RequireRole>
        }
      >
        <Route index element={<Navigate to="/shop/dashboard" replace />} />
        <Route path="dashboard" element={<ShopDashboardPage />} />
        <Route path="products" element={<ShopProductsPage />} />
        <Route path="orders" element={<ShopOrdersPage />} />
        <Route path="inventory" element={<ShopInventoryPage />} />
        <Route path="alerts" element={<ShopAlertsPage />} />
        <Route path="suppliers" element={<ShopSuppliersPage />} />
        <Route path="purchase-orders" element={<ShopPurchaseOrdersPage />} />
        <Route path="*" element={<Navigate to="/shop/dashboard" replace />} />
      </Route>
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
