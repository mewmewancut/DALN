# E2 — Silver

E2 giữ nguyên 7 phép biến đổi trong [Planning E2](PLANNING.md#e2-02_silver_transformpy--làm-sạch). Chạy Spark trên serverless compute sau E1; setup Job/checkpoint và nghiệm thu chung nằm tại [Data platform](DATA_PLATFORM.md).

## Bảng và phụ thuộc

| Silver | Nguồn phải đổi mới refresh | Biến đổi |
|---|---|---|
| dim_shops | bronze.shops, users; excluded_shop_ids | LEFT JOIN owner_name; loại đúng ID khai báo |
| dim_products | bronze.products, categories, shops | LEFT JOIN category_name/shop_name, giữ inactive |
| dim_variants | bronze.product_variants | TRIM + UPPER size; INITCAP(LOWER(TRIM(color))) |
| fact_orders | bronze.orders | Chuẩn hóa sáu status; bỏ total_amount NULL/<=0; thêm ngày VN |
| fact_order_items | bronze.order_items, silver.fact_orders | Gắn trạng thái/ngày/shop; giữ snapshot item |
| fact_inventory | bronze.inventory, silver.dim_variants | Gắn variant; threshold, is_low = quantity < threshold |
| fact_reviews | bronze.reviews | Chỉ nhận rating 1–5 |

Mỗi dependency được so cả Delta table ID và version. Marker lưu riêng mỗi Silver trong Volume, gồm phiên bản biến đổi, input fingerprint và target version/ID. Bảng đích bị sửa/drop hoặc tham số thay đổi sẽ được refresh; marker chỉ ghi sau MERGE thành công. Không dùng task value tạm thời làm nguồn sự thật cho skip, nên retry độc lập không bỏ sót cập nhật.

fact_order_items chạy sau fact_orders; fact_inventory sau dim_variants. Nếu order trở thành invalid, item liên quan cũng bị loại. Nếu variant đổi màu/size hoặc bị hard-delete, inventory refresh theo dimension mới. Khi tất cả input giữ nguyên, không staging, không count, không MERGE.

## Snapshot và bất biến

Khi refresh, projection được materialize vào staging Delta `_silver_*`; kiểm tra id NULL/trùng, count rejected, schema và MERGE dùng cùng snapshot. Stage được dọn trong finally. Mỗi bảng MERGE theo id, update chỉ khi giá trị khác, insert và xóa dòng không còn trong projection hợp lệ.

LEFT JOIN giữ sản phẩm/shop kể cả thiếu tên tham chiếu. Không tự lọc shop khóa hay sản phẩm/variant inactive. `excluded_shop_ids` mặc định rỗng, chỉ áp dụng dim_shops; không đoán shop test theo tên/email. Không đổi revenue/metric C9.

Timestamp gốc giữ UTC. TIMESTAMP instant tính ngày từ epoch cộng đúng 7 giờ; TIMESTAMP_NTZ nguồn hiểu là giờ UTC rồi cộng 7 giờ. NULL giữ NULL; kết quả không phụ thuộc timezone SQL session. `2026-09-30 17:00:00 UTC` thành ngày `2026-10-01`; Gold chỉ dùng cột `_date_vn`.

Log chỉ gồm bảng, count, thời gian và tổng rejected, không log dữ liệu cá nhân/review. Khóa NULL/trùng, join fanout hoặc schema drift làm task fail; không tự schema evolution. Âm tồn kho được giữ để gate E4 phát hiện. Task lỗi có thể đã hoàn tất bảng trước đó; retry an toàn, không có transaction chung bảy bảng.

## Nghiệm thu

Dùng `data/00_pipeline.py` hai lượt với nguồn ổn định, sau đó `data/acceptance.py` theo [hướng dẫn](DATA_PLATFORM.md#nghiệm-thu-e1e2). So cả giá trị 7 Silver với projection chuẩn; kiểm tra không duplicate id, status/amount/rating hợp lệ, không orphan item, inventory flag đúng và item snapshot không bị đổi theo catalog.

Test Delta local cover đủ 7 bảng, sáu status, decimal/inactive, rating biên/NULL, giờ 17:00 UTC, TIMESTAMP/TIMESTAMP_NTZ trong UTC/VN/Los Angeles, invalid→valid và ngược lại, join fanout/schema/rollback/dọn stage; test dependency cover no-op, order→items, variant→inventory, đổi exclusion, sửa target và retry khi marker chưa tiến.

Gold E3 được mô tả tại [E3_GOLD.md](E3_GOLD.md); E4–E6 còn Planned. Nghiệm thu E1/E2 không thay thế gate Gold E4.
