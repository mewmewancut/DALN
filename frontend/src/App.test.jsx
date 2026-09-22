// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it } from "vitest";

import App from "./App.jsx";
import { AuthProvider, useAuth } from "./auth/AuthContext.jsx";

let container;
let root;

beforeEach(() => {
  localStorage.clear();
  container = document.createElement("div");
  document.body.appendChild(container);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(async () => {
  if (root) {
    await act(async () => root.unmount());
    root = null;
  }
  container.remove();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

async function renderAt(path, role = null, extra = null) {
  if (role) {
    localStorage.setItem(
      "fashion_auth",
      JSON.stringify({ token: "test-token", role, shop_id: null }),
    );
  }
  root = createRoot(container);
  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          {extra}
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );
  });
  return container.textContent;
}

function LoginTrigger() {
  const { login } = useAuth();
  return (
    <button
      type="button"
      id="test-login"
      onClick={() => login({ access_token: "new-token", role: "SHOP_OWNER", shop_id: 7 })}
    >
      Test login
    </button>
  );
}

it("chuyển người chưa đăng nhập khỏi trang shop", async () => {
  const text = await renderAt("/shop/dashboard");
  expect(text).toContain("Đăng nhập");
  expect(text).not.toContain("Tổng quan shop");
});

it("chuyển người sai vai trò về đúng khu vực", async () => {
  const text = await renderAt("/admin/dashboard", "SHOP_OWNER");
  expect(text).toContain("Tổng quan shop");
  expect(text).not.toContain("Quản trị hệ thống");
});

it("đưa admin vào dashboard khi mở trang gốc", async () => {
  const text = await renderAt("/", "ADMIN");
  expect(text).toContain("Quản trị hệ thống");
});

it("lưu phiên và đi tới trang đúng vai trò sau đăng nhập", async () => {
  await renderAt("/login", null, <LoginTrigger />);
  await act(async () => container.querySelector("#test-login").click());
  expect(container.textContent).toContain("Tổng quan shop");
  expect(JSON.parse(localStorage.getItem("fashion_auth"))).toEqual({
    token: "new-token",
    role: "SHOP_OWNER",
    shop_id: 7,
  });
});

it("xóa phiên và rời trang được bảo vệ khi đăng xuất", async () => {
  await renderAt("/shop/dashboard", "SHOP_OWNER");
  await act(async () => container.querySelector("button").click());
  expect(container.textContent).toContain("Đăng nhập");
  expect(container.textContent).not.toContain("Tổng quan shop");
  expect(localStorage.getItem("fashion_auth")).toBeNull();
});
