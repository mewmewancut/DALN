// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import client from "../api/client.js";
import {
  button,
  click,
  field,
  fill,
  mountContainer,
  renderAt,
  signInAs,
  submit,
  unmountContainer,
} from "../testing/appHarness.jsx";

const profile = {
  id: 1,
  email: "buyer@example.com",
  full_name: "Nguyễn An",
  phone: "0900000000",
  avatar_url: null,
  role: "BUYER",
  is_active: true,
  email_verified_at: "2026-09-27T00:00:00Z",
};

let container;

beforeEach(() => {
  container = mountContainer();
  signInAs("BUYER");
});

afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

function mockProfileLoad(addresses = []) {
  return vi.spyOn(client, "get").mockImplementation(async (url, options) => {
    if (url === "/users/me/profile") return { data: profile };
    if (url === "/users/me/addresses") return { data: addresses };
    if (url === "/locations/provinces") {
      return {
        data: [
          { code: "01", name: "Thành phố Hà Nội" },
          { code: "79", name: "Thành phố Hồ Chí Minh" },
        ],
      };
    }
    if (url === "/locations/communes" && options.params.province_code === "79") {
      return { data: [{ code: "26734", name: "Phường Sài Gòn" }] };
    }
    if (url === "/locations/communes" && options.params.province_code === "01") {
      return { data: [{ code: "00004", name: "Phường Ba Đình" }] };
    }
    throw new Error(`GET chưa mock: ${url}`);
  });
}

it.each([
  ["BUYER", "Người mua"],
  ["SHOP_OWNER", "Chủ shop"],
  ["ADMIN", "Quản trị viên"],
])("shows a readable role on the %s profile", async (role, label) => {
  signInAs(role, role === "SHOP_OWNER" ? 7 : null);
  vi.spyOn(client, "get").mockImplementation(async (url) => ({
    data: url === "/users/me/profile" ? { ...profile, role } : [],
  }));
  await renderAt("/account/profile");
  expect(field("Vai trò").value).toBe(label);
  expect(field("Vai trò").disabled).toBe(true);
});

async function chooseCombobox(label, query, optionText, keyboard = false) {
  const input = field(label);
  await act(async () => input.focus());
  await fill(label, query);
  expect(container.textContent).toContain(optionText);
  if (keyboard) {
    await act(async () =>
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })),
    );
    await act(async () =>
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })),
    );
    expect(input.value).toBe(optionText);
    return;
  }
  const option = [...container.querySelectorAll('[role="option"]')].find(
    (item) => item.textContent === optionText,
  );
  await click(option);
}

describe("trang hồ sơ và sổ địa chỉ", () => {
  it("không gửi hai lần lưu hồ sơ khi request trước chưa xong", async () => {
    mockProfileLoad();
    let finish;
    const patch = vi.spyOn(client, "patch").mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    await renderAt("/account/profile");
    await fill("Họ và tên", "Tên mới");
    const form = field("Họ và tên").closest("form");
    await submit(form);
    await submit(form);
    expect(patch).toHaveBeenCalledTimes(1);
    expect(button("Đang lưu...").disabled).toBe(true);
    await act(async () => finish({ data: { ...profile, full_name: "Tên mới" } }));
    expect(container.textContent).toContain("Đã cập nhật hồ sơ");
    expect(button("Lưu hồ sơ").disabled).toBe(false);
  });
  it("cập nhật hồ sơ nhưng giữ email và vai trò chỉ đọc", async () => {
    mockProfileLoad();
    const patch = vi.spyOn(client, "patch").mockResolvedValue({
      data: { ...profile, full_name: "Nguyễn Bình", phone: null },
    });
    await renderAt("/account/profile");

    expect(field("Email").disabled).toBe(true);
    expect(field("Vai trò").disabled).toBe(true);
    await fill("Họ và tên", "Nguyễn Bình");
    await fill("Số điện thoại", "");
    await submit(field("Họ và tên").form);

    expect(patch).toHaveBeenCalledWith("/users/me/profile", {
      full_name: "Nguyễn Bình",
      phone: null,
      avatar_url: null,
    });
    expect(container.textContent).toContain("Đã cập nhật hồ sơ");
  });

  it("tìm địa danh không dấu, chỉ lưu lựa chọn chính thức và reset xã khi đổi tỉnh", async () => {
    mockProfileLoad();
    const post = vi.spyOn(client, "post").mockImplementation(async (_url, body) => ({
      data: {
        id: 5,
        ...body,
        province_name: "Thành phố Hồ Chí Minh",
        commune_name: "Phường Sài Gòn",
        is_default: true,
        created_at: "2026-09-27T00:00:00Z",
        updated_at: "2026-09-27T00:00:00Z",
      },
    }));
    await renderAt("/account/profile");

    await fill("Người nhận", "Nguyễn An");
    await fill("Số điện thoại nhận hàng", "0900000000");
    await fill("Địa chỉ cụ thể", "12 Nguyễn Huệ");
    await chooseCombobox("Tỉnh/Thành phố", "ho chi minh", "Thành phố Hồ Chí Minh", true);
    await chooseCombobox("Xã/Phường/Đặc khu", "sai gon", "Phường Sài Gòn");
    expect(field("Xã/Phường/Đặc khu").value).toBe("Phường Sài Gòn");
    await fill("Xã/Phường/Đặc khu", "Giá trị tự nhập");
    expect(field("Xã/Phường/Đặc khu").checkValidity()).toBe(false);

    await chooseCombobox("Tỉnh/Thành phố", "ha noi", "Thành phố Hà Nội");
    expect(field("Xã/Phường/Đặc khu").value).toBe("");
    await chooseCombobox("Xã/Phường/Đặc khu", "ba dinh", "Phường Ba Đình");
    await submit(button("Thêm địa chỉ").form);

    expect(post).toHaveBeenCalledWith("/users/me/addresses", {
      label: "Nhà riêng",
      receiver_name: "Nguyễn An",
      receiver_phone: "0900000000",
      province_code: "01",
      commune_code: "00004",
      address_detail: "12 Nguyễn Huệ",
      is_default: false,
    });
  });

  it("checkout tự điền địa chỉ mặc định và cho đổi địa chỉ đã lưu", async () => {
    const home = {
      id: 1,
      label: "Nhà riêng",
      receiver_name: "Nguyễn An",
      receiver_phone: "0900000000",
      address_detail: "12 Đội Cấn",
      commune_name: "Phường Ba Đình",
      province_name: "Thành phố Hà Nội",
      is_default: true,
    };
    const office = {
      ...home,
      id: 2,
      label: "Công ty",
      receiver_name: "Lê Bình",
      receiver_phone: "0911111111",
      address_detail: "99 Nguyễn Huệ",
      commune_name: "Phường Sài Gòn",
      province_name: "Thành phố Hồ Chí Minh",
      is_default: false,
    };
    vi.spyOn(client, "get").mockImplementation(async (url) => {
      if (url === "/cart") {
        return {
          data: {
            shop_name: "Shop A",
            total_amount: 100000,
            items: [
              {
                id: 1,
                product_name: "Áo",
                color: "Đen",
                size: "M",
                quantity: 1,
              },
            ],
          },
        };
      }
      if (url === "/users/me/profile") return { data: profile };
      if (url === "/users/me/addresses") return { data: [home, office] };
      throw new Error(`GET chưa mock: ${url}`);
    });
    await renderAt("/checkout");

    expect(field("Người nhận").value).toBe("Nguyễn An");
    expect(field("Địa chỉ giao hàng").value).toBe("12 Đội Cấn, Phường Ba Đình, Thành phố Hà Nội");
    await fill("Địa chỉ đã lưu", "2");
    expect(field("Người nhận").value).toBe("Lê Bình");
    expect(field("Địa chỉ giao hàng").value).toBe(
      "99 Nguyễn Huệ, Phường Sài Gòn, Thành phố Hồ Chí Minh",
    );
  });

  it("sửa, đặt mặc định và xóa địa chỉ bằng đúng endpoint", async () => {
    const home = {
      id: 1,
      label: "Nhà riêng",
      receiver_name: "Nguyễn An",
      receiver_phone: "0900000000",
      province_code: "01",
      province_name: "Thành phố Hà Nội",
      commune_code: "00004",
      commune_name: "Phường Ba Đình",
      address_detail: "12 Đội Cấn",
      is_default: true,
      created_at: "2026-09-27T00:00:00Z",
      updated_at: "2026-09-27T00:00:00Z",
    };
    const office = { ...home, id: 2, label: "Công ty", is_default: false };
    mockProfileLoad([home, office]);
    const patch = vi.spyOn(client, "patch").mockResolvedValue({
      data: { ...home, address_detail: "15 Đội Cấn" },
    });
    const put = vi
      .spyOn(client, "put")
      .mockResolvedValue({ data: { ...office, is_default: true } });
    const remove = vi.spyOn(client, "delete").mockResolvedValue({ data: { message: "Đã xóa" } });
    await renderAt("/account/profile");

    const homeCard = [...container.querySelectorAll("article")].find((item) =>
      item.textContent.includes("Nhà riêng"),
    );
    await click(button("Sửa", homeCard));
    await fill("Địa chỉ cụ thể", "15 Đội Cấn");
    await submit(button("Lưu địa chỉ").form);
    expect(patch).toHaveBeenCalledWith("/users/me/addresses/1", {
      label: "Nhà riêng",
      receiver_name: "Nguyễn An",
      receiver_phone: "0900000000",
      province_code: "01",
      commune_code: "00004",
      address_detail: "15 Đội Cấn",
    });

    const officeCard = [...container.querySelectorAll("article")].find((item) =>
      item.textContent.includes("Công ty"),
    );
    await click(button("Đặt mặc định", officeCard));
    expect(put).toHaveBeenCalledWith("/users/me/addresses/2/default");
    await click(button("Xóa", officeCard));
    expect(remove).toHaveBeenCalledWith("/users/me/addresses/2");
  });
});
