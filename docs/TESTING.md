# Testing

**Trạng thái:** In progress  
**Phạm vi hiện tại:** health check, database constraints B1–B14, seed data B15, auth C1, catalog C2, giỏ hàng C3, checkout C4 và luồng API từ đăng ký đến đăng sản phẩm

Frontend D1 và phần đầu D2 có test gắn token, xử lý `401`, điều hướng theo vai trò, form auth và catalog.

## Các lớp kiểm tra hiện có

| Lớp | Công cụ | Phạm vi đang chạy |
|---|---|---|
| Database | pytest + PostgreSQL test | Constraint, giá trị mặc định, timestamp, seed chạy lại không nhân đôi |
| API và phân quyền | pytest + FastAPI TestClient | Auth, shop, catalog, giỏ hàng, lỗi nghiệp vụ, quyền sở hữu và rollback |
| Đồng thời giỏ hàng | pytest + PostgreSQL, hai session/thread | Lần thêm đầu tiên cùng variant hoặc khác shop bảo toàn một giỏ/một shop, không mất số lượng |
| Đồng thời checkout | pytest + PostgreSQL, hai session/thread | Hai buyer checkout cùng variant chỉ đủ cho một đơn không làm âm kho; hai request trên cùng giỏ không tạo hai đơn |
| Luồng API | pytest + FastAPI TestClient | Đăng ký chủ shop → đăng nhập → tạo shop → đăng sản phẩm → buyer xem catalog; category được tạo trong fixture vì API admin chưa có |
| Frontend | Vitest + jsdom | Axios token/`401`, điều hướng theo vai trò, form login/register, tìm kiếm/lọc/phân trang catalog, chọn variant và lỗi API |
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
- Catalog công khai lọc, sắp xếp, phân trang theo giá variant hoạt động; ẩn sản phẩm và shop không hoạt động; chi tiết có tồn kho và rating trung bình.
- Luồng API nối đăng ký, đăng nhập, tạo shop, tạo sản phẩm, catalog công khai, chặn buyer sửa sản phẩm và soft delete.
- Frontend gửi đúng body login/register, điều hướng sau auth, hiển thị lỗi API và giữ lỗi `401` của login trên form.
- Frontend gọi lại catalog với query params khi đổi bộ lọc hoặc trang, về trang 1 khi đổi filter, hiển thị trạng thái rỗng/lỗi và giá từ API.
- Chi tiết sản phẩm hiển thị giá/tồn kho đúng variant được chọn, xóa size khi đổi màu và báo lỗi sản phẩm không tồn tại.
- Giỏ hàng C3/F2-10–11: xem giỏ rỗng, cộng dồn variant, chặn khác shop đúng error payload, giá/tồn kho hiện tại, sửa/xóa item và đặt lại shop khi giỏ rỗng.
- Giỏ hàng từ chối số lượng không hợp lệ, tài nguyên thiếu/ẩn, quyền truy cập của shop owner hoặc buyer khác và dữ liệu giá/shop/buyer do client gửi. Lỗi vượt tồn và lỗi commit đều giữ nguyên giỏ; test hai session kiểm tra các request thêm đồng thời.
- Checkout C4/F2-12–17: giỏ rỗng trả `400`; checkout hợp lệ trừ đúng kho, xóa giỏ và ghi đúng một dòng lịch sử trạng thái; thiếu tồn kho rollback toàn bộ (không tạo đơn, không trừ kho, giỏ giữ nguyên); giá trong đơn giữ nguyên sau khi shop đổi giá; `total_amount` client gửi bị bỏ qua và tổng luôn tính từ giá database; test hai session xác nhận hai buyer checkout đồng thời trên cùng variant chỉ một đơn thành công khi kho chỉ đủ một đơn, đồng thời hai request trên cùng giỏ chỉ tạo đúng một đơn.

Các test F1 phụ thuộc vào API admin/order/stats và test nghiệp vụ F3–F7 sẽ được bổ sung khi module tương ứng được triển khai.
