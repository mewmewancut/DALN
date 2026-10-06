# Chatbot Genie trên website

Người dùng đăng nhập tài khoản dự án, mở **Chatbot Genie** ở sidebar admin/shop.
Không yêu cầu đăng nhập hoặc cấp quyền Databricks cho từng người dùng web.
Yêu cầu mở rộng này được người dùng xác nhận ngày 06/10/2026. Không thay Planning.
Gate [E4](E4_QUALITY.md) đã PASS 5/5 trước khi bắt đầu triển khai Genie.

## Phạm vi và quyền dữ liệu

Admin dùng space **Fashion Platform Assistant**, đọc sáu bảng `fashion.gold.*`
của E3 để phân tích toàn hệ thống. Mỗi shop có một space, một service principal
và sáu view riêng trong schema Gold: `shop_<id>_<table>`. Mỗi view là
`SELECT * FROM fashion.gold.<table> WHERE shop_id = <id>` cố định ở định nghĩa
view; số ID không được lấy từ câu hỏi hoặc request của client.

Service principal shop chỉ có USE CATALOG/SCHEMA và SELECT sáu view của chính
shop. Không cấp SELECT Gold gốc, view shop khác, Bronze, Silver hoặc federation.
Không thêm principal vào nhóm admin và không cấp quyền ghi dữ liệu. Admin
chatbot cũng chỉ có SELECT sáu bảng Gold, không có quyền dữ liệu vận hành.
Space cấp CAN RUN cho đúng principal; warehouse cấp CAN USE để nghiệm thu bằng
SQL API. Chủ sở hữu space/view là danh tính quản trị triển khai hiện có.

Backend xác thực user từ database. SHOP_OWNER được suy shop qua `shops.owner_id`
trong database và bị chặn nếu shop chưa có hoặc đã khóa. ADMIN dùng scope toàn
hệ thống; BUYER bị từ chối. Không có fallback từ shop sang identity admin.
Client không gửi shop ID, space ID, OAuth credential hoặc SQL tùy ý. Unity
Catalog cưỡng chế giới hạn dữ liệu ngay cả khi câu hỏi yêu cầu bỏ lọc/shop khác.
Đây là quyền dữ liệu thật, không dựa vào prompt của Genie hoặc việc ẩn route.

[Tài liệu Databricks](https://docs.databricks.com/aws/en/genie-agents/set-up)
xác nhận quyền dữ liệu Genie được kiểm tra theo danh tính người gọi trong Unity
Catalog; compute credentials của tác giả chỉ áp dụng quyền warehouse.

## Luồng hội thoại và giới hạn

`Axios → FastAPI chatbot router → chatbot_service → Genie REST API`.
OAuth M2M được thực hiện ở backend; token truy cập được cache riêng từng
principal và hết hạn theo OAuth. Frontend chỉ giữ lịch sử trong bộ nhớ trang;
tải lại/đăng xuất hoặc bấm Cuộc trò chuyện mới sẽ bắt đầu lại. Không thêm bảng
chat vào Lakebase, không thêm migration hoặc nguồn CDC.

Backend cấp `conversation_token` có chữ ký HS256, hạn một giờ, ràng buộc user,
role hiện tại, shop lấy từ database, host, principal, space và conversation ID.
Audience `daln-genie-conversation` bắt buộc và riêng với JWT đăng nhập; dùng
token hội thoại làm Bearer đăng nhập bị từ chối 401.
Mỗi request tiếp tục/poll đều kiểm tra lại quyền và chữ ký. Token hội thoại
không thay token đăng nhập; tài khoản khác (kể cả admin) không thể dùng nó để
đọc cuộc trò chuyện của người khác. Đổi scope/space/principal vô hiệu token cũ.

Genie xử lý bất đồng bộ. Frontend poll mỗi hai giây sau khi request trước hoàn
tất, dừng sau 60 lần và cho Kiểm tra lại kết quả. Retry này chỉ đọc kết quả,
không gửi lại câu hỏi. Chặn gửi trùng trong khi đang xử lý; bỏ response cũ khi
đổi cuộc trò chuyện/rời trang. Mỗi HTTP request backend timeout 20 giây;
lỗi upstream được làm sạch, không trả secret, lỗi SQL nội bộ hoặc link tải
chứa credential. HTTP 429 hiển thị quá tải. Không tự retry POST tạo câu hỏi.

Bảng hiển thị tối đa 100 dòng trong chunk đầu của kết quả inline, báo khi
còn dòng/chunk khác hoặc Databricks cắt kết quả. Không tải external result URL.
Text model hiển thị bằng React text, không chèn HTML. Giá dùng formatter VND
chung, cancellation ratio hiển thị %. Chưa có lưu hội thoại lâu dài, xuất file,
chart từ Genie hoặc điều phối nhiều câu hỏi cùng lúc trên một trang.

## Metric và câu hỏi hỗ trợ

Metric theo [E3 Gold](E3_GOLD.md) và Planning C9. Space có description cho từng
bảng/cột, sáu sample questions và năm example SQL. General instructions dùng
ngày Việt Nam, doanh thu DELIVERED theo ngày giao, số đơn/hủy theo ngày tạo;
AOV và tỷ lệ hủy phải tính lại từ tổng số, không trung bình tỷ lệ nhiều shop.
`today`/`this month` dựa current_timestamp chuyển Asia/Ho_Chi_Minh, không cộng
múi giờ lần hai lên cột date/month đã chuẩn hóa.

Gold chưa có số đơn SHIPPING. Câu hỏi README “Có bao nhiêu đơn hàng đang giao?”
được test để Genie giải thích không đủ dữ liệu, không đoán số và không đọc
bảng thô. `top_products` không có date nên chỉ hỗ trợ sản phẩm bán chạy toàn
thời gian. Tồn kho là snapshot pipeline, không phải tồn kho trực tiếp thời gian
thực. Không mở rộng metric/schema Gold trong task chatbot này.

## Cấu hình và triển khai

`backend/genie.example.json` là mẫu giả, `e4_passed=false` để không bật nhầm.
File runtime thật `backend/.env.genie.json` và journal `.env.genie.json.provision`
nằm trong pattern `.env.*` bị Git bỏ qua. Không đưa file này vào commit, log
hoặc frontend. Bảo vệ quyền đọc trên host; khi triển khai thật dùng secret store/
secret mount backend. Dùng secret OAuth theo principal, không dùng token admin
chung cho shop. Secret được cấp hạn một năm trong script; cần luân chuyển trước
khi hết hạn, hoặc thay sớm nếu quyền đã đổi.

Sau khi [E4 thật PASS](E4_QUALITY.md), dùng cùng Python/SDK và profile quản trị:

```powershell
.venv/Scripts/python.exe data/genie_provision.py --profile daln-cdc --warehouse-id 261b45209f3d8a59 --e4-passed
.venv/Scripts/python.exe data/genie_acceptance.py --warehouse-id 261b45209f3d8a59
```

`--e4-passed` là xác nhận của người vận hành về gate đã chạy, không chạy gate
thay họ. Script provision lấy shop ID từ Gold `shop_performance`, tạo view và
principal riêng, cấp quyền từng object và tạo space với metadata. Không thay
Job pipeline. Journal ghi ngay từng credential/space để retry không tạo trùng
hoặc mất secret; runtime JSON chỉ được thay khi tất cả scope cấu hình xong.
Script hiện dành cho catalog `fashion` và workspace của dự án; nghiệm thu độc
lập so view với Gold và kiểm tra permission denial thật, không coi query lỗi
hạ tầng hoặc bảng không tồn tại là chứng cứ chặn quyền.

Đặt trong `.env` của máy chạy Compose:

```dotenv
GENIE_CONFIG_PATH=/app/.env.genie.json
```

```powershell
docker compose --env-file .env up -d --no-deps backend
docker compose --env-file .env restart frontend
```

Shop mới sau lượt provision chưa có mapping: web báo chưa cấu hình, API trả
503. Chạy pipeline để shop xuất hiện trong Gold, chạy lại provision và
nghiệm thu rồi mới cho shop dùng chatbot. File cấu hình được đọc lại mỗi
request; JSON lỗi, E4 chưa pass, identity/space dùng chung giữa các scope hoặc
credential thiếu làm chatbot không khả dụng. Không ảnh hưởng API vận hành.
Rà soát quyền kế thừa của principal/nhóm khi thay đổi grants; không cấp quyền
rộng lên catalog/schema cho các principal chatbot về sau.

`VITE_DATABRICKS_GENIE_URL` cũ chỉ là link Databricks tùy chọn ở dashboard admin,
không phải cấu hình chatbot mới. Không cần đặt link này để dùng chatbot trên web.

## Kiểm thử và nghiệm thu

```powershell
docker compose --env-file .env.example exec -T backend pytest -q app/tests/test_chatbot.py app/tests/test_genie_client.py
docker compose --env-file .env.example exec -T frontend npm test -- src/pages/chatbot.test.jsx
docker run --rm -v D:/DALN/data:/data daln-data-test pytest -q tests/test_genie_space.py tests/test_genie_acceptance.py
```

Backend test role/quyền theo database, token hội thoại user/shop/role/space,
hết hạn/chữ ký sai, missing scope fail closed, cấu hình trùng identity/space,
payload giả scope, mọi trạng thái Genie, query pending/failed/empty/truncated,
OAuth cache và lỗi được làm sạch. Frontend test hai role, route BUYER bị chặn,
request đúng contract, followup/reset, chặn gửi trùng, polling/retry/timeout,
response trễ bị bỏ, text HTML không chạy và bảng VND/rỗng/truncated.

Ngày 06/10/2026, đã tạo một space admin và ba space shop 1–3 trên workspace.
Nghiệm thu bằng OAuth của từng principal PASS: admin đọc đủ sáu Gold và bị
chặn Bronze; mỗi shop đọc đủ sáu view, count khớp Gold lọc shop, không có dòng
shop khác/null. Sáu Gold gốc, view shop khác, Bronze orders, Silver fact_orders
và Lakebase orders đều bị từ chối rõ ràng INSUFFICIENT_PERMISSIONS.

Sáu câu README và bốn biến thể đã chạy COMPLETED bằng identity admin. Kết quả
truy vấn được đối chiếu SQL độc lập; revenue, số đơn, AOV và tỷ lệ hủy theo kỳ
còn được so với Lakebase bằng danh tính nghiệm thu. Decimal AOV so ở scale 6
của kết quả Genie, các giá trị tỷ lệ dùng sai số số thực phù hợp.

| Câu hỏi nghiệm thu (06/10/2026) | Kết quả đã đối chiếu |
|---|---|
| Doanh thu toàn hệ thống tháng này? | 3.473.000 VND |
| Top 10 shop có doanh thu cao nhất? | Shop 2: 5.378.000; shop 3: 4.531.000; shop 1: 2.384.000 VND |
| Có bao nhiêu đơn hàng đang giao? | Giải thích Gold thiếu SHIPPING; không truy vấn bảng thô |
| Sản phẩm nào bán chạy nhất? | Túi xách mẫu 05 — Shop 3, số lượng 3; top 10 khớp SQL |
| Shop nào có tỷ lệ hủy đơn cao? | Shop 3: 16,67%; shop 1/2: 8,33% |
| Những sản phẩm nào đang có tồn kho thấp? | 19 biến thể, toàn bộ dòng khớp SQL |
| Tổng doanh thu các đơn đã giao trong toàn bộ dữ liệu? | 12.293.000 VND |
| Có bao nhiêu đơn được tạo trong tháng này? | 8 |
| Giá trị trung bình các đơn đã giao tháng này? | 1.157.666,666667 VND trong bảng kết quả |
| Tỷ lệ hủy đơn toàn hệ thống tháng này? | 0% |

Văn bản AOV ở lượt đầu cắt phần thập phân mà chưa ghi xấp xỉ; bảng SQL đúng.
Đã bổ sung instruction về độ chính xác/làm tròn tiền. Lượt thử lại trả bảng
1.157.666,666667 và văn bản 1.157.666,67 VND. Không đổi metric.

Kịch bản demo sáu câu có dữ liệu: đăng nhập admin, mở `/admin/chatbot`, lần lượt
hỏi doanh thu tháng này, top shop, sản phẩm bán chạy, shop có tỷ lệ hủy cao,
tồn kho thấp và tổng doanh thu đã giao toàn thời gian (sáu dòng tương ứng trong
bảng trên). Dùng Cuộc trò chuyện mới để thử độc lập, rồi thử một câu tiếp nối.
Các số trên là snapshot nghiệm thu; khi dữ liệu/ tháng thay đổi, đối chiếu lại.
Đăng nhập shop 1, mở `/shop/chatbot` và hỏi tổng doanh thu: chỉ 2.384.000 VND.

Đã kiểm tra Chromium thật cho admin/shop trên desktop và màn hình 390 px,
gọi API Genie thật, hiển thị bảng/VND và trạng thái lỗi token cũ sau cập nhật.
Khi shop 1 yêu cầu bỏ giới hạn và truy vấn Gold gốc để lấy doanh thu shop 2/
toàn hệ thống, không đọc được dữ liệu khác. Lượt đầu model đặt sai nhãn tổng
shop thành tổng hệ thống; đã bổ sung instruction gắn shop ID, cấm suy luận từ
view rỗng và yêu cầu từ chối. Lượt thử lại trên web đã từ chối rõ ràng, không
trả bảng dữ liệu. Quyền Unity Catalog vẫn là lớp bảo vệ dữ liệu độc lập với model.
Ảnh kiểm tra lưu ở `output/playwright/` (Git ignored). Dashboard Databricks E5
và demo tổng thể G vẫn Planned.
