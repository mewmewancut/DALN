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
  const field = label.querySelector("input, select");
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(field.constructor.prototype, "value").set;
    setter.call(field, value);
    field.dispatchEvent(
      new Event(field.tagName === "SELECT" ? "change" : "input", { bubbles: true }),
    );
  });
}

async function submit() {
  await act(async () =>
    container
      .querySelector("form")
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
  );
}

const product = {
  id: 5,
  shop_id: 2,
  shop_name: "Shop A",
  category_id: 3,
  name: "Áo mẫu",
  image_url: null,
  base_price: 90000,
  price_from: 100000,
  rating_average: 4.5,
};

it("đăng nhập bằng API, lưu phiên và chuyển tới trang đúng vai trò", async () => {
  const post = vi
    .spyOn(client, "post")
    .mockResolvedValue({ data: { access_token: "token", role: "SHOP_OWNER", shop_id: 2 } });
  vi.spyOn(client, "get").mockResolvedValue({ data: [] });
  await renderAt("/login");
  await fill("Email", "owner@example.com");
  await fill("Mật khẩu", "secret");
  await submit();
  expect(post).toHaveBeenCalledWith("/auth/login", {
    email: "owner@example.com",
    password: "secret",
  });
  expect(container.textContent).toContain("Tổng quan shop");
  expect(JSON.parse(localStorage.getItem("fashion_auth"))).toEqual({
    token: "token",
    role: "SHOP_OWNER",
    shop_id: 2,
  });
});

it("hiện lỗi xác thực từ API và giữ form để thử lại", async () => {
  vi.spyOn(client, "post").mockRejectedValue({
    response: { data: { detail: "Sai email hoặc mật khẩu" } },
  });
  await renderAt("/login");
  await fill("Email", "buyer@example.com");
  await fill("Mật khẩu", "wrong");
  await submit();
  expect(container.querySelector('[role="alert"]').textContent).toBe("Sai email hoặc mật khẩu");
  expect(container.querySelector('input[type="email"]').value).toBe("buyer@example.com");
  expect(localStorage.getItem("fashion_auth")).toBeNull();
});

it("đăng ký chủ shop và chuyển sang đăng nhập với thông báo thành công", async () => {
  const post = vi.spyOn(client, "post").mockResolvedValue({ data: { id: 9 } });
  await renderAt("/register");
  await fill("Họ và tên", "Nguyễn An");
  await fill("Email", "an@example.com");
  await fill("Mật khẩu", "secret");
  await fill("Loại tài khoản", "SHOP_OWNER");
  await submit();
  expect(post).toHaveBeenCalledWith("/auth/register", {
    full_name: "Nguyễn An",
    email: "an@example.com",
    password: "secret",
    role: "SHOP_OWNER",
  });
  expect(container.querySelector('[role="status"]').textContent).toContain("Đăng ký thành công");
});

it("hiện lỗi đăng ký, kể cả lỗi validation dạng danh sách", async () => {
  vi.spyOn(client, "post").mockRejectedValue({
    response: { data: { detail: [{ msg: "Email đã tồn tại" }] } },
  });
  await renderAt("/register");
  await fill("Họ và tên", "Nguyễn An");
  await fill("Email", "an@example.com");
  await fill("Mật khẩu", "secret");
  await submit();
  expect(container.querySelector('[role="alert"]').textContent).toBe("Email đã tồn tại");
  expect(container.textContent).toContain("Tạo tài khoản");
});

it("tìm kiếm, lọc, sắp xếp và phân trang bằng query params; đổi filter về trang 1", async () => {
  const get = vi.spyOn(client, "get").mockImplementation(async (url, options) => {
    if (url === "/categories") return { data: [{ id: 3, name: "Áo" }] };
    return { data: { items: [product], total: 25, page: options.params.page, page_size: 20 } };
  });
  await renderAt("/");
  expect(container.textContent).toContain("Áo mẫu");
  expect(container.textContent).toContain("Shop A");
  expect(container.textContent).toContain("100.000 ₫");
  await fill("Tìm sản phẩm", "áo");
  await fill("Danh mục", "3");
  await fill("Giá từ", "50000");
  await fill("Giá đến", "200000");
  await fill("Sắp xếp", "price_asc");
  expect(get).toHaveBeenLastCalledWith("/products", {
    params: {
      keyword: "áo",
      category_id: "3",
      min_price: "50000",
      max_price: "200000",
      sort: "price_asc",
      page: 1,
      page_size: 20,
    },
  });
  await act(async () =>
    [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Trang sau")
      .click(),
  );
  expect(get).toHaveBeenLastCalledWith("/products", {
    params: expect.objectContaining({ page: 2, keyword: "áo" }),
  });
  await fill("Tìm sản phẩm", "quần");
  expect(get).toHaveBeenLastCalledWith("/products", {
    params: expect.objectContaining({ page: 1, keyword: "quần" }),
  });
});

it("hiện trạng thái rỗng và lỗi khi tải catalog", async () => {
  const get = vi.spyOn(client, "get").mockImplementation(async (url) => {
    if (url === "/categories") return { data: [] };
    return { data: { items: [], total: 0, page: 1, page_size: 20 } };
  });
  await renderAt("/");
  expect(container.textContent).toContain("Không tìm thấy sản phẩm phù hợp");
  get.mockRejectedValue({ response: { data: { detail: "Lỗi catalog" } } });
  await fill("Tìm sản phẩm", "áo");
  expect(container.querySelector('[role="alert"]').textContent).toBe("Lỗi catalog");
});

it("chọn màu rồi size để xem đúng giá và tồn kho, đổi màu sẽ xóa size đã chọn", async () => {
  vi.spyOn(client, "get").mockResolvedValue({
    data: {
      ...product,
      description: "Mô tả",
      variants: [
        { id: 1, color: "Đỏ", size: "M", price: 120000, quantity: 3 },
        { id: 2, color: "Xanh", size: "L", price: 150000, quantity: 0 },
      ],
    },
  });
  await renderAt("/products/5");
  expect(container.textContent).toContain("Từ 100.000 ₫");
  expect(container.textContent).toContain("4.5");
  await act(async () =>
    [...container.querySelectorAll("button")].find((button) => button.textContent === "Đỏ").click(),
  );
  await act(async () =>
    [...container.querySelectorAll("button")].find((button) => button.textContent === "M").click(),
  );
  expect(container.textContent).toContain("120.000 ₫");
  expect(container.textContent).toContain("Còn 3 sản phẩm");
  await act(async () =>
    [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Xanh")
      .click(),
  );
  expect(container.textContent).toContain("Từ 100.000 ₫");
  await act(async () =>
    [...container.querySelectorAll("button")].find((button) => button.textContent === "L").click(),
  );
  expect(container.textContent).toContain("150.000 ₫");
  expect(container.textContent).toContain("Hết hàng");
  expect(
    [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Thêm vào giỏ",
    ).disabled,
  ).toBe(true);
});

it("báo lỗi khi chi tiết sản phẩm không tồn tại", async () => {
  vi.spyOn(client, "get").mockRejectedValue({
    response: { data: { detail: "Không tìm thấy sản phẩm" } },
  });
  await renderAt("/products/999");
  expect(container.querySelector('[role="alert"]').textContent).toBe("Không tìm thấy sản phẩm");
});
