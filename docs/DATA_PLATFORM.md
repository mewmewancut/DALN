# Data platform — E1/E2

E1/E2 dùng Lakebase CDC và Spark trên serverless notebook compute. E3–E6 còn **Planned**. Không triển khai Dashboard/Genie trước gate E4. Phạm vi bảng và nghiệp vụ vẫn theo [Planning phần E](PLANNING.md#phần-e--data-platform-databricks).

Người dùng đã duyệt đổi cách lấy dữ liệu E1 từ đọc Lakebase đầy đủ mỗi lượt sang CDC để tối ưu Job. Catalog đích vẫn là `fashion`; Bronze vẫn 13 bảng E1 và Silver vẫn 7 bảng E2. Feed nguồn có thể chứa nhiều bảng hơn nhưng pipeline không sao chép bảng ngoài allow-list E1.

## Luồng chạy

`Lakebase → fashion_cdc.bronze.lb_*_history → fashion.bronze → fashion.silver`

- Lakebase CDF ghi thay đổi vào Delta history trên external managed storage S3. [Yêu cầu chính thức](https://docs.databricks.com/aws/en/oltp/projects/lakebase-cdf): Postgres 16+, REPLICA IDENTITY FULL và catalog đích không dùng default storage. Free Edition cần external catalog cho feed.
- Lần đầu, E1 chốt một version Delta nguồn, dựng trạng thái mới nhất theo id và MERGE snapshot vào Bronze. Xóa dòng Bronze cũ không còn trong snapshot, bao gồm khi nguồn rỗng.
- Các lượt sau chỉ đọc commit mới bằng Structured Streaming, `availableNow=True`, rồi kết thúc. [Serverless hỗ trợ trigger này](https://docs.databricks.com/aws/en/compute/serverless/streaming). Không duy trì stream chạy vô hạn.
- E1 lưu offsets riêng cho mỗi bảng trong Volume, kèm source/target table ID và version. Nếu source version không đổi thì không mở stream, không đọc lại history và không MERGE.
- Mỗi microbatch lấy sự kiện cuối của từng id theo LSN/sort order. insert/postimage upsert; delete/preimage là tombstone, nên cả đổi primary key được xử lý. Timestamp `_ingested_at` lấy từ sự kiện CDC để retry tạo cùng giá trị.
- Checkpoint chỉ tiến khi MERGE hoàn tất. Nếu lỗi giữa MERGE và ghi marker, retry dùng lại offsets; dữ liệu không nhân đôi. Không chạy nhiều writer vào cùng checkpoint/target.
- E2 kiểm tra version/ID của đúng bảng phụ thuộc, danh sách shop bị loại và version phép biến đổi. Chỉ refresh bảng bị ảnh hưởng; fact_order_items chạy sau fact_orders, fact_inventory sau dim_variants. Xem [hướng dẫn Silver](E2_SILVER.md).
- Metadata được lấy song song tối đa hai request và dùng chung giữa E1/E2; writer và stream vẫn chạy tuần tự. Metadata nguồn chốt trước xử lý; commit đến sau được xử lý ở lượt kế tiếp, không tăng checkpoint lên version chưa đọc.

Job bình thường không dùng SQL warehouse/SDK, không cài pip hoặc restart Python, không chạy kiểm tra count nguồn hai lần và không tạo staging Bronze. Silver chỉ tạo staging khi cần refresh để kiểm tra khóa, rejection và MERGE cùng một snapshot. MERGE chỉ update dòng có giá trị khác.

## File

| File | Vai trò |
|---|---|
| `data/00_pipeline.py` | Entry Job chính: E1 rồi E2 trong một phiên compute |
| `data/01_bronze_ingest.py` | Chạy riêng E1 |
| `data/01_bronze_job.py` | Entry E1 tương thích đường dẫn Job cũ; cùng runner CDC |
| `data/02_silver_transform.py` | Chạy riêng E2 sau E1 thành công |
| `data/cdc_ingest.py`, `cdc_merge.py` | Bootstrap, offsets, validation và MERGE CDC |
| `data/silver_job.py`, `silver_transform.py`, `silver_queries.py` | Dependency skip và biến đổi Silver |
| `data/pipeline_job.py`, `bronze_ingest.py` | Điều phối, widget và allow-list/identifier |
| `data/delta_metadata.py` | Prefetch metadata có giới hạn, dùng chung snapshot giữa các stage |
| `data/acceptance.py`, `warehouse_sql.py` | Nghiệm thu chỉ đọc, chạy riêng qua warehouse |
| `data/03_gold_aggregate.py`, `04_data_quality_check.py` | Placeholder **Planned**, không có trong Job E1/E2 |

## Setup một lần

1. Chuẩn bị Lakebase database ứng dụng, migration và dữ liệu theo [Deployment guide](DEPLOYMENT_GUIDE.md). Backend local không tự chuyển sang Lakebase.
2. Bật Lakebase CDF cho schema ứng dụng; mọi bảng tham gia phải có REPLICA IDENTITY FULL. Khi thêm bảng mới, migration cần cấu hình lại thuộc tính này. Không bật Delta CDF hay tự sửa/drop các bảng history do Lakebase quản lý.
3. Tạo storage credential, external location, catalog `fashion_cdc` trên S3 cùng vùng metastore; tạo schema `bronze`. Với S3 dùng IAM trust/external ID đúng workspace và quyền giới hạn bucket, không đưa access key vào code.
4. Tạo Volume và namespace:
   ```sql
   CREATE VOLUME IF NOT EXISTS fashion_cdc.bronze.pipeline_checkpoints;
   CREATE SCHEMA IF NOT EXISTS fashion.bronze;
   CREATE SCHEMA IF NOT EXISTS fashion.silver;
   ```
5. Đồng bộ toàn bộ thư mục `data` trong Git folder. Các file có header Databricks notebook là notebook, module hỗ trợ giữ dạng Workspace file. Không chỉ copy notebook thiếu module.
6. Tạo một Notebook task trỏ tới `data/00_pipeline.py` trên serverless compute, **Maximum concurrent runs = 1**. Runtime cung cấp Spark/Delta; không cài requirements-test vào Databricks. Không cần dependency SDK cho Job thường.
7. Điền task parameters:

| Parameter | Mặc định |
|---|---|
| `source_catalog` | `fashion_cdc` |
| `source_schema` | `bronze` — chứa bảng history, không phải schema Postgres |
| `target_catalog` | `fashion` |
| `checkpoint_root` | `/Volumes/fashion_cdc/bronze/pipeline_checkpoints` |
| `excluded_shop_ids` | Rỗng; chỉ điền ID shop test đã biết |

Run as cần SELECT history, USE CATALOG/SCHEMA, READ/WRITE VOLUME checkpoint, CREATE TABLE và SELECT/MODIFY Bronze/Silver; quyền quản lý staging Silver. Chạy tay trước demo hoặc lịch 15 phút theo Planning. Dừng lịch/Job Bronze cũ trước khi bật Job mới; không chạy notebook riêng chồng Job.

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

`source_catalog` ở lệnh nghiệm thu là catalog **Lakebase federation** đã đăng ký. Công cụ đối chiếu count/khóa 13 Bronze với nguồn và so toàn bộ 7 Silver với projection Planning E2 bằng EXCEPT ALL hai chiều, in PASS từng bảng. Nghiệm thu cần SDK trong `data/requirements.txt`; Job thường không dùng SDK. Có shop loại trừ thì thêm `--excluded-shop-ids 90001,90002` (ID minh họa).

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
