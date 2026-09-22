# API

**Trạng thái:** In progress
**Phạm vi đã triển khai:** Planning C0–C1 (auth và dependency phân quyền)

Swagger chạy tại `http://localhost:8000/docs`. Các endpoint nghiệp vụ từ C2 trở đi vẫn là `Planned` trong [`PLANNING.md`](PLANNING.md#phần-c--backend-từng-endpoint--pseudocode-chỗ-khó).

## Auth

| Method | Path | Quyền | Request | Response thành công |
|---|---|---|---|---|
| POST | `/auth/register` | Public | `email`, `password`, `full_name`, `role` (`BUYER` hoặc `SHOP_OWNER`) | `201` với `id`, `email`, `full_name`, `role`, `is_active` |
| POST | `/auth/login` | Public | `email`, `password` | `200` với `access_token`, `role`, `shop_id` (`null` nếu chưa có shop) |
| GET | `/auth/me` | Bearer token | — | `200` với thông tin user như response đăng ký |

Mật khẩu chỉ được lưu dưới dạng bcrypt hash và không xuất hiện trong response. Đăng ký email trùng hoặc role `ADMIN` trả `400`; sai thông tin đăng nhập trả `401`; tài khoản bị khóa trả `403`. Thiếu, sai hoặc hết hạn token khi gọi `/auth/me` trả `401`. Response lỗi dùng dạng `{"detail": "..."}`.

JWT được ký bằng HS256 với `JWT_SECRET`, hết hạn theo `JWT_EXPIRE_MINUTES`. Payload gồm `sub` (user ID dạng chuỗi), `role`, `shop_id` và `exp` (UTC). Các dependency luôn tải user và shop từ database khi phân quyền; giá trị `role` và `shop_id` trong token không được dùng làm nguồn xác thực quyền sở hữu. `require_role(...)` trả `403` khi sai role; `get_current_shop` trả `403` khi shop owner chưa có shop.
