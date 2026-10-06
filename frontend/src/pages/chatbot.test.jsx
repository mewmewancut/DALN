// @vitest-environment jsdom

import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../api/client.js";
import {
  alertText,
  button,
  click,
  fill,
  mountContainer,
  renderAt,
  routeGet as rawRouteGet,
  signInAs,
  submit,
  unmountContainer,
} from "../testing/appHarness.jsx";

function routeGet(routes) {
  return rawRouteGet({ "/analytics/chat/conversations": [], ...routes });
}
let container;
beforeEach(() => {
  container = mountContainer();
  signInAs("ADMIN");
});
afterEach(async () => {
  await unmountContainer();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const ready = { available: true, scope: "Toàn hệ thống", message: "Dữ liệu Gold" };
const completed = {
  status: "COMPLETED",
  message_id: "message-1",
  conversation_token: "fake-conversation",
  text: "Doanh thu tháng này: **123.000 VND**",
  tables: [
    {
      description: "Tổng doanh thu",
      columns: [{ name: "revenue", type_name: "DECIMAL" }],
      rows: [["123000"]],
      truncated: false,
    },
  ],
};

it("sends with Enter, keeps Shift+Enter multiline and does not submit during IME composition", async () => {
  routeGet({ "/analytics/chat/config": ready });
  const post = vi.spyOn(client, "post").mockResolvedValue({ data: completed });
  await renderAt("/admin/chatbot");
  await fill("Câu hỏi", "doanh thu thang 9");
  const input = container.querySelector("textarea");
  for (const options of [{ shiftKey: true }, { isComposing: true }, { keyCode: 229 }]) {
    await act(async () =>
      input.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true, ...options }),
      ),
    );
    expect(post).not.toHaveBeenCalled();
  }
  await act(async () =>
    input.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }),
    ),
  );
  expect(post).toHaveBeenCalledExactlyOnceWith("/analytics/chat/messages", {
    question: "doanh thu thang 9",
  });
  expect(input.value).toBe("");
});

it("automatically checks again while a new shop is being provisioned", async () => {
  vi.useFakeTimers();
  let waiting = true;
  const get = routeGet({
    "/analytics/chat/config": () =>
      waiting
        ? { ...ready, available: false, provisioning: true, message: "Đang cấp quyền" }
        : ready,
  });
  await renderAt("/admin/chatbot");
  expect(container.querySelector(".genie-form")).toBeNull();
  waiting = false;
  await act(async () => vi.advanceTimersByTimeAsync(5000));
  expect(container.querySelector(".genie-form")).not.toBeNull();
  expect(get.mock.calls.filter(([url]) => url === "/analytics/chat/config")).toHaveLength(2);
});

it("reopens stored history with a fresh token, renames and deletes only after confirmation", async () => {
  const historyUrl = "/analytics/chat/conversations";
  const detailUrl = `${historyUrl}/42`;
  let items = [{ id: 42, title: "Doanh thu tháng 9", updated_at: "2026-10-06T00:00:00Z" }];
  routeGet({
    "/analytics/chat/config": ready,
    [historyUrl]: () => items,
    [detailUrl]: {
      id: 42,
      title: "Doanh thu tháng 9",
      can_resume: true,
      has_more: false,
      conversation_token: "fresh-owned-token",
      messages: [{ ...completed, question: "doanh thu thang 9", conversation_id: 42 }],
    },
  });
  const patch = vi.spyOn(client, "patch").mockImplementation(async (url, data) => {
    items = [{ ...items[0], title: data.title }];
    return { data: items[0] };
  });
  const remove = vi.spyOn(client, "delete").mockImplementation(async () => {
    items = [];
    return {};
  });
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValue({ data: { ...completed, message_id: "new" } });
  await renderAt("/admin/chatbot");
  await click(button("Doanh thu tháng 9"));
  expect(container.textContent).toContain("doanh thu thang 9");
  await fill("Câu hỏi", "Còn tháng 8?");
  await submit(container.querySelector(".genie-form"));
  expect(post).toHaveBeenCalledWith("/analytics/chat/messages", {
    question: "Còn tháng 8?",
    conversation_token: "fresh-owned-token",
  });
  await click(button("Đổi tên"));
  await fill("Tên cuộc trò chuyện", "So sánh doanh thu");
  await submit(container.querySelector(".genie-history form"));
  expect(patch).toHaveBeenCalledWith(detailUrl, { title: "So sánh doanh thu" });
  await click(button("Xóa"));
  expect(remove).not.toHaveBeenCalled();
  await click(button("Xác nhận xóa"));
  expect(remove).toHaveBeenCalledWith(detailUrl);
  expect(container.querySelectorAll(".genie-turn")).toHaveLength(0);
});

it("does not restore private history after leaving the session", async () => {
  let finish;
  routeGet({
    "/analytics/chat/config": ready,
    "/analytics/chat/conversations": [{ id: 42, title: "Chat cũ" }],
  });
  const original = client.get.getMockImplementation();
  client.get.mockImplementation((url, options) =>
    url.endsWith("/42")
      ? new Promise((resolve) => {
          finish = resolve;
        })
      : original(url, options),
  );
  await renderAt("/admin/chatbot");
  await click(button("Chat cũ"));
  expect(button("Gửi câu hỏi").disabled).toBe(true);
  await unmountContainer();
  container = mountContainer();
  signInAs("SHOP_OWNER", 7);
  await renderAt("/shop/chatbot");
  await act(async () =>
    finish({
      data: { messages: [{ ...completed, question: "private-old-question" }], can_resume: true },
    }),
  );
  expect(container.textContent).not.toContain("private-old-question");
});

it("keeps archived chat readable when its old space cannot be resumed", async () => {
  routeGet({
    "/analytics/chat/config": ready,
    "/analytics/chat/conversations": [{ id: 42, title: "Chat cũ" }],
    "/analytics/chat/conversations/42": {
      id: 42,
      can_resume: false,
      conversation_token: null,
      has_more: false,
      messages: [{ ...completed, question: "Doanh thu cũ" }],
    },
  });
  await renderAt("/admin/chatbot");
  await click(button("Chat cũ"));
  expect(container.textContent).toContain("Doanh thu cũ");
  expect(container.querySelector("textarea").disabled).toBe(true);
  await click(button("Cuộc trò chuyện mới"));
  expect(container.querySelector("textarea").disabled).toBe(false);
});

it("keeps saved results readable while Genie configuration is unavailable", async () => {
  routeGet({
    "/analytics/chat/config": { ...ready, available: false, message: "Chatbot tạm chưa khả dụng" },
    "/analytics/chat/conversations": [{ id: 42, title: "Chat đã lưu" }],
    "/analytics/chat/conversations/42": {
      id: 42,
      can_resume: false,
      conversation_token: null,
      has_more: false,
      messages: [{ ...completed, question: "Doanh thu cũ" }],
    },
  });
  await renderAt("/admin/chatbot");
  await click(button("Chat đã lưu"));
  expect(container.textContent).toContain("Doanh thu cũ");
  expect(container.textContent).toContain("123.000 ₫");
  expect(container.querySelector(".genie-form")).toBeNull();
});

it.each([
  ["ADMIN", "/admin/chatbot", null],
  ["SHOP_OWNER", "/shop/chatbot", 7],
])(
  "loads the %s chat from shared API and shows role navigation and server scope",
  async (role, path, shop) => {
    signInAs(role, shop);
    const get = routeGet({
      "/analytics/chat/config": {
        ...ready,
        scope: role === "ADMIN" ? "Toàn hệ thống" : "Shop của bạn",
      },
    });
    await renderAt(path);
    expect(get).toHaveBeenCalledWith(
      "/analytics/chat/config",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(container.querySelector(`a[href="${path}"]`).textContent).toContain("Chatbot Genie");
    expect(container.textContent).toContain(
      role === "ADMIN" ? "Phạm vi: Toàn hệ thống" : "Phạm vi: Shop của bạn",
    );
    expect(button("Gửi câu hỏi").disabled).toBe(true);
  },
);

it("sends trimmed question, shows VND, preserves followup token and resets conversation", async () => {
  routeGet({ "/analytics/chat/config": ready });
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValueOnce({ data: completed })
    .mockResolvedValueOnce({ data: { ...completed, message_id: "message-2" } })
    .mockResolvedValueOnce({ data: { ...completed, message_id: "message-3" } });
  await renderAt("/admin/chatbot");
  await fill("Câu hỏi", " Doanh thu? ");
  await submit(container.querySelector(".genie-form"));
  expect(post).toHaveBeenLastCalledWith("/analytics/chat/messages", { question: "Doanh thu?" });
  expect(container.textContent).toContain("123.000 ₫");
  expect(container.querySelector(".genie-text strong").textContent).toBe("123.000 VND");
  expect(container.querySelector(".genie-answer th").textContent).toBe("Doanh thu");
  expect(container.textContent).toContain("Doanh thu?");
  await fill("Câu hỏi", "Còn tháng trước?");
  await submit(container.querySelector(".genie-form"));
  expect(post).toHaveBeenLastCalledWith("/analytics/chat/messages", {
    question: "Còn tháng trước?",
    conversation_token: "fake-conversation",
  });
  await click(button("Cuộc trò chuyện mới"));
  expect(container.querySelectorAll(".genie-turn").length).toBe(0);
  await fill("Câu hỏi", "Câu hỏi mới");
  await submit(container.querySelector(".genie-form"));
  expect(post).toHaveBeenLastCalledWith("/analytics/chat/messages", { question: "Câu hỏi mới" });
});

it("polls pending response and blocks duplicate submits while processing", async () => {
  vi.useFakeTimers();
  routeGet({ "/analytics/chat/config": ready });
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValueOnce({ data: { ...completed, status: "PENDING", tables: [], text: "" } })
    .mockResolvedValueOnce({ data: completed });
  await renderAt("/admin/chatbot");
  await click(button("Doanh thu tháng này là bao nhiêu?"));
  await submit(container.querySelector(".genie-form"));
  expect(button("Gửi câu hỏi").disabled).toBe(true);
  expect(container.textContent).toContain("Genie đang phân tích dữ liệu");
  await submit(container.querySelector(".genie-form"));
  expect(post).toHaveBeenCalledTimes(1);
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(post).toHaveBeenLastCalledWith(
    "/analytics/chat/messages/message-1",
    { conversation_token: "fake-conversation" },
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  );
  expect(container.textContent).toContain("123.000 ₫");
});

it("keeps pending token on polling failure and retries reading without resending question", async () => {
  vi.useFakeTimers();
  routeGet({ "/analytics/chat/config": ready });
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValueOnce({ data: { ...completed, status: "PENDING" } })
    .mockRejectedValueOnce({ response: { data: { detail: "Genie quá tải" } } })
    .mockResolvedValueOnce({ data: completed });
  await renderAt("/admin/chatbot");
  await fill("Câu hỏi", "Doanh thu?");
  await submit(container.querySelector(".genie-form"));
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(alertText()).toBe("Genie quá tải");
  await click(button("Kiểm tra lại kết quả"));
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(container.textContent).toContain("123.000 ₫");
  expect(post.mock.calls.filter(([path]) => path === "/analytics/chat/messages")).toHaveLength(1);
});

it("stops polling after bounded wait and lets user check result", async () => {
  vi.useFakeTimers();
  routeGet({ "/analytics/chat/config": ready });
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValue({ data: { ...completed, status: "PENDING" } });
  await renderAt("/admin/chatbot");
  await fill("Câu hỏi", "Doanh thu?");
  await submit(container.querySelector(".genie-form"));
  await act(async () => vi.advanceTimersByTimeAsync(122000));
  expect(button("Kiểm tra lại kết quả")).toBeTruthy();
  const count = post.mock.calls.length;
  await act(async () => vi.advanceTimersByTimeAsync(10000));
  expect(post.mock.calls.length).toBe(count);
});

it("ignores a late polling response after the conversation is reset", async () => {
  vi.useFakeTimers();
  routeGet({ "/analytics/chat/config": ready });
  let finish;
  vi.spyOn(client, "post")
    .mockResolvedValueOnce({ data: { ...completed, status: "PENDING" } })
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
  await renderAt("/admin/chatbot");
  await fill("Câu hỏi", "Doanh thu?");
  await submit(container.querySelector(".genie-form"));
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  await click(button("Cuộc trò chuyện mới"));
  await act(async () => finish({ data: completed }));
  expect(container.querySelectorAll(".genie-turn")).toHaveLength(0);
  expect(container.textContent).not.toContain("123.000 ₫");
});

it("shows a failed Genie reply and allows a new question", async () => {
  routeGet({ "/analytics/chat/config": ready });
  vi.spyOn(client, "post").mockResolvedValue({
    data: { ...completed, status: "FAILED", text: "Genie chưa trả lời được", tables: [] },
  });
  await renderAt("/admin/chatbot");
  await fill("Câu hỏi", "Doanh thu?");
  await submit(container.querySelector(".genie-form"));
  expect(container.textContent).toContain("Genie chưa trả lời được");
  expect(container.querySelector("textarea").disabled).toBe(false);
});

it("shows unavailable or load error without an active question form", async () => {
  routeGet({
    "/analytics/chat/config": { ...ready, available: false, message: "Chatbot chưa được cấu hình" },
  });
  await renderAt("/admin/chatbot");
  expect(container.textContent).toContain("chưa được cấu hình");
  expect(container.querySelector(".genie-form")).toBeNull();
});

it("retries config load failure and keeps question on send failure", async () => {
  vi.spyOn(client, "get")
    .mockRejectedValueOnce({ response: { data: { detail: "Shop đã bị khóa" } } })
    .mockResolvedValueOnce({ data: ready })
    .mockResolvedValue({ data: [] });
  vi.spyOn(client, "post").mockRejectedValue({
    response: { data: { detail: "Không thể kết nối Genie" } },
  });
  await renderAt("/admin/chatbot");
  expect(alertText()).toBe("Shop đã bị khóa");
  await click(button("Tải lại"));
  await fill("Câu hỏi", "Doanh thu?");
  await submit(container.querySelector(".genie-form"));
  expect(alertText()).toBe("Không thể kết nối Genie");
  expect(container.querySelector("textarea").value).toBe("Doanh thu?");
});

it("shows empty, failed and truncated results and escapes model text", async () => {
  routeGet({ "/analytics/chat/config": ready });
  vi.spyOn(client, "post").mockResolvedValue({
    data: {
      ...completed,
      text: "<img src=x onerror=alert(1)>",
      tables: [{ ...completed.tables[0], rows: [], truncated: true }],
    },
  });
  await renderAt("/admin/chatbot");
  await fill("Câu hỏi", "Doanh thu?");
  await submit(container.querySelector(".genie-form"));
  expect(container.querySelector(".genie-answer img")).toBeNull();
  expect(container.textContent).toContain("Không có dữ liệu phù hợp");
  expect(container.textContent).toContain("tối đa 100 dòng");
});

it.each(["/admin/chatbot", "/shop/chatbot"])("buyer cannot enter %s", async (path) => {
  signInAs("BUYER");
  const get = routeGet({
    "/products": { items: [], total: 0 },
    "/categories": [],
    "/recommendations/products": { items: [] },
    "/wishlist": { items: [] },
  });
  await renderAt(path);
  expect(get.mock.calls.some(([url]) => url === "/analytics/chat/config")).toBe(false);
  expect(container.textContent).not.toContain("Phạm vi:");
});

it("formats cancellation ratios as percentages and preserves an undefined AOV", async () => {
  routeGet({ "/analytics/chat/config": ready });
  vi.spyOn(client, "post").mockResolvedValue({
    data: {
      ...completed,
      tables: [
        {
          description: "Tỷ lệ hủy và giá trị đơn",
          columns: [{ name: "cancel_rate" }, { name: "aov_vnd" }],
          rows: [["0.16666666666666666", null]],
          truncated: false,
        },
      ],
    },
  });
  await renderAt("/admin/chatbot");
  await fill("Câu hỏi", "Tỷ lệ hủy?");
  await submit(container.querySelector(".genie-form"));
  const cells = [...container.querySelectorAll(".genie-answer td")];
  expect(cells.map((cell) => cell.textContent)).toEqual(["16,67%", "—"]);
});
