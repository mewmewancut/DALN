import { createContext, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { clearSession, homeForRole, readSession, saveSession } from "./session.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(readSession);
  const navigate = useNavigate();

  useEffect(() => {
    const onSessionCleared = () => setSession(null);
    window.addEventListener("fashion:session-cleared", onSessionCleared);
    return () => window.removeEventListener("fashion:session-cleared", onSessionCleared);
  }, []);

  function login({ access_token, role, shop_id }) {
    const nextSession = { token: access_token, role, shop_id };
    saveSession(nextSession);
    setSession(nextSession);
    navigate(homeForRole(role), { replace: true });
  }

  function logout() {
    clearSession();
    setSession(null);
  }

  function setShopId(shopId) {
    const nextSession = { ...session, shop_id: shopId };
    saveSession(nextSession);
    setSession(nextSession);
  }

  return (
    <AuthContext.Provider value={{ session, login, logout, setShopId }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
