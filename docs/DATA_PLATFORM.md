# Data platform — E1/E2/E3

E1/E2 dùng Lakebase CDC và Spark trên serverless notebook compute. E3 đã triển khai và nghiệm thu sáu bảng Gold; nghiệp vụ, cách chạy và bằng chứng nằm ở [E3_GOLD.md](E3_GOLD.md). E4–E6 còn **Planned**. Không triển khai Dashboard/Genie trước gate E4. Phạm vi bảng và nghiệp vụ theo [Planning phần E](PLANNING.md#phần-e--data-platform-databricks), cách xử lý ngày tạo/ngày giao E3 được ghi rõ trong tài liệu Gold.

Người dùng đã duyệt đổi cách lấy dữ liệu E1 từ đọc Lakebase đầy đủ mỗi lượt sang CDC để tối ưu Job. Catalog đích vẫn là `fashion`; Bronze vẫn 13 bảng E1 và Silver vẫn 7 bảng E2. Feed nguồn có thể chứa nhiều bảng hơn nhưng pipeline không sao chép bảng ngoài allow-list E1.

## Luồng chạy

`Lakebase → fashion_cdc.bronze.lb_*_history → fashion.bronze → fashion.silver → fashion.gold`

- Lakebase CDF ghi thay đổi vào Delta history trên external managed storage S3. [Yêu cầu chính thức](https://docs.databricks.com/aws/en/oltp/projects/lakebase-cdf): Postgres 16+, REPLICA IDENTITY FULL và catalog đích không dùng default storage. Free Edition cần external catalog cho feed.
- Lần đầu, E1 chốt một version Delta nguồn, dựng trạng thái mới nhất theo id và MERGE snapshot vào Bronze. Xóa dòng Bronze cũ không còn trong snapshot, bao gồm khi nguồn rỗng.
- Các lượt sau chỉ đọc commit mới bằng Structured Streaming, `availableNow=True`, rồi kết thúc. [Serverless hỗ trợ trigger này](https://docs.databricks.com/aws/en/compute/serverless/streaming). Không duy trì stream chạy vô hạn.
- E1 lưu offsets riêng cho mỗi bảng trong Volume, kèm source/target table ID và version. Nếu source version không đổi thì không mở stream, không đọc lại history và không MERGE.
- Mỗi microbatch lấy sự kiện cuối của từng id theo LSN/sort order. insert/postimage upsert; delete/preimage là tombstone, nên cả đổi primary key được xử lý. Timestamp `_ingested_at` lấy từ sự kiện CDC để retry tạo cùng giá trị.
- Checkpoint chỉ tiến khi MERGE hoàn tất. Nếu lỗi giữa MERGE và ghi marker, retry dùng lại offsets; dữ liệu không nhân đôi. Không chạy nhiều writer vào cùng checkpoint/target.
- E2 kiểm tra version/ID của đúng bảng phụ thuộc, danh sách shop bị loại và version phép biến đổi. Chỉ refresh bảng bị ảnh hưởng; fact_order_items chạy sau fact_orders, fact_inventory sau dim_variants. Xem [hướng dẫn Silver](E2_SILVER.md).
- Khi cấu hình `metadata_warehouse_id`, Job kiểm tra checkpoint qua Files API và đọc metadata Delta qua SQL warehouse trước khi gọi Spark của notebook. Chỉ khi **toàn bộ tầng được yêu cầu** khớp source/target ID, version nguồn, fingerprint và target Silver, Job mới trả SKIP sớm. Không đọc dữ liệu nghiệp vụ, không ghi bảng/checkpoint trong bước này.
- Preflight đọc `DESCRIBE DETAIL` song song tối đa 4 request và gộp version của các bảng vào một query `DESCRIBE HISTORY ... LIMIT 1`/`UNION ALL`. Query version có `uuid()` ở kết quả để tránh dùng SQL result cache. Không suy ra thay đổi dữ liệu từ timestamp của Unity Catalog.
- Nếu có thay đổi, thiếu marker/bảng, metadata không đầy đủ hoặc warehouse lỗi, Job chạy luồng Spark bình thường và kiểm tra lại toàn bộ; không coi lỗi kiểm tra là SKIP. Preflight dùng chung ngân sách 60 giây cho các lượt đọc, cộng thời gian HTTP/retry/cancel giới hạn của SDK; câu SQL còn chạy khi hết hạn được yêu cầu hủy.
- Trong luồng Spark, metadata được lấy song song tối đa hai request và dùng chung giữa E1/E2; writer và stream vẫn chạy tuần tự. Metadata nguồn chốt trước xử lý; commit đến sau được xử lý ở lượt kế tiếp, không tăng checkpoint lên version chưa đọc.

Job dùng SDK có sẵn trong runtime cho preflight khi bật `metadata_warehouse_id`; không cài pip hoặc restart Python trong lượt chạy. Không chạy kiểm tra count nguồn hai lần và không tạo staging Bronze. Silver chỉ tạo staging khi cần refresh để kiểm tra khóa, rejection và MERGE cùng một snapshot. MERGE chỉ update dòng có giá trị khác. Để trống warehouse ID thì chạy trực tiếp bằng Spark như trước.

`timings_seconds` tách `preflight`, `spark_startup`, `bronze`, `silver`, `gold`. `spark_startup` đo từ trước query đầu `SELECT 1` đến khi nhận kết quả; log thông báo trước lúc chờ. Khi E1/E2 SKIP sớm, startup và thời gian hai tầng bằng 0; Gold vẫn overwrite qua warehouse đã cấu hình. Notebook E1/E2 riêng vẫn có thể SKIP và không ghi bảng. Thời gian tổng Job gồm khởi tạo Python/điều phối ngoài các số đo này. Không có cam kết latency cố định từ serverless.

## File

| File | Vai trò |
|---|---|
| `data/00_pipeline.py` | Entry Job chính: E1 rồi E2 rồi E3; dùng warehouse cho Gold khi E1/E2 SKIP sớm |
| `data/01_bronze_ingest.py` | Notebook demo riêng: chỉ nạp CDC vào Bronze |
| `data/02_silver_transform.py` | Notebook demo riêng: chỉ cập nhật Silver từ Bronze hiện có |
| `data/03_gold_aggregate.py` | Notebook riêng: overwrite 6 Gold từ Silver hiện có |
| `data/gold_queries.py`, `gold_transform.py`, `gold_job.py` | SQL metric và full overwrite Gold trên Spark/warehouse |
| `data/gold_acceptance.py` | Nghiệm thu E3 chỉ đọc, projection và tổng số liệu so Lakebase; không thay gate E4 |
| `data/cdc_ingest.py`, `cdc_merge.py` | Bootstrap, offsets, validation và MERGE CDC |
| `data/silver_job.py`, `silver_transform.py`, `silver_queries.py` | Dependency skip và biến đổi Silver |
| `data/pipeline_job.py`, `bronze_ingest.py` | Điều phối, widget và allow-list/identifier |
| `data/delta_metadata.py` | Prefetch metadata có giới hạn, dùng chung snapshot giữa các stage |
| `data/pipeline_preflight.py`, `warehouse_metadata.py` | Kiểm tra điều kiện SKIP trước khi khởi tạo Spark của notebook |
| `data/warehouse_sql.py` | SQL Statement Execution adapter, deadline/poll/cancel; dùng cho preflight và nghiệm thu |
| `data/acceptance.py` | Nghiệm thu chỉ đọc, chạy riêng qua warehouse |
| `data/tests/`, `Dockerfile.test`, `requirements-test.txt`, `requirements.txt`, `ruff.toml`, `.dockerignore` | Test Delta local, dependency và cấu hình kiểm tra |

`data/00_pipeline.py` vẫn là entry của Job chính. Ba notebook riêng gọi cùng điều phối với stage bronze/silver/gold, dùng cùng widget; Gold không dùng checkpoint riêng. Entry tương thích `01_bronze_job.py` đã bỏ. Gate chất lượng E4 còn **Planned**; danh sách file hiện có nằm ở bảng trên.

## Setup một lần

1. Chuẩn bị Lakebase database ứng dụng, migration và dữ liệu theo [Deployment guide](DEPLOYMENT_GUIDE.md#kết-nối-web-với-lakebase). Compose dùng `DATABASE_URL` trong `.env` để chọn Lakebase; file mẫu vẫn dành cho local/test.
2. Bật Lakebase CDF cho schema ứng dụng; mọi bảng tham gia phải có REPLICA IDENTITY FULL. Khi thêm bảng mới, migration cần cấu hình lại thuộc tính này. Không bật Delta CDF hay tự sửa/drop các bảng history do Lakebase quản lý.
3. Tạo storage credential, external location, catalog `fashion_cdc` trên S3 cùng vùng metastore; tạo schema `bronze`. Với S3 dùng IAM trust/external ID đúng workspace và quyền giới hạn bucket, không đưa access key vào code.
4. Tạo Volume và namespace:
   ```sql
   CREATE VOLUME IF NOT EXISTS fashion_cdc.bronze.pipeline_checkpoints;
   CREATE SCHEMA IF NOT EXISTS fashion.bronze;
   CREATE SCHEMA IF NOT EXISTS fashion.silver;
   CREATE SCHEMA IF NOT EXISTS fashion.gold;
   ```
5. Đồng bộ toàn bộ thư mục `data` trong Git folder. Các file có header Databricks notebook là notebook, module hỗ trợ giữ dạng Workspace file. Không chỉ copy notebook thiếu module.
6. Tạo một Notebook task trỏ tới `data/00_pipeline.py` trên serverless compute, **Maximum concurrent runs = 1**, **Performance optimized = bật**. Runtime cung cấp Spark/Delta và SDK; không cài requirements-test vào Databricks.
7. Điền task parameters:

| Parameter | Mặc định |
|---|---|
| `source_catalog` | `fashion_cdc` |
| `source_schema` | `bronze` — chứa bảng history, không phải schema Postgres |
| `target_catalog` | `fashion` |
| `checkpoint_root` | `/Volumes/fashion_cdc/bronze/pipeline_checkpoints` |
| `excluded_shop_ids` | Rỗng; chỉ điền ID shop test đã biết |
| `metadata_warehouse_id` | Rỗng để dùng Spark trực tiếp; điền SQL warehouse ID để bật SKIP trước Spark |

Run as cần SELECT history, USE CATALOG/SCHEMA, READ/WRITE VOLUME checkpoint, CREATE TABLE và SELECT/MODIFY Bronze/Silver/Gold; quyền quản lý staging Silver. Gold có thể tạo schema khi thiếu; dùng warehouse cần CAN USE và quyền ghi Gold. Chạy tay trước demo hoặc lịch 15 phút theo Planning. Dừng lịch/Job Bronze cũ trước khi bật Job mới; không chạy notebook chính chồng Job.

Preflight cần thêm CAN USE trên warehouse được chọn, dùng danh tính Run as hiện có; không đặt token trong widget/code. Warehouse dừng có thể cần startup và phát sinh compute để kiểm tra metadata. Bản tối ưu không bật chế độ giữ warehouse chạy liên tục. Workspace DALN dùng warehouse sẵn có `261b45209f3d8a59`; đây là cấu hình task, không hard-code trong Python. Muốn tắt preflight chỉ cần đặt `metadata_warehouse_id` rỗng.

## Demo từng bước Bronze → Silver

Đồng bộ cả thư mục `data` lên Git folder/Workspace để hai notebook mới có đầy đủ module. Dùng cùng catalog, `checkpoint_root` và `excluded_shop_ids` như Job chính; không tạo checkpoint mới cho demo. Các notebook riêng cũng chạy trên serverless compute và trả kết quả/timing của đúng tầng được chọn.

1. Chờ Job chính hoàn tất; trong khi demo, không chạy Job chính hoặc notebook khác đồng thời vào cùng checkpoint/bảng đích.
2. Chọn một sản phẩm, ghi nhận `id` và tên hiện tại trong `fashion.bronze.products` và `fashion.silver.dim_products`. Sửa tên qua website/API của shop sở hữu sản phẩm.
3. Chờ thay đổi xuất hiện trong `fashion_cdc.bronze.lb_products_history`. Bronze/Silver vẫn giữ giá trị trước đó nếu chưa chạy pipeline.
4. Chạy [`01_bronze_ingest.py`](../data/01_bronze_ingest.py): tên mới xuất hiện ở `fashion.bronze.products`; `fashion.silver.dim_products` chưa cập nhật vì notebook không chạy Silver.
5. Chạy [`02_silver_transform.py`](../data/02_silver_transform.py): tên mới xuất hiện ở `fashion.silver.dim_products`. Notebook chỉ đọc Bronze hiện có, không nạp thêm CDC.
6. Khi nguồn không đổi, chạy lại từng notebook sẽ SKIP các bảng đã xử lý. Có thể dùng `00_pipeline.py` cho các lượt chạy hệ thống tiếp theo như trước.

Đối chiếu giá trị theo cùng `id` thay vì chỉ đếm dòng: sửa tên không làm tăng số dòng. Ghi nhận tên cũ để có thể khôi phục qua website/API sau demo, rồi chạy Job chính để đồng bộ lại các tầng. Kiểm thử local xác nhận mỗi notebook chỉ gọi tầng được chọn, trả kết quả đúng tầng và không báo thành công khi tầng đó lỗi; việc chạy hai entry mới trên workspace thật chưa được xác minh.

## Lỗi và recovery

- Thiếu history, event/key/ordering lỗi hoặc schema khác: fail trước checkpoint; sửa nguồn/cấu hình rồi retry.
- Source/target bị drop/recreate hoặc version lùi: fail, không tự bỏ dữ liệu hay bỏ checkpoint.
- CDF schema change gây overwrite/re-snapshot: stream mặc định fail thay vì skip commit. Sau khi xác minh schema mới và feed ổn, dùng **checkpoint_root mới** để bootstrap/reconcile lại toàn bộ Bronze rồi Silver. Giữ checkpoint cũ để điều tra; không xóa tùy tiện offsets.
- Mất marker nhưng vẫn còn thư mục stream: fail, cần rebuild có chủ đích. Marker/offsets phải lưu cùng Volume, không dùng `/tmp`.
- Transaction Delta theo từng bảng, không có transaction cho 20 bảng. Nếu lỗi giữa pipeline, không báo thành công; retry hoàn tất các bảng còn lại. E2 chỉ chạy sau toàn bộ E1 thành công.
- Khi sửa phép biến đổi Silver, tăng `TRANSFORM_VERSION` trong `silver_job.py` để không bỏ qua bảng cần refresh.
- CDF là Public Preview; Free Edition có quota. Thời gian thực tế còn gồm startup compute, S3 và tải dữ liệu. Đo Job thật, không suy ra benchmark từ test local.

## Nghiệm thu E1/E2

Với nguồn ổn định, chạy toàn bộ Job hai lượt. Lượt đầu bootstrap/refresh, lượt tiếp theo phải SKIP 13 Bronze và 7 Silver khi không có thay đổi. Số dòng và giá trị nghiệp vụ không đổi. Sau đó chạy kiểm tra **riêng**, không đưa vào lịch Job:

```powershell
python data/acceptance.py --profile <profile> --warehouse-id <warehouse-id> --source-catalog daln_source
```

`source_catalog` ở lệnh nghiệm thu là catalog **Lakebase federation** đã đăng ký. Công cụ đối chiếu count/khóa 13 Bronze với nguồn và so toàn bộ 7 Silver với projection Planning E2 bằng EXCEPT ALL hai chiều, in PASS từng bảng. Nghiệm thu local cần SDK trong `data/requirements.txt`. Có shop loại trừ thì thêm `--excluded-shop-ids 90001,90002` (ID minh họa).

Test local chạy bootstrap/retry/update/delete thật, offsets qua restart, nguồn rỗng, schema/key lỗi, transaction, dependency propagation, timezone và nghiệp vụ E2. Test local không thay thế nghiệm thu Job thật.

```powershell
docker build -f data/Dockerfile.test -t daln-data-test data
docker run --rm daln-data-test ruff check .
docker run --rm daln-data-test ruff format --check .
docker run --rm daln-data-test pytest -q tests
```

### Bằng chứng workspace — 04/10/2026

Job `DALN E1 E2 CDC` (ID `712610164863330`) chạy tay, serverless environment version 4, maximum concurrent runs 1, checkpoint Volume như trên. Lakebase CDF có 23 history tables STREAMING; E1 chỉ nhận 13 bảng Planning. Backend Docker local chưa đổi kết nối.

| Kiểm tra | Kết quả |
|---|---|
| Bootstrap E1→E2, run `466393436616499` | SUCCESS; khoảng 404 giây gồm startup/khởi tạo |
| Lượt không đổi trước prefetch, run `402693782258521` | SUCCESS; 13 Bronze + 7 Silver SKIP; tổng Job 85.96 giây |
| Lượt không đổi sau prefetch, run `1032837227480655` | SUCCESS; 20 bảng SKIP; tổng Job 47.40 giây, E1 28.96 giây/E2 7.78 giây |
| CDC thật, run `1041715882610161` | SUCCESS; ghi lại cùng giá trị category ở Lakebase, chỉ categories CDC và dim_products refresh; tổng Job 97.71 giây |
| Nghiệm thu nguồn→Bronze | 13 bảng khớp count, id không NULL/trùng; tổng 571 dòng |
| Nghiệm thu Silver | Cả 7 projection khớp EXCEPT ALL hai chiều; counts 3/45/135/36/72/135/0 theo thứ tự bảng E2 |
| Kiểm tra local/pre-commit | 69 test data, 162 backend, 89 frontend pass; lint/format, migration, build, audit và smoke test pass |

Số đo lượt không đổi giảm khoảng 45% overhead Job so với bản CDC chưa prefetch; đây không phải benchmark cho lượt có nhiều dữ liệu mới. Lần bootstrap đọc toàn bộ history một lần; lượt thường chỉ đọc commit mới. E3/E4 và chuyển backend đang chạy local sang Lakebase nằm ngoài task E1/E2.

### Cutover website sang Lakebase — 04/10/2026

Sau nghiệm thu E1/E2 ở trên, backend trên máy đã chuyển sang database Lakebase `fashion`. Người dùng chọn giữ dữ liệu Lakebase hiện có, không chuyển dữ liệu Docker. Runtime dùng role `daln_app` và SSL; cấu hình, quyền và rollback nằm ở [Deployment guide](DEPLOYMENT_GUIDE.md#kết-nối-web-với-lakebase). Frontend/backend vẫn chạy local; database Docker giữ bản cũ và database test riêng.

- Kết nối thật xác nhận host Lakebase, current_user `daln_app`, SSL và không có quyền tạo schema/table hoặc quản lý database/role. Schema khớp toàn bộ model; Alembic revision `20260929_0008`.
- API catalog, đăng nhập buyer/shop/admin và danh sách admin đọc đúng 9 user/45 product/36 order từ Lakebase. Sai role và shop khác bị từ chối. Thử tăng ngưỡng tồn kho variant 10 rồi khôi phục ngay giá trị gốc; kiểm tra trực tiếp database xác nhận cả lần ghi và khôi phục. Không đổi số lượng tồn kho hoặc đơn hàng.
- Job E1/E2 run `350942916805940` **SUCCESS**: chỉ inventory có CDC, chỉ fact_inventory refresh (135 dòng); 18 bảng còn lại SKIP. Thời gian tổng khoảng 193 giây, gồm startup; E1 150.715 giây/E2 30.805 giây. Đây là kiểm tra cutover, không phải benchmark.
- Nghiệm thu chỉ đọc sau Job: 13 Bronze khớp count/khóa với Lakebase và cả 7 Silver khớp projection hai chiều. `updated_at` variant 10 từ lần ghi API khớp giữa Lakebase và Bronze (`2026-10-04 12:45:51.837233` UTC); phép đối chiếu Silver xác nhận fact_inventory đã nhận cùng trạng thái.
- Test sau cutover: 162 backend, 3 cấu hình Compose và 7 hook pass; lint/format, frontend HTTP smoke và diff check pass. Hook khôi phục `.env` sau kiểm thử local; ba regression về khôi phục đều fail trên hook cũ.

Tại thời điểm cutover 04/10/2026, Gold E3, gate E4 và Dashboard/Genie còn **Planned**. Job chạy tay; Bronze/Silver chỉ cập nhật khi Job chạy. Trạng thái E3 mới nhất nằm ở [E3_GOLD.md](E3_GOLD.md).

### Tối ưu lượt không thay đổi — 04/10/2026

Job hiện tên `DALN`, ID `712610164863330`, vẫn gọi `00_pipeline` và dùng một task. Đã đồng bộ 5 module thay đổi lên Workspace và thêm task parameter `metadata_warehouse_id=261b45209f3d8a59`. Performance optimized, timeout 1800 giây, giới hạn một lượt đồng thời và checkpoint gốc được giữ.

| Lượt kiểm chứng | Tổng Job | Preflight | Spark startup / Bronze / Silver | Kết quả |
|---|---:|---:|---|---|
| `582034883532015` | 41.658 giây | 29.060 giây | 0 / 0 / 0 | SUCCESS, 13 Bronze + 7 Silver SKIP |
| `661197161083225` | 37.422 giây | 25.710 giây | 0 / 0 / 0 | SUCCESS, 13 Bronze + 7 Silver SKIP |

Hai lượt chạy trên warehouse đang sẵn sàng; không khởi tạo Spark của notebook, không ghi bảng/checkpoint. Kiểm tra sau chạy xác nhận timestamp checkpoint users và 7 marker Silver không đổi. Module trên Workspace đã đối chiếu khớp source local.

Kiểm tra bản tối ưu: `pytest -q tests` trong image `daln-data-test` với thư mục `data` bind mount **98 passed**; `ruff check .`, `ruff format --check .` và `git diff --check` pass. Bộ test Delta xác nhận bootstrap/CDC/retry và Silver vẫn đúng; test mới bao phủ SKIP trước Spark, metadata thiếu/sai, thay đổi source/target/config, deadline và fallback.

Lượt chậm trước đó `162214251233450` mất 839.869 giây, trong đó query Spark đầu tiên được ghi nhận gần 12 phút sau khi Job bắt đầu. Lượt đó Bronze SKIP nhưng Silver có refresh `dim_shops`; **hai lượt benchmark mới là trường hợp cả hai tầng đều không đổi**, không chứng minh latency cho lượt có dữ liệu cần xử lý. Nếu Bronze hoặc Silver cần cập nhật, hoặc preflight không xác minh được trạng thái, Job vẫn cần Spark và chịu startup của dịch vụ. Tắt preflight bằng cách để trống `metadata_warehouse_id`; không cần đổi/xóa checkpoint.
