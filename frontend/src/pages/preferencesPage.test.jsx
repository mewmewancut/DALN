// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../api/client.js";
import {
  alertText,
  button,
  click,
  fill,
  mountContainer,
  renderAt,
  signInAs,
  submit,
  unmountContainer,
} from "../testing/appHarness.jsx";

let container;

const options = {
  categories: [
    { id: 1, name: "Áo" },
    { id: 2, name: "Giày" },
  ],
  colors: ["Đen", "Trắng"],
};

const preferences = {
  category_ids: [1],
  colors: ["Đen"],
  min_price: 100000,
  max_price: 500000,
};

beforeEach(() => {
  container = mountContainer();
  signInAs("BUYER");
});

afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

function checkbox(labelText) {
  return [...container.querySelectorAll("label")]
    .find((label) => label.textContent.trim() === labelText)
    .querySelector('input[type="checkbox"]');
}

function mockLoad() {
  return vi.spyOn(client, "get").mockImplementation(async (url) => {
    if (url === "/users/me/preferences/options") return { data: options };
    if (url === "/users/me/preferences") return { data: preferences };
    throw new Error(`Unexpected GET ${url}`);
  });
}

it("tải lựa chọn hiện tại và lưu danh mục, màu, khoảng giá", async () => {
  mockLoad();
  const put = vi.spyOn(client, "put").mockResolvedValue({
    data: {
      category_ids: [1, 2],
      colors: ["Đen", "Trắng"],
      min_price: 150000,
      max_price: 600000,
    },
  });

  await renderAt("/account/preferences");
  expect(checkbox("Áo").checked).toBe(true);
  expect(checkbox("Đen").checked).toBe(true);
  expect(container.textContent).toContain("Sở thích");
  await click(checkbox("Giày"));
  await click(checkbox("Trắng"));
  await fill("Giá tối thiểu (₫)", "150000");
  await fill("Giá tối đa (₫)", "600000");
  await submit(button("Lưu sở thích").form);

  expect(put).toHaveBeenCalledWith("/users/me/preferences", {
    category_ids: [1, 2],
    colors: ["Đen", "Trắng"],
    min_price: 150000,
    max_price: 600000,
  });
  expect(container.textContent).toContain("Đã lưu sở thích mua sắm");
});

it("chặn khoảng giá ngược trước khi gọi API", async () => {
  mockLoad();
  const put = vi.spyOn(client, "put");
  await renderAt("/account/preferences");
  await fill("Giá tối thiểu (₫)", "700000");
  await fill("Giá tối đa (₫)", "600000");
  await submit(button("Lưu sở thích").form);

  expect(alertText()).toBe("Giá tối thiểu không được lớn hơn giá tối đa");
  expect(put).not.toHaveBeenCalled();
});

it("hiện lỗi tải và không hiện form rỗng giả", async () => {
  vi.spyOn(client, "get").mockRejectedValue({
    response: { data: { detail: "Không tải được sở thích" } },
  });
  await renderAt("/account/preferences");

  expect(alertText()).toBe("Không tải được sở thích");
  expect(container.querySelector("form")).toBeNull();
});
