import { Navigate, useLocation } from "react-router";

import { useAuth } from "./AuthContext.jsx";
import { homeForRole } from "./session.js";

export default function RequireRole({ role, children }) {
  const { session } = useAuth();
  const location = useLocation();

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (session.role !== role) {
    return <Navigate to={homeForRole(session.role)} replace />;
  }
  return children;
}
