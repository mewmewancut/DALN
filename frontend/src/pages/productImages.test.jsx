// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import client from "../api/client.js";
import {
  button,
  click,
  dialog,
  field,
  mountContainer,
  renderAt,
  routeGet,
  rowContaining,
  signInAs,
  submit,
  unmountContainer,
} from "../testing/appHarness.jsx";

let container;
const main = "/media/product-images/7/main.webp";
const details = Array.from({ length: 10 }, (_, i) => `/media/product-images/7/detail${i}.webp`);
const product = {
  id: 1,
  category_id: 3,
  name: "Áo ảnh",
  base_price: 100000,
  image_url: main,
  detail_image_urls: details,
  variants: [],
};

beforeEach(() => {
  container = mountContainer();
});
afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

async function choose(input, files) {
  Object.defineProperty(input, "files", { configurable: true, value: files });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
}
const image = (name = "shirt.png") => new File(["test-image"], name, { type: "image/png" });

async function openForm(edit = false, current = product) {
  signInAs("SHOP_OWNER", 7);
  routeGet({
    "/categories": [{ id: 3, name: "Áo" }],
    "/shop/products": { items: [current], total: 1, page: 1, page_size: 20 },
  });
  await renderAt("/shop/products");
  await click(edit ? button("Sửa", rowContaining(current.name)) : button("Thêm sản phẩm"));
  return dialog();
}

it("requires the main image and sends a real multipart file before creating", async () => {
  const post = vi.spyOn(client, "post").mockResolvedValue({ data: { image_url: main } });
  const scope = await openForm();
  await submit(scope.querySelector("form"));
  expect(scope.textContent).toContain("Vui lòng tải lên ảnh chính");
  expect(post).not.toHaveBeenCalled();
  const file = image();
  await choose(field("Ảnh chính", { scope }), [file]);
  const [url, body] = post.mock.calls[0];
  expect(url).toBe("/shop/product-images");
  expect(body).toBeInstanceOf(FormData);
  expect(body.get("file")).toBe(file);
  expect(scope.querySelector("img").src).toBe(new URL(main, client.defaults.baseURL).href);
});

it("prevents saving or closing during upload, shows failure and allows retry", async () => {
  let reject;
  const post = vi.spyOn(client, "post").mockImplementation(
    () =>
      new Promise((_, fail) => {
        reject = fail;
      }),
  );
  const scope = await openForm();
  await choose(field("Ảnh chính", { scope }), [image()]);
  expect(button("Tạo sản phẩm", scope).disabled).toBe(true);
  expect(button("Đóng", scope).disabled).toBe(true);
  await submit(scope.querySelector("form"));
  expect(post).toHaveBeenCalledTimes(1);
  await act(async () => reject({ response: { data: { detail: "Không lưu được ảnh" } } }));
  expect(scope.textContent).toContain("Không tải được ảnh: Không lưu được ảnh");
  expect(button("Tạo sản phẩm", scope).disabled).toBe(false);
  post.mockResolvedValue({ data: { image_url: main } });
  await choose(field("Ảnh chính", { scope }), [image()]);
  expect(scope.querySelector("img")).not.toBeNull();
});

it("caps detail images at ten, rejects a batch over the cap and supports removal and main replacement", async () => {
  const scope = await openForm(true);
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValue({ data: { image_url: "/media/product-images/7/replacement.webp" } });
  const put = vi.spyOn(client, "put").mockResolvedValue({ data: {} });
  expect(field("Ảnh chi tiết (10/10)", { scope }).disabled).toBe(true);
  await click(button("Bỏ ảnh chi tiết 3", scope));
  expect(field("Ảnh chi tiết (9/10)", { scope }).disabled).toBe(false);
  await choose(field("Ảnh chi tiết (9/10)", { scope }), [image("a.png"), image("b.png")]);
  expect(scope.textContent).toContain("Chỉ được chọn tối đa 10 ảnh chi tiết");
  expect(post).not.toHaveBeenCalled();
  await choose(field("Ảnh chính", { scope }), [image()]);
  await submit(scope.querySelector("form"));
  expect(put).toHaveBeenCalledWith(
    "/products/1",
    expect.objectContaining({
      image_url: "/media/product-images/7/replacement.webp",
      detail_image_urls: details.filter((_, i) => i !== 2),
    }),
  );
});

it("keeps successful files after a batch upload partially fails and refuses invalid type or size", async () => {
  const scope = await openForm(true, { ...product, detail_image_urls: [] });
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValueOnce({ data: { image_url: details[0] } })
    .mockRejectedValueOnce({ response: { data: { detail: "Ảnh bị hỏng" } } });
  await choose(field("Ảnh chi tiết (0/10)", { scope }), [image("a.png"), image("b.png")]);
  expect(scope.textContent).toContain("Ảnh bị hỏng");
  expect(field("Ảnh chi tiết (1/10)", { scope })).not.toBeNull();
  const invalid = new File(["svg"], "bad.svg", { type: "image/svg+xml" });
  await choose(field("Ảnh chính", { scope }), [invalid]);
  const huge = image();
  Object.defineProperty(huge, "size", { value: 5 * 1024 * 1024 + 1 });
  await choose(field("Ảnh chính", { scope }), [huge]);
  expect(scope.textContent).toContain("tối đa 5 MB mỗi ảnh");
  expect(post).toHaveBeenCalledTimes(2);
  const put = vi.spyOn(client, "put").mockResolvedValue({ data: {} });
  await click(button("Bỏ ảnh chi tiết 1", scope));
  await submit(scope.querySelector("form"));
  expect(put).toHaveBeenCalledWith(
    "/products/1",
    expect.objectContaining({ image_url: main, detail_image_urls: [] }),
  );
});

it("starts with the main image, switches all ten details and resets on another product", async () => {
  routeGet({
    "/products/1": product,
    "/products/2": {
      ...product,
      id: 2,
      name: "Áo khác",
      image_url: "/media/product-images/7/other.webp",
      detail_image_urls: [],
    },
    "/products/1/reviews": { items: [], total: 0 },
    "/products/2/reviews": { items: [], total: 0 },
  });
  await renderAt("/products/1", ["/products/2"]);
  expect(container.querySelector(".detail-image").src).toBe(
    new URL(main, client.defaults.baseURL).href,
  );
  const thumbnails = container.querySelectorAll(".product-thumbnails button");
  expect(thumbnails).toHaveLength(11);
  for (let i = 1; i <= 10; i++) {
    await click(thumbnails[i]);
    expect(container.querySelector(".detail-image").src).toBe(
      new URL(details[i - 1], client.defaults.baseURL).href,
    );
    expect(thumbnails[i].getAttribute("aria-pressed")).toBe("true");
  }
  await click(container.querySelector('[aria-label="Test navigation"] a'));
  expect(container.querySelector(".detail-image").src).toContain("other.webp");
  expect(container.querySelector(".product-thumbnails")).toBeNull();
});
