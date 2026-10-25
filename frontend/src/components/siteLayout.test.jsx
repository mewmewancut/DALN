// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it } from "vitest";

import { AuthProvider } from "../auth/AuthContext.jsx";
import SiteLayout from "./SiteLayout.jsx";

let container;
let root;

beforeEach(() => {
  localStorage.clear();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  localStorage.clear();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

async function render(role = null, path = "/") {
  if (role)
    localStorage.setItem(
      "fashion_auth",
      JSON.stringify({ token: "fake-ui-token", role, shop_id: role === "SHOP_OWNER" ? 7 : null }),
    );
  await act(async () =>
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <SiteLayout>
            <h1>Nội dung trang</h1>
          </SiteLayout>
        </AuthProvider>
      </MemoryRouter>,
    ),
  );
}

it("có lối tắt đầu trang tới nội dung chính có thể nhận focus", async () => {
  await render();
  const skip = container.querySelector("a");
  expect(skip.textContent).toBe("Đến nội dung chính");
  const main = container.querySelector(skip.getAttribute("href"));
  expect(main.tagName).toBe("MAIN");
  main.focus();
  expect(document.activeElement).toBe(main);
  expect(main.textContent).toContain("Nội dung trang");
  expect(main.contains(container.querySelector("header"))).toBe(false);
});

it.each([
  ["BUYER", ["/", "/cart", "/wishlist", "/account/preferences", "/orders", "/account/profile"]],
  ["SHOP_OWNER", ["/shop", "/account/profile"]],
  ["ADMIN", ["/admin", "/account/profile"]],
])("giữ điều hướng tài khoản đúng role %s và nhãn link khi có icon", async (role, links) => {
  await render(role);
  const nav = container.querySelector('nav[aria-label="Điều hướng tài khoản"]');
  expect(container.querySelector(".site-frame").classList.contains("is-management")).toBe(
    role !== "BUYER",
  );
  expect([...nav.querySelectorAll("a")].map((link) => link.getAttribute("href"))).toEqual(links);
  expect(nav.querySelectorAll('svg[aria-hidden="true"]').length).toBe(links.length);
  expect([...nav.querySelectorAll("a")].every((link) => link.textContent.trim().length > 0)).toBe(
    true,
  );
});

it.each([
  [null, true, ["/", "/cart", "/login", "/register"]],
  ["BUYER", true, ["/", "/cart", "/orders", "/account/profile"]],
  ["SHOP_OWNER", false, []],
  ["ADMIN", false, []],
])(
  "chỉ hiện tìm kiếm catalog và link footer dùng được cho role %s",
  async (role, search, links) => {
    await render(role);
    expect(container.querySelector(".header-search") !== null).toBe(search);
    const footer = container.querySelector("footer");
    expect([...footer.querySelectorAll("a")].map((link) => link.getAttribute("href"))).toEqual(
      links,
    );
  },
);

it.each([
  [null, "/", null],
  [null, "/cart", "Về trang chủ"],
  ["SHOP_OWNER", "/shop/dashboard", null],
  ["SHOP_OWNER", "/account/profile", "Về trang quản lý shop"],
  ["ADMIN", "/admin/dashboard", null],
  ["ADMIN", "/account/profile", "Về trang quản trị"],
])("nút quay về của role %s ở %s không trỏ vào chính trang hiện tại", async (role, path, label) => {
  await render(role, path);
  expect(container.querySelector(".back-home-button")?.textContent.replace("←", "") ?? null).toBe(
    label,
  );
});
