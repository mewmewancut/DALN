# Demo hệ thống — 10 phút

**Trạng thái:** Implemented; demo local và chuỗi F7 đã chạy ngày 10/10/2026.

## Chuẩn bị

Môi trường Docker demo độc lập dùng `compose.demo.yml`, project `daln-demo`, database `fashion_demo`, volume database/ảnh riêng. Nó không đọc DATABASE_URL, SMTP hoặc credential Genie từ `.env` của ứng dụng đang kết nối Lakebase. Frontend được build bằng Vite và phục vụ bằng nginx; API dùng proxy cùng origin. Chạy được bên cạnh runtime dev trên 8000/5173.

```powershell
docker compose --env-file .env.example -f compose.demo.yml up --build -d --wait
# Chỉ khi muốn xóa dữ liệu demo riêng và migrate/seed lại:
bash reset_demo.sh --confirm-local-demo
# Browser E2E thật với API/database demo, không mock response:
docker compose --env-file .env.example -f compose.demo.yml --profile test run --build --rm e2e
```

Windows cần Git Bash cho `reset_demo.sh`; có thể chạy `& 'C:\Program Files\Git\bin\bash.exe' reset_demo.sh --confirm-local-demo`. Script dùng psql qua socket local trong container Postgres demo và chỉ reset schema `public` của `fashion_demo`; lỗi reset/migration/build chặn thông báo thành công. Ảnh upload được giữ trong volume ảnh riêng khi reset database.

Website demo: `http://localhost:15173`; Swagger: `http://localhost:18000/docs`. Tài khoản giả đã được seed và xác minh email sẵn theo [Deployment guide](DEPLOYMENT_GUIDE.md#8-tạo-dữ-liệu-mẫu). Không gửi email thật trong test browser. Các tài khoản/mật khẩu demo chỉ dành cho môi trường demo local.

Docker demo này không đẩy dữ liệu sang pipeline Databricks của Lakebase. Để nghiệm thu **F7**, thực hiện phần vận hành trên runtime kết nối Lakebase đã xác nhận, rồi chạy đúng Job của nguồn đó. Không so một đơn local với Gold của nguồn khác.

## Trình diễn

| Thời gian | Thao tác | Điểm chứng minh |
|---|---|---|
| 0–2 phút | Khách mở gian hàng, chọn variant hết kho rồi chuyển variant còn hàng; thêm hai sản phẩm cùng shop và một sản phẩm shop khác | Giá/kho ở cấp variant; giỏ nhiều shop; reload vẫn giữ giỏ khách |
| 2–4 phút | Chọn một shop, đăng nhập buyer, checkout COD, mở chi tiết đơn | Tổng từ database; đơn chỉ chứa shop đã chọn; hàng shop khác vẫn ở giỏ; snapshot item và lịch sử |
| 4–6 phút | Shop xác nhận → chuẩn bị → giao → đã giao; buyer gửi review | Không nhảy trạng thái; COD PAID; review chỉ sau DELIVERED |
| 6–7 phút | Shop mở cảnh báo, tạo phiếu nhập → ORDERED → RECEIVED, xem kho/alert | Kho tăng một lần, cảnh báo được giải quyết; thử nhận lại bị từ chối |
| 7–8 phút | Admin xem dashboard web và mở Fashion Platform Overview | Phạm vi toàn hệ thống; KPI C9; dữ liệu Gold có độ trễ pipeline |
| 8–10 phút | Hỏi Genie bốn câu đã đối chiếu, mở sơ đồ Medallion trong [báo cáo hệ thống](SYSTEM_REPORT.md) | Revenue chỉ DELIVERED; ngày Việt Nam; Bronze MERGE, Silver làm sạch, Gold metric; Genie chỉ Gold theo quyền |

## Nghiệm thu F7

Ghi ID/mã đơn mới, hai item và giá snapshot; đối chiếu tổng đơn, tồn trước/sau, delivered_at, history, payment_status và review. Ghi tổng doanh thu hôm nay trước/sau giao để xác nhận tăng đúng total_amount của đơn mới.

Ngày 10/10/2026 đã thực hiện phần vận hành trên runtime Lakebase bằng trình duyệt: buyer5 đặt **ORD-20261010-0037** (order 37, shop 1), gồm áo 100.000 ₫ và quần 200.000 ₫, mỗi item một chiếc M/Đen. Hai variant bắt đầu tồn 5; checkout còn 4. Shop xử lý đủ bốn bước, đơn DELIVERED lúc `2026-10-10T01:13:55.398328Z` (08:13 Việt Nam), COD PAID, history đủ năm trạng thái. Buyer review item áo; API trả `review_id=1`. Doanh thu hôm nay trước khi giao là 0. Bằng chứng browser/API được lưu cục bộ trong `output/playwright/f7-20261010.json` và `f7-delivered-review.png`.

Chờ CDC, chạy E1→E2→E3 bằng Job hiện có. Chỉ dùng lượt SUCCESS, đối chiếu Gold/Lakebase và các dataset E5; sau đó hỏi Genie **Doanh thu hôm nay là bao nhiêu?** và kiểm tra bảng số bằng SQL độc lập. Thử shop hỏi cùng câu để chứng minh chỉ thấy doanh thu của shop; thử yêu cầu shop khác để xác nhận quyền vẫn bị chặn.

Bốn câu demo: doanh thu hôm nay, tổng doanh thu tháng này, số đơn đang giao hiện tại, những biến thể cần nhập thêm. Kết quả là snapshot nghiệm thu, không hard-code giá trị kỳ vọng từ buổi trước.

## Tự động hóa và giới hạn

`frontend/e2e/buyerJourney.e2e.js` dùng Chromium thật với dữ liệu/API thật trong demo riêng. Runner chỉ nhận service Compose hoặc cổng demo 15173/18000, từ chối URL runtime thường hoặc remote. Bộ kiểm tra chạy trong job browser của [CI](../.github/workflows/ci.yml); ảnh nằm ở `output/playwright/e2e`, không commit. Reset lại database demo trước mỗi lượt chạy đầy đủ để có baseline sạch.

Pipeline nhận đơn mới qua run `300361564726189` SUCCESS. Hai run E4 và số liệu Dashboard được ghi chuẩn tại [E5 Dashboard](E5_DASHBOARD.md#nghiệm-thu). Revenue hôm nay Gold/Lakebase tăng **0 → 300.000 ₫**, đúng tổng đơn mới. Bộ bốn câu demo qua API chatbot thật và SQL độc lập đều PASS cho admin và shop1:

| Câu hỏi | Admin | Shop 1 |
|---|---:|---:|
| Doanh thu hôm nay | 300.000 ₫ | 300.000 ₫ |
| Doanh thu tháng này | 4.381.000 ₫ | 300.000 ₫ |
| Đơn đang giao (mọi ngày tạo) | 7 | 2 |
| Biến thể cần nhập thêm | 21 | 8 |

Bằng chứng JSON: `output/playwright/f7-genie-admin-20261010.json`, `f7-genie-shop1-20261010.json`; các file này được ignore. Bộ 12 câu trước đơn mới cũng PASS 12/12 cho từng role, bao gồm follow-up, không dấu, tiếng Anh và kỳ rỗng. Các principal shop vẫn chỉ SELECT sáu view Gold có session_user/shop mapping; nguồn Gold gốc, Bronze, Silver và federation bị từ chối. Bộ browser E2E demo PASS 5/5, reset từ project mới và reset lại đều đã chạy thành công ngày 10/10.

Dashboard bản publish với preset Today đã hiện đúng 300.000 ₫, 1 đơn, 0,00% hủy và AOV 300.000 ₫; evidence `output/playwright/e5-f7-today.png`. Kiểm tra local/browser không tự chứng nhận production, backup/HA hoặc Safari/Firefox. F7 đã được chạy bằng các role buyer/shop/admin; hai thành viên vẫn cần cùng diễn tập kịch bản trước buổi bảo vệ như Planning yêu cầu.
