# Testing

**Trạng thái:** In progress  
**Phạm vi hiện tại:** health check và database constraints B1–B6

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

Các test auth, phân quyền và nghiệp vụ F1–F7 sẽ được bổ sung khi module tương ứng được triển khai.
