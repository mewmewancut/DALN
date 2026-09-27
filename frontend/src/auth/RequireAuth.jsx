import { Navigate, useLocation } from "react-router";

import { useAuth } from "./AuthContext.jsx";

export default function RequireAuth({ children }) {
  const { session } = useAuth();
  const location = useLocation();

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}
