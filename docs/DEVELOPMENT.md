# Development

**Trạng thái:** In progress

Tài liệu này mô tả môi trường development đã được triển khai. Các workflow của những phần chưa xây dựng sẽ được bổ sung cùng task tương ứng.

## Yêu cầu

- Docker Desktop với Docker Compose.
- Git.
- Python 3.11+ và Node.js 20.19+, 22.13+ hoặc 24+ nếu muốn chạy service ngoài container (theo yêu cầu ESLint 10).

## Biến môi trường

Sao chép `.env.example` thành `.env` trước khi dùng thông tin riêng trên máy local. Không commit `.env`.

- `DATABASE_URL`: database development `fashion`.
- `TEST_DATABASE_URL`: database test độc lập `fashion_test`.
- `JWT_SECRET`: khóa ký JWT HS256; phải thay giá trị mẫu bằng khóa bí mật dài ít nhất 32 byte ở môi trường không phải local.
- `JWT_EXPIRE_MINUTES`: thời hạn token.
- `VITE_API_URL`: địa chỉ backend mà frontend sử dụng.
- `VITE_DATABRICKS_DASHBOARD_URL`, `VITE_DATABRICKS_GENIE_URL`: link Databricks AI/BI Dashboard và Genie space hiển thị trên dashboard admin. Để trống cho tới khi Planning E5–E6 được triển khai; khi trống, giao diện ghi "chưa được cấu hình". Vite nhúng giá trị lúc khởi động/build, nên cần khởi động lại service frontend sau khi đổi.

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

## Chuẩn hóa code

Backend dùng Ruff với cấu hình `backend/ruff.toml`: kiểm tra lỗi Python, import không dùng và thứ tự import; format theo độ rộng 100 ký tự. Các migration lịch sử trong `alembic/versions` được loại khỏi quá trình lint/format để không sửa revision đã áp dụng. Frontend dùng ESLint 10 với bộ rule JavaScript recommended và hai rule React Hooks (thứ tự gọi hook, dependency của effect); Prettier quản lý định dạng. Cấu hình nằm trong `frontend/eslint.config.js` và `frontend/.prettierrc.json`.

Chạy các lệnh kiểm tra từ thư mục gốc repository:

```powershell
docker compose --env-file .env.example exec -T backend ruff check .
docker compose --env-file .env.example exec -T backend ruff format --check .
docker compose --env-file .env.example exec -T frontend npm run lint
docker compose --env-file .env.example exec -T frontend npm run format:check
```

Sửa định dạng chủ động bằng `docker compose --env-file .env.example exec -T backend ruff format .` và `docker compose --env-file .env.example exec -T frontend npm run format`. Với import Python, dùng `ruff check --fix .` trong container backend rồi review diff. Hook chỉ kiểm tra, không tự sửa file hoặc stage code. Sau khi thay requirements backend, build lại bằng `docker compose --env-file .env.example up --build -d`.

## Skill review DALN

Skill cá nhân `daln-review` đã được tạo trên máy phát triển tại `~/.codex/skills/daln-review/SKILL.md`; file này nằm ngoài repository và không tự có trên máy của người clone. Có thể gọi: `Dùng $daln-review để review thay đổi hiện tại theo Planning, kiểm tra test và báo lỗi trước commit.` Skill đọc nguồn sự thật trong repository, review theo phần nghiệp vụ bị thay đổi và báo phát hiện kèm bằng chứng; yêu cầu review đơn thuần không tự cho phép sửa code hay tạo commit.
