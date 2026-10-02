# Data platform

**Trạng thái: In progress.** E1 đã có code notebook và test Delta local. Kết nối Lakebase, chạy notebook/Job trên Databricks web và nghiệm thu số dòng trên nguồn thật vẫn **Planned**. E2–E6 chưa triển khai; chưa tạo Dashboard hoặc Genie. Đặc tả chuẩn nằm ở [Planning phần E](PLANNING.md#phần-e--data-platform-databricks).

## Chạy E1 trên Databricks web

Databricks và Lakebase chạy trong workspace của bạn. Không triển khai chúng bằng Docker. PostgreSQL trong Compose hiện chỉ là database development của backend; notebook không tự chuyển hoặc sao chép database đó sang Lakebase.

1. Trong Lakebase, chuẩn bị database có schema ứng dụng và dữ liệu cần ingest. Backend hiện vẫn dùng PostgreSQL local; khi chuyển backend sang Lakebase cần cấu hình kết nối, áp dụng migration và seed theo [Deployment guide](DEPLOYMENT_GUIDE.md). Kết nối Lakebase thật của ứng dụng chưa được kiểm chứng trong task này.
2. Trong Catalog Explorer, đăng ký database Lakebase thành một catalog nguồn, ví dụ `daln_source`. Notebook dùng phương án Lakehouse Federation mà Planning E1 cho phép. Với Lakebase Autoscaling, catalog này cần **serverless SQL warehouse**; [hướng dẫn Databricks](https://docs.databricks.com/aws/en/oltp/projects/query-sql-editor) mô tả cách đăng ký và quyền cần thiết. Catalog nguồn chỉ dùng để đọc.
3. Trong SQL editor, chọn serverless SQL warehouse rồi tạo catalog đích và các namespace của Planning, nếu workspace chưa có:

   ```sql
   CREATE CATALOG IF NOT EXISTS fashion;
   CREATE SCHEMA IF NOT EXISTS fashion.bronze;
   CREATE SCHEMA IF NOT EXISTS fashion.silver;
   CREATE SCHEMA IF NOT EXISTS fashion.gold;
   ```

   Việc tạo schema rỗng không triển khai Silver/Gold. Người chạy cần quyền đọc 13 bảng nguồn, `USE CATALOG`/`USE SCHEMA`, quyền tạo schema/bảng và đọc/sửa bảng Bronze, cùng quyền `CAN USE` trên warehouse. Để dọn bảng staging, người chạy cần quyền quản lý các bảng do notebook tạo. Nếu dùng Job, cấp các quyền này cho danh tính **Run as** của Job.
4. Đưa repository vào **Databricks Git folder**, giữ các file `01_bronze_ingest.py`, `bronze_ingest.py` và `warehouse_sql.py` cạnh nhau. Nếu tải thủ công vào Workspace, import `01_bronze_ingest.py` dưới dạng Python notebook và upload hai module hỗ trợ dưới dạng **Workspace files**, không chuyển chúng thành notebooks. Không chỉ dán riêng notebook nếu thiếu hai module hỗ trợ. Dùng notebook compute có Python 3.11 trở lên và khả năng gọi Workspace API; notebook điều phối, còn SQL ingestion thực thi trên warehouse ở bước 2.
5. Chạy các ô cài SDK, restart Python và khai báo hàm. Notebook dùng [xác thực mặc định trong notebook của SDK](https://docs.databricks.com/aws/en/dev-tools/sdk-python); không điền token/mật khẩu vào code hoặc widget. SDK được khóa phiên bản `0.139.0`. Nếu workspace chặn cài thư viện, cấu hình dependency này qua môi trường compute trước khi chạy.
6. Chạy ô cuối để tạo widgets. Lần đầu notebook báo thiếu cấu hình; điền `source_catalog` và `warehouse_id`, rồi chạy lại **ô cuối**. Lấy warehouse ID trong trang SQL Warehouses của warehouse đã chọn. `source_schema` mặc định `public`, `target_catalog` mặc định `fashion`; giữ `check_twice=true` để nghiệm thu E1.
7. Tạm ngừng thao tác ghi vào nguồn trong lúc nghiệm thu. Notebook ingest đủ 13 bảng hai lần và đối chiếu số dòng từng bảng với nguồn hiện tại. Chỉ khi không có lỗi và có dòng `two-run count check passed` mới coi kiểm tra số dòng E1 đạt. Lưu kết quả run trong workspace; test local không thay thế bước này.
8. Sau nghiệm thu, tạo **Lakeflow Job** có Notebook task trỏ đến notebook này. Nhập các widgets thành task parameters; dùng `check_twice=false` cho các lần chạy định kỳ. Đặt tối đa một run đồng thời; lịch development 15 phút/lần hoặc chạy tay trước demo theo Planning. Notebook compute và SQL warehouse đều cần sẵn sàng và có quyền tương ứng. Chưa cấu hình lịch Job thật trong repository này.

## Hành vi ingestion

- Allow-list đúng 13 bảng E1: `users`, `shops`, `categories`, `products`, `product_variants`, `inventory`, `suppliers`, `purchase_orders`, `purchase_order_items`, `orders`, `order_items`, `order_status_history`, `reviews`. Không tự thêm bảng wishlist, preferences, cart hoặc auth token.
- Mỗi bảng nguồn được materialize vào bảng Delta staging riêng dưới `fashion.bronze`, tên bắt đầu `_ingest_`. Staging giữ toàn bộ cột nguồn và thêm `_ingested_at = current_timestamp()`. Không đổi thời điểm UTC sang ngày Việt Nam ở Bronze; quy đổi ngày thuộc E2.
- Trước MERGE, kiểm tra `id` không null/không trùng. Tạo bảng đích Delta nếu chưa có, rồi `MERGE ON id`, update dòng đã có và insert dòng mới. Không append. Giữ dòng soft-delete và dữ liệu nguồn chưa làm sạch.
- Nếu tập tên cột nguồn và đích khác nhau, run thất bại để tránh âm thầm mất cột. Không bật schema evolution tự động; thay đổi schema cần migration rõ ràng. Kiểm tra này chưa bảo đảm mọi thay đổi kiểu dữ liệu tương thích: lỗi cast/constraint khi MERGE do Delta xử lý.
- Mỗi MERGE là một transaction Delta; 13 bảng không nằm trong một transaction chung và không phải snapshot nhất quán toàn database. Run dừng tại lỗi; bảng trước đó có thể đã cập nhật. Chạy lại an toàn với khóa `id` hợp lệ. Khi nguồn đang đổi, đợi nguồn ổn định để kiểm tra count hai lần.
- Không xóa Bronze khi nguồn hard-delete vì E1 chỉ quy định update/insert. Count lệch sẽ làm run thất bại; cần xử lý nguồn hoặc thống nhất thay đổi thiết kế trước khi thêm xóa.
- Dọn staging trong `finally`. Nếu mất quyền/kết nối hoặc run bị kill, có thể còn bảng `_ingest_`; kiểm tra bảng và run tương ứng trước khi dọn thủ công. Chúng chứa dữ liệu nguồn, nên áp dụng cùng quyền hạn và chính sách bảo vệ như Bronze.
- Adapter chờ SQL hoàn thành, thất bại khi trạng thái FAILED/CANCELED/CLOSED hoặc quá 600 giây mỗi statement. Khi quá hạn/lỗi polling, yêu cầu cancel theo best effort; không coi yêu cầu cancel là xác nhận statement đã dừng. Giữ một run đồng thời và kiểm tra Query History trước khi retry sau timeout. Output chỉ gồm tên bảng/count/trạng thái, không in dòng dữ liệu hay nội dung lỗi SQL từ server.

## Kiểm tra code

Test nằm trong `data/tests`: Delta MERGE thật cho 13 bảng chạy hai lần, update/insert, bảng rỗng, giữ UTC/decimal/soft-delete, khóa lỗi, schema lệch, rollback khi constraint fail, nguồn đổi sau snapshot và dọn staging. Test adapter kiểm tra polling/failure/timeout; test notebook kiểm tra widgets và nghiệm thu hai lần.

Container dưới đây **chỉ chạy test Spark/Delta local**, không cài Databricks hoặc Lakebase và không cần tài khoản workspace. Không phải bước setup trên web của bạn. Hook pre-commit chạy cùng các kiểm tra này để bảo vệ code đã commit:

```powershell
docker build -f data/Dockerfile.test -t daln-data-test data
docker run --rm daln-data-test ruff check .
docker run --rm daln-data-test ruff format --check .
docker run --rm daln-data-test pytest -q tests
```

Image dùng Java 17, Spark 3.5.7 và Delta 3.3.2 theo [ma trận tương thích Delta](https://docs.delta.io/releases/). Dependency Python và jar Delta được tải lúc build; không trộn vào image backend/frontend. Để chạy test bằng Python trực tiếp, cần Java 17, `pip install -r data/requirements-test.txt`, rồi `python -m pytest -q data/tests`; lần đầu Spark cần tải jar từ Maven. Chi tiết các lớp kiểm tra khác ở [Testing](TESTING.md).

## Phần còn Planned

- Kết nối backend với Lakebase và kiểm tra migration/seed trên database thật.
- Chạy E1 trên catalog nguồn thật hai lần; cấu hình Job và xác nhận quyền Run as.
- E2 Silver, E3 Gold và toàn bộ gate E4.
- E5 Dashboard, E6 Genie: chỉ bắt đầu sau khi E4 đạt.
