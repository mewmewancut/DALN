# Architecture

**Trạng thái:** In progress
**Phạm vi đã triển khai:** Nền tảng A–B, backend C0–C2 và khung frontend D1.

## Thành phần đang chạy

```mermaid
flowchart LR
    Browser[React + Vite] --> Client[Axios client]
    Client --> API[FastAPI routers]
    API --> Services[Business services]
    Services --> Models[SQLAlchemy models]
    Models --> DB[(PostgreSQL development)]
```

Backend tách router, schema, service và model. Router nhận request, dùng dependency xác thực/phân quyền và gọi service. Service xử lý nghiệp vụ, sở hữu transaction; model và Alembic quản lý schema. Các endpoint hiện có được ghi trong [`API.md`](API.md), còn cấu trúc bảng nằm trong [`DATABASE.md`](DATABASE.md).

Frontend dùng `BrowserRouter` để định tuyến. `AuthProvider` đọc và lưu `{token, role, shop_id}` trong `localStorage`, rồi điều hướng theo vai trò sau khi đăng nhập; `RequireRole` chuyển người chưa đăng nhập tới `/login` và người sai vai trò về trang của vai trò đó. Đây là điều hướng giao diện; backend vẫn xác thực token và quyền trên từng request. Axios client gắn token vào header `Authorization` và xóa phiên, chuyển tới `/login` khi API trả `401`.

Khung hiện có định tuyến `/` cho buyer, `/shop/dashboard` cho shop owner và `/admin/dashboard` cho admin. Các trang này và `/login`, `/register` hiện chỉ là màn hình khung; form và giao diện nghiệp vụ thuộc D2–D4 vẫn là **Planned**. Hàm `formatCurrency` đã có cho các trang hiển thị tiền về sau.

Lakebase và pipeline Bronze/Silver/Gold vẫn là **Planned** theo phần E của [`PLANNING.md`](PLANNING.md). Môi trường development hiện dùng PostgreSQL trong Docker Compose.
