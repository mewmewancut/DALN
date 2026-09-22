const STORAGE_KEY = "fashion_auth";
const HOME_BY_ROLE = {
  BUYER: "/",
  SHOP_OWNER: "/shop/dashboard",
  ADMIN: "/admin/dashboard",
};

export function homeForRole(role) {
  return HOME_BY_ROLE[role] ?? "/";
}

export function readSession() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (
      stored &&
      typeof stored.token === "string" &&
      stored.token.length > 0 &&
      Object.hasOwn(HOME_BY_ROLE, stored.role)
    ) {
      return stored;
    }
  } catch {
    // Treat invalid or unavailable browser storage as a signed-out session.
  }
  return null;
}

export function saveSession(session) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
}
