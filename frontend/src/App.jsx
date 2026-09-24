import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";

import { useAuth } from "./auth/AuthContext.jsx";
import RequireRole from "./auth/RequireRole.jsx";
import { homeForRole } from "./auth/session.js";
import AdminLayout from "./components/AdminLayout.jsx";
import ShopLayout from "./components/ShopLayout.jsx";
import AdminDashboardPage from "./pages/admin/AdminDashboardPage.jsx";
import AdminOrdersPage from "./pages/admin/AdminOrdersPage.jsx";
import AdminShopsPage from "./pages/admin/AdminShopsPage.jsx";
import AdminUsersPage from "./pages/admin/AdminUsersPage.jsx";
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

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [pathname]);

  return null;
}

export default function App() {
  return (
    <>
      <ScrollToTop />
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
          path="/admin"
          element={
            <RequireRole role="ADMIN">
              <AdminLayout />
            </RequireRole>
          }
        >
          <Route index element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="dashboard" element={<AdminDashboardPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="shops" element={<AdminShopsPage />} />
          <Route path="orders" element={<AdminOrdersPage />} />
          <Route path="*" element={<Navigate to="/admin/dashboard" replace />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
