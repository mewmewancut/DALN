# API

**Trạng thái:** In progress
**Phạm vi đã triển khai:** Planning C0–C7 (auth, shop, catalog, giỏ hàng, checkout, state machine đơn hàng, tồn kho/cảnh báo hết hàng và supplier/nhập hàng)

Swagger chạy tại `http://localhost:8000/docs`. Các endpoint nghiệp vụ từ C8 trở đi vẫn là `Planned` trong [`PLANNING.md`](PLANNING.md#phần-c--backend-từng-endpoint--pseudocode-chỗ-khó).

## Auth

| Method | Path | Quyền | Request | Response thành công |
|---|---|---|---|---|
| POST | `/auth/register` | Public | `email`, `password`, `full_name`, `role` (`BUYER` hoặc `SHOP_OWNER`) | `201` với `id`, `email`, `full_name`, `role`, `is_active` |
| POST | `/auth/login` | Public | `email`, `password` | `200` với `access_token`, `role`, `shop_id` (`null` nếu chưa có shop) |
| GET | `/auth/me` | Bearer token | — | `200` với thông tin user như response đăng ký |

Mật khẩu chỉ được lưu dưới dạng bcrypt hash và không xuất hiện trong response. Email đăng ký được chuẩn hóa về chữ thường; mật khẩu đăng ký/đăng nhập dài quá giới hạn 72 byte của bcrypt hoặc body có trường ngoài contract bị từ chối với `422`. Đăng ký email trùng hoặc role `ADMIN` trả `400`; sai thông tin đăng nhập trả `401`; tài khoản bị khóa trả `403`. Thiếu, sai hoặc hết hạn token khi gọi `/auth/me` trả `401`. Response lỗi dùng dạng `{"detail": "..."}`.

JWT được ký bằng HS256 với `JWT_SECRET`, hết hạn theo `JWT_EXPIRE_MINUTES`. Payload gồm `sub` (user ID dạng chuỗi), `role`, `shop_id` và `exp` (UTC). Các dependency luôn tải user và shop từ database khi phân quyền; giá trị `role` và `shop_id` trong token không được dùng làm nguồn xác thực quyền sở hữu. `require_role(...)` trả `403` khi sai role; `get_current_shop` trả `403` khi shop owner chưa có shop.

## Shop và catalog

| Method | Path | Quyền | Request | Response thành công |
|---|---|---|---|---|
| POST | `/shops` | SHOP_OWNER chưa có shop | `name`, `description?` | `201` với `id`, `owner_id`, `name`, `description`, `is_active` |
| PUT | `/shops/me` | SHOP_OWNER có shop | `name`, `description?` | `200` với shop đã sửa |
| GET | `/categories` | Public | — | `200` với danh sách `{id, name}` |
| POST | `/products` | SHOP_OWNER có shop | `category_id`, `name`, `description?`, `image_url?`, `base_price`, `variants` | `201` với chi tiết sản phẩm |
| PUT | `/products/{id}` | Chủ shop của sản phẩm | Các trường product cần sửa | `200` với chi tiết sản phẩm |
| DELETE | `/products/{id}` | Chủ shop của sản phẩm | — | `204`; đặt `is_active=false` |
| POST | `/products/{id}/variants` | Chủ shop của sản phẩm | `size`, `color`, `price`, `initial_quantity` | `201` với variant mới |
| PUT | `/variants/{id}` | Chủ shop của variant | `price?`, `is_active?` | `200` với variant đã sửa |
| GET | `/products` | Public | Bộ lọc và phân trang bên dưới | `200` với `{items, total, page, page_size}` |
| GET | `/products/{id}` | Public | — | `200` với chi tiết sản phẩm |

`variants` khi tạo sản phẩm là mảng không rỗng gồm `{size, color, price, initial_quantity}`. `base_price` và `price` là số nguyên VND không âm; `initial_quantity` không âm. Backend tự lấy shop từ người dùng đã đăng nhập, sinh SKU `P{product_id}-{size}-{color}` và tạo product, variants, inventory trong một transaction. Dấu `%` và `-` trong thành phần size/color được percent-encode để các cặp khác nhau không sinh cùng SKU. Body gửi `shop_id` hoặc `owner_id` đến endpoint ghi bị từ chối. Tạo shop lần hai trả `400`; variant trùng trả `409`; sửa sản phẩm hoặc variant của shop khác trả `403`. ID không tồn tại trả `404`.

`PUT /products/{id}` nhận các trường tùy chọn `category_id`, `name`, `description`, `image_url`, `base_price`, `is_active`; chỉ các trường được gửi mới thay đổi. Đặt `is_active=false` sẽ ẩn sản phẩm, còn `true` sẽ hiện lại. `PUT /variants/{id}` chỉ đổi giá hoặc trạng thái, không đổi size/color hay tồn kho. Các endpoint ghi trả cả variant không hoạt động để chủ shop có thể quản lý; endpoint công khai chỉ trả variant hoạt động.

`GET /products` nhận `keyword` (tìm tên không phân biệt chữ hoa/thường), `category_id`, `shop_id`, `min_price`, `max_price`, `sort` (`newest`, `price_asc`, `price_desc`), `page` (mặc định 1) và `page_size` (mặc định 20, tối đa 100). Giá dùng cho lọc, sắp xếp và `price_from` là giá thấp nhất trong các variant đang hoạt động; nếu không còn variant hoạt động thì `price_from=null`. Chỉ sản phẩm hoạt động của shop hoạt động xuất hiện trong danh sách và chi tiết công khai. `items` chứa `id`, `shop_id`, `shop_name`, `category_id`, `name`, `image_url`, `base_price`, `price_from`, `rating_average`; chi tiết thêm `description`, `is_active` và `variants` (mỗi variant có `quantity` tồn kho). `rating_average=null` khi chưa có review.

## Giỏ hàng

Tất cả endpoint dưới đây yêu cầu token của `BUYER`. Thiếu/sai token trả `401`, vai trò khác trả `403`. Buyer được xác định từ phiên đăng nhập.

| Method | Path | Request | Response thành công |
|---|---|---|---|
| GET | `/cart` | — | `200`, giỏ hiện tại; buyer chưa có giỏ nhận giỏ rỗng |
| POST | `/cart/items` | `{variant_id, quantity}` | `200`, giỏ sau khi thêm/cộng dồn |
| PUT | `/cart/items/{id}` | `{quantity}` | `200`, giỏ sau khi thay số lượng |
| DELETE | `/cart/items/{id}` | — | `200`, giỏ sau khi xóa item |
| DELETE | `/cart` | — | `200`, giỏ rỗng; gọi lại vẫn thành công |

Response giỏ gồm `{shop_id, shop_name, items, total_amount}`. Mỗi item có `id` (ID cart item), `variant_id`, `product_id`, `product_name`, `image_url`, `size`, `color`, `quantity`, `unit_price` và `stock_quantity`. Giá, ảnh, tên và tồn kho lấy từ database hiện tại; `total_amount` là tổng `quantity × unit_price` của giỏ, không phải snapshot đơn hàng. Giỏ rỗng có `shop_id=null`, `shop_name=null`, `items=[]`, `total_amount=0`.

`quantity` phải là số nguyên từ 1 đến 2.147.483.647; `variant_id` là số nguyên dương. Body chứa trường ngoài schema, kể cả `buyer_id`, `shop_id` hoặc giá từ client, bị từ chối với `422`. Item không tồn tại trả `404`; sửa/xóa item của buyer khác trả `403`. Thêm hoặc sửa variant đã ẩn, sản phẩm đã ẩn hoặc shop ngừng hoạt động trả `404`; item cũ vẫn có thể được xóa khỏi giỏ. Số lượng mới vượt tồn kho trả `409` với `{"detail":"Không đủ hàng"}` và giữ nguyên giỏ.

Khi thêm hàng khác shop, response `409` có đúng dạng:

```json
{
  "detail": "CART_DIFFERENT_SHOP",
  "current_shop": { "id": 1, "name": "Shop A" }
}
```

Frontend xử lý theo Planning C3: chỉ sau khi buyer xác nhận xóa giỏ mới gọi `DELETE /cart`, rồi thêm sản phẩm lại. Quy tắc transaction và tồn kho được mô tả tại [`BUSINESS_RULES.md`](BUSINESS_RULES.md#giỏ-hàng-c3).

## Checkout

| Method | Path | Quyền | Request | Response thành công |
|---|---|---|---|---|
| POST | `/orders/checkout` | BUYER | `receiver_name`, `receiver_phone`, `shipping_address`, `payment_method` (`COD` hoặc `MOCK_CARD`) | `200` với đơn hàng vừa tạo |

Response gồm `{id, code, shop_id, status, receiver_name, receiver_phone, shipping_address, payment_method, payment_status, total_amount, items}`. `code` sinh dạng `ORD-YYYYMMDD-{id}` theo ngày UTC. `items` là snapshot lúc đặt: `{id, variant_id, product_name, size, color, unit_price, quantity}`. Đơn mới luôn ở `status=PENDING`; `payment_status=PAID` ngay nếu `payment_method=MOCK_CARD`, ngược lại `UNPAID`.

Giỏ rỗng hoặc buyer chưa có giỏ trả `400`. Nếu client gửi `total_amount`, backend bỏ trường này và vẫn tự tính tổng từ giá variant hiện tại trong database; các trường ngoài contract khác bị từ chối với `422`. Nếu bất kỳ item nào không đủ tồn kho, toàn bộ giao dịch rollback (không tạo đơn, không trừ kho item nào khác) và trả `409` với thông báo nêu rõ sản phẩm/size/màu thiếu hàng. Trừ kho dùng `UPDATE` có điều kiện nguyên tử nên hai buyer checkout đồng thời trên cùng variant chỉ một request thành công khi tồn kho chỉ đủ cho một đơn. Buyer và giỏ được khóa trước khi đọc item nên hai checkout đồng thời trên cùng giỏ không thể tạo đơn trùng. Sau khi tạo đơn thành công, giỏ hàng được xóa sạch và `cart.shop_id` đặt về `null`. Quy tắc transaction và tồn kho được mô tả tại [`BUSINESS_RULES.md`](BUSINESS_RULES.md#checkout-c4).

## Đơn hàng và state machine

| Method | Path | Quyền | Ghi chú |
|---|---|---|---|
| GET | `/orders/my` | BUYER | Danh sách đơn của buyer hiện tại; filter `status`, phân trang bằng `page`, `page_size` |
| GET | `/orders/{id}` | BUYER/SHOP_OWNER/ADMIN | Buyer chỉ xem đơn của mình; shop chỉ xem đơn thuộc shop lấy từ database; admin xem mọi đơn |
| GET | `/shop/orders` | SHOP_OWNER | Danh sách đơn thuộc shop hiện tại; filter `status`, phân trang |
| PATCH | `/orders/{id}/status` | SHOP_OWNER | Body `{status, note?}`; chuyển trạng thái qua state machine |
| POST | `/orders/{id}/cancel` | BUYER | Body `{reason}`; chỉ hủy đơn `PENDING` của chính buyer |

Danh sách trả `{items, total, page, page_size}`; mỗi item có ID, code, buyer/shop, trạng thái, thanh toán, tổng tiền và thời gian tạo. Chi tiết trả thêm thông tin nhận hàng, item snapshot, thời điểm giao/hủy, lý do hủy và `status_history` theo thứ tự phát sinh.

Các chuyển trạng thái hợp lệ là `PENDING → CONFIRMED → PREPARING → SHIPPING → DELIVERED`; shop có thể chuyển `PENDING` hoặc `CONFIRMED` sang `CANCELLED`. Buyer chỉ có thể hủy từ `PENDING`. Chuyển sai trả `400`; đọc hoặc sửa đơn của tài khoản/shop khác trả `403`; ID không tồn tại trả `404`.

Mọi chuyển trạng thái khóa dòng đơn và ghi `order_status_history` trong cùng transaction. Hủy đơn hoàn lại tồn kho đúng một lần, đặt `cancelled_at` và `cancel_reason`. Giao thành công đặt `delivered_at`; đơn COD được chuyển `payment_status=PAID`. Hai thao tác đồng thời trên cùng đơn được tuần tự hóa, nên chỉ một transition từ trạng thái ban đầu có thể thành công.

## Tồn kho và cảnh báo hết hàng

Tất cả endpoint dưới đây yêu cầu token `SHOP_OWNER` và chỉ thao tác trên tồn kho của shop hiện tại (lấy từ database, không nhận `shop_id` từ client).

| Method | Path | Request | Response thành công |
|---|---|---|---|
| GET | `/shop/inventory` | — | `200` với danh sách tồn kho mọi variant của shop |
| PUT | `/shop/inventory/{variant_id}/threshold` | `{low_stock_threshold}` | `200` với dòng tồn kho đã cập nhật ngưỡng |
| GET | `/shop/alerts` | — | `200` với danh sách cảnh báo `is_resolved=false` của shop |

Mỗi dòng tồn kho gồm `{variant_id, product_id, product_name, size, color, sku, quantity, low_stock_threshold, is_low}`; `is_low = quantity < low_stock_threshold`. `low_stock_threshold` khi sửa phải là số nguyên không âm, sai kiểu hoặc âm trả `422`. Variant không tồn tại trả `404`; variant thuộc shop khác trả `403`.

Mỗi cảnh báo gồm `{id, variant_id, product_name, size, color, quantity_at_alert, is_resolved, created_at}`, chỉ trả các cảnh báo chưa được giải quyết. Cảnh báo được tạo tự động ngay sau khi checkout trừ kho xuống dưới ngưỡng (không tạo cảnh báo trùng nếu đã có cảnh báo chưa giải quyết cho variant đó) và được đánh dấu `is_resolved=true` tự động khi tồn kho được cộng trở lại từ mức ngưỡng trở lên (hủy đơn hoàn kho; nhận hàng nhập kho theo C7). Quy tắc chi tiết tại [`BUSINESS_RULES.md`](BUSINESS_RULES.md#tồn-kho-và-cảnh-báo-hết-hàng-c6).

## Nhà cung cấp

Tất cả endpoint dưới đây yêu cầu token `SHOP_OWNER` và chỉ thao tác trên nhà cung cấp của shop hiện tại.

| Method | Path | Request | Response thành công |
|---|---|---|---|
| GET | `/shop/suppliers` | — | `200` với danh sách nhà cung cấp của shop, kể cả đã ẩn |
| POST | `/shop/suppliers` | `name`, `phone?`, `address?` | `201` với nhà cung cấp mới |
| PUT | `/shop/suppliers/{id}` | Các trường tùy chọn cần sửa | `200` với nhà cung cấp đã sửa |
| DELETE | `/shop/suppliers/{id}` | — | `204`; đặt `is_active=false` |

Mỗi nhà cung cấp gồm `{id, name, phone, address, is_active}`. Sửa `name=null` trả `400`; sửa hoặc xóa nhà cung cấp của shop khác trả `403`; ID không tồn tại trả `404`. Xóa là soft delete, phiếu nhập cũ vẫn tham chiếu được nhà cung cấp.

## Nhập hàng

Tất cả endpoint dưới đây yêu cầu token `SHOP_OWNER` và chỉ thao tác trên phiếu nhập của shop hiện tại.

| Method | Path | Request | Response thành công |
|---|---|---|---|
| POST | `/shop/purchase-orders` | `supplier_id`, `note?`, `items: [{variant_id, quantity, unit_cost}]` | `201` với phiếu nhập mới ở trạng thái `DRAFT` |
| GET | `/shop/purchase-orders` | Filter `status`, phân trang `page`, `page_size` | `200` với `{items, total, page, page_size}` |
| PATCH | `/shop/purchase-orders/{id}/status` | `{status}` | `200` với phiếu nhập sau khi chuyển trạng thái |

`items` không được rỗng và không được trùng `variant_id` trong cùng request (`422` nếu vi phạm). Mọi `variant_id` phải thuộc shop hiện tại và `supplier_id` phải là nhà cung cấp của shop hiện tại, sai một trong hai trả `403`. Phiếu nhập trả `{id, shop_id, supplier_id, status, note, received_at, created_at, items}`; mỗi item có `{id, variant_id, quantity, unit_cost}`.

Chuyển trạng thái hợp lệ là `DRAFT → ORDERED → RECEIVED`; `DRAFT` hoặc `ORDERED` có thể chuyển sang `CANCELLED`. `RECEIVED` và `CANCELLED` là trạng thái cuối. Chỉ khi chuyển sang `RECEIVED` mới cộng kho cho từng variant trong phiếu và đặt `received_at`; vì đây là trạng thái cuối nên gọi lại không cộng kho lần hai. Sau khi cộng kho và commit, backend tự động giải quyết cảnh báo tồn kho thấp cho các variant vừa nhập theo C6. Chuyển sai trạng thái trả `400`; phiếu của shop khác trả `403`; ID không tồn tại trả `404`. Quy tắc chi tiết tại [`BUSINESS_RULES.md`](BUSINESS_RULES.md#supplier-và-nhập-hàng-c7).
