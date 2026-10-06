// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it } from "vitest";

import ProductImage from "./ProductImage.jsx";

let container;
let root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

async function render(src, props = {}) {
  await act(async () => root.render(<ProductImage src={src} alt="Áo linen" {...props} />));
}

it("hiển thị tên và giữ kích thước ảnh sản phẩm đang tải", async () => {
  await render("/test-shirt.jpg");
  const image = container.querySelector("img");
  expect(image.alt).toBe("Áo linen");
  expect(image.getAttribute("loading")).toBe("lazy");
  expect(image.width / image.height).toBe(3 / 4);
});

it("thay ảnh hỏng bằng trạng thái dễ đọc, rồi thử lại khi URL thay đổi", async () => {
  await render("/missing-shirt.jpg");
  await act(async () => container.querySelector("img").dispatchEvent(new Event("error")));
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector('[role="img"]').getAttribute("aria-label")).toBe(
    "Áo linen: chưa có ảnh",
  );
  expect(container.textContent).toContain("Chưa có ảnh");

  await render("/replacement-shirt.jpg", { loading: "eager" });
  expect(container.querySelector("img").getAttribute("src")).toBe("/replacement-shirt.jpg");
  expect(container.querySelector("img").getAttribute("loading")).toBe("eager");
});

it("hiển thị fallback khi sản phẩm không có URL ảnh", async () => {
  await render(null, { placeholderClassName: "cart-image-placeholder" });
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector('[role="img"]').textContent).toContain("Chưa có ảnh");
});
