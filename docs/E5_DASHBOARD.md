# E5 — Fashion Platform Overview

**Trạng thái:** Implemented; đã nghiệm thu SQL/workspace và browser ngày 10/10/2026.

Dashboard AI/BI chỉ dùng sáu bảng Gold của E3. Không dùng Bronze, Silver hoặc database vận hành làm nguồn visualization. Bộ dựng JSON ở `data/dashboard_definition.py`; SQL chuẩn ở `data/dashboard_queries.py`. API triển khai theo [Databricks Dashboard API](https://docs.databricks.com/aws/en/dashboards/tutorials/dashboard-crud-api).

## Metric và bộ lọc

- Bốn KPI: doanh thu DELIVERED theo ngày giao Việt Nam; số đơn mọi trạng thái theo ngày tạo; tỷ lệ hủy = tổng cancelled / tổng total_orders; AOV = tổng revenue / tổng delivered_orders. Mẫu số bằng 0 hiện NULL, không đổi thành một số liệu có ý nghĩa giả.
- Bộ lọc khoảng ngày áp dụng cho KPI, biểu đồ doanh thu ngày và phân bố trạng thái. SQL chỉ dùng ngày đã chuyển ở Silver, không cộng thêm bảy giờ.
- Top 10 shop theo doanh thu và top 10 sản phẩm theo lượng bán là **toàn thời gian**. Gold hiện không có chiều ngày cho `top_products` hoặc `shop_performance`; hai widget ghi rõ phạm vi và không chịu bộ lọc ngày.
- Bảng tồn thấp là **snapshot pipeline gần nhất**, với `quantity < threshold`; không phải tồn kho realtime.

Người dùng đã duyệt bổ sung `pending`, `confirmed`, `preparing`, `shipping` vào `gold.orders_summary_daily` ngày 10/10/2026. Bốn cột BIGINT đếm trạng thái hiện tại theo ngày tạo Việt Nam. GoldTransform thêm cột vào bảng cũ rồi overwrite dữ liệu; giữ định danh bảng và quyền Unity Catalog. Không có migration PostgreSQL.

`delivered` cũ vẫn theo **ngày giao** để giữ C9 và AOV. Trong biểu đồ trạng thái theo ngày tạo, DELIVERED được tính bằng `total_orders - pending - confirmed - preparing - shipping - cancelled`. Không lấy `delivered` theo ngày giao để ghép với các trạng thái theo ngày tạo. Các ngày chỉ có giao hàng và không có đơn mới có số lượng trạng thái bằng 0.

## Triển khai

1. Đồng bộ module `gold_queries.py`, `gold_transform.py` lên cùng thư mục Workspace của Job hiện có; giữ định dạng Workspace FILE.
2. Chạy [gate E4](E4_QUALITY.md), ghi lại hai run SUCCESS và PASS 5/5. Không triển khai E5 chỉ dựa vào test local.
3. Tạo dashboard ở thư mục cá nhân với unified authentication:

```powershell
.venv/Scripts/python.exe data/dashboard_deploy.py --profile daln-cdc --warehouse-id 261b45209f3d8a59 --source-catalog daln_source --catalog fashion --from-date 2026-10-01 --to-date 2026-10-31 --parent-path /Users/23010313@st.phenikaa-uni.edu.vn --e4-passed
```

CLI đối chiếu KPI theo kỳ và sáu trạng thái với Lakebase bằng identity nghiệm thu, chạy các query snapshot rồi mới tạo/publish dashboard. Sai metric/query hoặc E4 chưa pass thì fail, không publish. Khi cập nhật dùng thêm `--dashboard-id <id>`; CLI kiểm tra tên và etag, không tự ghi đè dashboard khác. Không chạy lệnh tạo nhiều lần để cập nhật vì sẽ tạo artifact mới.

Publish dùng `embed_credentials=False`: người xem cần quyền dữ liệu của chính mình; không chia sẻ credential tác giả. URL chỉ cấu hình cho dashboard ADMIN qua `VITE_DATABRICKS_DASHBOARD_URL` trong `.env`, sau đó recreate frontend. Không đưa secret vào JSON dashboard, source hoặc URL.

## Kiểm thử

```powershell
docker run --rm -v D:/DALN/data:/data daln-data-test pytest -q tests/test_dashboard.py tests/test_gold_transform.py tests/test_genie_space.py
```

Test Delta thật kiểm tra ngày tạo/giao khác nhau, đủ sáu trạng thái, ngày không có dữ liệu, ratio từ tổng, nâng cấp bảng E3 cũ và chạy lại không thêm cột/dữ liệu trùng. Test deployment chặn trước E4 hoặc khi đối chiếu fail, kiểm tra cập nhật đúng artifact và publish không nhúng credential.

## Nghiệm thu

Dashboard ID: `01f1c44623e51df7a724b38609b959e2`. [Mở bản đã publish](https://dbc-d0dc0f2d-91aa.cloud.databricks.com/dashboardsv3/01f1c44623e51df7a724b38609b959e2/published). Không dùng `/sql/dashboardsv3/<id>/published` vì workspace này trả 404; URL draft vẫn có tiền tố `/sql`.

Ngày 10/10/2026, Gold mới đã qua E4 với hai run `362587574453634`, `979712061889830`, PASS 5/5 trước khi dựng E5. Sau đơn nghiệm thu F7, hai run `672654625068247`, `630578045990270` tiếp tục SUCCESS và PASS 5/5: doanh thu **13.201.000 VND**, tổng đơn **37**, đủ 13 bảng Bronze khớp Lakebase, nguồn ổn định trong cửa sổ gate. Đối chiếu đủ sáu projection Gold PASS.

| Kỳ Việt Nam | Revenue | Đơn tạo | Trạng thái hiện tại theo ngày tạo |
|---|---:|---:|---|
| 10/10/2026 | 300.000 ₫ | 1 | DELIVERED 1; các trạng thái khác 0 |
| 01–31/10/2026 | 4.381.000 ₫ | 9 | PENDING 1, CONFIRMED 1, PREPARING 1, SHIPPING 2, DELIVERED 4, CANCELLED 0 |
| 01/01/2000 | 0 ₫ | 0 | Không có đơn; ratio/AOV NULL |

SQL của cả ba kỳ khớp Lakebase; ba dataset snapshot chạy thành công. Gold có 24 dòng top_products, 21 low_stock_current, 3 shop_performance. Genie sau nâng cấp đã kiểm tra quyền UC cho admin và ba shop; đủ 12 câu/role admin và shop1 PASS, cùng bốn câu demo sau đơn F7.

Browser đã xác minh bốn KPI sau Refresh: toàn thời gian 13.201.000 ₫, 37 đơn, 10,81%, AOV 942.929 ₫; Today 300.000 ₫, 1 đơn, 0,00%, AOV 300.000 ₫. Preset Yesterday (09/10) hiện No data cho KPI/chart, phù hợp kỳ rỗng đã đối chiếu SQL; snapshot xếp hạng/tồn kho giữ phạm vi toàn thời gian. Hai biểu đồ top và bảng low stock đã render, trong bảng có hai variant F7 tồn 4/ngưỡng 5. Counter dùng format field `number-currency`/VND và `number-percent` lấy từ editor Databricks; chia hai cột để tiền không bị cắt ở panel hẹp. Ảnh: `output/playwright/e5-f7-today.png`, `e5-empty-period.png`, `e5-rankings-stock.png`.

Sau pipeline hoặc publish cần bấm **Refresh**: cache Dashboard có thể giữ kết quả của revision/lượt query trước. Không dùng số trên cache để kết luận số liệu mới chưa được đồng bộ. SQL acceptance chạy độc lập, không dùng cache visualization.
