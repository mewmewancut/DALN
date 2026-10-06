# E3 — Gold

**Trạng thái:** Implemented; nghiệm thu workspace ngày 06/10/2026.

Gold có sáu bảng Delta trong `fashion.gold`. Entry riêng là
[`03_gold_aggregate.py`](../data/03_gold_aggregate.py); Job chính `00_pipeline.py`
chạy E1 → E2 → E3. Metric theo [Planning C9](PLANNING.md#c9-thống-kê-shop-shop_statspy).
[Gate E4](E4_QUALITY.md) đã PASS; [Genie admin/shop](GENIE_CHATBOT.md) dùng các
bảng Gold này. Dashboard Databricks E5 còn **Planned**.

## Bảng và metric

| Bảng | Grain | Nguồn và ý nghĩa |
|---|---|---|
| `revenue_daily` | ngày giao VN, shop | SUM total_amount của fact_orders DELIVERED; delivered_orders là số đơn giao ngày đó; tên shop từ dim_shops |
| `revenue_monthly` | tháng giao VN, shop | Rollup revenue_daily; month là DATE ngày đầu tháng |
| `orders_summary_daily` | ngày VN, shop | total_orders và cancelled theo created_date_vn; delivered và aov theo delivered_date_vn; xem chi tiết bên dưới |
| `top_products` | shop, product | Item DELIVERED nối variant để lấy product_id, SUM quantity và SUM unit_price × quantity; tên hiện tại từ dim_products, rating từ fact_reviews |
| `low_stock_current` | dòng inventory đang thấp | fact_inventory WHERE is_low, kèm tên shop/product, size/color Silver, quantity và threshold |
| `shop_performance` | shop | Doanh thu DELIVERED, số đơn mọi trạng thái, tỷ lệ hủy, AOV toàn thời gian và số product |

Gold chỉ dùng `created_date_vn`/`delivered_date_vn` từ Silver, không đọc timestamp để
tự chuyển múi giờ nữa. Tiền giữ DECIMAL; tỷ lệ hủy là tỷ lệ 0–1, không nhân 100.
AOV và cancel_rate trả NULL khi mẫu số bằng 0. Không cộng/trung bình trực tiếp
các tỷ lệ hoặc AOV của nhiều ngày/shop: phải tính lại từ tổng tiền và tổng số đơn.

### Ngày tạo và ngày giao trong orders_summary_daily

Người dùng cho phép chọn cách xử lý điểm chưa rõ của E3 trong task ngày 06/10/2026.
Chọn giữ định nghĩa C9 để Gold khớp API thống kê hiện có:

- `total_orders`: số đơn được tạo trong ngày, mọi trạng thái.
- `cancelled`: số đơn tạo trong ngày có trạng thái hiện tại CANCELLED.
- `cancel_rate = cancelled / total_orders`; NULL nếu không có đơn tạo.
- `delivered`: số đơn giao thành công trong ngày, cùng số đếm ở revenue_daily.
- `aov`: doanh thu giao trong ngày / delivered; NULL nếu không giao đơn nào.

Đây là cách diễn giải được chọn cho E3, khác mô tả gom tất cả số đếm theo ngày
tạo của dòng bảng trong Planning. Không đổi API C9 hay tài liệu Planning.
Bảng lấy hợp ngày tạo và ngày giao. Ví dụ một đơn tạo 30/09, giao 01/10: ngày
30/09 có total_orders=1, delivered=0, aov=NULL; ngày 01/10 có total_orders=0,
delivered=1, cancel_rate=NULL và AOV bằng giá trị đơn. Vì dùng hai mốc ngày,
delivered không nhất thiết nhỏ hơn total_orders trong cùng dòng.
Không lấy total_orders trừ delivered/cancelled để suy số đơn đang xử lý trong ngày.

## Join và dữ liệu lịch sử

Sales, review và product_count được tổng hợp riêng trước join để nhiều review,
variant hoặc product không nhân doanh thu/số đơn. top_products dùng giá snapshot
item, không dùng giá catalog hiện tại; tên product hiện tại giống API C9.
Không giới hạn top 10 khi tạo bảng; consumer tự ORDER BY/LIMIT.

Giữ shop/product inactive và số liệu lịch sử. Fact vẫn được giữ khi không có
dimension tương ứng; tên khi đó NULL. Silver chỉ áp dụng excluded_shop_ids cho
dim_shops, vì vậy loại một tên shop ở Silver không tự loại doanh thu của shop ấy.
shop_performance có cả shop chưa có đơn/product (tiền/số đếm 0, tỷ lệ/AOV NULL)
và shop_id chỉ xuất hiện trong fact/product. product_count đếm tất cả product,
kể cả inactive; không đếm variant. is_low dùng đúng cờ Silver, quantity bằng
threshold không bị xem là thấp.

## Chạy, lỗi và overwrite

- Gold được refresh đầy đủ mỗi lượt, không append, MERGE hoặc checkpoint SKIP.
  Tạo bảng nếu thiếu bằng projection rỗng, rồi `INSERT OVERWRITE TABLE` trong một
  Delta commit cho từng bảng. Nguồn rỗng xóa các nhóm cũ; schema không tự mở rộng.
- revenue_daily chạy trước revenue_monthly/orders_summary_daily. Silver thành
  công mới chạy Gold; lỗi ghi/query Gold làm Job fail và dừng các bảng tiếp theo.
- Một bảng ghi nguyên tử; sáu bảng không có transaction chung. Retry refresh lại
  đủ sáu bảng sau lỗi. Không dùng kết quả của một Job fail cho báo cáo nghiệm thu.
- Nếu fact_orders thiếu shop_id/ngày tạo hoặc đơn DELIVERED thiếu ngày giao, fail
  trước khi ghi bảng Gold để tránh doanh thu dưới ngày NULL.
- Giới hạn một writer; không chạy notebook Gold riêng đồng thời Job chính.
  Notebook riêng đọc Silver hiện có, không đợi CDC hoặc refresh E1/E2.
- Nếu preflight xác minh E1/E2 không đổi và metadata_warehouse_id có giá trị,
  Job SKIP E1/E2 và chạy cùng SQL Gold qua warehouse đó, không khởi tạo Spark
  notebook. Gold vẫn overwrite, không còn lượt Job hoàn toàn không ghi bảng.
- Nếu E1/E2 có thay đổi hoặc preflight không xác minh được, chạy Spark E1→E2→E3.
  Để warehouse ID rỗng thì luôn dùng Spark. Notebook Gold riêng có warehouse ID
  sẽ dùng warehouse trực tiếp. Lỗi ghi Gold qua warehouse làm Job fail, không tự
  chạy writer thứ hai trên Spark.
- `timings_seconds.gold` ghi thời gian Gold; giữ số đo preflight/startup/E1/E2.
  Không cam kết latency vì warehouse/compute có thể cần startup.

Run as cần USE CATALOG/SCHEMA, SELECT Silver, CREATE SCHEMA/CREATE TABLE và quyền
ghi bảng Gold; cần CAN USE warehouse khi chọn nhánh warehouse. Không cấp quyền
cho buyer/shop qua frontend và không đưa credential vào notebook/widget.

## Kiểm thử

```powershell
docker run --rm -v D:/DALN/data:/data daln-data-test pytest -q tests/test_gold_transform.py tests/test_gold_job.py tests/test_gold_acceptance.py tests/test_bronze_job.py tests/test_pipeline_preflight.py tests/test_notebook.py
docker run --rm -v D:/DALN/data:/data daln-data-test pytest -q tests --ignore-glob=tests/test_genie*.py
docker run --rm -v D:/DALN/data:/data daln-data-test ruff check .
docker run --rm -v D:/DALN/data:/data daln-data-test ruff format --check .
```

Lệnh suite rộng chạy toàn bộ pipeline E1–E4; test Genie nằm ngoài phạm vi E3.

Test Delta kiểm tra đủ sáu bảng, hai mốc ngày/tháng, timezone session khác UTC,
snapshot giá, nhiều variant/review/product, không có rating, shop/product ẩn,
shop rỗng/thiếu dimension, shop chỉ có product và biên năm, chia 0, chạy lại
không nhân đôi và overwrite nguồn rỗng. Lỗi biểu thức SQL trong overwrite Delta
ở bảng thứ hai giữ nguyên bảng bị lỗi và các bảng sau; retry refresh đủ sáu
bảng và khớp tổng/AOV mới, lượt tiếp theo không nhân đôi. Input thiếu shop_id,
ngày tạo hoặc ngày giao DELIVERED bị từ chối; kiểm tra cả khi Gold đã có dữ liệu
để bảo đảm không ghi đè kết quả cũ. Test điều phối kiểm tra E1/E2 lỗi chặn Gold,
notebook riêng chỉ chạy Gold, preflight vẫn bắt thay đổi nguồn và Gold warehouse
fail không báo thành công.
Nghiệm thu chỉ đọc (nguồn ổn định, Job chính đã thành công):

```powershell
python data/gold_acceptance.py --profile daln-cdc --warehouse-id 261b45209f3d8a59 --source-catalog daln_source
```

Công cụ so projection sáu bảng bằng EXCEPT ALL hai chiều, rồi đối chiếu tổng
doanh thu/số đơn/số đơn giao với Lakebase federation. Không chạy tự động trong
Job; E3 không thay gate E4. Test chạy SQL nghiệm thu trên Delta thật, phát hiện
projection sai dù count không đổi và tổng nguồn lệch; CLI trả exit code 1 khi
lỗi, không in PASS hay dữ liệu lỗi. Thông báo cuối chỉ xác nhận E3 và nêu rõ
không chứng nhận E4. Dashboard/Genie chỉ được mở sau khi gate E4 PASS đủ 5/5;
chúng nằm ngoài phạm vi rà soát E3 này.

## Bằng chứng nghiệm thu — 06/10/2026

Đã đồng bộ bảy source/module thay đổi lên Workspace và đối chiếu nội dung.
Job `DALN` (ID `712610164863330`) giữ nguyên cấu hình, checkpoint và giới hạn một
lượt đồng thời; entry `00_pipeline` nay chạy thêm E3. Nguồn không đổi trong hai
lượt; 13 Bronze và 7 Silver SKIP, Gold overwrite qua warehouse `261b45209f3d8a59`.

| Lượt Job | Kết quả | Tổng thời gian | Preflight | Gold | Spark startup |
|---|---|---:|---:|---:|---:|
| `1041277866370402` | SUCCESS, tạo Gold lần đầu | 111.059 giây | 53.531 giây | 44.558 giây | 0 |
| `862794641473473` | SUCCESS, overwrite lại | 63.269 giây | 28.570 giây | 23.370 giây | 0 |

| Bảng | Số dòng | Đối chiếu projection hai chiều |
|---|---:|---|
| revenue_daily | 12 | PASS |
| revenue_monthly | 4 | PASS |
| orders_summary_daily | 36 | PASS |
| top_products | 21 | PASS |
| low_stock_current | 19 | PASS |
| shop_performance | 3 | PASS |

`gold_acceptance.py` PASS cả trước và sau lượt hai. Tổng doanh thu Gold/Lakebase
cùng **12.293.000 VND**, tổng đơn **36**, số đơn DELIVERED **12**. Snapshot chỉ đọc
đối chiếu toàn bộ dòng của cả sáu bảng giữa hai lượt cho kết quả giống hệt nhau.
Không sửa dữ liệu vận hành để làm test workspace.

Local: toàn bộ suite data **119 passed**; sau bổ sung dữ liệu nhiều đơn giao cùng
ngày và kiểm tra loại nhóm cũ, toàn bộ `test_gold_transform.py` **6 passed**.
Sau chỉnh thông báo log, test preflight/job/nghiệm thu **31 passed**. Ruff lint,
format và diff check pass. Không thay backend/frontend nên không chạy lại suite
ứng dụng. Hai lượt workspace kiểm chứng nhánh warehouse; nhánh Gold Spark được
kiểm chứng bằng Delta local, chưa chạy riêng trên workspace. Notebook E3 riêng
đã upload và có test entry local, chưa chạy riêng trên workspace.

Các số đo trên là hai lượt với nguồn ổn định và warehouse sẵn sàng, không phải
cam kết thời gian cho nguồn có thay đổi/startup compute. Tại lần nghiệm thu E3,
E4–E6 chưa thực hiện; trạng thái mới nằm ở tài liệu gate/chatbot liên kết đầu trang.

## Rà soát local bổ sung — 06/10/2026

Gold E3 đã nằm trong HEAD ở đầu lượt rà soát này; các thay đổi chatbot/UI đang
mở được giữ nguyên. Không đổi query, schema hoặc metric. Sửa thông báo CLI về
E4 sau khi regression test tái hiện lỗi; bổ sung các nhánh kiểm chứng mô tả ở trên.
Suite E3/điều phối **59 passed**; toàn bộ pipeline E1–E4 (loại test Genie theo
lệnh ở mục Kiểm thử) **151 passed**. Ruff lint, format (55 file), Compose config
với `.env.example` và `git diff --check` PASS.

Không chạy lại Job hoặc nghiệm thu trên Databricks trong lượt này; kết quả local
không chứng nhận gate E4 trên workspace. Bằng chứng workspace ở phần trên và
[E4 Quality](E4_QUALITY.md) thuộc các lượt nghiệm thu trước. Dashboard/Genie
nằm ngoài phạm vi thay đổi này.
