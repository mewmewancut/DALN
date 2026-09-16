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
- `JWT_SECRET`: khóa ký JWT; phải thay giá trị mẫu ở môi trường không phải local.
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

## Test backend

```powershell
docker compose --env-file .env.example exec -T backend pytest -q
```

Test database tách khỏi database development. Test có thể tạo dữ liệu và rollback mà không làm thay đổi dữ liệu dùng để chạy ứng dụng.

## Kiểm tra frontend

```powershell
docker compose --env-file .env.example exec -T frontend npm run build
docker compose --env-file .env.example exec -T frontend npm audit --audit-level=moderate
```
