import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "./client.js";
import { readSession, saveSession } from "../auth/session.js";

let values;
let replace;

beforeEach(() => {
  values = new Map();
  replace = vi.fn();
  vi.stubGlobal("localStorage", {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  });
  vi.stubGlobal("window", {
    dispatchEvent: vi.fn(),
    location: { pathname: "/shop/dashboard", replace },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("gắn token hiện tại vào mỗi request", async () => {
  saveSession({ token: "first-token", role: "SHOP_OWNER", shop_id: 1 });
  const adapter = async (config) => ({
    data: null,
    status: 200,
    statusText: "OK",
    headers: {},
    config,
  });

  const first = await client.get("/products", { adapter });
  assertToken(first, "first-token");

  saveSession({ token: "second-token", role: "BUYER", shop_id: null });
  const second = await client.get("/products", { adapter });
  assertToken(second, "second-token");
});

function assertToken(response, token) {
  expect(response.config.headers.Authorization).toBe(`Bearer ${token}`);
}

it("xóa phiên và chuyển tới đăng nhập khi API trả 401", async () => {
  saveSession({ token: "expired", role: "SHOP_OWNER", shop_id: 1 });
  const unauthorized = Object.assign(new Error("Unauthorized"), {
    response: { status: 401 },
  });

  await expect(
    client.get("/auth/me", {
      adapter: async () => {
        throw unauthorized;
      },
    }),
  ).rejects.toBe(unauthorized);

  expect(readSession()).toBeNull();
  expect(window.dispatchEvent).toHaveBeenCalledOnce();
  expect(replace).toHaveBeenCalledWith("/login");
});

it("giữ lỗi 401 của form đăng nhập để hiển thị trên form", async () => {
  const unauthorized = Object.assign(new Error("Sai mật khẩu"), {
    response: { status: 401, data: { detail: "Sai mật khẩu" } },
    config: { url: "/auth/login" },
  });
  await expect(
    client.post(
      "/auth/login",
      {},
      {
        adapter: async () => {
          throw unauthorized;
        },
      },
    ),
  ).rejects.toBe(unauthorized);
  expect(replace).not.toHaveBeenCalled();
});
