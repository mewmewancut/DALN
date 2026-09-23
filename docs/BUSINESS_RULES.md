# Business rules

**Trạng thái:** In progress
**Phạm vi:** Toàn bộ backend Planning C3–C10 (giỏ hàng, checkout, state machine đơn hàng, tồn kho/cảnh báo hết hàng, supplier/nhập hàng, review, số liệu thống kê shop và admin) đã triển khai.

## Giỏ hàng C3

- Mỗi buyer có tối đa một giỏ. Giỏ không có item có `shop_id=NULL`; giỏ có item chỉ chứa variant thuộc cùng một shop.
- Thêm cùng variant cộng số lượng vào dòng hiện có. Sửa số lượng thay thế giá trị hiện tại. Thêm hàng khác shop trả lỗi và không tự xóa giỏ của buyer.
- Giá và thông tin sản phẩm lấy từ database hiện tại. Giỏ không giữ giá và không giữ chỗ tồn kho. Tồn kho có thể giảm sau khi thêm; kiểm tra cứng được thực hiện khi checkout theo C4.
- Mọi thao tác ghi giỏ khóa dòng buyer rồi dòng cart trong một transaction. Khóa buyer bảo vệ cả lần tạo giỏ đầu tiên khi chưa có dòng cart để khóa; các request cùng buyer được xử lý tuần tự. Lỗi nghiệp vụ hoặc database làm rollback toàn bộ thay đổi của thao tác.
- Xóa item cuối cùng hoặc xóa sạch giỏ đặt lại `shop_id=NULL`, cho phép thêm hàng của shop khác. Xóa giỏ nhiều lần không thay đổi tồn kho.
- Chỉ buyer sở hữu giỏ mới được sửa/xóa item. Thêm và đổi số lượng kiểm tra trạng thái hoạt động của variant, sản phẩm và shop, cùng tồn kho hiện tại. Các item đã ngừng bán vẫn được trả về trong giỏ để buyer có thể xóa.

Contract endpoint và mã lỗi nằm tại [`API.md`](API.md#giỏ-hàng). Test và cách chạy nằm tại [`TESTING.md`](TESTING.md).

## Checkout C4

- Checkout khóa dòng buyer rồi dòng giỏ trước khi đọc item. Mọi thao tác giỏ của cùng buyer vì vậy chạy tuần tự; hai request checkout đồng thời trên cùng một giỏ chỉ một request được tạo đơn, request còn lại nhận lỗi giỏ rỗng.
- Checkout đọc giỏ và item hiện tại của buyer; giỏ rỗng hoặc chưa tồn tại bị từ chối trong transaction và toàn bộ transaction được rollback.
- Mỗi variant, product và shop được kiểm tra lại trạng thái hoạt động dưới khóa đọc chia sẻ trong transaction checkout. Nhiều checkout vẫn có thể đọc đồng thời, nhưng thao tác ẩn catalog phải chờ transaction checkout kết thúc. Item bị ẩn sau khi thêm vào giỏ, item không còn thuộc shop của giỏ hoặc shop bị admin khóa đều trả `409`; không tạo đơn, không trừ kho và không xóa giỏ.
- Toàn bộ thao tác (tạo đơn, trừ kho từng item, ghi order item, ghi lịch sử trạng thái, xóa giỏ) nằm trong một transaction. Bất kỳ item nào lỗi làm rollback toàn bộ: không tạo đơn, không trừ kho item nào, giỏ giữ nguyên.
- Trừ kho dùng `UPDATE inventory SET quantity = quantity - :n WHERE variant_id = :id AND quantity >= :n`, không đọc rồi so sánh rồi ghi. Nếu số dòng bị ảnh hưởng bằng 0 (không đủ hàng), giao dịch rollback và trả lỗi nêu rõ sản phẩm/size/màu. Cách này chống được hai request checkout đồng thời cùng làm âm kho.
- Giá và tên sản phẩm trong `order_items` là snapshot tại thời điểm checkout, lấy bằng truy vấn variant hiện tại trong cùng transaction — không lấy từ giỏ hàng (giỏ không giữ giá) và không lấy từ payload client. Đơn đã tạo không đổi khi shop sửa giá sau đó.
- `total_amount` luôn do backend cộng dồn `unit_price × quantity` của từng order item. Trường `total_amount` không xuất hiện trong OpenAPI request contract; nếu client vẫn gửi thì backend loại bỏ trước khi validate và không dùng giá trị đó.
- Đơn mới luôn ở `status=PENDING` và có đúng một dòng `order_status_history` (`from_status=NULL → to_status=PENDING`). `payment_status=PAID` ngay khi `payment_method=MOCK_CARD`, còn `COD` giữ `UNPAID` đến khi giao hàng theo C5.
- Sau khi đơn tạo thành công, toàn bộ `cart_items` bị xóa và `cart.shop_id` đặt `NULL` trong cùng transaction — không có bước riêng có thể thất bại giữa chừng.
- Mã đơn (`code`) được gán từ một giá trị tạm duy nhất (UUID) trước, sau đó ghi đè bằng `ORD-{YYYYMMDD}-{order.id}` sau khi `id` đã có — tránh hai transaction đồng thời tranh chấp cùng một giá trị `code` trước khi mỗi đơn có `id` riêng.
- Sau khi transaction trừ kho commit thành công, backend kiểm tra `low_stock_alerts` cho từng variant vừa trừ theo C6. Bước này chạy ngoài transaction checkout nên không bao giờ làm rollback hoặc fail đơn đã đặt thành công.

Contract endpoint và mã lỗi nằm tại [`API.md`](API.md#checkout). Test và cách chạy nằm tại [`TESTING.md`](TESTING.md).

## State machine đơn hàng C5

- Tất cả thay đổi trạng thái đi qua duy nhất `transition_order()`. Hàm khóa dòng order bằng `SELECT ... FOR UPDATE`, nên buyer hủy và shop xác nhận đồng thời không thể cùng áp dụng trên trạng thái `PENDING` ban đầu.
- Chuỗi hợp lệ là `PENDING → CONFIRMED → PREPARING → SHIPPING → DELIVERED`. Shop có thể hủy từ `PENDING` hoặc `CONFIRMED`; buyer chỉ được hủy đơn của mình khi còn `PENDING`. `DELIVERED` và `CANCELLED` là trạng thái cuối.
- Buyer chỉ đọc đơn có `buyer_id` của mình. Shop owner chỉ đọc và sửa đơn có `shop_id` lấy từ shop của user trong database; không dùng `shop_id` từ token hoặc request. Admin chỉ có quyền đọc chi tiết trong phạm vi C5.
- Mỗi transition cập nhật order và thêm đúng một dòng `order_status_history` trong cùng transaction. Lỗi quyền, transition, hoàn kho hoặc commit rollback toàn bộ.
- Hủy đơn cộng lại số lượng từ snapshot `order_items`, đặt `cancelled_at` và `cancel_reason`. Vì order bị khóa và `CANCELLED` là trạng thái cuối, gọi hủy lại không cộng kho lần hai.
- Khi chuyển sang `DELIVERED`, backend đặt `delivered_at`; đơn COD chuyển sang `payment_status=PAID` trong cùng transaction.
- Sau khi transaction hủy đơn commit thành công, backend gọi `resolve_alerts_if_ok` (C6) cho từng variant vừa được hoàn kho, ngoài transaction hủy đơn.

Contract endpoint và response nằm tại [`API.md`](API.md#đơn-hàng-và-state-machine). Test F3 và concurrency nằm tại [`TESTING.md`](TESTING.md).

## Tồn kho và cảnh báo hết hàng C6

- `check_low_stock(variant_id)` chỉ được gọi ngay sau khi một transaction trừ kho (checkout C4) đã commit thành công, không nằm trong transaction đó. ⚠️ Hàm này (và `resolve_alerts_if_ok`) tự bọc toàn bộ logic trong `try/except Exception` và không bao giờ raise ra ngoài — nếu việc ghi cảnh báo lỗi (kể cả lỗi không lường trước), backend chỉ log lại chứ tuyệt đối không trả lỗi cho request đã hoàn tất thành công (checkout/hủy đơn/nhận hàng).
- Sinh cảnh báo mới chỉ khi `quantity < low_stock_threshold` **và** variant đó chưa có cảnh báo nào với `is_resolved=false`. Nhờ vậy nhiều lần checkout liên tiếp đưa tồn kho xuống dưới ngưỡng chỉ tạo đúng một cảnh báo đang mở cho mỗi variant. ⚠️ Kiểm tra "đã có cảnh báo chưa" ở service là đọc-rồi-ghi nên hai checkout đồng thời trên cùng variant vẫn có thể cùng vượt qua bước kiểm tra; **chốt chặn thật sự** là partial unique index `uq_low_stock_alerts_open_variant` ở DB (xem [`DATABASE.md`](DATABASE.md#low_stock_alerts)) — request thua race nhận `IntegrityError`, được bắt và bỏ qua như một no-op an toàn.
- `resolve_alerts_if_ok(variant_id)` chỉ được gọi ngay sau khi một transaction cộng kho (hủy đơn C5; nhận hàng C7) đã commit thành công. Khi `quantity >= low_stock_threshold`, mọi cảnh báo `is_resolved=false` của variant đó được đặt `is_resolved=true`.
- Cả bước tạo và giải quyết cảnh báo đều khóa dòng inventory bằng `SELECT ... FOR UPDATE`. Vì checkout/hủy đơn/nhận hàng cũng cập nhật chính dòng này, quyết định alert được tuần tự hóa với thay đổi tồn kho và không thể tạo alert lỗi thời hoặc resolve alert mới trong một race ngược chiều.
- Đổi `low_stock_threshold` chỉ tính lại cờ `is_low` khi đọc (`quantity < low_stock_threshold`); không tự tạo hoặc tự giải quyết cảnh báo tại thời điểm đổi ngưỡng.
- Mọi endpoint tồn kho/cảnh báo lấy `shop_id` từ `get_current_shop()` (SHOP_OWNER đã đăng nhập); sửa hoặc đọc variant thuộc shop khác trả `403`.

Contract endpoint nằm tại [`API.md`](API.md#tồn-kho-và-cảnh-báo-hết-hàng). Test F4-28, F4-29 và test hoàn kho kèm giải quyết cảnh báo nằm tại [`TESTING.md`](TESTING.md).

## Supplier và nhập hàng C7

- Supplier thuộc về đúng một shop. CRUD supplier lấy `shop_id` từ `get_current_shop()`; sửa/xóa supplier của shop khác trả `403`. Xóa là soft delete (`is_active=false`); phiếu nhập cũ vẫn tham chiếu supplier đã ẩn nhưng không được tạo phiếu nhập mới bằng supplier đó.
- Tạo phiếu nhập kiểm tra `supplier_id` thuộc shop hiện tại (tái sử dụng `supplier_service.get_owned_supplier_or_403`) và mọi `variant_id` trong `items` thuộc shop hiện tại (qua dòng `inventory` của variant) trước khi ghi, không tạo phiếu nếu sai. Theo đúng quy ước 404-vs-403 dùng chung toàn backend: `supplier_id`/`variant_id` không tồn tại trả `404`; tồn tại nhưng thuộc shop khác trả `403` — hai trường hợp này không được gộp chung một mã lỗi. `items` không được trùng `variant_id` (chặn ở schema, có `UNIQUE(purchase_order_id, variant_id)` ở DB làm chốt cuối).
- Tất cả thay đổi trạng thái phiếu nhập đi qua duy nhất `transition_purchase_order()`, khóa dòng bằng `SELECT ... FOR UPDATE` giống `transition_order()` ở C5. Chuỗi hợp lệ là `DRAFT → ORDERED → RECEIVED`; `DRAFT` hoặc `ORDERED` có thể chuyển sang `CANCELLED`. `RECEIVED` và `CANCELLED` là trạng thái cuối, không có transition nào đi tiếp từ đó.
- ⚠️ Chỉ khi chuyển đúng `ORDERED → RECEIVED` mới cộng kho, dùng `UPDATE inventory SET quantity = quantity + item.quantity` cho từng item trong cùng transaction với đổi `status` và đặt `received_at`. Vì `RECEIVED` là trạng thái cuối và transition được kiểm tra bảng chuyển hợp lệ, một phiếu không thể được nhận 2 lần nên không thể cộng kho 2 lần.
- Sau khi transaction nhận hàng commit thành công, backend gọi `resolve_alerts_if_ok` (C6) cho từng variant vừa được cộng kho, ngoài transaction nhận hàng — cùng nguyên tắc với hủy đơn ở C5.
- Đọc/sửa phiếu nhập của shop khác trả `403`; ID không tồn tại trả `404`; chuyển sai trạng thái trả `400`.

Contract endpoint nằm tại [`API.md`](API.md#nhà-cung-cấp) và [`API.md`](API.md#nhập-hàng). Test F4-25, F4-26, F4-27 nằm tại [`TESTING.md`](TESTING.md).

## Review C8

- Thứ tự kiểm tra khi tạo review, đúng theo Planning: order item tồn tại (`404`) → đơn của order item thuộc buyer hiện tại (`403`) → đơn ở trạng thái `DELIVERED` (`400`) → order item chưa có review (`400`). `reviews.order_item_id` có `UNIQUE` ở database (B13) làm chốt chặn cuối cùng nếu code kiểm tra sót, tránh race hai request review cùng lúc tạo hai dòng.
- `product_id` của review lấy từ `order_item.variant.product_id` trong database, không nhận từ payload — buyer không thể tự gán review cho sản phẩm khác.
- Rating trung bình sản phẩm không phải cột lưu sẵn; cả `GET /products/{id}` (C2) và `GET /products/{id}/reviews` (C8) đều tính trực tiếp bằng `AVG(rating)` trên bảng `reviews` tại thời điểm đọc, nên luôn nhất quán và tự động cập nhật ngay sau khi có review mới.
- `GET /products/{id}/reviews` là endpoint public, không lọc theo trạng thái `is_active` của sản phẩm/shop (khác với catalog listing C2) vì review vẫn cần xem được từ trang chi tiết đơn hàng cũ; sản phẩm không tồn tại trả `404`.

Contract endpoint nằm tại [`API.md`](API.md#review). Test F5-31–34 nằm tại [`TESTING.md`](TESTING.md).

## Số liệu thống kê shop C9

- 📌 Định nghĩa metric ở Planning C9 là nguồn duy nhất, dùng chung cho endpoint này, Gold layer, Dashboard và Genie khi triển khai (E3, E5, E6) — sai lệch giữa các nơi là lỗi nặng nhất khi demo nên không được tự định nghĩa lại ở bất kỳ nơi nào khác.
- **Doanh thu** tính theo ngày `delivered_at` **quy đổi sang giờ Việt Nam** (`Asia/Ho_Chi_Minh`, UTC+7), chỉ tính đơn `DELIVERED`. Ví dụ đơn giao lúc `2026-01-01T20:00:00Z` (03:00 giờ VN ngày 02/01) được tính vào doanh thu ngày `2026-01-02`, không phải `2026-01-01`.
- **Số đơn** và **số đơn hủy** đếm theo `created_at` quy đổi sang giờ Việt Nam, không lọc theo trạng thái (số đơn) hoặc chỉ đếm `CANCELLED` (số đơn hủy). Đây là lần chuyển đổi giờ VN thứ hai, tách biệt với cột dùng cho doanh thu vì hai metric dùng hai mốc thời gian khác nhau (`delivered_at` vs `created_at`) theo đúng Planning.
- **Tỷ lệ hủy** = số đơn hủy / số đơn; trả `null` khi số đơn trong kỳ bằng 0, không chia cho 0.
- **AOV** = doanh thu / số đơn `DELIVERED` dùng để tính doanh thu (cùng kỳ, cùng điều kiện lọc); trả `null` khi không có đơn `DELIVERED` nào.
- `revenue-by-day` nhóm theo cùng cột ngày VN của `delivered_at` như doanh thu ở overview, để hai số liệu luôn khớp nhau khi vẽ chung một dashboard.
- `top-products` cộng dồn theo `product_id` hiện tại (join từ `order_items.variant_id` qua `product_variants.product_id`), không theo `product_name` snapshot trong `order_items` — sản phẩm đổi tên vẫn gộp đúng một dòng.
- Mọi truy vấn ở C9 đều có điều kiện `shop_id = current_shop.id`; không có tham số `shop_id` nào được nhận từ client.

Contract endpoint nằm tại [`API.md`](API.md#số-liệu-thống-kê-shop). Test F1-8 (số liệu chỉ ra đúng shop hiện tại) nằm tại [`TESTING.md`](TESTING.md).

## Admin C10

- Mọi endpoint admin đi qua `require_role('ADMIN')`; không có nghiệp vụ nào tự kiểm tra quyền riêng ngoài dependency chung ở `deps.py`.
- Khóa tài khoản (`is_active=false`) chặn đăng nhập và mọi request xác thực tiếp theo (theo `get_current_user` đã có từ C0/C1) — vì vậy backend chặn riêng trường hợp admin tự đặt `is_active=false` cho chính `user_id` của mình (`400`), tránh admin tự khóa mất quyền truy cập của chính phiên đang dùng. Tự mở lại (`is_active=true`) cho chính mình không bị chặn vì không gây khóa quyền truy cập.
- Khóa shop (`is_active=false`) không xóa hay sửa dữ liệu sản phẩm/đơn hàng liên quan; nó chỉ khiến điều kiện `Shop.is_active` sẵn có ở catalog công khai (C2) loại sản phẩm của shop đó khỏi `GET /products`/`GET /products/{id}`. Đơn hàng cũ của shop bị khóa vẫn giữ nguyên và vẫn xem được qua các endpoint đơn hàng hiện có.
- `GET /admin/orders` và `GET /admin/stats/overview` tái sử dụng đúng logic truy vấn của C5 (`order_service.list_all_orders`) và C9 (`shop_stats_service.get_overview`) thay vì viết lại, chỉ khác là không ràng buộc `shop_id`; nhờ vậy định nghĩa metric và cấu trúc response luôn khớp với C9, không có nơi thứ hai định nghĩa lại doanh thu/AOV/tỷ lệ hủy.
- Không có endpoint admin nào nhận trực tiếp bản ghi để sửa nhiều trường tùy ý; mỗi endpoint sửa đúng một cờ trạng thái (`is_active`) để tránh admin vô tình đổi dữ liệu nghiệp vụ khác (giá, tồn kho, trạng thái đơn) ngoài phạm vi quản trị.

Contract endpoint nằm tại [`API.md`](API.md#admin).
