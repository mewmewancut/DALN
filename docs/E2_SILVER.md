# E2 — Silver: triển khai và nghiệm thu

**Trạng thái:** đã triển khai code cho 7 bảng theo [Planning E2](PLANNING.md#e2-02_silver_transformpy--làm-sạch), có test Spark/Delta local. Nghiệm thu E1 hai lượt, cấu hình Job thật và nghiệm thu E2 trên Databricks chưa hoàn tất. E3–E6 vẫn **Planned**. Checklist E1 cần hoàn tất trước khi nghiệm thu E2 nằm ở cuối tài liệu này.

## File và dữ liệu đầu vào

- `data/02_silver_transform.py`: notebook chạy tay hoặc dùng trực tiếp làm Notebook task; một lần refresh, không cài thư viện/restart, không chạy lại Bronze.
- `data/silver_transform.py`: staging, kiểm tra khóa/schema, MERGE và dọn staging.
- `data/silver_queries.py`: phép biến đổi 7 bảng E2 và quy đổi ngày Việt Nam.
- `data/warehouse_sql.py`, `data/bronze_ingest.py`: adapter SQL và kiểm tra identifier dùng chung với E1.

Đầu vào là các bảng **Delta Bronze đã được E1 tạo**, trong cùng `target_catalog`. Không đọc Lakebase lần nữa ở E2. Kiểu/cột nguồn theo schema backend hiện tại; timestamp Bronze giữ UTC. E2 không thêm cột hoặc migration vào database ứng dụng.

| Bảng Silver | Biến đổi và cột bổ sung |
|---|---|
| `dim_shops` | Giữ các cột shops, LEFT JOIN users lấy `owner_name`; loại ID shop test được khai báo trong `excluded_shop_ids` |
| `dim_products` | Giữ các cột products kể cả inactive, LEFT JOIN lấy `category_name`, `shop_name` từ Bronze |
| `dim_variants` | Giữ cột nguồn; thay `size` bằng `UPPER(TRIM(size))`, `color` bằng `INITCAP(LOWER(TRIM(color)))`, ví dụ ` DARK bLUE ` → `Dark Blue` |
| `fact_orders` | Chuẩn hóa `status` bằng TRIM + UPPER; chỉ giữ PENDING, CONFIRMED, PREPARING, SHIPPING, DELIVERED, CANCELLED và `total_amount > 0`; thêm `created_date_vn`, `delivered_date_vn` |
| `fact_order_items` | INNER JOIN với fact_orders đã làm sạch, thêm `status`, `shop_id` và hai cột ngày; giữ nguyên snapshot tên, size/color, giá của item |
| `fact_inventory` | INNER JOIN dim_variants; thêm `product_id`, `size`, `color`, `sku`, `threshold = low_stock_threshold`, `is_low = quantity < low_stock_threshold` |
| `fact_reviews` | Giữ cột nguồn; chỉ nhận rating từ 1 đến 5, loại NULL |

Các LEFT JOIN dimension giữ lịch sử kể cả khi thiếu tên tham chiếu; nếu join nhân dòng cùng `id`, task thất bại trước MERGE. E2 không tự lọc shop khóa hoặc sản phẩm/variant inactive. Schema chưa có cờ `is_test`: mặc định `excluded_shop_ids` rỗng, không đoán shop test từ tên hoặc email. Danh sách này chỉ áp dụng cho `dim_shops` đúng phạm vi Planning E2; không tự thay đổi tập orders hoặc định nghĩa metric C9. Nếu dùng danh sách loại trừ, cần đối chiếu các join/metric khi triển khai E3–E4.

## Ngày Việt Nam và refresh

Timestamp gốc không bị sửa. Với TIMESTAMP chứa instant UTC, E2 dùng [unix_micros](https://docs.databricks.com/aws/en/sql/language-manual/functions/unix_micros), cộng đúng 7 giờ rồi tính ngày từ epoch; kết quả không phụ thuộc múi giờ phiên SQL. Với TIMESTAMP_NTZ, giá trị Bronze được hiểu là giờ UTC theo contract nguồn và cộng 7 giờ trước khi lấy ngày. NULL vẫn là NULL. Ví dụ `2026-09-30 17:00:00 UTC` → `2026-10-01`; `16:59:59.999999 UTC` vẫn là `2026-09-30`. Gold trở đi chỉ sử dụng `_date_vn`, không cộng 7 giờ thêm.

Chạy tuần tự để fact_order_items đọc fact_orders mới và fact_inventory đọc dim_variants mới. Mỗi projection được materialize một lần thành `_silver_<table>_<run_id>` trong schema Silver; kiểm tra khóa, số dòng loại, count và MERGE đọc cùng snapshot đó. Log chỉ có tên bảng, số dòng, thời gian và tổng số lỗi; không in thông tin cá nhân, nội dung review hay payload SQL từ server. Hai loại lỗi order có thể trùng nhau nên không cộng hai số log để suy ra tổng dòng bị loại.

Mỗi bảng dùng [Delta MERGE](https://docs.databricks.com/aws/en/delta/merge) theo `id`: update, insert và `WHEN NOT MATCHED BY SOURCE THEN DELETE` trên **snapshot Silver đã làm sạch**. Nhờ đó order/rating chuyển từ hợp lệ sang lỗi không còn sót ở Silver, item của order bị loại cũng biến mất khi refresh bảng item. Đây là đồng bộ bảng phân tích; không xóa dữ liệu Bronze/Lakebase. Nguồn rỗng hợp lệ sẽ làm bảng Silver tương ứng rỗng. Không chạy E2 khi E1 chưa hoàn tất.

Khóa NULL/trùng, tập tên cột thay đổi hoặc lỗi SQL làm task thất bại. Không tự bật schema evolution. Mỗi MERGE là một transaction Delta; 7 bảng không có transaction chung, bảng trước lỗi có thể đã cập nhật. Dọn staging trong `finally`; nếu run bị kill hoặc mất quyền, kiểm tra staging và Query History trước retry/dọn thủ công. Không để E1/E2 của các run khác nhau chạy chồng nhau. Rerun sau khi sửa lỗi nguồn an toàn với khóa hợp lệ.

Notebook dùng chung adapter E1 chờ SQL tối đa 10 giây trong request, tiếp tục polling với deadline nếu cần. Không chạy nghiệm thu hai lần trong task định kỳ. Thời gian thực tế trên Free Edition còn phụ thuộc queue, warehouse/compute và dữ liệu; chưa benchmark workspace thật.

## Cấu hình Databricks Free Edition

1. Đồng bộ các file ở mục đầu vào Git folder/Workspace. Import `02_silver_transform.py` thành **Python notebook**; các module hỗ trợ là **Workspace files**, giữ cùng thư mục `data`. Đưa `databricks-sdk==0.139.0` vào **Environment / Dependencies** của task serverless, giống [Job E1](DATA_PLATFORM.md#notebook-riêng-cho-job-định-kỳ).
2. Trong Job đang có task Bronze, thêm **Notebook task**, đặt key `silver`, trỏ tới `data/02_silver_transform.py`. Chọn serverless notebook compute và Environment đã cấu hình dependency. SQL vẫn thực thi trên warehouse qua SDK.
3. Đặt **Depends on** = task chạy `01_bronze_job.py`, **Run if = All succeeded**. Không chọn task notebook nghiệm thu E1 làm lịch định kỳ. Giữ **Maximum concurrent runs = 1** cho cả Job và chỉ lập lịch cho Job chứa chuỗi `bronze → silver`.
4. Cấu hình task parameters:

   | Parameter | Giá trị |
   |---|---|
   | `target_catalog` | `fashion`, hoặc catalog đích đã dùng ở E1 |
   | `warehouse_id` | ID serverless SQL warehouse của E1 |
   | `excluded_shop_ids` | Để trống nếu chưa xác định shop test; nếu có, danh sách ID dương ngăn bằng dấu phẩy, ví dụ `90001,90002` (ID minh họa, không tự điền) |
   | `statement_timeout` | `600`, đơn vị giây cho mỗi câu SQL, phải dương |

5. Danh tính **Run as** cần `CAN USE` warehouse, `USE CATALOG`, `USE SCHEMA`, `SELECT` các bảng Bronze; quyền tạo schema/bảng, `SELECT`/`MODIFY` bảng Silver và quyền quản lý/dọn staging do task tạo. Cấp quyền đúng catalog/schema của bạn, giữ schema Gold cho giai đoạn sau.
6. Chọn **Run now** cho toàn bộ Job. Chỉ coi refresh thành công khi task Silver có 7 dòng `DONE` và `Silver completed: 7 tables`. Nếu chạy notebook Silver riêng để nghiệm thu, phải chờ Bronze hoàn tất và không để lịch Job chạy đồng thời.

## Nghiệm thu E2 trên workspace

Tạm ngừng thay đổi nguồn khi so sánh hai lượt. Chạy chuỗi Bronze → Silver hai lần, lưu output/count và Job run URL. Với cùng dữ liệu nguồn, count 7 bảng Silver và giá trị nghiệp vụ phải giữ nguyên; `_ingested_at` có thể đổi theo E1 nên không dùng nó để khẳng định toàn bộ row byte-for-byte giống nhau.

Chạy các query sau trên cùng warehouse (đổi `fashion` nếu catalog khác). Các query lỗi phải trả `0` hoặc không có dòng:

```sql
SELECT COUNT(*) AS invalid_orders
FROM fashion.silver.fact_orders
WHERE status IS NULL
   OR status NOT IN ('PENDING', 'CONFIRMED', 'PREPARING', 'SHIPPING', 'DELIVERED', 'CANCELLED')
   OR total_amount IS NULL OR total_amount <= 0;

SELECT COUNT(*) AS invalid_reviews
FROM fashion.silver.fact_reviews
WHERE rating IS NULL OR rating NOT BETWEEN 1 AND 5;

SELECT COUNT(*) AS orphan_items
FROM fashion.silver.fact_order_items i
LEFT JOIN fashion.silver.fact_orders o ON i.order_id = o.id
WHERE o.id IS NULL;

SELECT COUNT(*) AS invalid_inventory_flag
FROM fashion.silver.fact_inventory
WHERE NOT (is_low <=> (quantity < threshold));

SELECT COUNT(*) AS negative_inventory
FROM fashion.silver.fact_inventory WHERE quantity < 0;

SELECT id, COUNT(*) AS duplicates
FROM fashion.silver.fact_orders GROUP BY id HAVING id IS NULL OR COUNT(*) > 1;

SELECT id, created_at, created_date_vn, delivered_at, delivered_date_vn
FROM fashion.silver.fact_orders ORDER BY id LIMIT 20;
```

Kiểm tra NULL/trùng `id` tương tự cho 6 bảng còn lại. Đối chiếu count fact_orders với Bronze sau cùng điều kiện `UPPER(TRIM(status))` và `total_amount > 0`, fact_reviews với rating 1–5. Kiểm tra sản phẩm inactive vẫn có trong dim_products; snapshot item không bị thay bằng tên/size/color/giá catalog hiện tại; inventory tại `quantity = threshold` phải có `is_low = false`. Nếu nguồn có timestamp sát 17:00 UTC, ngày VN phải chuyển đúng như ví dụ bên trên; dữ liệu không có ca biên chưa đủ chứng minh riêng nghiệm thu timezone trên workspace.

Log REJECT khác 0 cần điều tra nguồn trước khi làm E3/E4; E2 loại dữ liệu lỗi theo Planning nhưng không tự sửa database nghiệp vụ. Âm tồn kho vẫn được giữ để gate E4 phát hiện; phải sửa nguyên nhân ở nguồn. Chưa tạo Dashboard/Genie trước khi toàn bộ E4 pass.

Test local: `tests/test_silver_transform.py` chạy MERGE thật cho đủ 7 bảng, hai lượt không nhân đôi, update/insert và loại dòng cũ, dữ liệu rỗng, sáu status, rating biên/NULL, decimal, soft-delete/item snapshot, timezone UTC/VN/Los Angeles cho TIMESTAMP và TIMESTAMP_NTZ, khóa lỗi/join nhân dòng, schema drift, rollback và dọn staging. `tests/test_silver_notebook.py` kiểm tra widgets, validation trước authentication, dependency/timeout và lỗi remote không lộ payload. Lệnh chung nằm ở [Data platform](DATA_PLATFORM.md#kiểm-tra-code).

## E1 — điều kiện cần hoàn tất trước khi nghiệm thu E2

Code E1 đã được cập nhật nhưng nghiệm thu trên Databricks chưa hoàn tất. Cần xác nhận các mục sau trên workspace trước khi chạy nghiệm thu E2. Nếu đã có `two-run count check passed` cho đủ 13 bảng với nguồn ổn định và đã lưu bằng chứng, không cần chạy lại riêng nghiệm thu E1 chỉ vì triển khai E2.

1. **Bằng chứng E1:** giữ output notebook nghiệm thu với `check_twice=true`, count từng bảng khớp Lakebase và nguồn ổn định trong hai lượt. Nếu lần trước chỉ chạy một lượt/check_twice=false, thực hiện kiểm tra hai lượt theo [hướng dẫn E1](DATA_PLATFORM.md#chạy-e1-trên-databricks-web) khi Job định kỳ đang dừng.
2. **Task định kỳ:** Bronze phải trỏ tới `01_bronze_job.py`; dependency SDK nằm trong Environment riêng của Job, `source_catalog`, `warehouse_id`, catalog đích đúng; quyền Run as được kiểm tra bằng Run now. Output notebook tương tác thành công chưa xác minh danh tính/môi trường của Job.
3. **Lịch và concurrency:** chuyển lịch 15 phút hoặc chạy tay sang Job chứa cả `bronze → silver`, giữ một run đồng thời; dừng lịch Bronze riêng nếu trước đó đã tạo để tránh ghi chồng dữ liệu.
4. **Staging và hiệu suất:** kiểm tra bảng `_ingest_*` còn sót từ run lỗi và Query History trước dọn/retry; lưu thời gian từng bảng của Job thật để chọn `parallelism=2` hoặc đo thêm `4` theo tài liệu E1. Chưa có benchmark workspace từ task này.
5. **Nguồn ứng dụng:** nếu backend đã được chuyển sang Lakebase, đối chiếu `current_database()` là database ứng dụng đúng, migration/seed và dữ liệu đơn/kho mới đi vào cùng nguồn E1 đang đọc. Nếu vẫn chạy backend PostgreSQL local, kết nối backend → Lakebase còn **Planned**; E2 không tự thực hiện chuyển nguồn.
