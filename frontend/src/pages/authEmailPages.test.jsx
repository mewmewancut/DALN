// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import App from "../App.jsx";
import client from "../api/client.js";
import { AuthProvider } from "../auth/AuthContext.jsx";

let container;
let root;

beforeEach(() => {
  localStorage.clear();
  container = document.createElement("div");
  document.body.appendChild(container);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  root = null;
  container.remove();
  vi.restoreAllMocks();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

async function renderAt(path) {
  root = createRoot(container);
  await act(async () =>
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    ),
  );
}

async function fill(labelText, value) {
  const label = [...container.querySelectorAll("label")].find((item) =>
    item.textContent.includes(labelText),
  );
  const field = label.querySelector("input");
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(field.constructor.prototype, "value").set;
    setter.call(field, value);
    field.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function submit() {
  await act(async () =>
    container
      .querySelector("form")
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
  );
}

it("xác minh email bằng token trong fragment qua POST", async () => {
  const post = vi.spyOn(client, "post").mockResolvedValue({
    data: { message: "Email đã được xác nhận. Bạn có thể đăng nhập." },
  });
  await renderAt("/verify-email#token=verify-token-value-1234567890123456");
  await act(async () => container.querySelector("button").click());
  expect(post).toHaveBeenCalledWith("/auth/verify-email", {
    token: "verify-token-value-1234567890123456",
  });
  expect(container.querySelector('[role="status"]').textContent).toContain("đã được xác nhận");
});

it("gửi yêu cầu quên mật khẩu và hiển thị thông báo chung", async () => {
  const message = "Nếu email thuộc tài khoản hợp lệ, hệ thống đã gửi hướng dẫn.";
  const post = vi.spyOn(client, "post").mockResolvedValue({ data: { message } });
  await renderAt("/forgot-password");
  await fill("Email", "buyer@example.com");
  await submit();
  expect(post).toHaveBeenCalledWith("/auth/forgot-password", { email: "buyer@example.com" });
  expect(container.querySelector('[role="status"]').textContent).toBe(message);
});

it("không gửi khi xác nhận mật khẩu sai và đặt lại thành công khi khớp", async () => {
  const post = vi.spyOn(client, "post").mockResolvedValue({
    data: { message: "Mật khẩu đã được thay đổi. Hãy đăng nhập lại." },
  });
  await renderAt("/reset-password#token=reset-token-value-12345678901234567");
  await fill("Mật khẩu mới", "NewSecret@123");
  await fill("Xác nhận mật khẩu mới", "Different@123");
  await submit();
  expect(post).not.toHaveBeenCalled();
  expect(container.querySelector('[role="alert"]').textContent).toContain("không khớp");

  await fill("Xác nhận mật khẩu mới", "NewSecret@123");
  await submit();
  expect(post).toHaveBeenCalledWith("/auth/reset-password", {
    token: "reset-token-value-12345678901234567",
    new_password: "NewSecret@123",
  });
  expect(container.querySelector('[role="status"]').textContent).toContain("đã được thay đổi");
});

it("đăng nhập chưa xác minh hiển thị đường dẫn gửi lại", async () => {
  vi.spyOn(client, "post").mockRejectedValue({
    response: { data: { detail: "Email chưa được xác nhận" } },
  });
  await renderAt("/login");
  await fill("Email", "pending@example.com");
  await fill("Mật khẩu", "Secret@123");
  await submit();
  const link = [...container.querySelectorAll("a")].find((item) =>
    item.textContent.includes("Gửi lại email xác minh"),
  );
  expect(link).toBeTruthy();
});
