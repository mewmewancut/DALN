# Testing

**Trạng thái:** In progress  
**Phạm vi hiện tại:** health check, database constraints B1–B14, seed data B15 và toàn bộ backend C0–C10 (auth, catalog, giỏ hàng, checkout, state machine đơn hàng, tồn kho/cảnh báo hết hàng, supplier/nhập hàng, review, số liệu thống kê shop, admin) cùng luồng API từ đăng ký đến đăng sản phẩm

Frontend D1–D2 có test gắn token, xử lý `401`, điều hướng theo vai trò, form auth, catalog và toàn bộ luồng buyer từ giỏ hàng tới review.

## Các lớp kiểm tra hiện có

| Lớp | Công cụ | Phạm vi đang chạy |
|---|---|---|
| Database | pytest + PostgreSQL test | Constraint, giá trị mặc định, timestamp, seed chạy lại không nhân đôi |
| API và phân quyền | pytest + FastAPI TestClient | Auth, shop, catalog, giỏ hàng, đơn hàng, lỗi nghiệp vụ, quyền sở hữu và rollback |
| Đồng thời giỏ hàng | pytest + PostgreSQL, hai session/thread | Lần thêm đầu tiên cùng variant hoặc khác shop bảo toàn một giỏ/một shop, không mất số lượng |
| Đồng thời checkout | pytest + PostgreSQL, hai session/thread | Hai buyer checkout cùng variant chỉ đủ cho một đơn không làm âm kho; hai request trên cùng giỏ không tạo hai đơn |
| Đồng thời state machine | pytest + PostgreSQL, hai session/thread | Buyer hủy và shop xác nhận cùng đơn: đúng một transition thành công, tồn kho khớp trạng thái cuối |
| Đồng thời cảnh báo tồn kho | pytest + PostgreSQL, hai session/thread | Tạo alert không trùng; resolve alert và trừ kho đồng thời được tuần tự hóa theo dòng inventory, trạng thái alert khớp tồn kho cuối |
| Luồng API | pytest + FastAPI TestClient | Đăng ký chủ shop → đăng nhập → tạo shop → đăng sản phẩm → buyer xem catalog; category được tạo trong fixture vì API admin chưa có |
| Frontend | Vitest + jsdom | Axios token/`401`, route theo vai trò, auth/catalog, đổi shop trong giỏ, sửa/xóa giỏ, checkout, lọc/hủy đơn và review |
| Migration và cấu hình | Alembic + Docker Compose | Áp dụng migration và kiểm tra model khớp schema; kiểm tra Compose |
| Lint và format | Ruff + ESLint + Prettier | Lỗi Python/JavaScript, import, React Hooks và định dạng; test cấu hình xác nhận code sai bị từ chối |
| Runtime và dependency | HTTP smoke + Vite build + npm audit | Health backend, frontend phục vụ trang, build và lỗ hổng mức moderate trở lên |

Browser end-to-end cho luồng mua hàng và kiểm tra Bronze/Silver/Gold của F6–F7 vẫn là **Planned** vì các module đó chưa triển khai. Test luồng API hiện tại chạy với database test và rollback sau test; nó không thay thế browser end-to-end.

## Nguyên tắc

- Mỗi hành vi mới hoặc thay đổi hành vi (API, service, model/constraint, component/route frontend, script, cấu hình) phải có test mới hoặc test được cập nhật trong cùng task và commit. Test phải kiểm tra kết quả quan sát được cùng các nhánh lỗi, phân quyền, biên và invariant liên quan; chỉ chạy lại test cũ không tính là đã cover phần mới.
- Thay đổi chỉ về tài liệu phải có lệnh kiểm tra phù hợp, tối thiểu là kiểm tra diff. Chỉ coi task hoàn thành khi test và kiểm tra liên quan đều pass.
- Backend test dùng PostgreSQL `fashion_test`, tách khỏi database development `fashion`.
- Các test thông thường dùng transaction riêng và rollback sau test. Hai ca giỏ hàng đồng thời tạo schema riêng trong database test để dùng commit thật giữa các session; schema được xóa trong `finally`. Không tạo dữ liệu này trong database development.
- Constraint quan trọng phải được kiểm tra ở database, không chỉ kiểm tra bằng Python.
- Không bỏ qua, làm yếu hoặc xóa test đang fail để làm suite xanh.

## Cách chạy

```powershell
docker compose --env-file .env.example up -d db backend frontend
docker compose --env-file .env.example exec -T backend pytest -q
docker compose --env-file .env.example exec -T frontend npm test
```

## Hook pre-commit

Hook được lưu trong `.githooks/pre-commit`. Kích hoạt một lần cho mỗi clone:

```powershell
git config core.hooksPath .githooks
```

Mỗi lần `git commit`, hook build/khởi động Docker Compose, chạy Ruff lint/format, đồng bộ npm theo lockfile, chạy ESLint/Prettier, áp dụng và kiểm tra migration, chạy toàn bộ pytest và Vitest, build frontend, audit dependency và smoke test hai service. Bất kỳ lệnh nào thất bại sẽ chặn commit. Lint/format chỉ kiểm tra, không tự sửa file. Có thể chạy lại thủ công bằng `git hook run pre-commit`. Docker Desktop cần chạy; cài dependency và audit cần truy cập registry. Hook kiểm tra working tree đang có trên máy, nên trước khi commit từng phần cần bảo đảm code được test khớp phần đã stage. Lệnh lint/format thủ công và phạm vi cấu hình nằm trong [`DEVELOPMENT.md`](DEVELOPMENT.md#chuẩn-hóa-code).

`backend/app/tests/test_code_quality.py` và `frontend/quality.test.js` chạy CLI thật trên đoạn code qua stdin: code hợp lệ được chấp nhận, biến/import lỗi, JSX chưa khai báo, hook có điều kiện và dependency effect thiếu bị từ chối. Test format xác nhận code chưa chuẩn trả exit code 1 và output sau format pass. Các probe không tạo file lỗi trong source tree.

## Test đã có

- FastAPI health endpoint trả `200` và payload `{"status": "ok"}`.
- User role chỉ nhận `BUYER`, `SHOP_OWNER`, `ADMIN`.
- Email user và tên category là duy nhất.
- Một user sở hữu tối đa một shop.
- Giá cơ sở của product không âm.
- SKU và bộ `(product_id, size, color)` của variant là duy nhất.
- Tồn kho không âm và mỗi variant có tối đa một dòng inventory.
- Các giá trị mặc định và timestamp có timezone được tạo đúng.
- Trạng thái phiếu nhập hợp lệ, số lượng nhập dương và variant không bị lặp trong một phiếu nhập.
- Mỗi buyer chỉ có một giỏ; giỏ rỗng cho phép `shop_id=NULL`; số lượng và variant trong giỏ được ràng buộc.
- Mã đơn là duy nhất; trạng thái đơn và thanh toán chỉ nhận giá trị hợp lệ.
- Order item lưu snapshot và có số lượng dương; lịch sử đầu tiên cho phép `from_status=NULL`.
- Rating nằm trong khoảng 1–5 và mỗi order item chỉ có một review.
- Low-stock alert mặc định ở trạng thái chưa xử lý.
- Seed tạo đủ tài khoản, shop, catalog, tồn kho, supplier và đơn hàng; mật khẩu admin kiểm tra được bằng bcrypt.
- Chạy seed lần hai không làm thay đổi số lượng bản ghi.
- SKU của seed khớp `P{product_id}-{size}-{color}` và chạy lại với mốc ngày khác vẫn không nhân đôi đơn hàng.
- Các bảng có luồng cập nhật nhận `updated_at` có timezone.
- Auth: đăng ký thành công, chuẩn hóa email về chữ thường, email trùng, cấm role ADMIN, từ chối mật khẩu quá 72 byte và trường ngoài contract; login đúng/sai mật khẩu; JWT chứa user ID, role và shop ID; `/auth/me` không lộ password hash.
- Thiếu, sai, hết hạn token hoặc user bị khóa đều bị từ chối; dependency role và shop lấy quyền sở hữu từ database thay vì tin `shop_id` trong token.
- API shop chỉ cho SHOP_OWNER tạo và sửa shop của mình; từ chối `owner_id` do client gửi và không cho tạo shop thứ hai.
- Tạo sản phẩm cùng variant và inventory trong một transaction; variant trùng làm rollback toàn bộ; `shop_id` do client gửi bị từ chối.
- SKU do catalog service sinh không va chạm khi size/color chứa dấu gạch ngang, dấu phần trăm hoặc dấu gạch dưới.
- Shop khác không được sửa, ẩn sản phẩm hoặc quản lý variant; xóa sản phẩm là soft delete và có thể hiện lại qua `PUT`.
- Catalog công khai lọc, sắp xếp, phân trang theo giá variant hoạt động; ẩn sản phẩm và shop không hoạt động; chi tiết có tồn kho và rating trung bình. Danh sách quản lý shop chỉ trả sản phẩm thuộc shop hiện tại nhưng giữ cả product/variant đã ẩn, hỗ trợ lọc và phân trang; buyer/khách không gọi được.
- Luồng API nối đăng ký, đăng nhập, tạo shop, tạo sản phẩm, catalog công khai, chặn buyer sửa sản phẩm và soft delete.
- Frontend gửi đúng body login/register, điều hướng sau auth, hiển thị lỗi API và giữ lỗi `401` của login trên form.
- Frontend gọi lại catalog với query params khi đổi bộ lọc hoặc trang, về trang 1 khi đổi filter, hiển thị trạng thái rỗng/lỗi và giá từ API.
- Chi tiết sản phẩm hiển thị giá/tồn kho đúng variant được chọn, xóa size khi đổi màu và báo lỗi sản phẩm không tồn tại.
- Frontend thêm đúng `variant_id` vào giỏ; khi nhận `CART_DIFFERENT_SHOP` chỉ gọi xóa giỏ và thêm lại sau khi buyer xác nhận. Trang giỏ chặn số lượng vượt `stock_quantity`, gửi đúng body cập nhật, xóa item và cập nhật tổng tiền/trạng thái rỗng từ response API.
- Frontend checkout gửi thông tin người nhận cùng phương thức thanh toán, giữ nguyên thông báo `409` thiếu hàng trên form và chuyển tới chi tiết đơn sau khi thành công. Danh sách đơn gửi filter trạng thái, chỉ hiện thao tác hủy cho `PENDING` và gửi lý do hủy.
- Chi tiết đơn hiển thị item snapshot, tổng tiền, giao hàng và lịch sử trạng thái; nút đánh giá chỉ hiện cho item `DELIVERED` có `review_id=null`, gửi rating/comment đúng contract và đổi ngay sang trạng thái đã đánh giá sau response thành công.
- Giỏ hàng C3/F2-10–11: xem giỏ rỗng, cộng dồn variant, chặn khác shop đúng error payload, giá/tồn kho hiện tại, sửa/xóa item và đặt lại shop khi giỏ rỗng.
- Giỏ hàng từ chối số lượng không hợp lệ, tài nguyên thiếu/ẩn, quyền truy cập của shop owner hoặc buyer khác và dữ liệu giá/shop/buyer do client gửi. Lỗi vượt tồn và lỗi commit đều giữ nguyên giỏ; test hai session kiểm tra các request thêm đồng thời.
- Checkout C4/F2-12–17: giỏ rỗng trả `400`; checkout hợp lệ trừ đúng kho, xóa giỏ và ghi đúng một dòng lịch sử trạng thái; thiếu tồn kho rollback toàn bộ (không tạo đơn, không trừ kho, giỏ giữ nguyên); từ chối và rollback nếu variant/product bị ẩn hoặc shop bị khóa sau khi item đã vào giỏ; giá trong đơn giữ nguyên sau khi shop đổi giá; `total_amount` client gửi bị bỏ qua và tổng luôn tính từ giá database; test hai session xác nhận hai buyer checkout đồng thời trên cùng variant chỉ một đơn thành công khi kho chỉ đủ một đơn, đồng thời hai request trên cùng giỏ chỉ tạo đúng một đơn.
- State machine C5/F3-18–24: chuỗi giao hàng đầy đủ ghi đủ history và thanh toán COD; chặn nhảy cóc/hủy sai trạng thái; buyer/shop chỉ truy cập đúng đơn; hủy hoàn kho đúng một lần; lỗi commit rollback trạng thái, history và tồn kho; race buyer hủy với shop xác nhận chỉ áp dụng một transition.
- Tồn kho/cảnh báo C6/F4-28–29: danh sách tồn kho chỉ trả variant của shop hiện tại kèm cờ `is_low`; sửa ngưỡng tính lại `is_low`, từ chối shop khác (`403`), variant không tồn tại (`404`) và ngưỡng âm (`422`); checkout đưa tồn kho xuống dưới ngưỡng sinh đúng một cảnh báo, checkout tiếp theo vẫn dưới ngưỡng không sinh cảnh báo thứ hai; hủy đơn hoàn kho lên trên ngưỡng tự động giải quyết cảnh báo đang mở; `check_low_stock`/`resolve_alerts_if_ok` không bao giờ raise ra ngoài kể cả khi `commit()` lỗi (test ép lỗi bằng monkeypatch); test hai session gọi đồng thời `check_low_stock` trên cùng variant xác nhận partial unique index chặn tạo trùng; test resolve alert đồng thời với trừ kho xác nhận row lock chặn quyết định từ số lượng cũ và giữ đúng một alert mở khi tồn kho cuối dưới ngưỡng.
- Supplier C7: CRUD giới hạn theo shop hiện tại; sửa tên rỗng (`null`) trả `400`; sửa/xóa nhà cung cấp shop khác trả `403`; xóa là soft delete và vẫn hiện trong danh sách quản lý với `is_active=false`.
- Nhập hàng C7/F4-25–27, F4-30: tạo phiếu với supplier/variant không tồn tại trả `404`, thuộc shop khác trả `403` (hai trường hợp tách biệt, không gộp chung mã lỗi), supplier đã soft-delete trả `400`; `items` trùng `variant_id` trả `422`; `DRAFT→ORDERED→RECEIVED` cộng đúng kho từng variant, đặt `received_at` và tự động giải quyết cảnh báo tồn kho thấp đang mở khi kho vượt ngưỡng; gọi `RECEIVED` lần hai trả `400` và kho không đổi; chuyển trạng thái sai (`RECEIVED` từ `DRAFT`, tiếp tục sau `CANCELLED`) trả `400`; đọc/sửa phiếu của shop khác trả `403`; danh sách phân trang và lọc đúng theo `status`, chỉ trả phiếu của shop hiện tại.
- Review C8/F5-31–34: review khi đơn chưa `DELIVERED` trả `400`; review order item của buyer khác trả `403`; order item không tồn tại trả `404`; rating ngoài 1–5 trả `422`; review hợp lệ trả `200` và lưu đúng `product_id` suy từ variant; chi tiết đơn đổi `review_id` từ `null` sang ID review tương ứng; review lần hai cùng order item trả `400`; `GET /products/{id}/reviews` trả đúng tổng số, `rating_average` cập nhật ngay sau review mới và khớp với `rating_average` ở chi tiết sản phẩm; sản phẩm chưa có review trả `rating_average=null`; sản phẩm không tồn tại trả `404`.
- Số liệu thống kê shop C9/F1-8: đơn giao lúc 20:00 UTC (03:00 giờ VN ngày hôm sau) được tính doanh thu đúng vào ngày VN kế tiếp, không lệch sang ngày UTC — kiểm tra trực tiếp việc quy đổi múi giờ trong query thay vì chỉ test dữ liệu cùng ngày; `order_count`/`cancelled_count` đếm theo `created_at` giờ VN, mọi trạng thái; `cancel_rate` và `aov` trả `null` khi mẫu số bằng 0; số liệu chỉ tính trên đơn của shop hiện tại dù có đơn shop khác cùng thời điểm; `revenue-by-day` nhóm đúng theo ngày VN của `delivered_at`, bỏ qua đơn chưa `DELIVERED`; `top-products` cộng dồn đúng theo `product_id` khi nhiều variant cùng sản phẩm được bán, sắp xếp giảm dần và giới hạn theo `limit`; `from` lớn hơn `to` trả `400`; vai trò khác `SHOP_OWNER` trả `403`.
- Admin C10: danh sách user lọc theo role và tìm theo email/họ tên, chỉ `ADMIN` gọi được (`401`/`403` cho trường hợp khác); admin tự khóa chính mình trả `400`, tự mở lại vẫn `200`, khóa user không tồn tại trả `404`; khóa shop khiến sản phẩm của shop đó biến mất khỏi `GET /products` công khai, mở lại thì hiện lại (gián tiếp qua điều kiện `Shop.is_active` đã có ở C2); danh sách đơn admin trả đúng tổng số trên toàn hệ thống và lọc đúng theo `shop_id`/`status`; số liệu tổng quan admin cộng dồn đúng doanh thu/số đơn của nhiều shop trong cùng kỳ.

Toàn bộ backend Planning C0–C10 và frontend D1–D2 đã có test. Phần còn lại là frontend SHOP_OWNER/ADMIN (D3–D4) và data platform (E).
