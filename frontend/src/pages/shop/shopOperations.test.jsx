// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import client from "../../api/client.js";
import {
  alertText,
  button,
  buttonLabels,
  click,
  dialog,
  field,
  fill,
  mountContainer,
  renderAt,
  routeGet,
  rowContaining,
  setValue,
  signInAs,
  submit,
  unmountContainer,
} from "../../testing/appHarness.jsx";

let container;

beforeEach(() => {
  container = mountContainer();
  signInAs("SHOP_OWNER", 7);
});

afterEach(async () => {
  await unmountContainer();
  vi.restoreAllMocks();
});

function order(id, status) {
  return {
    id,
    code: `ORD-20260924-${id}`,
    buyer_id: 3,
    shop_id: 7,
    status,
    payment_method: "COD",
    payment_status: "UNPAID",
    total_amount: 200000,
    created_at: "2026-09-24T03:00:00Z",
  };
}

const allStatusOrders = [
  order(1, "PENDING"),
  order(2, "CONFIRMED"),
  order(3, "PREPARING"),
  order(4, "SHIPPING"),
  order(5, "DELIVERED"),
  order(6, "CANCELLED"),
];

const inventory = [
  {
    variant_id: 1,
    product_id: 5,
    product_name: "Áo mẫu",
    size: "M",
    color: "Đỏ",
    sku: "P5-M-Đỏ",
    quantity: 2,
    low_stock_threshold: 5,
    is_low: true,
  },
  {
    variant_id: 2,
    product_id: 5,
    product_name: "Áo mẫu",
    size: "L",
    color: "Đỏ",
    sku: "P5-L-Đỏ",
    quantity: 8,
    low_stock_threshold: 5,
    is_low: false,
  },
];

const suppliers = [
  { id: 1, name: "Xưởng May A", phone: "0901", address: "Hà Nội", is_active: true },
  { id: 2, name: "Xưởng Cũ", phone: null, address: null, is_active: false },
];

function actionsOf(code) {
  return buttonLabels(rowContaining(code).querySelector(".table-actions"));
}

it("đơn của shop chỉ hiện nút đúng các chuyển trạng thái backend cho phép", async () => {
  routeGet({
    "/shop/orders": (options) => ({
      items: allStatusOrders,
      total: 6,
      page: options.params.page,
      page_size: 20,
    }),
  });
  await renderAt("/shop/orders");

  expect(actionsOf("ORD-20260924-1")).toEqual(["Xác nhận", "Hủy"]);
  expect(actionsOf("ORD-20260924-2")).toEqual(["Chuẩn bị", "Hủy"]);
  expect(actionsOf("ORD-20260924-3")).toEqual(["Giao hàng"]);
  expect(actionsOf("ORD-20260924-4")).toEqual(["Đã giao"]);
  expect(actionsOf("ORD-20260924-5")).toEqual([]);
  expect(actionsOf("ORD-20260924-6")).toEqual([]);
  expect(rowContaining("ORD-20260924-1").textContent).toContain("200.000 ₫");
  const actionGroup = rowContaining("ORD-20260924-1").querySelector(".table-actions");
  expect(actionGroup.tagName).toBe("DIV");
  expect(actionGroup.parentElement.tagName).toBe("TD");
});

it("chuyển trạng thái, hủy có lý do, lọc theo trạng thái và hiện lỗi từ backend", async () => {
  const get = routeGet({
    "/shop/orders": (options) => ({
      items: allStatusOrders,
      total: 6,
      page: options.params.page,
      page_size: 20,
    }),
  });
  const patch = vi.spyOn(client, "patch").mockResolvedValue({ data: {} });
  await renderAt("/shop/orders");

  await click(button("Xác nhận", rowContaining("ORD-20260924-1")));
  expect(patch).toHaveBeenCalledWith("/orders/1/status", { status: "CONFIRMED" });
  expect(get).toHaveBeenCalledTimes(2);

  await click(button("Hủy", rowContaining("ORD-20260924-2")));
  expect(patch).toHaveBeenCalledTimes(1);
  await fill("Lý do hủy", "Hết hàng", { scope: dialog() });
  await submit(dialog().querySelector("form"));
  expect(patch).toHaveBeenLastCalledWith("/orders/2/status", {
    status: "CANCELLED",
    note: "Hết hàng",
  });
  expect(dialog()).toBeNull();

  await click(button("Đang giao", container.querySelector(".status-tabs")));
  expect(get).toHaveBeenLastCalledWith("/shop/orders", {
    params: { page: 1, page_size: 20, status: "SHIPPING" },
  });

  patch.mockRejectedValueOnce({ response: { data: { detail: "Không thể chuyển trạng thái" } } });
  await click(button("Giao hàng", rowContaining("ORD-20260924-3")));
  expect(alertText()).toBe("Không thể chuyển trạng thái");

  get.mockRejectedValueOnce({ response: { data: { detail: "Không tải được đơn hàng" } } });
  await click(button("Đã giao", container.querySelector(".status-tabs")));
  expect(alertText()).toBe("Không tải được đơn hàng");
  expect(rowContaining("ORD-20260924-1")).toBeUndefined();
});

it("tồn kho tô đỏ dòng sắp hết và sửa ngưỡng inline theo response API", async () => {
  routeGet({ "/shop/inventory": inventory });
  const put = vi
    .spyOn(client, "put")
    .mockResolvedValueOnce({ data: { ...inventory[1], low_stock_threshold: 10, is_low: true } })
    .mockRejectedValueOnce({ response: { data: { detail: [{ msg: "Ngưỡng không hợp lệ" }] } } });
  await renderAt("/shop/inventory");

  const lowRow = rowContaining("P5-M-Đỏ");
  const okRow = rowContaining("P5-L-Đỏ");
  expect(lowRow.className).toBe("row-low");
  expect(lowRow.textContent).toContain("Sắp hết");
  expect(okRow.className).toBe("");
  expect(button("Lưu ngưỡng", okRow).disabled).toBe(true);

  await setValue(okRow.querySelector("input"), "-1");
  expect(button("Lưu ngưỡng", okRow).disabled).toBe(true);
  await setValue(okRow.querySelector("input"), "10");
  await click(button("Lưu ngưỡng", okRow));
  expect(put).toHaveBeenCalledWith("/shop/inventory/2/threshold", { low_stock_threshold: 10 });
  expect(rowContaining("P5-L-Đỏ").className).toBe("row-low");

  await setValue(rowContaining("P5-M-Đỏ").querySelector("input"), "6");
  await click(button("Lưu ngưỡng", rowContaining("P5-M-Đỏ")));
  expect(alertText()).toBe("Ngưỡng không hợp lệ");
  expect(rowContaining("P5-M-Đỏ").querySelector("input").value).toBe("6");
});

it("tồn kho tìm kiếm, lọc mức tồn và phân trang phía client", async () => {
  const manyItems = Array.from({ length: 12 }, (_, index) => ({
    ...inventory[index % inventory.length],
    variant_id: index + 1,
    product_id: index + 1,
    product_name: `Sản phẩm ${index + 1}`,
    sku: `SKU-${index + 1}`,
    is_low: index % 2 === 0,
  }));
  routeGet({ "/shop/inventory": manyItems });
  await renderAt("/shop/inventory");

  expect(container.querySelectorAll("tbody tr")).toHaveLength(10);
  await click(button("Trang sau"));
  expect(rowContaining("SKU-12")).not.toBeUndefined();

  await fill("Tìm sản phẩm hoặc SKU", "SKU-12");
  expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
  expect(container.textContent).toContain("Trang 1/1");

  await fill("Tìm sản phẩm hoặc SKU", "");
  await fill("Mức tồn kho", "low");
  expect(container.querySelectorAll("tbody tr")).toHaveLength(6);
  expect(container.textContent).toContain("Tìm thấy 6 biến thể");
});

it("trang cảnh báo liệt kê cảnh báo đang mở hoặc báo không có cảnh báo", async () => {
  const get = routeGet({
    "/shop/alerts": [
      {
        id: 4,
        variant_id: 1,
        product_name: "Áo mẫu",
        size: "M",
        color: "Đỏ",
        quantity_at_alert: 2,
        is_resolved: false,
        created_at: "2026-09-24T03:00:00Z",
      },
    ],
  });
  await renderAt("/shop/alerts");
  expect(rowContaining("Áo mẫu").textContent).toContain("Đỏ");
  expect(rowContaining("Áo mẫu").querySelectorAll("td")[3].textContent).toBe("2");
  expect(container.querySelector('a[href="/shop/purchase-orders"]')).not.toBeNull();

  await unmountContainer();
  container = mountContainer();
  signInAs("SHOP_OWNER", 7);
  get.mockResolvedValue({ data: [] });
  await renderAt("/shop/alerts");
  expect(container.textContent).toContain("Không có cảnh báo tồn kho nào đang mở.");
});

it("cảnh báo tồn kho có tìm kiếm và phân trang", async () => {
  const alerts = Array.from({ length: 12 }, (_, index) => ({
    id: index + 1,
    variant_id: index + 1,
    product_name: `Sản phẩm cảnh báo ${index + 1}`,
    size: "M",
    color: index % 2 === 0 ? "Đỏ" : "Xanh",
    quantity_at_alert: index,
    is_resolved: false,
    created_at: "2026-09-24T03:00:00Z",
  }));
  routeGet({ "/shop/alerts": alerts });
  await renderAt("/shop/alerts");

  expect(container.querySelectorAll("tbody tr")).toHaveLength(10);
  await click(button("Trang sau"));
  expect(rowContaining("Sản phẩm cảnh báo 12")).not.toBeUndefined();
  await fill("Tìm sản phẩm", "cảnh báo 3");
  expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
  expect(rowContaining("Sản phẩm cảnh báo 3")).not.toBeUndefined();
});

it("nhà cung cấp: thêm, sửa, ngừng hợp tác (soft delete) và khôi phục", async () => {
  const get = routeGet({ "/shop/suppliers": suppliers });
  const post = vi.spyOn(client, "post").mockResolvedValue({ data: {} });
  const put = vi.spyOn(client, "put").mockResolvedValue({ data: {} });
  const remove = vi.spyOn(client, "delete").mockResolvedValue({ data: null });
  await renderAt("/shop/suppliers");

  expect(rowContaining("Xưởng May A").textContent).toContain("Đang hợp tác");
  expect(rowContaining("Xưởng Cũ").textContent).toContain("Ngừng hợp tác");

  const createForm = container.querySelector('form[aria-label="Thêm nhà cung cấp"]');
  await fill("Tên nhà cung cấp", " Xưởng B ", { scope: createForm });
  await submit(createForm);
  expect(post).toHaveBeenCalledWith("/shop/suppliers", {
    name: "Xưởng B",
    phone: null,
    address: null,
  });
  expect(field("Tên nhà cung cấp", { scope: createForm }).value).toBe("");

  await click(button("Ngừng hợp tác", rowContaining("Xưởng May A")));
  expect(remove).toHaveBeenCalledWith("/shop/suppliers/1");
  await click(button("Khôi phục", rowContaining("Xưởng Cũ")));
  expect(put).toHaveBeenCalledWith("/shop/suppliers/2", { is_active: true });

  await click(button("Sửa", rowContaining("Xưởng May A")));
  expect(field("Số điện thoại", { scope: dialog() }).value).toBe("0901");
  await fill("Địa chỉ", "Hải Phòng", { scope: dialog() });
  await submit(dialog().querySelector("form"));
  expect(put).toHaveBeenLastCalledWith("/shop/suppliers/1", {
    name: "Xưởng May A",
    phone: "0901",
    address: "Hải Phòng",
  });
  expect(dialog()).toBeNull();
  expect(get.mock.calls.length).toBe(5);
});

it("nhà cung cấp có tìm kiếm, lọc trạng thái và phân trang", async () => {
  const manySuppliers = Array.from({ length: 12 }, (_, index) => ({
    id: index + 1,
    name: `Nhà cung cấp ${index + 1}`,
    phone: `090${index}`,
    address: index % 2 === 0 ? "Hà Nội" : "TP.HCM",
    is_active: index % 2 === 0,
  }));
  routeGet({ "/shop/suppliers": manySuppliers });
  await renderAt("/shop/suppliers");

  expect(container.querySelectorAll("tbody tr")).toHaveLength(10);
  await click(button("Trang sau"));
  expect(rowContaining("Nhà cung cấp 12")).not.toBeUndefined();

  await fill("Tìm nhà cung cấp", "Nhà cung cấp 2");
  expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
  await fill("Tìm nhà cung cấp", "");
  await fill("Trạng thái", "false");
  expect(container.querySelectorAll("tbody tr")).toHaveLength(6);
  expect(container.textContent).toContain("Tìm thấy 6 nhà cung cấp");
});

function purchaseOrder(id, status, overrides = {}) {
  return {
    id,
    shop_id: 7,
    supplier_id: 1,
    status,
    note: null,
    received_at: null,
    created_at: "2026-09-24T03:00:00Z",
    items: [{ id: id * 10, variant_id: 1, quantity: 5, unit_cost: 60000 }],
    ...overrides,
  };
}

function purchaseRoutes() {
  return {
    "/shop/suppliers": suppliers,
    "/shop/inventory": inventory,
    "/shop/purchase-orders": (options) => ({
      items: [
        purchaseOrder(1, "DRAFT"),
        purchaseOrder(2, "ORDERED"),
        purchaseOrder(3, "RECEIVED", { received_at: "2026-09-24T04:00:00Z" }),
        purchaseOrder(4, "CANCELLED"),
      ],
      total: 4,
      page: options.params.page,
      page_size: 20,
    }),
  };
}

it("tạo phiếu nhập chỉ với nhà cung cấp đang hợp tác và chặn biến thể trùng", async () => {
  routeGet(purchaseRoutes());
  const post = vi.spyOn(client, "post").mockResolvedValue({ data: purchaseOrder(9, "DRAFT") });
  await renderAt("/shop/purchase-orders");

  const form = container.querySelector('form[aria-label="Tạo phiếu nhập"]');
  const supplierOptions = [...field("Nhà cung cấp", { scope: form }).options].map(
    (option) => option.textContent,
  );
  expect(supplierOptions).toEqual(["Chọn nhà cung cấp", "Xưởng May A"]);

  await fill("Nhà cung cấp", "1", { scope: form });
  await fill("Biến thể", "1", { scope: form });
  await fill("Số lượng", "10", { scope: form });
  await fill("Giá nhập (₫)", "60000", { scope: form });
  await click(button("Thêm dòng", form));
  await fill("Biến thể", "1", { scope: form, index: 1 });
  expect(form.textContent).toContain("Mỗi biến thể chỉ được xuất hiện một lần");
  expect(button("Tạo phiếu nháp", form).disabled).toBe(true);

  await fill("Biến thể", "2", { scope: form, index: 1 });
  await fill("Số lượng", "3", { scope: form, index: 1 });
  await fill("Giá nhập (₫)", "65000", { scope: form, index: 1 });
  await fill("Ghi chú", "Nhập bổ sung", { scope: form });
  await submit(form);
  expect(post).toHaveBeenCalledWith("/shop/purchase-orders", {
    supplier_id: 1,
    note: "Nhập bổ sung",
    items: [
      { variant_id: 1, quantity: 10, unit_cost: 60000 },
      { variant_id: 2, quantity: 3, unit_cost: 65000 },
    ],
  });
  expect(form.querySelectorAll(".variant-row")).toHaveLength(1);
  expect(field("Nhà cung cấp", { scope: form }).value).toBe("");
});

it("không mở form nhập hàng khi dữ liệu supplier hoặc inventory tải lỗi", async () => {
  vi.spyOn(client, "get").mockImplementation(async (url, options) => {
    if (url === "/shop/suppliers") {
      throw { response: { data: { detail: "Không tải được nhà cung cấp" } } };
    }
    if (url === "/shop/inventory") return { data: inventory };
    if (url === "/shop/purchase-orders") {
      return {
        data: { items: [], total: 0, page: options.params.page, page_size: 20 },
      };
    }
    throw new Error(`GET ${url} chưa được mock`);
  });

  await renderAt("/shop/purchase-orders");

  expect(alertText()).toContain("Không thể mở form nhập hàng: Không tải được nhà cung cấp");
  expect(container.querySelector('form[aria-label="Tạo phiếu nhập"]')).toBeNull();
  expect(container.textContent).toContain("Chưa có phiếu nhập phù hợp");
});

it("không giữ phiếu nhập cũ trên màn hình khi tải bộ lọc mới thất bại", async () => {
  let purchaseRequest = 0;
  vi.spyOn(client, "get").mockImplementation(async (url, options) => {
    if (url === "/shop/suppliers") return { data: suppliers };
    if (url === "/shop/inventory") return { data: inventory };
    if (url === "/shop/purchase-orders") {
      purchaseRequest += 1;
      if (purchaseRequest > 1) {
        throw { response: { data: { detail: "Không tải được phiếu nhập" } } };
      }
      return {
        data: {
          items: [purchaseOrder(1, "DRAFT")],
          total: 1,
          page: options.params.page,
          page_size: 20,
        },
      };
    }
    throw new Error(`GET ${url} chưa được mock`);
  });

  await renderAt("/shop/purchase-orders");
  expect(rowContaining("Phiếu #1 ·")).not.toBeUndefined();

  await click(button("Nháp", container.querySelector(".status-tabs")));

  expect(alertText()).toBe("Không tải được phiếu nhập");
  expect(rowContaining("Phiếu #1 ·")).toBeUndefined();
});

it("phiếu nhập hiện nút theo trạng thái, nhận hàng xong có link sang tồn kho", async () => {
  routeGet(purchaseRoutes());
  const patch = vi
    .spyOn(client, "patch")
    .mockResolvedValueOnce({ data: purchaseOrder(2, "RECEIVED") })
    .mockRejectedValueOnce({ response: { data: { detail: "Chuyển trạng thái không hợp lệ" } } });
  await renderAt("/shop/purchase-orders");

  const card = (id) => rowContaining(`Phiếu #${id} ·`);
  expect(card(1).textContent).toContain("Xưởng May A");
  expect(card(1).textContent).toContain("Áo mẫu — Đỏ / M (P5-M-Đỏ) × 5");
  expect(card(1).textContent).toContain("Tổng giá nhập: 300.000 ₫");
  expect(buttonLabels(card(1).querySelector(".table-actions"))).toEqual(["Đặt hàng", "Hủy"]);
  expect(buttonLabels(card(2).querySelector(".table-actions"))).toEqual(["Đã nhận hàng", "Hủy"]);
  expect(buttonLabels(card(3).querySelector(".table-actions"))).toEqual([]);
  expect(card(3).querySelector('a[href="/shop/inventory"]')).not.toBeNull();
  expect(buttonLabels(card(4).querySelector(".table-actions"))).toEqual([]);

  await click(button("Đã nhận hàng", card(2)));
  expect(patch).toHaveBeenCalledWith("/shop/purchase-orders/2/status", { status: "RECEIVED" });
  const notice = [...container.querySelectorAll('[role="status"]')].find((item) =>
    item.textContent.includes("Đã nhận hàng phiếu #2"),
  );
  expect(notice.querySelector('a[href="/shop/inventory"]')).not.toBeNull();

  await click(button("Đặt hàng", card(1)));
  expect(patch).toHaveBeenLastCalledWith("/shop/purchase-orders/1/status", { status: "ORDERED" });
  expect(alertText()).toBe("Chuyển trạng thái không hợp lệ");
});
