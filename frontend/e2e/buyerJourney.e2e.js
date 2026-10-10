import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import test from "node:test";
import { chromium, request } from "playwright";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:15173";
const apiURL = process.env.E2E_API_URL ?? "http://localhost:18000";
// The runner writes demo orders. Accept only the isolated Compose service or
// its dedicated host ports, never the normal app on :8000 or a remote API.
assert.ok(["http://localhost", "http://localhost:15173"].includes(baseURL));
assert.ok(["http://backend:8000", "http://localhost:18000"].includes(apiURL));

async function login(page, email, password) {
  await page.goto(`${baseURL}/login`);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((url) => url.pathname !== "/login");
}

async function session(email, password) {
  const api = await request.newContext({ baseURL: apiURL });
  const response = await api.post("/auth/login", { data: { email, password } });
  assert.equal(response.status(), 200);
  const { access_token } = await response.json();
  await api.dispose();
  return request.newContext({
    baseURL: apiURL,
    extraHTTPHeaders: { Authorization: `Bearer ${access_token}` },
  });
}

async function json(api, method, path, data) {
  const response = await api[method](path, data == null ? {} : { data });
  assert.ok(response.ok(), `${method} ${path} returned ${response.status()}`);
  return response.json();
}

async function add(page, product, size = "M") {
  await page.goto(`${baseURL}/products/${product.id}`);
  await page.getByRole("button", { name: "Đen", exact: true }).click();
  await page.getByRole("button", { name: size, exact: true }).click();
  await page.getByRole("button", { name: "Thêm vào giỏ", exact: true }).click();
  await page.getByText("Đã thêm", { exact: false }).waitFor();
}

test(
  "real browser: guest multi-shop cart, checkout, delivery, review and permissions",
  { timeout: 240_000 },
  async (t) => {
    const browser = await chromium.launch({ headless: true });
    const contexts = [],
      apis = [];
    const results = process.env.E2E_RESULTS_DIRECTORY ?? "/results";
    await mkdir(results, { recursive: true });
    const owner = await session("shop1@shop.vn", "Shop@123");
    const otherOwner = await session("shop2@shop.vn", "Shop@123");
    const buyer = await session("buyer5@shop.vn", "Buyer@123");
    const otherBuyer = await session("buyer4@shop.vn", "Buyer@123");
    apis.push(owner, otherOwner, buyer, otherBuyer);
    try {
      const suffix = Date.now();
      async function create(api, name, price, variants = null) {
        return json(api, "post", "/products", {
          name: `${name} ${suffix}`,
          category_id: 1,
          base_price: price,
          image_url: "https://placehold.co/600x800?text=demo",
          variants: variants ?? [{ size: "M", color: "Đen", price, initial_quantity: 7 }],
        });
      }
      const first = await create(owner, "Áo demo E2E", 100000, [
        { size: "S", color: "Đen", price: 100000, initial_quantity: 0 },
        { size: "M", color: "Đen", price: 100000, initial_quantity: 5 },
      ]);
      const second = await create(owner, "Quần demo E2E", 200000);
      const other = await create(otherOwner, "Áo shop khác E2E", 300000);
      const buyerContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
      contexts.push(buyerContext);
      const page = await buyerContext.newPage();
      let order;
      await t.test(
        "out-of-stock variant is blocked; guest cart survives reload and checks out one shop",
        async () => {
          await page.goto(`${baseURL}/products/${first.id}`);
          await page.getByRole("button", { name: "Đen", exact: true }).click();
          await page.getByRole("button", { name: "S", exact: true }).click();
          assert.equal(
            await page.getByRole("button", { name: "Thêm vào giỏ", exact: true }).isEnabled(),
            false,
          );
          await add(page, first);
          await add(page, second);
          await add(page, other);
          await page.goto(`${baseURL}/cart`);
          await page
            .getByRole("radio", { name: "Thanh toán Thời trang Shop 1", exact: true })
            .check();
          await page.reload();
          await page
            .getByRole("radio", { name: "Thanh toán Thời trang Shop 1", exact: true })
            .waitFor();
          assert.equal(await page.locator(".cart-shop-group").count(), 2);
          await page.getByRole("button", { name: "Thanh toán", exact: true }).click();
          await page.waitForURL("**/login");
          // Stay on the checkout-redirect login page so the chosen shop resumes.
          await page.getByLabel("Email", { exact: true }).fill("buyer5@shop.vn");
          await page.getByLabel("Mật khẩu", { exact: true }).fill("Buyer@123");
          await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
          await page.waitForURL("**/checkout");
          await page.getByLabel("Người nhận", { exact: true }).fill("Người nhận demo");
          await page.getByLabel("Số điện thoại", { exact: true }).fill("0900000000");
          await page
            .getByLabel("Địa chỉ giao hàng", { exact: true })
            .fill("Địa chỉ giả phục vụ kiểm thử demo");
          const checkout = page.waitForResponse(
            (r) => r.url().endsWith("/orders/checkout") && r.request().method() === "POST",
          );
          await page.getByRole("button", { name: "Đặt hàng", exact: true }).click();
          const response = await checkout;
          assert.equal(response.status(), 200);
          order = await response.json();
          await page.waitForURL(`**/orders/${order.id}`);
          assert.equal(Number(order.total_amount), 300000);
          assert.equal(order.items.length, 2);
          assert.equal(order.shop_id, 1);
          const remaining = await json(buyer, "get", "/cart");
          assert.equal(remaining.items.length, 1);
          assert.equal(remaining.items[0].variant_id, other.variants[0].id);
          assert.equal(
            (await json(owner, "get", `/products/${first.id}`)).variants.find((v) => v.size === "M")
              .quantity,
            4,
          );
          assert.equal((await otherOwner.get(`/orders/${order.id}`)).status(), 403);
          assert.equal((await otherBuyer.get(`/orders/${order.id}`)).status(), 403);
          assert.equal((await buyer.get("/admin/users")).status(), 403);
          await page.screenshot({ path: `${results}/buyer-order.png`, fullPage: true });
        },
      );
      await t.test(
        "shop uses every allowed transition; delivery enables buyer review and keeps snapshots",
        async () => {
          assert.ok(order, "checkout must succeed before delivery");
          const shopContext = await browser.newContext();
          contexts.push(shopContext);
          const shopPage = await shopContext.newPage();
          await login(shopPage, "shop1@shop.vn", "Shop@123");
          await shopPage.goto(`${baseURL}/shop/orders`);
          for (const label of ["Xác nhận", "Chuẩn bị", "Giao hàng", "Đã giao"]) {
            const changed = shopPage.waitForResponse(
              (r) =>
                r.url().endsWith(`/orders/${order.id}/status`) && r.request().method() === "PATCH",
            );
            await shopPage
              .getByRole("row")
              .filter({ hasText: order.code })
              .getByRole("button", { name: label, exact: true })
              .click();
            assert.equal((await changed).status(), 200);
          }
          await page.reload();
          await page.getByRole("button", { name: "Đánh giá", exact: true }).first().click();
          await page.getByLabel("Nhận xét", { exact: true }).fill("Đánh giá giả từ kiểm thử E2E");
          const reviewed = page.waitForResponse(
            (r) => r.url().endsWith("/reviews") && r.request().method() === "POST",
          );
          await page.getByRole("button", { name: "Gửi đánh giá", exact: true }).click();
          assert.equal((await reviewed).status(), 200);
          await page.getByRole("dialog").waitFor({ state: "hidden" });
          const delivered = await json(buyer, "get", `/orders/${order.id}`);
          assert.equal(delivered.status, "DELIVERED");
          assert.equal(delivered.payment_status, "PAID");
          assert.equal(delivered.status_history.length, 5);
          assert.ok(delivered.items.some((item) => item.review_id != null));
          assert.deepEqual(
            delivered.items.map((i) => [i.product_name, i.unit_price]),
            order.items.map((i) => [i.product_name, i.unit_price]),
          );
          await page.setViewportSize({ width: 390, height: 844 });
          assert.ok(
            await page.evaluate(
              () => globalThis.document.documentElement.scrollWidth <= globalThis.innerWidth,
            ),
          );
          await page.screenshot({ path: `${results}/buyer-mobile.png`, fullPage: true });
        },
      );
      await t.test(
        "purchase receipt replenishes stock once and resolves the checkout alert",
        async () => {
          assert.ok(order, "checkout must succeed before replenishment");
          const variantId = first.variants.find((v) => v.size === "M").id;
          const alerts = await json(owner, "get", "/shop/alerts");
          assert.equal(
            alerts.filter((a) => a.variant_id === variantId && !a.is_resolved).length,
            1,
          );
          const shopPage = await contexts[1].newPage();
          await shopPage.goto(`${baseURL}/shop/purchase-orders`);
          const suppliers = await json(owner, "get", "/shop/suppliers");
          await shopPage
            .getByRole("combobox", { name: /^Nhà cung cấp/ })
            .selectOption(String(suppliers[0].id));
          await shopPage
            .getByRole("combobox", { name: /^Biến thể/ })
            .selectOption(String(variantId));
          await shopPage.getByLabel("Số lượng", { exact: true }).fill("5");
          await shopPage.getByLabel("Giá nhập (₫)", { exact: true }).fill("50000");
          await shopPage.getByLabel("Ghi chú", { exact: true }).fill(`Nhập hàng E2E ${suffix}`);
          const created = shopPage.waitForResponse(
            (r) => r.url().endsWith("/shop/purchase-orders") && r.request().method() === "POST",
          );
          await shopPage.getByRole("button", { name: "Tạo phiếu nháp", exact: true }).click();
          const poResponse = await created;
          assert.equal(poResponse.status(), 201);
          const po = await poResponse.json();
          for (const label of ["Đặt hàng", "Đã nhận hàng"]) {
            const changed = shopPage.waitForResponse(
              (r) =>
                r.url().endsWith(`/shop/purchase-orders/${po.id}/status`) &&
                r.request().method() === "PATCH",
            );
            await shopPage
              .locator("article.order-box")
              .filter({ hasText: `Nhập hàng E2E ${suffix}` })
              .getByRole("button", { name: label, exact: true })
              .click();
            assert.equal((await changed).status(), 200);
          }
          const stock = async () =>
            (await json(owner, "get", "/shop/inventory")).find((v) => v.variant_id === variantId)
              .quantity;
          assert.equal(await stock(), 9);
          assert.equal(
            (
              await owner.patch(`/shop/purchase-orders/${po.id}/status`, {
                data: { status: "RECEIVED" },
              })
            ).status(),
            400,
          );
          assert.equal(await stock(), 9);
          assert.equal(
            (await json(owner, "get", "/shop/alerts")).filter(
              (a) => a.variant_id === variantId && !a.is_resolved,
            ).length,
            0,
          );
          await shopPage.screenshot({ path: `${results}/purchase-receipt.png`, fullPage: true });
        },
      );
      await t.test(
        "admin sees operational dashboard; buyer route guard returns to the catalog",
        async () => {
          await page.goto(`${baseURL}/admin/dashboard`);
          await page.waitForURL(`${baseURL}/`);
          const adminContext = await browser.newContext({
            viewport: { width: 1440, height: 1000 },
          });
          contexts.push(adminContext);
          const adminPage = await adminContext.newPage();
          const dashboardResponse = adminPage.waitForResponse((r) =>
            r.url().includes("/admin/stats/dashboard"),
          );
          await login(adminPage, "admin@shop.vn", "Admin@123");
          await adminPage
            .getByRole("heading", { name: "Quản trị hệ thống", exact: true })
            .waitFor();
          await adminPage.locator(".dashboard-body").waitFor();
          const dashboard = await (await dashboardResponse).json();
          assert.ok(Number(dashboard.overview.revenue) >= 300000);
          const displayedRevenue = new Intl.NumberFormat("vi-VN").format(
            Number(dashboard.overview.revenue),
          );
          assert.ok(
            (await adminPage.locator(".dashboard-body").innerText()).includes(displayedRevenue),
          );
          await adminPage.screenshot({ path: `${results}/admin-dashboard.png`, fullPage: true });
        },
      );
    } finally {
      for (const [index, context] of contexts.entries()) {
        for (const [pageIndex, failurePage] of context.pages().entries()) {
          await failurePage
            .screenshot({
              path: `${results}/last-page-${index}-${pageIndex}.png`,
              fullPage: true,
            })
            .catch(() => {});
        }
      }
      for (const context of contexts) await context.close();
      for (const api of apis) await api.dispose();
      await browser.close();
    }
  },
);
