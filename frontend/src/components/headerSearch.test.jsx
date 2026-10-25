// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../api/client.js";
import HeaderSearch from "./HeaderSearch.jsx";

let container;
let root;

function CurrentPath() {
  const location = useLocation();
  return <output>{location.pathname + location.search}</output>;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.useRealTimers();
  vi.restoreAllMocks();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

async function render(path = "/") {
  await act(async () =>
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <HeaderSearch />
        <Routes>
          <Route path="*" element={<CurrentPath />} />
        </Routes>
      </MemoryRouter>,
    ),
  );
}

function input() {
  return container.querySelector('input[aria-label="Tìm kiếm sản phẩm"]');
}

async function type(value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    setter.call(input(), value);
    input().dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function waitDebounce() {
  await act(async () => vi.advanceTimersByTimeAsync(300));
}

const product = (id, name) => ({ id, name, image_url: null, price_from: 150000 });

it("gợi ý sau khi ngừng gõ, không giữ kết quả của từ khóa cũ và mở đúng sản phẩm", async () => {
  const get = vi.spyOn(client, "get").mockImplementation(async (url, options) => ({
    data: { items: options.params.keyword === "áo" ? [product(1, "Áo thun")] : [] },
  }));
  await render();
  await type("áo");
  expect(get).not.toHaveBeenCalled();
  await waitDebounce();
  expect(get).toHaveBeenCalledWith(
    "/products",
    expect.objectContaining({
      params: { keyword: "áo", page: 1, page_size: 5 },
    }),
  );
  expect(container.textContent).toContain("Áo thun");
  expect(container.textContent).toContain("150.000 ₫");

  await type("áo khoác");
  expect(container.textContent).not.toContain("Áo thun");
  expect(container.textContent).toContain("Đang tìm kiếm...");

  await type("áo");
  await waitDebounce();
  await act(async () => container.querySelector(".header-search-suggestion").click());
  expect(container.querySelector("output").textContent).toBe("/products/1");
});

it("hiện lỗi API thay vì báo không có sản phẩm", async () => {
  vi.spyOn(client, "get").mockRejectedValue({ response: { data: { detail: "Máy chủ lỗi" } } });
  await render();
  await type("váy");
  await waitDebounce();
  expect(container.querySelector('[role="alert"]').textContent).toBe(
    "Không tải được gợi ý: Máy chủ lỗi",
  );
  expect(container.textContent).not.toContain("Không tìm thấy sản phẩm phù hợp");
});

it("gửi tìm kiếm tới catalog chung và không lấy từ khóa của gian hàng", async () => {
  vi.spyOn(client, "get").mockResolvedValue({ data: { items: [] } });
  await render("/shops/7?keyword=linen");
  expect(input().value).toBe("");
  await type("đầm  ");
  await act(async () =>
    container
      .querySelector(".header-search-form")
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
  );
  expect(container.querySelector("output").textContent).toBe(
    `/?keyword=${encodeURIComponent("đầm")}`,
  );
  expect(input().value).toBe("đầm");
});
