// @vitest-environment jsdom

import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../../api/client.js";
import {
  button,
  click,
  fill,
  mountContainer,
  renderAt,
  routeGet,
  signInAs,
  submit,
  unmountContainer,
} from "../../testing/appHarness.jsx";

let container;
const ready = { available: true, scope: "Shop của bạn", message: "Dữ liệu Gold" };
const completed = {
  status: "COMPLETED",
  message_id: "message-1",
  conversation_id: 42,
  conversation_token: "fake-conversation",
  text: "Doanh thu: 123.000 VND",
  tables: [],
};
function launcher() {
  return container.querySelector(".genie-widget-launcher");
}
function mockPages(config = ready) {
  return routeGet({
    "/auth/me": { id: 1 },
    "/admin/users": { items: [], total: 0 },
    "/admin/shops": { items: [], total: 0 },
    "/shop/inventory": [],
    "/suppliers": [],
    "/users/me/profile": { full_name: "Tài khoản thử", email: "test@example.com", role: "ADMIN" },
    "/analytics/chat/config": config,
    "/analytics/chat/conversations": [],
  });
}
beforeEach(() => {
  container = mountContainer();
  signInAs("ADMIN");
});
afterEach(async () => {
  await unmountContainer();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

it.each([
  ["ADMIN", null, "/admin/users", "/admin/shops", "Toàn hệ thống"],
  ["SHOP_OWNER", 7, "/shop/inventory", "/shop/suppliers", "Shop của bạn"],
])(
  "keeps the %s conversation and draft across collapse, navigation and expansion",
  async (role, shop, start, next, scope) => {
    signInAs(role, shop);
    const get = mockPages({ ...ready, scope });
    const post = vi
      .spyOn(client, "post")
      .mockResolvedValueOnce({ data: completed })
      .mockResolvedValue({ data: { ...completed, message_id: "message-2" } });
    const chatPath = role === "ADMIN" ? "/admin/chatbot" : "/shop/chatbot";
    await renderAt(start, [next, start, "/account/profile"]);
    expect(launcher().getAttribute("aria-expanded")).toBe("false");
    expect(get.mock.calls.some(([url]) => url.startsWith("/analytics/chat"))).toBe(false);
    await click(launcher());
    expect(container.querySelector('[role="dialog"]').contains(document.activeElement)).toBe(true);
    expect(container.textContent).toContain(`Phạm vi: ${scope}`);
    await fill("Câu hỏi", "Doanh thu?");
    await submit(container.querySelector(".genie-form"));
    await fill("Câu hỏi", "Còn tháng trước?");
    await click(button("Thu gọn"));
    expect(container.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(launcher());
    await click(container.querySelector(`nav[aria-label="Test navigation"] a[href="${next}"]`));
    await click(launcher());
    expect(container.textContent).toContain(completed.text);
    expect(container.querySelector("textarea").value).toBe("Còn tháng trước?");
    expect(container.querySelector(".genie-widget-header a").getAttribute("href")).toBe(chatPath);
    await click(container.querySelector(".genie-widget-header a"));
    expect(launcher()).toBeNull();
    expect(container.querySelectorAll(".genie-form")).toHaveLength(1);
    expect(container.querySelector("textarea").value).toBe("Còn tháng trước?");
    await submit(container.querySelector(".genie-form"));
    expect(post).toHaveBeenLastCalledWith("/analytics/chat/messages", {
      question: "Còn tháng trước?",
      conversation_token: "fake-conversation",
    });
    await click(
      container.querySelector('nav[aria-label="Test navigation"] a[href="/account/profile"]'),
    );
    expect(launcher()).toBeTruthy();
    expect(container.textContent).toContain(completed.text);
    expect(get.mock.calls.filter(([url]) => url === "/analytics/chat/config")).toHaveLength(1);
  },
);

it("closes with Escape and returns keyboard focus to the launcher", async () => {
  mockPages();
  await renderAt("/admin/users");
  await click(launcher());
  const input = container.querySelector("textarea");
  input.focus();
  await act(async () =>
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })),
  );
  expect(container.querySelector('[role="dialog"]')).toBeNull();
  expect(document.activeElement).toBe(launcher());
});

it("continues one pending request while collapsed and on another page without resending", async () => {
  vi.useFakeTimers();
  mockPages();
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValueOnce({ data: { ...completed, status: "PENDING", text: "" } })
    .mockResolvedValueOnce({ data: completed });
  await renderAt("/admin/users", ["/admin/shops"]);
  await click(launcher());
  await fill("Câu hỏi", "Doanh thu?");
  await submit(container.querySelector(".genie-form"));
  await click(button("Thu gọn"));
  expect(launcher().textContent).toContain("đang xử lý");
  await click(container.querySelector('nav[aria-label="Test navigation"] a'));
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  await click(launcher());
  expect(container.textContent).toContain(completed.text);
  expect(button("Gửi câu hỏi").disabled).toBe(true);
  await fill("Câu hỏi", "Tiếp tục");
  expect(button("Gửi câu hỏi").disabled).toBe(false);
  expect(post.mock.calls.filter(([url]) => url === "/analytics/chat/messages")).toHaveLength(1);
  expect(
    post.mock.calls.filter(([url]) => url === "/analytics/chat/messages/message-1"),
  ).toHaveLength(1);
});

it("shows API errors, retries config and offers history while unavailable", async () => {
  const get = mockPages({ ...ready, available: false, message: "Chatbot chưa được cấu hình" });
  const original = get.getMockImplementation();
  let failed = false;
  get.mockImplementation((url, options) => {
    if (url === "/analytics/chat/config" && !failed) {
      failed = true;
      return Promise.reject({ response: { data: { detail: "Không thể tải chatbot" } } });
    }
    return original(url, options);
  });
  await renderAt("/admin/users");
  await click(launcher());
  expect(container.querySelector('[role="alert"]').textContent).toBe("Không thể tải chatbot");
  await click(button("Tải lại"));
  expect(container.textContent).toContain("Chatbot chưa được cấu hình");
  expect(container.querySelector(".genie-form")).toBeNull();
  expect(container.querySelector(".genie-compact-history")).toBeTruthy();
});

it("clears private data and aborts polling when signing out", async () => {
  vi.useFakeTimers();
  const get = mockPages();
  const original = get.getMockImplementation();
  get.mockImplementation((url, options) =>
    url === "/products"
      ? Promise.resolve({ data: { items: [], total: 0 } })
      : url === "/categories"
        ? Promise.resolve({ data: [] })
        : original(url, options),
  );
  let finish;
  let signal;
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValueOnce({ data: { ...completed, status: "PENDING", text: "private-pending" } })
    .mockImplementationOnce((_url, _body, options) => {
      signal = options.signal;
      return new Promise((resolve) => {
        finish = resolve;
      });
    });
  await renderAt("/admin/users");
  await click(launcher());
  await fill("Câu hỏi", "private-question");
  await submit(container.querySelector(".genie-form"));
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  await click(button("Đăng xuất"));
  expect(signal.aborted).toBe(true);
  await act(async () => finish({ data: { ...completed, text: "private-answer" } }));
  await act(async () => vi.advanceTimersByTimeAsync(6000));
  expect(launcher()).toBeNull();
  expect(container.textContent).not.toContain("private-");
  expect(post).toHaveBeenCalledTimes(2);
});

it.each([
  ["BUYER", null, "/"],
  [null, null, "/login"],
  ["SHOP_OWNER", null, "/shop"],
])("does not load or show chat for %s without access", async (role, shop, path) => {
  if (role) signInAs(role, shop);
  else localStorage.clear();
  const get = routeGet({
    "/products": { items: [], total: 0 },
    "/categories": [],
    "/recommendations/products": { items: [] },
    "/wishlist": { items: [] },
  });
  await renderAt(path);
  expect(launcher()).toBeNull();
  expect(get.mock.calls.some(([url]) => url.startsWith("/analytics/chat"))).toBe(false);
});
