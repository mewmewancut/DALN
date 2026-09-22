# Testing

**Trạng thái:** In progress  
**Phạm vi hiện tại:** health check, database constraints B1–B14, seed data B15 và auth C1

## Nguyên tắc

- Backend test dùng PostgreSQL `fashion_test`, tách khỏi database development `fashion`.
- Dữ liệu của mỗi test chạy trong transaction riêng và được rollback sau test.
- Constraint quan trọng phải được kiểm tra ở database, không chỉ kiểm tra bằng Python.
- Không bỏ qua, làm yếu hoặc xóa test đang fail để làm suite xanh.

## Cách chạy

```powershell
docker compose --env-file .env.example up -d db backend
docker compose --env-file .env.example exec -T backend pytest -q
```

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
- Auth: đăng ký thành công, email trùng, cấm role ADMIN; login đúng/sai mật khẩu; JWT chứa user ID, role và shop ID; `/auth/me` không lộ password hash.
- Thiếu, sai, hết hạn token hoặc user bị khóa đều bị từ chối; dependency role và shop lấy quyền sở hữu từ database thay vì tin `shop_id` trong token.

Các test F1 phụ thuộc vào API shop/admin/order và test nghiệp vụ F2–F7 sẽ được bổ sung khi module tương ứng được triển khai.
