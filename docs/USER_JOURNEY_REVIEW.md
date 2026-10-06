# Rà soát hành trình người dùng — 06/10/2026

## Đánh giá

Các luồng mua hàng, xử lý đơn và nhập kho hoạt động được khi dùng liên tục qua
BUYER, SHOP_OWNER và ADMIN. Điểm yếu trước lượt sửa là trải nghiệm vận hành:
shop không xem được hàng/người nhận trong bảng đơn, giỏ cho thanh toán khi
số lượng chưa lưu, form cho gửi trùng và trang chi tiết giữ dữ liệu cũ khi
chuyển route. Những lỗi đã xác nhận bên dưới đã được sửa, có regression.

Phân quyền, giá từ database, snapshot đơn, transaction, trừ/hoàn kho và metric
C9 được kiểm tra bằng suite hiện có; không có thay đổi quy tắc nghiệp vụ.
Chatbot đọc đúng Gold/phạm vi và mở lại lịch sử đã lưu, nhưng vẫn phụ thuộc
độ trễ đồng bộ Gold và khả năng diễn giải của Genie. Đây là kết quả rà soát
local/demo, không phải chứng nhận sẵn sàng production hoặc bao phủ mọi nhánh.

## Môi trường và độ bao phủ

Thao tác ghi dùng Compose project `daln-user-review`, Postgres riêng, JWT giả
riêng, web `localhost:5174`, API `localhost:8001`; migrate 0001–0009 và seed
375 record. Không chạy worker cấp quyền trên database QA, không gửi email
thật. Runtime Genie dùng các danh tính đọc hiện có của shop 1–3/admin; lịch
sử của phiên QA lưu trong database QA. Gold không lấy dữ liệu đơn QA mới.

| Vai trò | Dùng thử trực tiếp trong Chromium | Kiểm tra bổ sung bằng test |
|---|---|---|
| Khách | Catalog/chi tiết; đăng nhập sai hiển thị lỗi; mở đơn riêng bị chuyển về login; mở các form đăng ký/quên/reset/xác minh email (không gửi mail) | Đăng ký, xác minh/reset token, mail lỗi, tài khoản khóa, catalog/filter/paging |
| BUYER | Chọn Đen/S, thêm giỏ/cập nhật 2 cái, checkout COD; xem đơn giao và đánh giá; hủy đơn chờ xác nhận; lưu hồ sơ, địa chỉ mặc định bằng tìm không dấu, sở thích; thêm yêu thích và xem wishlist; route chatbot admin bị chuyển về catalog | Giá/tồn kho từ DB, hết hàng/concurrency, giỏ khác shop, checkout rollback, đơn/địa chỉ/wishlist riêng user, review trùng, recommendation/filters |
| SHOP_OWNER | Dashboard, sản phẩm, bảng đơn và chi tiết người nhận; chuyển đủ bốn bước đến giao; tồn kho/cảnh báo/nhà cung cấp; tạo–đặt–nhận phiếu nhập; chatbot và mở lịch sử sau reload | CRUD sản phẩm/variant/supplier, quyền chéo shop, transition sai, hủy/nhận kho idempotent, rollback, ngưỡng/cảnh báo |
| ADMIN | Dashboard, users và shops; khóa/mở tài khoản thử, kiểm tra không tự khóa; khóa/mở shop và đối chiếu catalog; danh sách/chi tiết đơn; chatbot toàn hệ thống, đổi tên hội thoại | Tìm/lọc/paging, self-lock backend, metric/Vietnam date, quyền route/API, lịch sử riêng kể cả admin |

Form/email và CRUD có test không đồng nghĩa đã gửi email thật hoặc thử mọi
CRUD bằng trình duyệt trong lượt này. Rà soát layout toàn bộ các trang ở lượt
trước được ghi riêng ở [UI/UX](UI_UX.md); phạm vi test ở [Testing](TESTING.md).

## Phát hiện và sửa

P2: ảnh hưởng luồng chính/kết quả thao tác. P3: gây nhầm lẫn hoặc giảm khả năng
sử dụng. Đây là lỗi tồn tại trước lượt rà soát này, không tính các nâng cấp
chatbot/worker ở lượt trước thành lỗi mới.

| Mức | Trigger và ảnh hưởng trước sửa | Sửa ở source |
|---|---|---|
| P2 | Đổi origin frontend theo cấu hình nhưng login/catalog vẫn bị CORS chặn vì hardcode 5173 | [main.py](../backend/app/main.py) lấy đúng origin của `FRONTEND_PUBLIC_URL`; preflight origin ngoài cấu hình vẫn bị từ chối |
| P2 | Sửa số lượng rồi checkout dùng số lượng DB cũ; request toàn giỏ có thể đè nháp dòng khác | [CartPage](../frontend/src/pages/CartPage.jsx) khóa checkout khi nháp/đang ghi/thiếu tồn, tuần tự thao tác, giữ nháp dòng khác |
| P2 | Shop nhận đơn nhưng không xem được hàng, số điện thoại hoặc địa chỉ để giao | [OrderDetailDialog](../frontend/src/components/orders/OrderDetailDialog.jsx) từ mã đơn shop/admin, dùng endpoint quyền hiện có; snapshot dùng chung với buyer, loading/lỗi/retry/Escape |
| P2 | Chuyển sang đơn khác/lỗi quyền nhưng đơn và form review cũ còn hiện; review trả chậm cập nhật nhầm trang | [OrderDetailPage](../frontend/src/pages/OrderDetailPage.jsx) reset khi đổi id, bỏ response cũ; regression kiểm tra cả review trả trễ |
| P2 | Đổi sản phẩm nhưng đánh giá cũ vẫn hiện, lỗi tải bị trình bày như không có đánh giá | [ProductDetailPage](../frontend/src/pages/ProductDetailPage.jsx) xóa đánh giá cũ, tách tải/lỗi đánh giá khỏi tải sản phẩm |
| P2/P3 | Gửi hồ sơ/checkout lần nữa khi request đang chờ; sửa form hồ sơ rồi bị response cũ ghi đè | [ProfilePage](../frontend/src/pages/ProfilePage.jsx), [CheckoutPage](../frontend/src/pages/CheckoutPage.jsx) chặn submit trùng và trạng thái đang lưu |
| P3 | Locale tiếng Việt nhưng ngày giờ vẫn theo timezone máy; trạng thái thanh toán khó đọc | [orderPresentation](../frontend/src/components/orderPresentation.js), [OrderSnapshot](../frontend/src/components/orders/OrderSnapshot.jsx) giờ Việt Nam, nhãn thanh toán và lý do hủy |
| P3 | Chatbot thiếu Enter gửi câu hỏi; phải giữ hỗ trợ nhập IME và xuống dòng | [ChatbotPage](../frontend/src/pages/ChatbotPage.jsx) Enter/Shift+Enter, IME guard, hướng dẫn ngay dưới form; cột year hiển thị Năm |

Dialog chi tiết đã xem ở desktop và 390 × 844: nội dung cuộn bên trong,
Escape đóng, nền trang không cuộn khi dialog mở. Không thêm dependency/API.

## Bằng chứng thao tác

- Buyer tạo đơn `ORD-20261006-0037`: 209.000 × 2 = **418.000 VND**;
  variant 1 từ 49 còn 47. Shop giao thành công, COD thành PAID và database
  có đủ **5** mốc lịch sử (khởi tạo + bốn chuyển trạng thái).
- Phiếu nhập QA #1 nhận **3** sản phẩm, 100.000/cái: RECEIVED, variant 1
  tăng **47 → 50**. Hủy đơn QA #10 hoàn đúng một cái cho từng variant:
  variant 31 **16 → 17**, variant 38 **46 → 47**.
- Buyer đánh giá đơn 37 một lần, trang sản phẩm hiển thị đúng nhận xét/5 sao.
  Hồ sơ, địa chỉ mặc định, wishlist và sở thích lưu được qua API/database QA.
- Admin khóa shop 3: catalog **45 → 30**, không còn hàng shop 3; mở khóa:
  **30 → 45**, đủ 15 sản phẩm shop 3. Khóa/mở buyer thử có phản hồi và
  trạng thái DB tương ứng, không thao tác trên tài khoản production.
- Cùng câu **“doanh thu thang 9”** qua giao diện: shop 1 **2.384.000 VND**,
  admin **8.820.000 VND**, đều ghi **tháng 9/2026**. Reload rồi mở lịch sử
  shop giữ kết quả; admin không thấy lịch sử shop và đổi tên chat được.
  Nghiệm thu 20 câu/SQL Gold ở lượt trước nằm ở [Genie Chatbot](GENIE_CHATBOT.md).

Ảnh/snapshot local tại `output/playwright/role-review/` (ignored); không đưa
snapshot đăng nhập hay dữ liệu hiển thị vào commit. Console có lỗi HTTP 401
được tạo chủ động khi thử sai mật khẩu; không coi lỗi kỳ vọng là crash.

## Kiểm tra đã chạy

| Lệnh | Kết quả |
|---|---|
| `docker compose --env-file .env.example exec -T backend pytest -q` | 236 pass; 1 warning tương thích Starlette/httpx hiện có |
| `docker compose --env-file .env.example exec -T frontend npm test` | 137 pass / 22 file |
| `docker run --rm -v D:/DALN/data:/data daln-data-test pytest -q tests` | 168 pass |
| `python -m unittest discover -s tests -v` | 5 pass, gồm Docker build context credential giả |
| Backend và data `ruff check .`, `ruff format --check .` | Pass |
| Frontend `npm run lint`, `npm run format:check`, `npm run build` | Pass |
| Frontend `npm audit --audit-level=moderate` | 0 vulnerability |
| `alembic check` trên backend project QA | Không có upgrade operation thiếu |
| `docker compose --env-file .env.example config --quiet`, `git diff --check` | Pass |

Backend/frontend đang chạy đã restart với cấu hình runtime hiện có; `/health`
trả `ok`, web trả HTTP 200. Worker cấp quyền vẫn chạy. Project QA được dừng
sau kiểm tra; volume riêng giữ lại để xem dữ liệu thử khi cần.

Regression CORS, giỏ, submit hồ sơ và đổi route đơn/sản phẩm được chạy fail
trước khi sửa rồi pass sau sửa. Các test mới cùng source; lệnh chuẩn và phạm
vi từng test được duy trì ở [Testing](TESTING.md).

## Giới hạn còn lại

- Email giao thật chưa chạy trong lượt này; SMTP QA cố ý tắt. Nhánh token/mail
  đã có test. Ảnh seed/demo không thay thế dữ liệu hàng thật.
- Đơn/nhập kho QA không đồng bộ tới Gold thật: không chứng nhận pipeline
  phản ánh ngay đơn QA hoặc realtime chatbot. Gold/pipeline theo gate E4 và
  lịch đồng bộ trong tài liệu data hiện có.
- Genie có thể diễn giải sai câu ngoài tập đã thử và trả chậm khi warehouse
  khởi động. Đã có polling/retry, lịch sử và đối chiếu metric; chưa có cam kết
  chất lượng mọi ngôn ngữ như một mô hình chat đa dụng.
- E5 AI/BI Dashboard Databricks, F7 chuỗi đơn → pipeline → dashboard → Genie
  đầy đủ, bộ browser E2E tự động, G demo tổng thể và production deployment
  tiếp tục **Planned**. Không sửa Planning
  hoặc trình bày các phần đó như đã hoàn thành.
