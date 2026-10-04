# Hướng dẫn cài đặt và chạy dự án từ đầu

**Trạng thái:** Implemented cho môi trường local/demo

**Đối tượng:** Người chưa quen Git, Docker, FastAPI, React hoặc PostgreSQL

**Hệ điều hành chính:** Windows 10/11 với PowerShell

Tài liệu này hướng dẫn tải source code, tạo cấu hình, khởi động database/backend/frontend, tạo dữ liệu mẫu, kiểm tra hệ thống và xử lý các lỗi thường gặp.

> [!IMPORTANT]
> Repository hiện chạy hoàn chỉnh phần web vận hành bằng PostgreSQL local. Bronze E1 và Silver E2 dùng CDC/checkpoint, đã chạy Job và nghiệm thu trên Databricks; setup và bằng chứng nằm ở [`DATA_PLATFORM.md`](DATA_PLATFORM.md) và [`E2_SILVER.md`](E2_SILVER.md). Gold E3, gate E4, AI/BI Dashboard, Genie và cấu hình production public chưa triển khai.

## 1. Sau khi hoàn thành bạn sẽ có gì?

Ba service chạy trên máy:

| Service | Vai trò | Địa chỉ |
|---|---|---|
| PostgreSQL | Lưu dữ liệu vận hành và dữ liệu test | `localhost:5432` |
| FastAPI backend | API, xác thực và nghiệp vụ | `http://localhost:8000` |
| React frontend | Giao diện người dùng | `http://localhost:5173` |

Các địa chỉ cần nhớ:

- Giao diện web: <http://localhost:5173>
- Tài liệu và màn hình thử API: <http://localhost:8000/docs>
- Kiểm tra backend: <http://localhost:8000/health>

## 2. Một số khái niệm cơ bản

- **Repository:** thư mục chứa toàn bộ source code của dự án.
- **Terminal/PowerShell:** cửa sổ dùng để nhập lệnh.
- **Docker image:** gói chứa chương trình và dependency cần thiết.
- **Container:** một phiên bản đang chạy của image.
- **Docker Compose:** công cụ khởi động nhiều container cùng lúc.
- **Migration:** các bước tạo hoặc nâng cấp cấu trúc bảng database.
- **Seed:** tạo dữ liệu mẫu để có thể đăng nhập và thử chức năng ngay.
- **Backend:** phần xử lý API và nghiệp vụ.
- **Frontend:** giao diện chạy trong trình duyệt.

Bạn không cần cài Python, Node.js hoặc PostgreSQL riêng nếu chỉ chạy dự án bằng Docker.

## 3. Chuẩn bị máy

### 3.1. Cài Git

Cài Git for Windows từ trang chính thức của Git. Sau khi cài, mở một cửa sổ PowerShell mới và kiểm tra:

```powershell
git --version
```

Nếu thấy một dòng tương tự `git version 2.x.x`, Git đã sẵn sàng.

### 3.2. Cài Docker Desktop

1. Cài Docker Desktop for Windows.
2. Nếu trình cài đặt hỏi, chọn backend WSL 2.
3. Khởi động lại máy nếu được yêu cầu.
4. Mở Docker Desktop và chờ tới khi giao diện báo Docker Engine đang chạy.

Kiểm tra trong PowerShell:

```powershell
docker --version
docker compose version
docker info
```

Hai lệnh đầu phải in ra phiên bản. `docker info` phải trả về thông tin server, không được báo không kết nối được Docker Engine.

### 3.3. Kiểm tra các cổng cần dùng

Dự án cần các cổng `5432`, `8000` và `5173`. Chạy:

```powershell
Get-NetTCPConnection -LocalPort 5432,8000,5173 -ErrorAction SilentlyContinue
```

Không có kết quả nghĩa là các cổng đang trống. Nếu có chương trình khác sử dụng cổng, hãy dừng chương trình đó trước. Không nên tự đổi cổng khi chưa hiểu cấu hình CORS và URL giữa frontend/backend.

## 4. Tải source code

Chọn thư mục muốn lưu dự án, ví dụ `D:\Projects`, sau đó chạy:

```powershell
Set-Location D:\Projects
git clone https://github.com/mewmewancut/DALN.git
Set-Location DALN
```

Nếu đã có source code, chỉ cần mở PowerShell tại thư mục chứa dự án rồi kiểm tra:

```powershell
git status
```

Bạn đang ở đúng thư mục nếu thấy tên nhánh Git và không thấy lỗi `not a git repository`.

Tất cả lệnh ở các phần tiếp theo phải chạy từ thư mục gốc `DALN`, là nơi có `docker-compose.yml`.

## 5. Tạo file cấu hình môi trường

Tạo `.env` từ file mẫu:

```powershell
Copy-Item .env.example .env
notepad .env
```

Nội dung tối thiểu:

```dotenv
POSTGRES_DB=fashion
POSTGRES_USER=fashion
POSTGRES_PASSWORD=fashion
DATABASE_URL=postgresql+psycopg://fashion:fashion@localhost:5432/fashion
TEST_DATABASE_URL=postgresql+psycopg://fashion:fashion@localhost:5432/fashion_test
JWT_SECRET=thay-bang-chuoi-bi-mat-dai-it-nhat-32-ky-tu
JWT_EXPIRE_MINUTES=60
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-project-account@gmail.com
SMTP_APP_PASSWORD=thay-bang-google-app-password
EMAIL_FROM_NAME=Fashion E-Commerce
FRONTEND_PUBLIC_URL=http://localhost:5173
VERIFY_EMAIL_EXPIRE_MINUTES=480
RESET_PASSWORD_EXPIRE_MINUTES=30
SMTP_TIMEOUT_SECONDS=10
VITE_API_URL=http://localhost:8000
VITE_DATABRICKS_DASHBOARD_URL=
VITE_DATABRICKS_GENIE_URL=
```

Quy tắc quan trọng:

- Với local/demo, có thể giữ tài khoản PostgreSQL mẫu.
- Thay `JWT_SECRET` bằng một chuỗi ngẫu nhiên dài ít nhất 32 ký tự.
- Điền Gmail và Google App Password thật vào `.env`; không dùng mật khẩu Gmail thông thường.
- Không thêm khoảng trắng hai bên dấu `=`.
- Giữ hai URL Databricks trống vì Dashboard và Genie chưa được triển khai.
- Không commit `.env`. File này có thể chứa bí mật và đã được `.gitignore` loại trừ.

Để tạo Google App Password: bật 2-Step Verification, mở mục App Passwords của Google Account, tạo mật khẩu dành riêng cho project rồi sao chép chuỗi 16 ký tự vào `SMTP_APP_PASSWORD`. Google có thể không hiện mục này với một số tài khoản tổ chức hoặc chế độ bảo vệ nâng cao. Tham khảo [Google App Passwords](https://support.google.com/accounts/answer/185833) và [SMTP Gmail](https://support.google.com/a/answer/176600). Link xác minh/reset dùng `localhost`, nên phải mở trên chính máy đang chạy frontend.

Kiểm tra Docker Compose đọc được cấu hình:

```powershell
docker compose --env-file .env config --quiet
```

Lệnh thành công thường không in gì và trả quyền nhập lệnh mới. Nếu có lỗi, kiểm tra lại cú pháp `.env` và chắc chắn bạn đang ở thư mục gốc repository.

## 6. Build và khởi động hệ thống

Lần đầu chạy, Docker cần tải image và cài dependency nên có thể mất vài phút:

```powershell
docker compose --env-file .env up --build -d
```

Ý nghĩa các tùy chọn:

- `--env-file .env`: dùng cấu hình vừa tạo.
- `--build`: build lại backend và frontend từ source code.
- `-d`: chạy nền để có thể tiếp tục dùng cửa sổ PowerShell.

Xem trạng thái:

```powershell
docker compose --env-file .env ps
```

Kết quả mong đợi:

- `db` ở trạng thái `Up` và `healthy`.
- `backend` ở trạng thái `Up`.
- `frontend` ở trạng thái `Up`.

Nếu service bị `Exited`, xem log:

```powershell
docker compose --env-file .env logs --tail 100 db
docker compose --env-file .env logs --tail 100 backend
docker compose --env-file .env logs --tail 100 frontend
```

Muốn theo dõi log liên tục, dùng `-f`; nhấn `Ctrl+C` để dừng xem log mà không dừng container:

```powershell
docker compose --env-file .env logs -f
```

## 7. Tạo cấu trúc database

Chạy toàn bộ migration:

```powershell
docker compose --env-file .env exec -T backend alembic upgrade head
```

Kiểm tra phiên bản migration và phát hiện migration còn thiếu:

```powershell
docker compose --env-file .env exec -T backend alembic current
docker compose --env-file .env exec -T backend alembic check
```

`alembic current` phải hiển thị revision mới nhất. `alembic check` phải báo không có operation mới cần tạo.

> [!WARNING]
> Không sửa các file migration cũ đã được áp dụng. Khi cấu trúc database thay đổi, phải tạo migration mới.

## 8. Tạo dữ liệu mẫu

Chạy seed:

```powershell
docker compose --env-file .env exec -T backend python -m app.seed
```

Seed hiện tạo 3 shop, 45 sản phẩm, 135 variant, 6 nhà cung cấp và 36 đơn hàng mẫu. Có thể chạy lại lệnh này; script được thiết kế để không nhân đôi dữ liệu.

Tài khoản đăng nhập mẫu:

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Admin | `admin@shop.vn` | `Admin@123` |
| Chủ shop | `shop1@shop.vn`, `shop2@shop.vn`, `shop3@shop.vn` | `Shop@123` |
| Người mua | `buyer1@shop.vn` đến `buyer5@shop.vn` | `Buyer@123` |

Các mật khẩu này chỉ dành cho local/demo, không được dùng trong môi trường public.

## 9. Kiểm tra hệ thống sau khi khởi động

### 9.1. Kiểm tra backend

Trong PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Kết quả đúng:

```text
status
------
ok
```

Mở Swagger:

```powershell
Start-Process http://localhost:8000/docs
```

Nếu trang hiện danh sách API theo nhóm auth, products, cart, orders, shop và admin thì backend hoạt động.

### 9.2. Kiểm tra frontend

```powershell
Start-Process http://localhost:5173
```

Trang danh sách sản phẩm phải hiển thị. Thử đăng nhập bằng một tài khoản ở phần 8.

### 9.3. Kiểm tra nhanh theo từng vai trò

Người mua:

1. Đăng nhập bằng `buyer1@shop.vn` / `Buyer@123`.
2. Mở một sản phẩm, chọn màu và size.
3. Thêm vào giỏ hàng.
4. Mở giỏ, chuyển tới checkout và đặt đơn.
5. Mở danh sách đơn để thấy đơn mới ở trạng thái `PENDING`.

Chủ shop:

1. Đăng xuất rồi đăng nhập `shop1@shop.vn` / `Shop@123`.
2. Kiểm tra dashboard, sản phẩm, tồn kho, cảnh báo và nhà cung cấp.
3. Mở danh sách đơn và cập nhật tuần tự `PENDING → CONFIRMED → PREPARING → SHIPPING → DELIVERED`.
4. Không bỏ qua trạng thái; backend sẽ từ chối transition không hợp lệ.

Admin:

1. Đăng xuất rồi đăng nhập `admin@shop.vn` / `Admin@123`.
2. Kiểm tra dashboard, người dùng, shop và đơn hàng toàn hệ thống.
3. Link Databricks hiển thị chưa cấu hình là đúng với trạng thái hiện tại.

## 10. Chạy toàn bộ kiểm tra

Chỉ coi môi trường local sẵn sàng khi các lệnh liên quan đều pass.

### 10.1. Backend và database

```powershell
docker compose --env-file .env exec -T backend ruff check .
docker compose --env-file .env exec -T backend ruff format --check .
docker compose --env-file .env exec -T backend pytest -q
```

Nếu pytest báo không tìm thấy database `fashion_test`, xem phần 14.5.

### 10.2. Frontend

```powershell
docker compose --env-file .env exec -T frontend npm run lint
docker compose --env-file .env exec -T frontend npm run format:check
docker compose --env-file .env exec -T frontend npm test
docker compose --env-file .env exec -T frontend npm run build
docker compose --env-file .env exec -T frontend npm audit --audit-level=moderate
```

### 10.3. Kiểm tra thay đổi Git

```powershell
git diff --check
git status --short
```

`git diff --check` không được báo lỗi whitespace. `git status --short` không có output nghĩa là working tree sạch.

### 10.4. Bật pre-commit hook cho người phát triển

Chạy một lần trong mỗi bản clone:

```powershell
git config core.hooksPath .githooks
```

Có thể chạy toàn bộ cổng kiểm tra mà chưa cần commit:

```powershell
git hook run pre-commit
```

Hook sẽ build service, chạy migration, lint, format check, backend/frontend test, frontend build, dependency audit và smoke test. Docker Desktop phải đang chạy.

## 11. Dừng, chạy lại và xem log

Dừng container nhưng giữ dữ liệu:

```powershell
docker compose --env-file .env down
```

Chạy lại mà không build:

```powershell
docker compose --env-file .env up -d
```

Khởi động lại một service:

```powershell
docker compose --env-file .env restart backend
docker compose --env-file .env restart frontend
```

Xem 100 dòng log gần nhất:

```powershell
docker compose --env-file .env logs --tail 100
```

## 12. Cập nhật source code lên phiên bản mới

Trước tiên kiểm tra có thay đổi local hay không:

```powershell
git status --short
```

Nếu có file đã sửa mà bạn không muốn mất, hãy commit hoặc nhờ người có kinh nghiệm xử lý trước. Không chạy lệnh xóa/reset tùy ý.

Khi working tree sạch:

```powershell
git pull --ff-only
docker compose --env-file .env up --build -d
docker compose --env-file .env exec -T backend alembic upgrade head
docker compose --env-file .env exec -T backend python -m app.seed
```

Sau đó chạy lại các kiểm tra ở phần 9 và 10.

## 13. Xóa toàn bộ dữ liệu và tạo lại từ đầu

Chỉ dùng khi muốn reset môi trường local/demo. Lệnh `down -v` sẽ xóa volume PostgreSQL và toàn bộ dữ liệu hiện có của dự án trên Docker.

```powershell
docker compose --env-file .env down -v
docker compose --env-file .env up --build -d
docker compose --env-file .env exec -T backend alembic upgrade head
docker compose --env-file .env exec -T backend python -m app.seed
```

> [!CAUTION]
> Dữ liệu bị xóa bằng `down -v` không thể khôi phục nếu chưa backup. Không dùng lệnh này với môi trường chứa dữ liệu cần giữ.

## 14. Xử lý lỗi thường gặp

### 14.1. Không kết nối được Docker Engine

Thông báo thường gặp:

```text
failed to connect to the docker API
```

Cách xử lý:

1. Mở Docker Desktop.
2. Chờ Docker Engine chạy hoàn toàn.
3. Chạy `docker info`.
4. Chạy lại lệnh Compose.

### 14.2. Cổng đã được sử dụng

Thông báo thường có `port is already allocated` hoặc `address already in use`.

Tìm chương trình đang giữ cổng:

```powershell
Get-NetTCPConnection -LocalPort 5432,8000,5173 -ErrorAction SilentlyContinue |
    Select-Object LocalPort,State,OwningProcess
```

Xem tên process, thay `<PID>` bằng số ở cột `OwningProcess`:

```powershell
Get-Process -Id <PID>
```

Đóng chương trình đó bằng giao diện hoặc dừng service tương ứng, rồi chạy lại Compose.

### 14.3. Database chưa sẵn sàng

Kiểm tra trạng thái và log:

```powershell
docker compose --env-file .env ps
docker compose --env-file .env logs --tail 100 db
```

Chờ `db` chuyển thành `healthy`, sau đó chạy lại migration.

### 14.4. Backend báo thiếu bảng hoặc relation does not exist

Migration chưa chạy hoặc chưa chạy hết:

```powershell
docker compose --env-file .env exec -T backend alembic upgrade head
docker compose --env-file .env exec -T backend alembic current
```

### 14.5. Test báo database `fashion_test` không tồn tại

Database test được tạo khi volume PostgreSQL khởi tạo lần đầu. Nếu volume cũ được tạo trước khi có script init, hãy chỉ reset volume khi chắc chắn không cần dữ liệu local:

```powershell
docker compose --env-file .env down -v
docker compose --env-file .env up --build -d
docker compose --env-file .env exec -T backend alembic upgrade head
docker compose --env-file .env exec -T backend python -m app.seed
```

Sau đó chạy lại pytest.

### 14.6. Frontend mở được nhưng gọi API lỗi

Kiểm tra lần lượt:

```powershell
Invoke-RestMethod http://localhost:8000/health
docker compose --env-file .env logs --tail 100 backend
docker compose --env-file .env logs --tail 100 frontend
```

Đảm bảo `.env` có:

```dotenv
VITE_API_URL=http://localhost:8000
```

Vite đọc biến môi trường khi khởi động. Sau khi đổi giá trị, chạy:

```powershell
docker compose --env-file .env up --build -d frontend
```

### 14.7. Đăng nhập không được

1. Kiểm tra đã chạy seed ở phần 8.
2. Kiểm tra đúng chữ hoa/thường trong mật khẩu.
3. Tài khoản đăng ký qua giao diện phải mở link xác minh trước; tài khoản seed đã được xác minh sẵn.
4. Xem log backend.
5. Chạy lại seed; script không nhân đôi dữ liệu.

```powershell
docker compose --env-file .env exec -T backend python -m app.seed
```

### 14.8. Source code thay đổi nhưng giao diện không cập nhật

Build lại service:

```powershell
docker compose --env-file .env up --build -d frontend
```

Sau đó tải lại trang bằng `Ctrl+F5`.

### 14.9. Không nhận được email xác minh hoặc reset

1. Kiểm tra `SMTP_USERNAME` là địa chỉ Gmail đầy đủ và `SMTP_APP_PASSWORD` là App Password, không phải mật khẩu tài khoản.
2. Kiểm tra tài khoản đã bật 2-Step Verification và App Password chưa bị thu hồi.
3. Xem thư mục Spam và log backend: `docker compose --env-file .env logs --tail 100 backend`.
4. Sau khi sửa `.env`, chạy `docker compose --env-file .env up -d --force-recreate backend` rồi dùng nút gửi lại. Nút resend có cooldown 60 giây.
5. Nếu mở link trên thiết bị khác, `localhost` sẽ trỏ tới thiết bị đó. Với cấu hình local, hãy mở email trên chính máy đang chạy frontend.

## 15. Trạng thái triển khai Databricks

E1 Bronze và E2 Silver đã có notebook, test Delta local và nghiệm thu trên workspace thật. E3 Gold và gate E4 còn Planned. Setup E1/E2 dùng CDC đã được duyệt, giữ nguyên bảng và nghiệp vụ Planning:

1. Chuẩn bị database ứng dụng trên Lakebase; backend local không tự chuyển kết nối.
2. Bật Lakebase CDF vào external catalog S3 và tạo Volume checkpoint, schema Bronze/Silver theo [`DATA_PLATFORM.md`](DATA_PLATFORM.md).
3. Đồng bộ Git folder; cấu hình một task serverless `data/00_pipeline.py`, maximum concurrent runs = 1. Chạy tay trước demo hoặc lịch 15 phút; dừng Job Bronze cũ trước khi bật lịch mới.
4. Chạy Job hai lượt và nghiệm thu riêng bằng `data/acceptance.py`; xem [`E2_SILVER.md`](E2_SILVER.md). Ngày Việt Nam chỉ tính ở Silver. Không chạy audit/đếm nguồn trong mỗi lượt Job.
5. Hoàn thiện `03_gold_aggregate.py` theo định nghĩa metric C9.
6. Chạy `04_data_quality_check.py`; cả năm kiểm tra E4 phải PASS.
7. Chỉ sau khi E4 PASS mới tạo AI/BI Dashboard và Genie space.
8. Điền URL thật vào `VITE_DATABRICKS_DASHBOARD_URL` và `VITE_DATABRICKS_GENIE_URL`, rồi build lại frontend.

Không tự tạo Dashboard hoặc Genie từ dữ liệu Bronze/Silver. Genie chỉ được đọc các bảng Gold theo Planning.

## 16. Giới hạn của cấu hình hiện tại

Cấu hình Docker hiện tại là môi trường phát triển/local demo:

- Backend chạy Uvicorn với `--reload`.
- Frontend chạy Vite development server.
- Chưa có HTTPS, reverse proxy, domain hoặc quản lý secret production.
- CORS backend chỉ cho phép `http://localhost:5173`.
- PostgreSQL được publish trực tiếp ra cổng `5432`.
- Chưa có backup/restore production, monitoring hoặc CI/CD triển khai public.
- Chưa có script `reset_demo.sh` và `DEMO.md` theo Planning G.

Vì vậy không đưa cấu hình này trực tiếp lên Internet. Production deployment phải được thiết kế và kiểm thử trong một task riêng trước khi sử dụng thật.

## 17. Checklist hoàn thành local/demo

- [ ] Git và Docker Desktop đã cài.
- [ ] `docker info` chạy thành công.
- [ ] Repository đã clone và PowerShell đang ở thư mục gốc.
- [ ] `.env` đã tạo; `JWT_SECRET` đã thay.
- [ ] Gmail App Password đã cấu hình và thử nhận email xác minh thật.
- [ ] `docker compose ... config --quiet` pass.
- [ ] Ba service đều `Up`; database `healthy`.
- [ ] Migration lên revision mới nhất.
- [ ] Seed chạy thành công.
- [ ] `/health` trả `status=ok`.
- [ ] Swagger và frontend mở được.
- [ ] Đăng nhập được bằng Buyer, Shop Owner và Admin.
- [ ] Backend test pass.
- [ ] Frontend lint, test, build và audit pass.
- [ ] Đã đọc phần giới hạn và không nhầm local/demo với production.

## 18. Tài liệu liên quan

- [`DEVELOPMENT.md`](DEVELOPMENT.md): lệnh và workflow dành cho người phát triển.
- [`TESTING.md`](TESTING.md): phạm vi test và pre-commit hook.
- [`API.md`](API.md): endpoint và contract API.
- [`DATABASE.md`](DATABASE.md): schema và migration.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): kiến trúc đã triển khai và phần còn planned.
- [`PLANNING.md`](PLANNING.md): đặc tả đầy đủ và Definition of Done.
