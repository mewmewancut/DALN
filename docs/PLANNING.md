# PLANNING CHI TIẾT — Fashion E-Commerce Platform

> Bản đặc tả "cầm tay chỉ việc": làm theo đúng thứ tự từ trên xuống, không cần tự nghĩ thêm gì.
> Dựa trên `PROPOSAL.md` + `README.md`.
>
> Cách đọc tài liệu này:
> - **Phần A → G**: đặc tả chi tiết từng phần (setup, database, backend, frontend, data, dashboard/Genie, test). Đây là "làm CÁI GÌ và làm NHƯ THẾ NÀO".
> - **Phần H**: quy trình làm việc + cách review để code không bị lỗi logic.
> - **Phần I**: quy tắc xây dựng tài liệu hệ thống để người đọc và người phát triển sau hiểu đúng trạng thái dự án.
> - Chỗ nào có ⚠️ là chỗ **dễ sai logic** — đọc kỹ, làm đúng y như hướng dẫn.
> - Chỗ nào có 📌 QUYẾT ĐỊNH là rule nghiệp vụ đã được chốt sẵn — cứ thế làm, đừng mỗi người hiểu một kiểu.

---

## PHẦN A — SETUP DỰ ÁN TỪ SỐ 0

### A1. Cài đặt trên máy (cả 2 người)

1. Docker Desktop (bật WSL2 nếu Windows).
2. Python 3.11 trở lên.
3. Node.js 20 trở lên.
4. Git.
5. Tài khoản Databricks (workspace có Lakebase + Unity Catalog) — 1 workspace dùng chung cho cả nhóm.

### A2. Cấu trúc repo (tạo đúng như này)

```text
fashion-ecommerce/
├── PROPOSAL.md
├── README.md
├── PLANNING.md               ← file này
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/              ← migration
│   ├── alembic.ini
│   └── app/
│       ├── main.py           ← khởi tạo FastAPI, gắn router
│       ├── config.py         ← đọc biến môi trường (DB_URL, JWT_SECRET...)
│       ├── database.py       ← engine + SessionLocal (SQLAlchemy)
│       ├── deps.py           ← get_db, get_current_user, require_role, get_current_shop
│       ├── models/           ← SQLAlchemy models (mỗi file 1 nhóm bảng)
│       ├── schemas/          ← Pydantic schemas (request/response)
│       ├── routers/          ← auth.py, shops.py, products.py, cart.py, orders.py,
│       │                        suppliers.py, purchase_orders.py, inventory.py,
│       │                        reviews.py, admin.py, shop_stats.py
│       ├── services/         ← LOGIC NGHIỆP VỤ để ở đây, KHÔNG viết trong router
│       │   ├── cart_service.py
│       │   ├── checkout_service.py
│       │   ├── order_service.py      ← state machine ở đây
│       │   ├── inventory_service.py
│       │   └── purchase_service.py
│       ├── seed.py           ← tạo dữ liệu mẫu
│       └── tests/            ← pytest
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── api/              ← 1 file axios client + các hàm gọi API
│       ├── auth/             ← context lưu token + role
│       ├── components/       ← component dùng chung
│       ├── pages/
│       │   ├── buyer/
│       │   ├── shop/
│       │   └── admin/
│       └── App.jsx           ← routing theo role
└── data/
    ├── 01_bronze_ingest.py   ← notebook/job Databricks
    ├── 02_silver_transform.py
    ├── 03_gold_aggregate.py
    └── 04_data_quality_check.py
```

**Quy tắc bất di bất dịch:** router chỉ nhận request → gọi service → trả response. Mọi logic (kiểm tra tồn kho, đổi trạng thái, tính tiền) nằm trong `services/`. Lý do: logic gom 1 chỗ thì test được, không bị mỗi endpoint tự chế một kiểu.

### A3. docker-compose.yml (dev)

3 service:

| Service | Image/Build | Port | Ghi chú |
|---|---|---|---|
| `db` | `postgres:16` | 5432 | ⚠️ Dev dùng Postgres local vì **Lakebase tương thích Postgres**. Code SQLAlchemy giữ nguyên, khi nào Lakebase sẵn sàng chỉ đổi `DATABASE_URL` trong `.env`. Không được viết SQL đặc thù chỉ Postgres-local có. |
| `backend` | `./backend` | 8000 | FastAPI + uvicorn, mount code để hot-reload |
| `frontend` | `./frontend` | 5173 | Vite dev server |

`.env.example` phải có: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES=60`, `VITE_API_URL=http://localhost:8000`.

### A4. Lệnh chạy (ghi vào README)

```bash
cp .env.example .env
docker compose up -d db
cd backend && pip install -r requirements.txt
alembic upgrade head          # tạo bảng
python -m app.seed            # dữ liệu mẫu
uvicorn app.main:app --reload # hoặc docker compose up backend
cd frontend && npm install && npm run dev
```

**Definition of Done phần A:** cả 2 máy chạy được `docker compose up`, mở `http://localhost:8000/docs` thấy Swagger, `http://localhost:5173` thấy trang React.

---

## PHẦN B — DATABASE: TỪNG BẢNG, TỪNG CỘT

Tất cả bảng có `id` kiểu `BIGSERIAL PRIMARY KEY` (trừ khi ghi khác), `created_at TIMESTAMPTZ DEFAULT now()`. Bảng nào có sửa đổi thì thêm `updated_at`.

⚠️ **Lưu thời gian luôn là UTC (`TIMESTAMPTZ`).** Hiển thị giờ VN là việc của frontend. Sai chỗ này thì "doanh thu theo ngày" ở pipeline sẽ lệch.

### B1. `users`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| password_hash | VARCHAR(255) | NOT NULL — hash bằng **bcrypt**, KHÔNG BAO GIỜ lưu plain text |
| full_name | VARCHAR(255) | NOT NULL |
| role | VARCHAR(20) | NOT NULL, CHECK role IN ('BUYER','SHOP_OWNER','ADMIN') |
| is_active | BOOLEAN | DEFAULT true — admin khóa tài khoản thì set false |

### B2. `shops`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| owner_id | BIGINT | FK → users.id, **UNIQUE** (1 user chỉ có 1 shop) |
| name | VARCHAR(255) | NOT NULL |
| description | TEXT | |
| is_active | BOOLEAN | DEFAULT true |

📌 QUYẾT ĐỊNH: đăng ký shop = đăng ký tài khoản role SHOP_OWNER rồi tạo shop trong lần đăng nhập đầu. Không làm luồng "duyệt shop" (ngoài scope).

### B3. `categories`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| name | VARCHAR(100) | UNIQUE, NOT NULL |

📌 QUYẾT ĐỊNH: category là **danh sách phẳng do ADMIN quản lý** (Áo, Quần, Váy, Giày, Túi xách, Phụ kiện). Không làm category lồng nhau (parent_id) — thêm phức tạp mà không thêm điểm.

### B4. `products`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| shop_id | BIGINT | FK → shops.id, NOT NULL |
| category_id | BIGINT | FK → categories.id, NOT NULL |
| name | VARCHAR(255) | NOT NULL |
| description | TEXT | |
| image_url | TEXT | link ảnh (dùng link ngoài/placeholder, không làm upload file — ngoài scope) |
| base_price | NUMERIC(12,0) | NOT NULL, CHECK >= 0 — đơn vị VND, không lưu số lẻ |
| is_active | BOOLEAN | DEFAULT true |
| updated_at | TIMESTAMPTZ | |

⚠️ **Không bao giờ DELETE product.** Xóa = `is_active=false` (soft delete). Lý do: order_items cũ còn trỏ tới nó, hard delete là vỡ dữ liệu lịch sử.

### B5. `product_variants`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| product_id | BIGINT | FK → products.id, NOT NULL |
| size | VARCHAR(10) | NOT NULL — 'S','M','L','XL','38','39'... |
| color | VARCHAR(30) | NOT NULL |
| price | NUMERIC(12,0) | NOT NULL — giá bán thật của biến thể (cho phép khác base_price) |
| sku | VARCHAR(50) | UNIQUE — sinh tự động: `P{product_id}-{size}-{color}` |
| is_active | BOOLEAN | DEFAULT true |
| | | **UNIQUE (product_id, size, color)** ← chặn tạo trùng biến thể |

### B6. `inventory` — ⚠️ bảng quan trọng nhất

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| variant_id | BIGINT | FK → product_variants.id, **UNIQUE** (1 variant có đúng 1 dòng tồn kho vì mỗi shop 1 kho) |
| shop_id | BIGINT | FK → shops.id (denormalize để query nhanh) |
| quantity | INT | NOT NULL DEFAULT 0, **CHECK (quantity >= 0)** ← chốt chặn cuối cùng ở DB, dù code có bug cũng không âm kho được |
| low_stock_threshold | INT | NOT NULL DEFAULT 5 |
| updated_at | TIMESTAMPTZ | |

### B7. `suppliers`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| shop_id | BIGINT | FK → shops.id, NOT NULL — supplier thuộc về từng shop |
| name | VARCHAR(255) | NOT NULL |
| phone | VARCHAR(20) | |
| address | TEXT | |
| is_active | BOOLEAN | DEFAULT true |

### B8. `purchase_orders` + `purchase_order_items` (nhập hàng)

`purchase_orders`:

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| shop_id | BIGINT | FK, NOT NULL |
| supplier_id | BIGINT | FK → suppliers.id, NOT NULL |
| status | VARCHAR(20) | CHECK IN ('DRAFT','ORDERED','RECEIVED','CANCELLED'), DEFAULT 'DRAFT' |
| received_at | TIMESTAMPTZ | NULL — set khi chuyển sang RECEIVED |
| note | TEXT | |

`purchase_order_items`:

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| purchase_order_id | BIGINT | FK, NOT NULL |
| variant_id | BIGINT | FK, NOT NULL |
| quantity | INT | NOT NULL, CHECK > 0 |
| unit_cost | NUMERIC(12,0) | NOT NULL — giá nhập |
| | | UNIQUE (purchase_order_id, variant_id) |

⚠️ Chỉ khi status chuyển **ORDERED → RECEIVED** mới cộng kho, và vì RECEIVED là trạng thái cuối (không quay lại được) nên **không thể cộng kho 2 lần**. Xem pseudocode C7.

### B9. `carts` + `cart_items` (giỏ hàng lưu server)

`carts`:

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| buyer_id | BIGINT | FK → users.id, **UNIQUE** — mỗi buyer đúng 1 giỏ |
| shop_id | BIGINT | FK → shops.id, **NULL khi giỏ rỗng** — đây chính là cách enforce "1 giỏ 1 shop" |

`cart_items`:

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| cart_id | BIGINT | FK, NOT NULL |
| variant_id | BIGINT | FK, NOT NULL |
| quantity | INT | NOT NULL, CHECK > 0 |
| | | UNIQUE (cart_id, variant_id) — thêm trùng variant thì cộng dồn quantity, không tạo dòng mới |

### B10. `orders`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| code | VARCHAR(20) | UNIQUE — mã đơn hiển thị, sinh dạng `ORD-20260916-0001` |
| buyer_id | BIGINT | FK → users.id, NOT NULL |
| shop_id | BIGINT | FK → shops.id, NOT NULL — 1 đơn thuộc đúng 1 shop (hệ quả rule 1 giỏ 1 shop) |
| status | VARCHAR(20) | CHECK IN ('PENDING','CONFIRMED','PREPARING','SHIPPING','DELIVERED','CANCELLED'), DEFAULT 'PENDING' |
| shipping_address | TEXT | NOT NULL — snapshot địa chỉ lúc đặt |
| receiver_name | VARCHAR(255) | NOT NULL |
| receiver_phone | VARCHAR(20) | NOT NULL |
| payment_method | VARCHAR(20) | CHECK IN ('COD','MOCK_CARD') |
| payment_status | VARCHAR(20) | CHECK IN ('UNPAID','PAID'), DEFAULT 'UNPAID' |
| total_amount | NUMERIC(12,0) | NOT NULL — tính ở backend lúc checkout, KHÔNG nhận từ client |
| delivered_at | TIMESTAMPTZ | NULL — set khi DELIVERED (dùng cho doanh thu + điều kiện review) |
| cancelled_at | TIMESTAMPTZ | NULL |
| cancel_reason | TEXT | |
| updated_at | TIMESTAMPTZ | |

### B11. `order_items` — ⚠️ toàn bộ là SNAPSHOT

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| order_id | BIGINT | FK, NOT NULL |
| variant_id | BIGINT | FK — để trace, nhưng KHÔNG dùng để lấy giá/tên khi hiển thị đơn |
| product_name | VARCHAR(255) | NOT NULL — copy tại lúc đặt |
| size | VARCHAR(10) | NOT NULL — copy |
| color | VARCHAR(30) | NOT NULL — copy |
| unit_price | NUMERIC(12,0) | NOT NULL — **giá tại lúc đặt**, shop đổi giá sau đó thì đơn cũ không đổi |
| quantity | INT | NOT NULL, CHECK > 0 |

### B12. `order_status_history`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| order_id | BIGINT | FK, NOT NULL |
| from_status | VARCHAR(20) | NULL với dòng đầu tiên (tạo đơn) |
| to_status | VARCHAR(20) | NOT NULL |
| changed_by | BIGINT | FK → users.id — ai đổi |
| note | TEXT | |

Mỗi lần đổi trạng thái đơn → **bắt buộc** insert 1 dòng vào đây (làm trong cùng transaction với update orders).

### B13. `reviews`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| order_item_id | BIGINT | FK → order_items.id, **UNIQUE** ← DB chặn review trùng, dù code có bug |
| product_id | BIGINT | FK — denormalize để query review theo sản phẩm |
| buyer_id | BIGINT | FK |
| rating | INT | NOT NULL, CHECK BETWEEN 1 AND 5 |
| comment | TEXT | |

### B14. `low_stock_alerts`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| variant_id | BIGINT | FK, NOT NULL |
| shop_id | BIGINT | FK, NOT NULL |
| quantity_at_alert | INT | NOT NULL — tồn kho tại lúc bắn alert |
| is_resolved | BOOLEAN | DEFAULT false — set true khi nhập hàng đưa tồn kho lên trên ngưỡng |

⚠️ Chống spam alert: chỉ tạo alert mới nếu **chưa có alert `is_resolved=false`** cho variant đó. Xem C6.

### B15. Seed data (`app/seed.py`)

Script phải tạo (idempotent — chạy lại không nhân đôi, dùng kiểu `get_or_create` theo email/sku):

- 1 admin: `admin@shop.vn / Admin@123`
- 3 shop owner + 3 shop: `shop1@shop.vn`, `shop2@shop.vn`, `shop3@shop.vn / Shop@123`
- 5 buyer: `buyer1..5@shop.vn / Buyer@123`
- 6 category cố định (B3)
- Mỗi shop ≥ 15 sản phẩm, mỗi sản phẩm 2–6 variant, tồn kho random 0–50 (cố tình để vài variant = 0 và vài variant dưới ngưỡng để demo hết hàng + low stock)
- Mỗi shop 2 supplier
- ≥ 30 đơn hàng rải trạng thái + rải ngày trong 30 ngày gần nhất (để dashboard có dữ liệu theo thời gian), trong đó ~10% CANCELLED

---

## PHẦN C — BACKEND: TỪNG ENDPOINT + PSEUDOCODE CHỖ KHÓ

### C0. Chuẩn chung

- Response lỗi thống nhất: `{"detail": "thông báo"}` với HTTP code đúng: 400 (sai nghiệp vụ), 401 (chưa đăng nhập), 403 (sai quyền), 404 (không tồn tại), 409 (xung đột, ví dụ hết hàng).
- JWT payload: `{"sub": user_id, "role": role, "shop_id": shop_id_hoặc_null}`.
- `deps.py` viết sẵn 3 dependency và **mọi router dùng lại**, không tự viết check quyền lẻ tẻ:
  - `get_current_user` — decode JWT, load user, 401 nếu fail.
  - `require_role("SHOP_OWNER")` — 403 nếu role sai.
  - `get_current_shop` — trả shop của user hiện tại, 403 nếu chưa có shop.
- ⚠️ **Cấm tuyệt đối** endpoint nào của shop owner nhận `shop_id` từ client. `shop_id` luôn = `get_current_shop().id`.

### C1. Router `auth.py`

| Method + Path | Ai gọi | Body | Trả về | Lỗi |
|---|---|---|---|---|
| POST `/auth/register` | public | email, password, full_name, role ('BUYER'\|'SHOP_OWNER') | user (không có hash) | 400 email trùng; 400 nếu role='ADMIN' (admin chỉ tạo bằng seed) |
| POST `/auth/login` | public | email, password | `{access_token, role, shop_id}` | 401 sai email/pass; 403 tài khoản bị khóa |
| GET `/auth/me` | đã login | — | thông tin user hiện tại | 401 |

### C2. Router `shops.py` + `products.py` (catalog)

| Method + Path | Ai gọi | Ghi chú |
|---|---|---|
| POST `/shops` | SHOP_OWNER chưa có shop | tạo shop; 400 nếu đã có |
| PUT `/shops/me` | SHOP_OWNER | sửa shop của mình |
| GET `/categories` | public | danh sách category |
| POST `/products` | SHOP_OWNER | tạo product cho shop mình, kèm mảng variants `[{size,color,price,initial_quantity}]` — tạo product + variants + dòng inventory trong 1 transaction |
| PUT `/products/{id}` | SHOP_OWNER | ⚠️ trước khi sửa: load product, nếu `product.shop_id != current_shop.id` → **403**. Viết hàm chung `get_owned_product_or_403()` dùng cho mọi endpoint sửa/xóa |
| DELETE `/products/{id}` | SHOP_OWNER | soft delete: `is_active=false` |
| POST `/products/{id}/variants` | SHOP_OWNER | thêm variant; 409 nếu trùng (size,color) |
| PUT `/variants/{id}` | SHOP_OWNER | sửa giá / is_active; check owner qua variant→product→shop |
| GET `/products` | public | query params: `keyword` (ILIKE trên name), `category_id`, `shop_id`, `min_price`, `max_price`, `sort` (newest\|price_asc\|price_desc), `page`, `page_size` (default 20). **Chỉ trả product `is_active=true` của shop `is_active=true`** |
| GET `/products/{id}` | public | chi tiết + variants kèm `quantity` tồn kho + rating trung bình |

### C3. Router `cart.py` — ⚠️ rule 1 giỏ 1 shop

| Method + Path | Ai gọi | Ghi chú |
|---|---|---|
| GET `/cart` | BUYER | giỏ hiện tại + items (kèm tên, ảnh, giá, tồn kho hiện tại của từng variant) |
| POST `/cart/items` | BUYER | body: `{variant_id, quantity}` |
| PUT `/cart/items/{id}` | BUYER | đổi quantity |
| DELETE `/cart/items/{id}` | BUYER | xóa item; nếu giỏ rỗng → set `cart.shop_id = NULL` |
| DELETE `/cart` | BUYER | xóa sạch giỏ + set shop_id NULL |

Pseudocode `add_to_cart` (trong `cart_service.py`):

```text
function add_to_cart(buyer, variant_id, quantity):
    variant = load variant JOIN product; 404 nếu không có hoặc is_active=false
    shop_of_item = variant.product.shop_id
    cart = get_or_create_cart(buyer)

    if cart.shop_id is not NULL and cart.shop_id != shop_of_item:
        # ⚠️ ĐÂY là rule 1 giỏ 1 shop
        raise 409 {"detail": "CART_DIFFERENT_SHOP",
                   "current_shop": {id, name}}   # FE dựa vào code này để hiện popup
    if cart.shop_id is NULL:
        cart.shop_id = shop_of_item

    existing = tìm cart_item cùng variant
    new_qty = (existing.quantity nếu có else 0) + quantity
    if new_qty > tồn kho hiện tại: raise 409 "Không đủ hàng"   # check mềm cho UX,
                                                # check CỨNG thật sự nằm ở checkout
    upsert cart_item với new_qty
```

FE khi nhận lỗi `CART_DIFFERENT_SHOP` → hiện popup "Giỏ đang có hàng của shop X. Xóa giỏ và thêm sản phẩm này?" → nếu OK thì gọi `DELETE /cart` rồi gọi lại `POST /cart/items`.

### C4. Checkout — ⚠️⚠️ đoạn code quan trọng nhất dự án

| Method + Path | Ai gọi | Body |
|---|---|---|
| POST `/orders/checkout` | BUYER | `{receiver_name, receiver_phone, shipping_address, payment_method}` |

Pseudocode `checkout_service.checkout()` — **chép đúng cấu trúc này**:

```text
function checkout(buyer, info):
    cart = load giỏ + items; 400 nếu giỏ rỗng
    BEGIN TRANSACTION                        # ← tất cả bên trong 1 transaction
        total = 0
        order = insert orders(buyer_id, shop_id=cart.shop_id, status='PENDING',
                              payment_status=..., snapshot info người nhận,
                              total_amount=0 tạm)
        for item in cart.items:
            variant = SELECT variant JOIN product (lấy giá + tên HIỆN TẠI từ DB,
                       KHÔNG lấy giá FE gửi lên)
            # ⚠️ TRỪ KHO ATOMIC — chống 2 người mua cùng lúc:
            rows = UPDATE inventory
                   SET quantity = quantity - item.quantity, updated_at = now()
                   WHERE variant_id = item.variant_id
                     AND quantity >= item.quantity
            if rows == 0:
                ROLLBACK
                raise 409 "Sản phẩm {tên} ({size}/{color}) không đủ hàng"
            insert order_items(order_id, variant_id,
                               product_name=variant.product.name,   # snapshot
                               size, color,
                               unit_price=variant.price,            # snapshot
                               quantity=item.quantity)
            total += variant.price * item.quantity
        UPDATE orders SET total_amount = total
        insert order_status_history(order, from=NULL, to='PENDING', by=buyer)
        if payment_method == 'MOCK_CARD':
            UPDATE orders SET payment_status='PAID'    # thanh toán mô phỏng
        DELETE cart_items; UPDATE carts SET shop_id=NULL
    COMMIT
    # SAU commit mới check low-stock (C6) — không để nó làm fail đơn
    for variant in các variant vừa trừ: check_low_stock(variant)
    return order
```

⚠️ Những cách làm **SAI** hay gặp — cấm làm:
- SAI: `SELECT quantity` rồi `if quantity >= n:` rồi `UPDATE quantity = quantity - n` — dính race condition, 2 request cùng đọc quantity=1 rồi cùng trừ → âm kho. Phải dùng UPDATE có điều kiện như trên.
- SAI: lấy giá từ payload FE gửi lên. Giá luôn SELECT từ DB tại thời điểm checkout.
- SAI: tạo đơn xong mới trừ kho ở request khác. Trừ kho phải cùng transaction với tạo đơn.

### C5. Router `orders.py` — state machine

| Method + Path | Ai gọi | Ghi chú |
|---|---|---|
| GET `/orders/my` | BUYER | đơn của mình, filter theo status, phân trang |
| GET `/orders/{id}` | BUYER/SHOP/ADMIN | ⚠️ BUYER chỉ xem đơn của mình; SHOP chỉ xem đơn `shop_id` của mình; ADMIN xem hết. Sai → 403 |
| GET `/shop/orders` | SHOP_OWNER | đơn của shop mình, filter status |
| PATCH `/orders/{id}/status` | SHOP_OWNER | body `{status, note?}` — đi qua `transition_order()` |
| POST `/orders/{id}/cancel` | BUYER | body `{reason}` — cũng đi qua `transition_order()` |

Pseudocode `order_service.py` — **toàn bộ thay đổi trạng thái đơn đi qua đúng 1 hàm này**, không ai được viết `order.status = X` chỗ khác:

```text
ALLOWED = {
  'PENDING':   ['CONFIRMED', 'CANCELLED'],
  'CONFIRMED': ['PREPARING', 'CANCELLED'],
  'PREPARING': ['SHIPPING'],
  'SHIPPING':  ['DELIVERED'],
  'DELIVERED': [],          # trạng thái cuối
  'CANCELLED': [],          # trạng thái cuối
}
# 📌 QUYẾT ĐỊNH: - Buyer chỉ được hủy khi đơn PENDING.
#                - Shop được hủy khi PENDING hoặc CONFIRMED.
#                - Từ PREPARING trở đi KHÔNG hủy được nữa. DELIVERED->CANCELLED cấm tuyệt đối.

function transition_order(order_id, new_status, actor, note=None):
    BEGIN TRANSACTION
        order = SELECT * FROM orders WHERE id=:id FOR UPDATE   # ⚠️ lock dòng,
                                     # chống buyer hủy và shop confirm cùng lúc
        # 1. Check quyền:
        if actor.role == 'BUYER':
            403 nếu order.buyer_id != actor.id
            400 nếu không phải (new_status=='CANCELLED' và order.status=='PENDING')
        if actor.role == 'SHOP_OWNER':
            403 nếu order.shop_id != actor.shop_id
            nếu new_status=='CANCELLED': 400 nếu order.status không thuộc
                                          ('PENDING','CONFIRMED')
        # 2. Check transition hợp lệ:
        if new_status not in ALLOWED[order.status]:
            raise 400 f"Không thể chuyển {order.status} → {new_status}"
        # 3. Side effect:
        if new_status == 'CANCELLED':
            # ⚠️ HOÀN KHO — vì mọi đường vào đây đều qua hàm này và có check
            # transition, đơn không thể bị CANCELLED 2 lần → không hoàn kho 2 lần
            for item in order.items:
                UPDATE inventory SET quantity = quantity + item.quantity
                WHERE variant_id = item.variant_id
            order.cancelled_at = now(); order.cancel_reason = note
        if new_status == 'DELIVERED':
            order.delivered_at = now()
            if order.payment_method == 'COD': order.payment_status = 'PAID'
        # 4. Ghi lại:
        UPDATE orders SET status = new_status, updated_at = now()
        INSERT order_status_history(order_id, from=old, to=new_status,
                                    changed_by=actor.id, note)
    COMMIT
```

### C6. Inventory + low stock (`inventory_service.py`, router `inventory.py`)

| Method + Path | Ai gọi | Ghi chú |
|---|---|---|
| GET `/shop/inventory` | SHOP_OWNER | tồn kho mọi variant của shop, cột: sản phẩm, size, màu, quantity, threshold, cờ `is_low` |
| PUT `/shop/inventory/{variant_id}/threshold` | SHOP_OWNER | đổi ngưỡng cảnh báo |
| GET `/shop/alerts` | SHOP_OWNER | alert `is_resolved=false` của shop |

```text
function check_low_stock(variant_id):        # gọi SAU khi trừ kho (checkout)
    inv = load inventory
    if inv.quantity < inv.low_stock_threshold:
        exists = SELECT 1 FROM low_stock_alerts
                 WHERE variant_id=:v AND is_resolved=false
        if not exists:                        # ⚠️ chống bắn alert trùng
            INSERT low_stock_alerts(variant_id, shop_id, quantity_at_alert=inv.quantity)

function resolve_alerts_if_ok(variant_id):   # gọi SAU khi cộng kho (nhận hàng, hủy đơn)
    inv = load inventory
    if inv.quantity >= inv.low_stock_threshold:
        UPDATE low_stock_alerts SET is_resolved=true
        WHERE variant_id=:v AND is_resolved=false
```

### C7. Supplier + nhập hàng (`suppliers.py`, `purchase_orders.py`)

| Method + Path | Ai gọi | Ghi chú |
|---|---|---|
| CRUD `/shop/suppliers` | SHOP_OWNER | supplier của shop mình; xóa = is_active=false |
| POST `/shop/purchase-orders` | SHOP_OWNER | body: supplier_id + items `[{variant_id, quantity, unit_cost}]`; ⚠️ check mọi variant thuộc shop mình, status khởi tạo DRAFT |
| GET `/shop/purchase-orders` | SHOP_OWNER | danh sách + filter status |
| PATCH `/shop/purchase-orders/{id}/status` | SHOP_OWNER | DRAFT→ORDERED→RECEIVED, DRAFT/ORDERED→CANCELLED |

```text
function receive_purchase_order(po_id, shop):
    BEGIN TRANSACTION
        po = SELECT ... FOR UPDATE; 403 nếu po.shop_id != shop.id
        if po.status != 'ORDERED': raise 400   # ⚠️ RECEIVED rồi thì không vào được
                                               # nữa → không cộng kho 2 lần
        for item in po.items:
            UPDATE inventory SET quantity = quantity + item.quantity
            WHERE variant_id = item.variant_id
        po.status = 'RECEIVED'; po.received_at = now()
    COMMIT
    for item in po.items: resolve_alerts_if_ok(item.variant_id)
```

### C8. Reviews (`reviews.py`)

| Method + Path | Ai gọi | Ghi chú |
|---|---|---|
| POST `/reviews` | BUYER | body `{order_item_id, rating, comment}` |
| GET `/products/{id}/reviews` | public | phân trang, kèm rating trung bình |

Check khi POST (theo đúng thứ tự): order_item tồn tại → order của nó thuộc buyer hiện tại (403) → `order.status == 'DELIVERED'` (400 "Chỉ đánh giá sau khi nhận hàng") → chưa có review cho order_item này (400; kể cả code check sót thì UNIQUE constraint B13 vẫn chặn).

### C9. Shop stats (`shop_stats.py`) — số liệu cho chủ shop (query thẳng Lakebase)

| Method + Path | Trả về |
|---|---|
| GET `/shop/stats/overview?from=&to=` | `{revenue, order_count, cancelled_count, cancel_rate, aov}` |
| GET `/shop/stats/revenue-by-day?from=&to=` | mảng `{date, revenue, order_count}` |
| GET `/shop/stats/top-products?limit=10` | top theo số lượng bán |

📌 **QUYẾT ĐỊNH — ĐỊNH NGHĨA METRIC (dùng CHUNG cho C9, Gold, Dashboard, Genie — sai lệch giữa các nơi là lỗi nặng nhất khi demo):**
- **Doanh thu** = SUM(`total_amount`) của đơn `status='DELIVERED'`, tính theo ngày **`delivered_at`** (giờ VN).
- **Số đơn** = COUNT đơn tạo trong kỳ (theo `created_at`), mọi trạng thái.
- **Tỷ lệ hủy** = COUNT đơn CANCELLED trong kỳ (theo `created_at`) / số đơn tạo trong kỳ.
- **AOV** (giá trị đơn trung bình) = doanh thu / COUNT đơn DELIVERED.
- **Sản phẩm bán chạy** = SUM(quantity) trong order_items của đơn DELIVERED.

Mọi query ở C9 đều có `WHERE shop_id = current_shop.id`.

### C10. Admin (`admin.py`) — tất cả require_role('ADMIN')

| Method + Path | Ghi chú |
|---|---|
| GET `/admin/users` | phân trang, filter role, keyword |
| PATCH `/admin/users/{id}` | khóa/mở `is_active` — ⚠️ 400 nếu tự khóa chính mình |
| GET `/admin/shops` + PATCH `/admin/shops/{id}` | danh sách + khóa shop (shop bị khóa: sản phẩm không hiện ở GET /products) |
| GET `/admin/orders` | toàn hệ thống, filter shop/status/ngày |
| GET `/admin/stats/overview` | như C9 nhưng không filter shop |

---

## PHẦN D — FRONTEND: TỪNG TRANG

### D1. Khung chung

- `src/api/client.js`: axios instance, tự gắn `Authorization: Bearer` từ localStorage, interceptor 401 → đá về `/login`.
- `AuthContext`: lưu `{token, role, shop_id}`; component `<RequireRole role="...">` bọc route — sai role → redirect. (Đây chỉ là UX; bảo mật thật nằm ở backend.)
- Route theo role sau login: BUYER → `/`, SHOP_OWNER → `/shop/dashboard`, ADMIN → `/admin/dashboard`.
- Mọi số tiền hiển thị `toLocaleString('vi-VN') + ' ₫'`.

### D2. Trang BUYER

| Route | Trang | Nội dung phải có |
|---|---|---|
| `/login`, `/register` | Auth | form + báo lỗi từ API |
| `/` | Danh sách sản phẩm | grid card (ảnh, tên, giá từ, shop, rating); thanh search; sidebar filter (category, khoảng giá); sort; phân trang. Mọi thay đổi filter → gọi lại GET /products với query params |
| `/products/:id` | Chi tiết | chọn màu → chọn size → hiện giá + tồn kho của đúng variant đó; nút "Thêm vào giỏ" **disable khi chưa chọn đủ size+màu hoặc hết hàng**; block review + rating trung bình |
| `/cart` | Giỏ hàng | tên shop trên đầu; sửa số lượng (không cho vượt tồn kho trả về từ API); xóa item; tổng tiền; nút Checkout. ⚠️ Xử lý popup `CART_DIFFERENT_SHOP` như C3 |
| `/checkout` | Đặt hàng | form người nhận + địa chỉ; chọn COD / MOCK_CARD; bấm đặt → gọi API → nếu 409 hết hàng thì hiện đúng thông báo sản phẩm nào thiếu → thành công thì sang trang đơn hàng |
| `/orders` | Đơn của tôi | tab theo status; mỗi đơn: code, ngày, tổng, trạng thái (badge màu), nút "Hủy đơn" **chỉ hiện khi PENDING** |
| `/orders/:id` | Chi tiết đơn | items (snapshot), timeline trạng thái từ order_status_history, nút "Đánh giá" cho từng item **chỉ khi DELIVERED và chưa review** |

### D3. Trang SHOP_OWNER (layout riêng có sidebar)

| Route | Trang | Nội dung phải có |
|---|---|---|
| `/shop/dashboard` | Tổng quan | 4 card số (doanh thu, số đơn, tỷ lệ hủy, AOV — gọi C9) + line chart doanh thu theo ngày + badge số alert tồn kho |
| `/shop/products` | Sản phẩm | bảng + nút thêm/sửa (modal: thông tin + bảng variants size/màu/giá/tồn kho ban đầu) + toggle ẩn/hiện |
| `/shop/orders` | Đơn hàng | bảng + filter status; nút hành động **hiện đúng theo trạng thái**: PENDING→[Xác nhận][Hủy], CONFIRMED→[Chuẩn bị][Hủy], PREPARING→[Giao hàng], SHIPPING→[Đã giao] (mapping đúng ALLOWED ở C5 — đừng hiện nút mà backend sẽ 400) |
| `/shop/inventory` | Tồn kho | bảng variant + quantity + threshold (sửa inline); dòng `is_low` tô đỏ |
| `/shop/alerts` | Cảnh báo | danh sách alert chưa resolved |
| `/shop/suppliers` | Nhà cung cấp | CRUD bảng đơn giản |
| `/shop/purchase-orders` | Nhập hàng | tạo phiếu (chọn supplier, thêm dòng variant+SL+giá nhập); nút theo trạng thái: DRAFT→[Đặt hàng][Hủy], ORDERED→[Đã nhận hàng][Hủy]; nhận hàng xong → link sang tồn kho thấy số đã cộng |

### D4. Trang ADMIN

| Route | Trang | Nội dung |
|---|---|---|
| `/admin/dashboard` | Tổng quan | card số toàn hệ thống + link mở Databricks Dashboard + link Genie (mở tab Databricks) |
| `/admin/users` | Users | bảng + filter role + nút khóa/mở |
| `/admin/shops` | Shops | bảng + khóa/mở shop |
| `/admin/orders` | Đơn toàn hệ thống | bảng + filter |

---

## PHẦN E — DATA PLATFORM (Databricks)

Catalog Unity: tạo catalog `fashion`, 3 schema: `bronze`, `silver`, `gold`. Chạy bằng **Databricks Job** đặt lịch (dev thì 15 phút/lần hoặc bấm tay trước demo; không cần streaming).

### E1. `01_bronze_ingest.py` — Lakebase → Bronze

Với **từng bảng** trong: users, shops, categories, products, product_variants, inventory, suppliers, purchase_orders, purchase_order_items, orders, order_items, order_status_history, reviews:

```text
df = đọc từ Lakebase (JDBC hoặc Lakehouse Federation)
df = df.withColumn("_ingested_at", current_timestamp())
MERGE INTO fashion.bronze.<tên_bảng> AS t USING df AS s
  ON t.id = s.id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
```

⚠️ Dùng MERGE theo `id`, **không** dùng append — chạy lại job không được nhân đôi dữ liệu. Test bắt buộc: chạy job 2 lần liên tiếp, `SELECT COUNT(*)` từng bảng bronze phải bằng số dòng bên Lakebase.

### E2. `02_silver_transform.py` — làm sạch

Tạo các bảng silver (mỗi bảng cũng MERGE theo khóa):

| Bảng silver | Nguồn | Việc phải làm |
|---|---|---|
| `silver.dim_shops` | bronze.shops + users | join lấy tên owner; lọc bỏ shop test nếu có |
| `silver.dim_products` | bronze.products + categories + shops | join tên category, tên shop; giữ cả sản phẩm inactive (đơn cũ cần) |
| `silver.dim_variants` | bronze.product_variants | chuẩn hóa size/color: TRIM + UPPER size, TRIM + lowercase→Capitalize color |
| `silver.fact_orders` | bronze.orders | ép status về đúng 6 giá trị (dòng lạ → bỏ + ghi log); thêm cột `created_date_vn = DATE(created_at + INTERVAL 7 HOURS)`, `delivered_date_vn` tương tự; loại đơn `total_amount <= 0` |
| `silver.fact_order_items` | bronze.order_items JOIN silver.fact_orders | gắn status + shop_id + các cột ngày từ orders vào từng item |
| `silver.fact_inventory` | bronze.inventory + dim_variants | snapshot tồn kho hiện tại kèm threshold, cờ `is_low` |
| `silver.fact_reviews` | bronze.reviews | rating ngoài 1–5 → bỏ |

⚠️ Timezone xử lý đúng 1 lần ở đây (tạo sẵn cột `_date_vn`); Gold trở đi **chỉ dùng cột `_date_vn`**, không ai tự cộng 7 giờ lần nữa.

### E3. `03_gold_aggregate.py` — bảng cho Dashboard + Genie

Gold **ghi đè toàn bộ mỗi lần chạy** (`overwrite`) — đơn giản, không sợ lệch. Dùng đúng định nghĩa metric ở C9.

| Bảng gold | Cột | Logic |
|---|---|---|
| `gold.revenue_daily` | date, shop_id, shop_name, revenue, delivered_orders | từ fact_orders DELIVERED, group by delivered_date_vn, shop |
| `gold.revenue_monthly` | month, shop_id, shop_name, revenue, delivered_orders | rollup từ revenue_daily |
| `gold.orders_summary_daily` | date, shop_id, total_orders, delivered, cancelled, cancel_rate, aov | theo created_date_vn; cancel_rate = cancelled/total_orders (⚠️ total=0 thì để NULL, đừng chia 0) |
| `gold.top_products` | shop_id, product_id, product_name, total_quantity_sold, total_revenue, avg_rating | từ fact_order_items DELIVERED + fact_reviews |
| `gold.low_stock_current` | shop_id, shop_name, product_name, size, color, quantity, threshold | từ fact_inventory WHERE is_low |
| `gold.shop_performance` | shop_id, shop_name, revenue, total_orders, cancel_rate, aov, product_count | tổng hợp toàn thời gian theo shop |

### E4. `04_data_quality_check.py` — GATE trước khi làm dashboard

Notebook so sánh và **in PASS/FAIL từng dòng**:

1. `SUM(revenue)` toàn bộ `gold.revenue_daily` == query thẳng Lakebase `SUM(total_amount) WHERE status='DELIVERED'`.
2. Tổng đơn trong `gold.orders_summary_daily` == `COUNT(*) FROM orders` bên Lakebase.
3. Số dòng bronze từng bảng == số dòng Lakebase.
4. Chạy `01→02→03` hai lần liên tiếp → mọi con số ở (1)(2) không đổi.
5. Không có dòng nào `quantity < 0` trong fact_inventory; không order nào status ngoài 6 giá trị.

**Chưa PASS hết 5 mục thì CẤM làm E5/E6.**

### E5. AI/BI Dashboard (làm trên UI Databricks)

Dashboard tên "Fashion Platform Overview", nguồn = các bảng `gold.*`:

1. Counter: tổng doanh thu, tổng đơn, tỷ lệ hủy toàn hệ thống, AOV (kèm filter khoảng ngày).
2. Line chart: doanh thu theo ngày (`revenue_daily`, sum theo date).
3. Bar chart: top 10 shop theo doanh thu (`shop_performance`).
4. Bar chart: top 10 sản phẩm bán chạy (`top_products`).
5. Table: `low_stock_current`.
6. Pie/bar: phân bố đơn theo trạng thái.

### E6. Genie space (làm trên UI Databricks)

1. Tạo Genie space "Fashion Platform Assistant", **chỉ add các bảng `gold.*`** (⚠️ không add bronze/silver/bảng vận hành — Genie đọc bảng thô sẽ tự suy diễn sai định nghĩa doanh thu).
2. Với từng bảng và từng cột: viết description tiếng Anh ngắn ("revenue: total amount of DELIVERED orders, in VND").
3. General instructions của space (dán nội dung kiểu): *"Revenue means sum of revenue in gold.revenue_daily (DELIVERED orders only). Dates are Vietnam local dates. Currency is VND. When asked about 'this month', filter by current month."*
4. Thêm sample questions = đúng 6 câu trong README mục 8.
5. Test lần lượt 6 câu + 4 biến thể tự nghĩ; câu nào Genie viết SQL sai → bổ sung instruction/description rồi test lại. Ghi lại 6 câu chạy ổn nhất vào kịch bản demo.

---

## PHẦN F — DANH SÁCH TEST CASE BẮT BUỘC

Viết pytest trong `backend/app/tests/`, dùng DB test riêng. Đây là danh sách tối thiểu — pass hết mới được coi là xong backend.

### F1. Auth & phân quyền

| # | Test | Kỳ vọng |
|---|---|---|
| 1 | Đăng ký email trùng | 400 |
| 2 | Đăng ký role=ADMIN | 400 |
| 3 | Login sai pass | 401 |
| 4 | Gọi API shop bằng token BUYER | 403 |
| 5 | Gọi API admin bằng token SHOP_OWNER | 403 |
| 6 | Shop A sửa product của shop B | 403 |
| 7 | Shop A xem đơn của shop B | 403 |
| 8 | Shop A xem `/shop/stats` → chỉ ra số của shop A | so sánh với dữ liệu seed |
| 9 | Buyer xem đơn của buyer khác | 403 |

### F2. Giỏ hàng & checkout

| # | Test | Kỳ vọng |
|---|---|---|
| 10 | Thêm variant shop B khi giỏ đang có hàng shop A | 409 CART_DIFFERENT_SHOP |
| 11 | Thêm cùng variant 2 lần | 1 dòng cart_item, quantity cộng dồn |
| 12 | Checkout giỏ rỗng | 400 |
| 13 | Checkout khi tồn kho đủ | 200; kho bị trừ đúng; giỏ rỗng; order PENDING; history có 1 dòng |
| 14 | Checkout khi 1 item vượt tồn | 409; **kho mọi item không đổi**; không có order nào được tạo (kiểm tra rollback) |
| 15 | ⚠️ 2 request checkout **đồng thời** cùng variant còn đúng 1 cái (dùng threading/2 session) | đúng 1 đơn thành công, kho = 0, không âm |
| 16 | Shop đổi giá sau khi buyer đã đặt | order_items.unit_price giữ giá cũ |
| 17 | total_amount do client gửi bậy | bị bỏ qua, backend tự tính |

### F3. State machine & hoàn kho

| # | Test | Kỳ vọng |
|---|---|---|
| 18 | PENDING→CONFIRMED→PREPARING→SHIPPING→DELIVERED (shop) | 200 từng bước; history đủ 5 dòng; delivered_at được set; COD → payment_status=PAID |
| 19 | PENDING→SHIPPING (nhảy cóc) | 400 |
| 20 | DELIVERED→CANCELLED | 400 |
| 21 | Buyer hủy khi PENDING | 200; kho hoàn đúng số lượng |
| 22 | Buyer hủy khi CONFIRMED | 400 (chỉ shop được hủy CONFIRMED) |
| 23 | Hủy đơn đã CANCELLED | 400; kho **không** cộng thêm lần nữa |
| 24 | Shop hủy khi PREPARING | 400 |

### F4. Nhập hàng & tồn kho & alert

| # | Test | Kỳ vọng |
|---|---|---|
| 25 | Tạo PO với variant của shop khác | 400/403 |
| 26 | ORDERED→RECEIVED | kho cộng đúng từng variant |
| 27 | Gọi RECEIVED lần 2 | 400; kho không đổi |
| 28 | Checkout làm tồn xuống dưới threshold | sinh đúng 1 alert |
| 29 | Checkout tiếp (vẫn dưới threshold) | **không** sinh alert thứ 2 |
| 30 | Nhận hàng đưa tồn lên trên threshold | alert cũ is_resolved=true |

### F5. Review

| # | Test | Kỳ vọng |
|---|---|---|
| 31 | Review khi đơn SHIPPING | 400 |
| 32 | Review order_item của người khác | 403 |
| 33 | Review 2 lần cùng order_item | 400 |
| 34 | Review hợp lệ | 200; rating trung bình sản phẩm cập nhật |

### F6. Data (chạy tay trên Databricks, chụp màn hình kết quả vào báo cáo)

35–39: đúng 5 mục của E4.

### F7. Test tay end-to-end trước demo (cả 2 người cùng làm, theo kịch bản)

40. Buyer mua 2 sản phẩm 1 shop → shop xử lý đến DELIVERED → buyer review → chạy pipeline → số hiện lên dashboard → hỏi Genie "doanh thu hôm nay" ra đúng số đó.

---

## PHẦN G — DOCKER HOÀN THIỆN + DEMO

1. `docker compose up --build` từ máy sạch chạy được toàn bộ (db + backend + frontend build production `npm run build` + nginx hoặc `vite preview`).
2. Script `reset_demo.sh`: drop DB → migrate → seed. Chạy trước mỗi buổi demo.
3. Kịch bản demo 10 phút (viết thành file `DEMO.md`): (1) buyer mua hàng gặp case hết tồn kho → đổi variant → đặt thành công; (2) shop confirm → delivered, xem alert tồn kho, tạo phiếu nhập, nhận hàng; (3) admin xem dashboard; (4) hỏi Genie 4 câu đã test; (5) mở slide kiến trúc Medallion giải thích luồng dữ liệu.

---

## PHẦN H — QUY TRÌNH LÀM VIỆC ĐỂ KHÔNG SINH LỖI LOGIC

### H1. Vòng lặp cho MỖI task backend (làm đúng thứ tự, không bỏ bước)

1. Đọc lại mục tương ứng trong Phần B/C của file này.
2. Viết service + router theo đúng đặc tả (đặc biệt các đoạn pseudocode — chép đúng cấu trúc).
3. Viết pytest cho các test case liên quan trong Phần F.
4. Chạy `pytest` — đỏ thì sửa đến xanh, không comment test để cho qua.
5. Nhờ Claude review bằng skill **`code-reviewer`**, prompt mẫu: *"Review file checkout_service.py, đối chiếu với đặc tả mục C4 trong PLANNING.md, tập trung: transaction, race condition, snapshot giá, rollback"*.
6. Với auth/checkout/payment/phân quyền: chạy thêm skill **`security-reviewer`**.
7. Cập nhật tài liệu kỹ thuật liên quan theo Phần I nếu task làm thay đổi hành vi, schema, API, kiến trúc hoặc cách chạy/test.
8. Tạo commit theo checkpoint H6, sau đó tạo PR để người kia review theo checklist H3 và merge.

### H2. Dùng skill của Claude theo từng loại việc

| Việc | Skill | Lúc nào |
|---|---|---|
| Review logic module backend | `code-reviewer` | sau khi test xanh, trước PR |
| Auth, checkout, endpoint nhận tiền/quyền | `security-reviewer` | trước PR |
| Viết SQL silver/gold | `sql-queries` / `write-query` | lúc viết transform |
| Soát số liệu gold vs vận hành | `validate-data` | E4 |
| Xem dữ liệu bronze trước khi viết silver | `explore-data` | đầu E2 |
| Chart/dashboard FE (nếu tự vẽ chart ở trang shop) | `dataviz` | D3 dashboard shop |

### H3. Checklist review PR (người review chạy qua từng dòng)

- [ ] Có endpoint nào của shop owner nhận `shop_id` từ client không? (phải là KHÔNG)
- [ ] Có chỗ nào đọc-rồi-ghi tồn kho thay vì UPDATE có điều kiện không?
- [ ] Có chỗ nào set `order.status` ngoài `transition_order()` không?
- [ ] Thao tác nhiều bảng có nằm trong 1 transaction không? Nhánh lỗi có rollback không?
- [ ] Giá/tổng tiền có chỗ nào lấy từ request client không?
- [ ] Test mới có cover nhánh lỗi (400/403/409) không, hay chỉ happy path?
- [ ] Migration có đi kèm nếu đổi schema không?

### H4. Bảng invariant — dán lên đầu README backend

| # | Invariant | Enforce ở | Test |
|---|---|---|---|
| I1 | Tồn kho không âm | UPDATE điều kiện (C4) + CHECK ở DB (B6) | F2-14, F2-15 |
| I2 | Đơn chỉ đi theo ALLOWED transitions | `transition_order()` duy nhất (C5) | F3-19, F3-20, F3-24 |
| I3 | 1 giỏ = 1 shop | `cart.shop_id` (B9) + add_to_cart (C3) | F2-10 |
| I4 | Giá trong đơn là snapshot | order_items copy giá (B11, C4) | F2-16 |
| I5 | Shop chỉ đụng dữ liệu shop mình | shop_id từ token (C0) | F1-6, F1-7, F1-8 |
| I6 | Hủy đơn hoàn kho đúng 1 lần | transition check + FOR UPDATE (C5) | F3-21, F3-23 |
| I7 | Review sau DELIVERED, 1 lần/item | check C8 + UNIQUE (B13) | F5-31..33 |
| I8 | Nhận hàng cộng kho 1 lần | status ORDERED→RECEIVED 1 chiều (C7) | F4-26, F4-27 |
| I9 | Metric 1 định nghĩa, mọi nơi khớp | 📌 mục C9, dùng chung C9/E3/E5/E6 | E4, F7-40 |
| I10 | Pipeline chạy lại không nhân đôi | MERGE bronze (E1), overwrite gold (E3) | E4-mục 4 |

### H5. Rủi ro & phương án

| Rủi ro | Phương án |
|---|---|
| Lakebase setup chậm | Phát triển backend trên Postgres local (A3), chỉ chuyển sang Lakebase khi bắt đầu phần E |
| Genie trả lời sai | Chỉ cho Genie thấy gold + viết description/instruction kỹ (E6); demo bằng câu đã test |
| 2 người lệch API contract | Frontend chỉ code theo Swagger `/docs`, không theo trao đổi miệng |
| Số dashboard lệch số web | Gate E4 + định nghĩa metric duy nhất ở C9 |
| Phạm vi quá lớn | Cắt lần lượt review/rating, trang alerts riêng, phần làm đẹp supplier UI và giảm số chart; không cắt checkout, tồn kho, state machine, phân quyền, Bronze/Silver/Gold hoặc Genie |

### H6. Checkpoint Git và commit

Chỉ tạo checkpoint khi một thay đổi logic đã hoàn chỉnh, test liên quan đã xanh và tài liệu kỹ thuật đã đồng bộ.

- Một commit nên chứa một thay đổi logic có thể mô tả ngắn gọn; không trộn backend, frontend hoặc refactor không liên quan chỉ vì đang sửa cùng lúc.
- Commit trước khi chuyển sang task khác hoặc trước một thay đổi lớn/rủi ro để có điểm quay lại rõ ràng.
- Không commit code đang biết là lỗi hoặc test đang đỏ, trừ khi cả nhóm chủ động tạo checkpoint `WIP`.
- Agent phải nhắc người làm code khi đã tới checkpoint phù hợp, nhưng không tự chạy `git commit` nếu chưa được yêu cầu rõ ràng.
- Trước khi đề xuất commit, phải xem lại diff để phát hiện file ngoài scope, secret, file build hoặc thay đổi tài liệu bị thiếu.
- Commit message viết bằng **tiếng Việt**, ngắn gọn, dạng mệnh lệnh và mô tả kết quả chính.

Ví dụ:

```text
Khởi tạo môi trường phát triển bằng Docker
Thêm mô hình dữ liệu người dùng và cửa hàng
Hoàn thiện luồng checkout và trừ tồn kho
Đồng bộ tài liệu API quản lý đơn hàng
```

---

## PHẦN I — TÀI LIỆU HỆ THỐNG

Mục tiêu của thư mục `docs/` là giúp thành viên mới, người review và người tiếp tục phát triển có thể hiểu hệ thống mà không cần suy đoán từ source code. Tài liệu phải phản ánh rõ nội dung nào đã triển khai và nội dung nào mới ở trạng thái kế hoạch.

### I1. Cấu trúc tài liệu

```text
docs/
├── README.md             # Mục lục, trạng thái và thứ tự đọc
├── PROPOSAL.md           # Mục tiêu, phạm vi đề tài
├── PLANNING.md           # Đặc tả và kế hoạch triển khai
├── ARCHITECTURE.md       # Kiến trúc tổng thể và ranh giới các thành phần
├── DATABASE.md           # Schema, quan hệ, constraint và migration
├── BUSINESS_RULES.md     # Luồng nghiệp vụ và invariant
├── API.md                # Endpoint, role, request/response và error contract
├── DATA_PLATFORM.md      # Lakebase, Bronze/Silver/Gold, metric và data quality
├── DEVELOPMENT.md        # Setup, lệnh chạy và workflow phát triển
└── TESTING.md            # Chiến lược test, fixture và cách chạy test
```

Không tạo hàng loạt file rỗng. Tạo tài liệu tương ứng khi phần hệ thống bắt đầu được triển khai và thêm file đó vào `docs/README.md`.

### I2. Phân loại và source of truth

- `PROPOSAL.md`: mục tiêu và phạm vi cấp đề tài.
- `PLANNING.md`: đặc tả dự kiến, thứ tự thực hiện và các quyết định đã được duyệt.
- Tài liệu kỹ thuật còn lại: trạng thái **đã triển khai thực tế** của hệ thống.
- Nếu tính năng chưa hoàn thành, ghi rõ `Planned`, `In progress` hoặc `Implemented`; không mô tả kế hoạch như chức năng đã chạy.
- Mỗi thông tin chỉ có một nơi làm source of truth. Các file khác dùng link tham chiếu thay vì copy nguyên khối nội dung.
- Thay đổi proposal, planning, kiến trúc hoặc business rule phải được thống nhất trước. Tài liệu kỹ thuật có thể cập nhật cùng task để phản ánh code đã được duyệt.

### I3. Tài liệu phải cập nhật theo từng loại task

| Khi thay đổi | Tài liệu cần kiểm tra/cập nhật |
|---|---|
| Cấu trúc service, component hoặc luồng tích hợp | `ARCHITECTURE.md` |
| Model, bảng, cột, constraint hoặc migration | `DATABASE.md` |
| Checkout, trạng thái đơn, tồn kho, nhập hàng, phân quyền | `BUSINESS_RULES.md` |
| Endpoint, schema, status code hoặc error payload | `API.md` |
| Pipeline, metric, Gold table, dashboard hoặc Genie | `DATA_PLATFORM.md` |
| Dependency, biến môi trường, Docker hoặc lệnh chạy | `DEVELOPMENT.md` |
| Test strategy, fixture hoặc lệnh test | `TESTING.md` |

### I4. Definition of Done cho documentation

Một task chỉ được coi là hoàn chỉnh khi:

1. Code và test liên quan đã hoàn thành.
2. Tài liệu kỹ thuật bị ảnh hưởng đã được cập nhật trong cùng task.
3. `docs/README.md` vẫn trỏ đúng tới các tài liệu hiện có và ghi đúng trạng thái.
4. Không có nội dung mâu thuẫn với `PROPOSAL.md` hoặc `PLANNING.md`.
5. Diff không chứa tài liệu suy đoán về chức năng chưa được duyệt.
