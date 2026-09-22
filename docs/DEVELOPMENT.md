# Development

**Trạng thái:** In progress

Tài liệu này mô tả môi trường development đã được triển khai. Các workflow của những phần chưa xây dựng sẽ được bổ sung cùng task tương ứng.

## Yêu cầu

- Docker Desktop với Docker Compose.
- Git.
- Python 3.11+ và Node.js 20+ nếu muốn chạy service ngoài container.

## Biến môi trường

Sao chép `.env.example` thành `.env` trước khi dùng thông tin riêng trên máy local. Không commit `.env`.

- `DATABASE_URL`: database development `fashion`.
- `TEST_DATABASE_URL`: database test độc lập `fashion_test`.
- `JWT_SECRET`: khóa ký JWT HS256; phải thay giá trị mẫu bằng khóa bí mật dài ít nhất 32 byte ở môi trường không phải local.
- `JWT_EXPIRE_MINUTES`: thời hạn token.
- `VITE_API_URL`: địa chỉ backend mà frontend sử dụng.

PostgreSQL tạo `fashion_test` từ `backend/docker/postgres-init.sql` khi volume database được khởi tạo lần đầu.

## Khởi động

```powershell
docker compose --env-file .env.example up -d
docker compose --env-file .env.example ps
```

Các địa chỉ local:

- Frontend: `http://localhost:5173`
- FastAPI Swagger: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- PostgreSQL: `localhost:5432`

## Migration

```powershell
docker compose --env-file .env.example exec -T backend alembic upgrade head
docker compose --env-file .env.example exec -T backend alembic current
docker compose --env-file .env.example exec -T backend alembic check
```

Không sửa migration đã được áp dụng. Schema mới phải được thêm bằng migration tiếp theo.

## Dữ liệu mẫu

Sau khi migration hoàn tất, chạy seed bằng container backend:

```powershell
docker compose --env-file .env.example exec -T backend python -m app.seed
```

Script có thể chạy lại an toàn mà không nhân đôi dữ liệu. Bộ dữ liệu hiện tại gồm 3 shop, 45 sản phẩm, 135 variant, 6 supplier và 36 đơn hàng mẫu.

Tài khoản demo:

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Admin | `admin@shop.vn` | `Admin@123` |
| Shop owner | `shop1@shop.vn` đến `shop3@shop.vn` | `Shop@123` |
| Buyer | `buyer1@shop.vn` đến `buyer5@shop.vn` | `Buyer@123` |

## Test backend

```powershell
docker compose --env-file .env.example exec -T backend pytest -q
```

Test database tách khỏi database development. Test có thể tạo dữ liệu và rollback mà không làm thay đổi dữ liệu dùng để chạy ứng dụng.

## Kiểm tra frontend

```powershell
docker compose --env-file .env.example exec -T frontend npm test
docker compose --env-file .env.example exec -T frontend npm run build
docker compose --env-file .env.example exec -T frontend npm audit --audit-level=moderate
```

Frontend D1 và các trang auth/catalog đầu tiên của D2 dùng Axios và React Router; package được khóa trong `frontend/package-lock.json`. Khi thay dependency frontend, chạy `npm install` trong `frontend/` rồi cập nhật cả `package.json` và lockfile.

Để bật bộ kiểm tra trước commit, chạy `git config core.hooksPath .githooks` một lần trong clone hiện tại. Danh sách kiểm tra và cách chạy thủ công nằm trong [`TESTING.md`](TESTING.md#hook-pre-commit).
