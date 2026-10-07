# Testing

**Trạng thái:** In progress  
**Phạm vi hiện tại:** health check, database constraints B1–B14, seed data B15 và toàn bộ backend C0–C10 (auth gồm xác minh email/reset mật khẩu, catalog, giỏ hàng, checkout, state machine đơn hàng, tồn kho/cảnh báo hết hàng, supplier/nhập hàng, review, số liệu thống kê shop, admin) cùng luồng API từ đăng ký đã xác minh đến đăng sản phẩm

Frontend D1–D4 có test gắn token, xử lý `401`, điều hướng theo vai trò, form auth, catalog/wishlist/preferences/recommendations, toàn bộ luồng buyer từ giỏ hàng tới review, toàn bộ trang quản lý của chủ shop và các trang admin.

Test UI dùng chung kiểm tra skip link đến vùng nội dung có thể focus, nhãn điều hướng theo ba role và ảnh sản phẩm khi thiếu URL/tải lỗi/đổi URL. Quy ước trình bày và bằng chứng kiểm tra trình duyệt thủ công nằm ở [UI/UX](UI_UX.md); các kiểm tra này không thay browser end-to-end tự động còn Planned.

## Các lớp kiểm tra hiện có

| Lớp | Công cụ | Phạm vi đang chạy |
|---|---|---|
| Database | pytest + PostgreSQL test | Constraint, giá trị mặc định, timestamp, seed chạy lại không nhân đôi |
| API và phân quyền | pytest + FastAPI TestClient | Auth, shop, catalog, giỏ hàng, đơn hàng, lỗi nghiệp vụ, quyền sở hữu và rollback |
| Đồng thời giỏ hàng | pytest + PostgreSQL, hai session/thread | Lần thêm đầu tiên cùng variant hoặc khác shop bảo toàn một giỏ/một shop, không mất số lượng |
| Đồng thời checkout | pytest + PostgreSQL, hai session/thread | Hai buyer checkout cùng variant chỉ đủ cho một đơn không làm âm kho; hai request trên cùng giỏ không tạo hai đơn |
| Đồng thời state machine | pytest + PostgreSQL, hai session/thread | Buyer hủy và shop xác nhận cùng đơn: đúng một transition thành công, tồn kho khớp trạng thái cuối |
| Đồng thời cảnh báo tồn kho | pytest + PostgreSQL, hai session/thread | Tạo alert không trùng; resolve alert và trừ kho đồng thời được tuần tự hóa theo dòng inventory, trạng thái alert khớp tồn kho cuối |
| Luồng API | pytest + FastAPI TestClient | Đăng ký chủ shop → đăng nhập → tạo shop → đăng sản phẩm → buyer xem catalog; category được tạo trong fixture vì API admin chưa có |
| Frontend | Vitest + jsdom | Axios token/`401`, route theo vai trò, auth/catalog, đổi shop trong giỏ, sửa/xóa giỏ, checkout, lọc/hủy đơn, review, các trang SHOP_OWNER D3 và ADMIN D4 |
| Migration và cấu hình | Alembic + Docker Compose | Áp dụng migration và kiểm tra model khớp schema; kiểm tra Compose |
| Lint và format | Ruff + ESLint + Prettier | Lỗi Python/JavaScript, import, React Hooks và định dạng; test cấu hình xác nhận code sai bị từ chối |
| Runtime và dependency | HTTP smoke + Vite build + npm audit | Health backend, frontend phục vụ trang, build và lỗ hổng mức moderate trở lên |
| Bronze E1 | pytest + Spark/Delta local | Bootstrap 13 bảng, checkpoint/skip qua restart, CDC update/insert/delete/preimage, replay, schema/key lỗi, transaction/retry và thay đổi identity |
| Silver E2 | pytest + Spark/Delta local | MERGE 7 bảng, no-op/dependency skip, order→items, variant→inventory, config/target/retry, nghiệp vụ status/amount/rating, timezone, snapshot item/decimal/inactive, khóa/join/schema lỗi và dọn staging |
| Gold E3 | pytest + Spark/Delta local | 6 bảng, metric ngày tạo/giao và tháng/biên năm, snapshot giá, join review/variant/product không nhân số liệu, NULL/chia 0, shop ẩn/rỗng/thiếu dimension/chỉ có product, overwrite lặp lại/nguồn rỗng, lỗi ghi Delta giữa chừng/retry và input báo cáo lỗi không thay Gold cũ |
| Điều phối/nghiệm thu E3 | pytest + Spark/Delta local | E1/E2 lỗi chặn Gold, notebook riêng, refresh Gold qua warehouse khi E1/E2 SKIP, lỗi Gold làm Job fail; SQL EXCEPT ALL thật và tổng độc lập với Lakebase, CLI lỗi không báo PASS và không chứng nhận gate E4 |
| Điều phối/metadata/nghiệm thu E1–E2 | pytest | E1 fail thì không chạy E2, dùng chung phiên/snapshot, giới hạn metadata Spark/warehouse, SKIP trước Spark, thay đổi ID/version/config và marker lỗi, fallback, deadline, đo startup riêng và đối chiếu thiếu/trùng/sai giá trị |
| Gate E4 | pytest + nghiệm thu workspace | Hai lượt pipeline, đối chiếu năm mục và phát hiện nguồn biến động |
| Chatbot Genie | pytest + Vitest + nghiệm thu OAuth/browser | Role/shop/database, token hội thoại, bất đồng bộ, view và principal riêng, câu hỏi đối chiếu SQL |

Bronze/Silver có test Delta local và Job/đối chiếu trên Databricks thật; bằng chứng nằm ở [`DATA_PLATFORM.md`](DATA_PLATFORM.md). Gold E3 có test Delta và công cụ nghiệm thu riêng, trạng thái workspace ở [`E3_GOLD.md`](E3_GOLD.md). Gate E4 của F6 đã PASS, bằng chứng ở [`E4_QUALITY.md`](E4_QUALITY.md). Browser end-to-end tự động và demo tổng thể F7 còn **Planned**. Test API dùng database test/rollback; không thay browser end-to-end.

Data có notebook chính `00_pipeline.py` và ba notebook riêng E1/E2/E3. Test notebook kiểm tra điều phối E1→E2→E3, từng entry chỉ chạy đúng tầng, trả kết quả cho Job và không báo thành công khi xử lý lỗi. Test preflight xác nhận lượt E1/E2 không đổi không gọi Spark/writer E1/E2 nhưng Gold vẫn refresh trên warehouse; thay đổi nguồn/dependency/target/config không được SKIP sai. Test warehouse kiểm tra metadata thiếu, deduplicate, deadline chung, giới hạn reader và đóng checkpoint stream. `acceptance.py` và `gold_acceptance.py` chạy riêng. Cách demo từng bước ở [Data platform](DATA_PLATFORM.md#demo-từng-bước-bronze--silver).

## Nguyên tắc

- Mỗi hành vi mới hoặc thay đổi hành vi (API, service, model/constraint, component/route frontend, script, cấu hình) phải có test mới hoặc test được cập nhật trong cùng task và commit. Test phải kiểm tra kết quả quan sát được cùng các nhánh lỗi, phân quyền, biên và invariant liên quan; chỉ chạy lại test cũ không tính là đã cover phần mới.
- Thay đổi chỉ về tài liệu phải có lệnh kiểm tra phù hợp, tối thiểu là kiểm tra diff. Chỉ coi task hoàn thành khi test và kiểm tra liên quan đều pass.
- Backend test dùng PostgreSQL `fashion_test`, tách khỏi database development `fashion`.
- Compose giữ `TEST_DATABASE_URL` trong container ở database local `fashion_test` ngay cả khi `DATABASE_URL` ứng dụng trỏ tới Lakebase. Test không được tạo/drop bảng trên Lakebase đang phục vụ website.
- Các test thông thường dùng transaction riêng và rollback sau test. Hai ca giỏ hàng đồng thời tạo schema riêng trong database test để dùng commit thật giữa các session; schema được xóa trong `finally`. Không tạo dữ liệu này trong database development.
- Constraint quan trọng phải được kiểm tra ở database, không chỉ kiểm tra bằng Python.
- Không bỏ qua, làm yếu hoặc xóa test đang fail để làm suite xanh.

## Cách chạy

```powershell
docker compose --env-file .env.example up -d db backend frontend
docker compose --env-file .env.example exec -T backend pytest -q
docker compose --env-file .env.example exec -T frontend npm test
```

## Hook pre-commit

Test cấu hình kết nối chạy bằng Python trên máy có Docker Compose, không khởi động hoặc sửa database:

```powershell
python -m unittest discover -s tests -v
```

Ba ca kiểm tra Compose thực tế: file mẫu trỏ `db`, URL Lakebase được chuyển nguyên vẹn cùng SSL và database test vẫn tách biệt, thiếu URL thì dùng thông số Postgres local.

Hook được lưu trong `.githooks/pre-commit`. Kích hoạt một lần cho mỗi clone:

```powershell
git config core.hooksPath .githooks
```

Mỗi lần `git commit`, hook build image, đồng bộ npm theo lockfile khi frontend đã dừng, kiểm tra regression của hook rồi khởi động Docker Compose bằng `.env.example` để kiểm tra local. Sau đó chạy Ruff lint/format, ESLint/Prettier, áp dụng và kiểm tra migration, toàn bộ pytest backend, lint/format và test Bronze/Silver trong image data test riêng, Vitest, build frontend, audit dependency và smoke test hai service. Bất kỳ lệnh nào thất bại sẽ chặn commit. Nếu `.env` tồn tại và hook đã bắt đầu thay đổi service, khi kết thúc hook khôi phục backend/frontend bằng `.env`, kể cả khi test hoặc dependency fail; khôi phục thất bại cũng chặn commit và không in thông báo pass. Vì vậy môi trường đã chuyển Lakebase không bị giữ lại ở cấu hình test local sau commit. Hook vẫn làm service khởi động lại trong quá trình kiểm tra. Lint/format chỉ kiểm tra, không tự sửa file. Có thể chạy lại thủ công bằng `git hook run pre-commit`. Docker Desktop cần chạy; build image data test cần Python registry/Maven, cài dependency và audit cần npm registry. Container data test chỉ là công cụ kiểm thử code local, không thay thế Databricks web. Hook kiểm tra working tree đang có trên máy, nên trước khi commit từng phần cần bảo đảm code được test khớp phần đã stage. Cách kiểm tra race dependency và lệnh lint/format nằm trong [`DEVELOPMENT.md`](DEVELOPMENT.md#chuẩn-hóa-code).

Test hook chạy hook thật với Docker giả lập: giữ kiểm tra lỗi dependency/test, đồng thời kiểm tra khôi phục `.env` khi thành công hoặc fail và lỗi khôi phục chặn commit. Ba regression về khôi phục đều fail với hook cũ và pass sau sửa.

`backend/app/tests/test_code_quality.py` và `frontend/quality.test.js` chạy CLI thật trên đoạn code qua stdin: code hợp lệ được chấp nhận, biến/import lỗi, JSX chưa khai báo, hook có điều kiện và dependency effect thiếu bị từ chối. Test format xác nhận code chưa chuẩn trả exit code 1 và output sau format pass. Các probe không tạo file lỗi trong source tree.

## Test đã có

- FastAPI health endpoint trả `200` và payload `{"status": "ok"}`.
- User role chỉ nhận `BUYER`, `SHOP_OWNER`, `ADMIN`.
- Email user và tên category là duy nhất.
- Một user sở hữu tối đa một shop.
- Giá cơ sở của product không âm.
- SKU và bộ `(product_id, size, color)` của variant là duy nhất.
- Tồn kho không âm và mỗi variant có tối đa một dòng inventory.
- Các giá trị mặc định và timestamp có timezone được tạo đúng.
- Trạng thái phiếu nhập hợp lệ, số lượng nhập dương và variant không bị lặp trong một phiếu nhập.
- Mỗi buyer chỉ có một giỏ; giỏ rỗng cho phép `shop_id=NULL`; số lượng và variant trong giỏ được ràng buộc.
- Mã đơn là duy nhất; trạng thái đơn và thanh toán chỉ nhận giá trị hợp lệ.
- Order item lưu snapshot và có số lượng dương; lịch sử đầu tiên cho phép `from_status=NULL`.
- Rating nằm trong khoảng 1–5 và mỗi order item chỉ có một review.
- Low-stock alert mặc định ở trạng thái chưa xử lý.
- Seed tạo đủ tài khoản, shop, catalog, tồn kho, supplier và đơn hàng; mật khẩu admin kiểm tra được bằng bcrypt.
- Chạy seed lần hai không làm thay đổi số lượng bản ghi.
- Seed tạo cảnh báo đúng variant/shop và snapshot số lượng cho toàn bộ tồn dưới ngưỡng; chạy lại bù cảnh báo thiếu, giữ tồn kho/ngưỡng đã sửa, cảnh báo mở và lịch sử đã giải quyết, không tạo trùng. Tồn bằng ngưỡng hoặc ngưỡng 0 với tồn 0 không tạo cảnh báo.
- Trang Tồn kho phân biệt `Hết hàng` ở số lượng 0 (kể cả ngưỡng 0), `Sắp hết` ở tồn dương dưới ngưỡng và tồn đủ không có nhãn cảnh báo.
- SKU của seed khớp `P{product_id}-{size}-{color}` và chạy lại với mốc ngày khác vẫn không nhân đôi đơn hàng.
- Các bảng có luồng cập nhật nhận `updated_at` có timezone.
- Auth: mật khẩu 8–72 byte được bcrypt hash; tài khoản mới bị chặn login trước xác minh; token xác minh/reset hết hạn, dùng một lần và token resend thay thế token cũ; response forgot không lộ email tồn tại; cooldown trả `429`; reset đổi mật khẩu và vô hiệu JWT cũ qua `auth_version`; lỗi SMTP đăng ký vẫn giữ account để resend; `/auth/me` không lộ hash.
- Hồ sơ/sổ địa chỉ P1: kiểm tra dữ liệu local đúng 34 tỉnh và 3.321 xã với mã duy nhất/hierarchy 2 cấp; endpoint địa danh lọc đúng tỉnh; mọi role đọc/sửa profile nhưng không sửa email/role; BUYER CRUD địa chỉ, ownership/role, mã tỉnh–xã, tối đa 10, tự tạo/đổi/xóa mặc định. Frontend kiểm tra tìm địa danh không dấu, reset xã khi đổi tỉnh, chỉ gửi mã đã chọn và checkout tự điền/đổi snapshot từ sổ địa chỉ.
- Wishlist P2: kiểm tra BUYER thêm/xóa idempotent, unique buyer–product, phân quyền, product không tồn tại, item được giữ nhưng đánh dấu không khả dụng khi product/shop bị ẩn và trạng thái tồn kho hiện tại. Frontend kiểm tra tim ở catalog/chi tiết, điều hướng, xóa item, product tạm ẩn và trạng thái rỗng/lỗi.
- Sở thích P3: kiểm tra mặc định rỗng, options từ catalog, lưu/thay thế atomically, loại lựa chọn trùng, tách dữ liệu giữa buyer, giữ màu cũ khi variant bị ẩn, validation category/color/khoảng giá và phân quyền. Frontend kiểm tra tải lựa chọn hiện tại, gửi đúng payload, chặn khoảng giá ngược và không hiện form rỗng giả khi tải lỗi.
- Gợi ý P4: `test_recommendations.py` kiểm tra điểm và thứ tự trước limit, nhiều variant không nhân điểm/product, fallback chưa có/rỗng/không khớp sở thích, biên giá/một cận/giá 0, giá variant thay vì base price, loại catalog ẩn/hết kho/thiếu inventory, không dùng variant không bán được để cộng điểm, sở thích riêng và giá/rating hiện tại, phân quyền/khóa tài khoản/limit. `recommendations.test.jsx` kiểm tra thứ tự API, link, giá VND, tim đồng bộ và lỗi lưu tim giữ trạng thái cũ, tải/rỗng/lỗi riêng, catalog tiếp tục lọc, không gọi API cho khách/role khác và bỏ response trễ sau đăng xuất.
- Email service: test fake SMTP xác nhận STARTTLS, App Password và link token nằm trong fragment; kiểm tra cả subject, bản text, template HTML, CTA, link dự phòng, thời hạn và hướng dẫn bảo mật của ba loại email. Toàn bộ API test dùng fake email sender nên không phụ thuộc Gmail/network.
- Thiếu, sai, hết hạn token hoặc user bị khóa đều bị từ chối; dependency role và shop lấy quyền sở hữu từ database thay vì tin `shop_id` trong token.
- API shop chỉ cho SHOP_OWNER tạo và sửa shop của mình; từ chối `owner_id` do client gửi và không cho tạo shop thứ hai.
- Tạo sản phẩm cùng variant và inventory trong một transaction; variant trùng làm rollback toàn bộ; `shop_id` do client gửi bị từ chối.
- SKU do catalog service sinh không va chạm khi size/color chứa dấu gạch ngang, dấu phần trăm hoặc dấu gạch dưới.
- Shop khác không được sửa, ẩn sản phẩm hoặc quản lý variant; xóa sản phẩm là soft delete và có thể hiện lại qua `PUT`.
- Catalog công khai lọc, sắp xếp, phân trang theo giá variant hoạt động; ẩn sản phẩm và shop không hoạt động; chi tiết có tồn kho và rating trung bình. Danh sách quản lý shop chỉ trả sản phẩm thuộc shop hiện tại nhưng giữ cả product/variant đã ẩn, hỗ trợ lọc và phân trang; buyer/khách không gọi được.
- Luồng API nối đăng ký, xác minh email, đăng nhập, tạo shop, tạo sản phẩm, catalog công khai, chặn buyer sửa sản phẩm và soft delete.
- Frontend gửi đúng body login/register/verify/resend/forgot/reset, điều hướng tới trang chờ email, kiểm tra xác nhận mật khẩu, hiển thị lỗi API và link resend khi email chưa xác minh.
- Quyền runtime sequence: test PostgreSQL local tái hiện INSERT lỗi 42501 khi chỉ có quyền bảng; áp dụng `backend/docker/grant-runtime-sequences.sql` bằng role chủ sở hữu rồi kiểm tra INSERT tự tăng ID cho sequence hiện có và mới, chạy script lặp lại và không cấp CREATE schema. Hướng dẫn áp dụng Lakebase nằm trong [Deployment Guide](DEPLOYMENT_GUIDE.md#đăng-ký-báo-lỗi-quyền-sequence).
- Frontend gọi lại catalog với query params khi đổi bộ lọc hoặc trang, về trang 1 khi đổi filter, hiển thị trạng thái rỗng/lỗi và giá từ API.
- Chi tiết sản phẩm hiển thị giá/tồn kho đúng variant được chọn, xóa size khi đổi màu và báo lỗi sản phẩm không tồn tại.
- Frontend thêm đúng `variant_id` vào giỏ; khi nhận `CART_DIFFERENT_SHOP` chỉ gọi xóa giỏ và thêm lại sau khi buyer xác nhận. Trang giỏ chặn số lượng vượt `stock_quantity`, gửi đúng body cập nhật, xóa item và cập nhật tổng tiền/trạng thái rỗng từ response API.
- Frontend checkout gửi thông tin người nhận cùng phương thức thanh toán, giữ nguyên thông báo `409` thiếu hàng trên form và chuyển tới chi tiết đơn sau khi thành công. Danh sách đơn gửi filter trạng thái, chỉ hiện thao tác hủy cho `PENDING` và gửi lý do hủy.
- Chi tiết đơn hiển thị item snapshot, tổng tiền, giao hàng và lịch sử trạng thái; nút đánh giá chỉ hiện cho item `DELIVERED` có `review_id=null`, gửi rating/comment đúng contract và đổi ngay sang trạng thái đã đánh giá sau response thành công.
- Giỏ hàng C3/F2-10–11: xem giỏ rỗng, cộng dồn variant, chặn khác shop đúng error payload, giá/tồn kho hiện tại, sửa/xóa item và đặt lại shop khi giỏ rỗng.
- Giỏ hàng từ chối số lượng không hợp lệ, tài nguyên thiếu/ẩn, quyền truy cập của shop owner hoặc buyer khác và dữ liệu giá/shop/buyer do client gửi. Lỗi vượt tồn và lỗi commit đều giữ nguyên giỏ; test hai session kiểm tra các request thêm đồng thời.
- Checkout C4/F2-12–17: giỏ rỗng trả `400`; checkout hợp lệ trừ đúng kho, xóa giỏ và ghi đúng một dòng lịch sử trạng thái; thiếu tồn kho rollback toàn bộ (không tạo đơn, không trừ kho, giỏ giữ nguyên); từ chối và rollback nếu variant/product bị ẩn hoặc shop bị khóa sau khi item đã vào giỏ; giá trong đơn giữ nguyên sau khi shop đổi giá; `total_amount` client gửi bị bỏ qua và tổng luôn tính từ giá database; test hai session xác nhận hai buyer checkout đồng thời trên cùng variant chỉ một đơn thành công khi kho chỉ đủ một đơn, đồng thời hai request trên cùng giỏ chỉ tạo đúng một đơn.
- State machine C5/F3-18–24: chuỗi giao hàng đầy đủ ghi đủ history và thanh toán COD; chặn nhảy cóc/hủy sai trạng thái; buyer/shop chỉ truy cập đúng đơn; hủy hoàn kho đúng một lần; lỗi commit rollback trạng thái, history và tồn kho; race buyer hủy với shop xác nhận chỉ áp dụng một transition.
- Tồn kho/cảnh báo C6/F4-28–29: danh sách tồn kho chỉ trả variant của shop hiện tại kèm cờ `is_low`; sửa ngưỡng tính lại `is_low`, từ chối shop khác (`403`), variant không tồn tại (`404`) và ngưỡng âm (`422`); checkout đưa tồn kho xuống dưới ngưỡng sinh đúng một cảnh báo, checkout tiếp theo vẫn dưới ngưỡng không sinh cảnh báo thứ hai; hủy đơn hoàn kho lên trên ngưỡng tự động giải quyết cảnh báo đang mở; `check_low_stock`/`resolve_alerts_if_ok` không bao giờ raise ra ngoài kể cả khi `commit()` lỗi (test ép lỗi bằng monkeypatch); test hai session gọi đồng thời `check_low_stock` trên cùng variant xác nhận partial unique index chặn tạo trùng; test resolve alert đồng thời với trừ kho xác nhận row lock chặn quyết định từ số lượng cũ và giữ đúng một alert mở khi tồn kho cuối dưới ngưỡng.
- Supplier C7: CRUD giới hạn theo shop hiện tại; sửa tên rỗng (`null`) trả `400`; sửa/xóa nhà cung cấp shop khác trả `403`; xóa là soft delete và vẫn hiện trong danh sách quản lý với `is_active=false`.
- Nhập hàng C7/F4-25–27, F4-30: tạo phiếu với supplier/variant không tồn tại trả `404`, thuộc shop khác trả `403` (hai trường hợp tách biệt, không gộp chung mã lỗi), supplier đã soft-delete trả `400`; `items` trùng `variant_id` trả `422`; `DRAFT→ORDERED→RECEIVED` cộng đúng kho từng variant, đặt `received_at` và tự động giải quyết cảnh báo tồn kho thấp đang mở khi kho vượt ngưỡng; gọi `RECEIVED` lần hai trả `400` và kho không đổi; chuyển trạng thái sai (`RECEIVED` từ `DRAFT`, tiếp tục sau `CANCELLED`) trả `400`; đọc/sửa phiếu của shop khác trả `403`; danh sách phân trang và lọc đúng theo `status`, chỉ trả phiếu của shop hiện tại.
- Review C8/F5-31–34: review khi đơn chưa `DELIVERED` trả `400`; review order item của buyer khác trả `403`; order item không tồn tại trả `404`; rating ngoài 1–5 trả `422`; review hợp lệ trả `200` và lưu đúng `product_id` suy từ variant; chi tiết đơn đổi `review_id` từ `null` sang ID review tương ứng; review lần hai cùng order item trả `400`; `GET /products/{id}/reviews` trả đúng tổng số, `rating_average` cập nhật ngay sau review mới và khớp với `rating_average` ở chi tiết sản phẩm; sản phẩm chưa có review trả `rating_average=null`; sản phẩm không tồn tại trả `404`.
- Số liệu thống kê shop C9/F1-8: đơn giao lúc 20:00 UTC (03:00 giờ VN ngày hôm sau) được tính doanh thu đúng vào ngày VN kế tiếp, không lệch sang ngày UTC — kiểm tra trực tiếp việc quy đổi múi giờ trong query thay vì chỉ test dữ liệu cùng ngày; `order_count`/`cancelled_count` đếm theo `created_at` giờ VN, mọi trạng thái; `cancel_rate` và `aov` trả `null` khi mẫu số bằng 0; số liệu chỉ tính trên đơn của shop hiện tại dù có đơn shop khác cùng thời điểm; `revenue-by-day` nhóm đúng theo ngày VN của `delivered_at`, bỏ qua đơn chưa `DELIVERED`; `top-products` cộng dồn đúng theo `product_id` khi nhiều variant cùng sản phẩm được bán, sắp xếp giảm dần và giới hạn theo `limit`; `from` lớn hơn `to` trả `400`; vai trò khác `SHOP_OWNER` trả `403`.
- Admin C10: danh sách user lọc theo role và tìm theo email/họ tên, chỉ `ADMIN` gọi được (`401`/`403` cho trường hợp khác); admin tự khóa chính mình trả `400`, tự mở lại vẫn `200`, khóa user không tồn tại trả `404`; khóa shop khiến sản phẩm của shop đó biến mất khỏi `GET /products` công khai, mở lại thì hiện lại (gián tiếp qua điều kiện `Shop.is_active` đã có ở C2); danh sách đơn admin trả đúng tổng số trên toàn hệ thống và lọc đúng theo `shop_id`/`status`; số liệu tổng quan admin cộng dồn đúng doanh thu/số đơn của nhiều shop trong cùng kỳ.

- Frontend SHOP_OWNER D3: chủ shop chưa có shop chỉ thấy form tạo shop (không gọi API quản lý), tạo thành công thì lưu `shop_id` vào phiên và mở sidebar, tạo lỗi thì giữ form và hiện lỗi API; dashboard gọi `/shop/stats/dashboard` với đúng khoảng 30 ngày mặc định, gọi lại khi đổi ngày, hiện 4 chỉ số, `—` khi `cancel_rate`/`aov` là `null`, ưu tiên tồn kho, lỗi `400` khi khoảng ngày sai và biểu đồ điền 0 cho ngày thiếu kể cả khi qua tháng; trang sản phẩm hiện cả sản phẩm đã ẩn, lọc `is_active`, bật/tắt qua `PUT /products/{id}`, tạo sản phẩm gửi mọi biến thể trong một request và giữ dialog khi lỗi, sửa thông tin, giá/trạng thái variant và thêm variant; trang đơn hàng chỉ hiện nút đúng transition của shop cho từng trạng thái, gửi `PATCH` đúng body, hủy kèm lý do trong `note`, lọc theo trạng thái, hiện lỗi backend và giữ ô thao tác là table cell hợp lệ; tồn kho tìm theo tên/SKU, lọc mức tồn, phân trang 10 dòng, tô đỏ dòng `is_low`, chặn ngưỡng không hợp lệ, cập nhật dòng theo response và giữ giá trị khi lỗi; cảnh báo tìm theo sản phẩm và phân trang; nhà cung cấp tìm theo tên/điện thoại/địa chỉ, lọc trạng thái, phân trang và thêm/sửa/ngừng hợp tác/khôi phục đúng endpoint; phiếu nhập chỉ cho chọn nhà cung cấp đang hợp tác, chặn biến thể trùng, gửi đúng body, hiện nút theo trạng thái và link sang tồn kho sau khi nhận hàng.

- Frontend ADMIN D4: vai trò khác không vào được `/admin/*`; dashboard gọi `/admin/stats/dashboard` với khoảng 30 ngày mặc định, hiện 4 chỉ số, sidebar đủ các trang quản lý cùng Chatbot Genie, hiển thị lỗi API khi khoảng ngày sai; link Databricks Dashboard/Genie chỉ xuất hiện (mở tab mới, `rel="noreferrer"`) khi biến môi trường có giá trị, ngược lại ghi "chưa được cấu hình"; trang người dùng gửi filter `role`/`keyword`, khóa/mở theo response và giữ nguyên dòng khi backend từ chối tự khóa; trang shop gửi `keyword`/`is_active` cùng tham số phân trang phía server, xóa được bộ lọc, khóa/mở theo response và hiện lỗi; trang đơn toàn hệ thống tải danh sách shop cho bộ lọc, gửi đúng `shop_id`/`status`/`from`/`to` và hiện tên shop.

- Dashboard website mở rộng D3/D4: `backend/app/tests/test_dashboards.py` kiểm tra kỳ trước cùng số ngày, ngày Việt Nam, revenue theo giao và status theo tạo, giá snapshot, tồn đọng ngoài kỳ, tồn kho hiện tại, không nhân đôi khi nối bảng, giới hạn shop từ user/database, role và lỗi ngày, giữ sales lịch sử catalog đã ẩn. `frontend/src/components/dashboard/dashboard.test.jsx` kiểm tra so sánh kỳ trước bằng 0/null, tỷ lệ hủy dùng điểm %, tỷ trọng shop trên tổng hệ thống, link đúng role, preset/làm mới, request cũ hoàn thành muộn, trạng thái rỗng, trục/bảng VND và nhóm tháng/năm đúng biên. Kiểm tra responsive bằng trình duyệt thật; định nghĩa ở [`WEB_DASHBOARDS.md`](WEB_DASHBOARDS.md).

Toàn bộ backend Planning C0–C10, P1–P4 và frontend D1–D4 đã có test. Data E1–E4 và chatbot Genie đã có test và nghiệm thu workspace; Dashboard Databricks E5 và demo tổng thể G còn Planned.

## E4 và chatbot Genie trên website

`data/tests/test_quality_check.py` kiểm tra năm điều kiện E4, biến động nguồn,
đếm Bronze sau hai lượt pipeline, fingerprint SQL thực trên Delta, Decimal tiền,
inventory/status không hợp lệ và nhánh lỗi. `test_quality_notebook.py` kiểm tra
tham số notebook con và việc gate thất bại không trả success. Bằng chứng gate
workspace PASS 5/5 nằm ở [E4 Quality](E4_QUALITY.md).
`test_quality_acceptance.py` kiểm tra CLI chờ hai Job thành công và chặn Job
sai target, loại shop, nhiều task, còn lượt chạy hoặc thất bại.

`backend/app/tests/test_chatbot.py` và `test_genie_client.py` kiểm tra admin/shop,
shop lấy từ database, buyer/khách/tài khoản khóa, scope thiếu không fallback,
token hội thoại ràng buộc user/role/shop/space và audience riêng với token đăng
nhập, chữ ký/hết hạn, trạng thái Genie/query, giới hạn kết quả và lỗi OAuth sạch.
`frontend/src/pages/chatbot.test.jsx` kiểm tra hai role và route buyer bị chặn,
contract Axios, hội thoại tiếp nối/reset, chặn gửi trùng, polling/retry/timeout,
response trễ, lỗi/rỗng/truncated, text HTML an toàn và định dạng VND.

`frontend/src/components/chatbot/chatbotWidget.test.jsx` kiểm tra nút nổi cho
ADMIN/SHOP_OWNER có shop, tải API khi mở lần đầu, thu gọn/Escape và focus,
giữ hội thoại/câu hỏi nháp qua chuyển trang, trang hồ sơ và mở rộng; chỉ poll
một luồng khi thu gọn/chuyển trang, không gửi lại câu hỏi; lỗi/retry cấu hình,
lịch sử khi không khả dụng; đăng xuất dừng request và bỏ dữ liệu riêng tư.
BUYER, khách và chủ shop chưa tạo shop không thấy nút và không gọi API chatbot.

`data/tests/test_genie_space.py` kiểm tra metadata chỉ dùng Gold, metric C9,
gate trước provision, shared shop view/grant, retry dùng lại principal/space.
`test_genie_acceptance.py` chỉ chấp nhận permission denial thật, phân biệt lỗi
bảng thiếu và lỗi hạ tầng. Nghiệm thu bằng OAuth của từng principal, đối chiếu
câu hỏi thực bằng SQL độc lập và kiểm tra browser nằm ở [Genie Chatbot](GENIE_CHATBOT.md).

```powershell
docker compose --env-file .env.example exec -T backend pytest -q app/tests/test_chatbot.py app/tests/test_genie_client.py
docker compose --env-file .env.example exec -T frontend npm test -- src/pages/chatbot.test.jsx
docker run --rm -v D:/DALN/data:/data daln-data-test pytest -q tests/test_quality_check.py tests/test_quality_notebook.py tests/test_quality_acceptance.py tests/test_genie_space.py tests/test_genie_acceptance.py
```


## Nâng cấp chatbot Space chung và lịch sử (06/10/2026)

`test_chat_history.py` kiểm tra ownership riêng từng tài khoản kể cả admin,
Space chung nhưng principal riêng, token chéo shop bị chặn, mở lại/lưu/poll
không nhân đôi, phân trang không mất/trùng tin, đổi tên/xóa, cấu hình cũ hoặc
Genie không khả dụng vẫn đọc snapshot nhưng không resume, rollback và trạng thái
đang cấp quyền. `test_chat_migration.py` tái hiện lỗi URL email percent-encoded.
Frontend có test lịch sử mở lại/fresh token, đọc snapshot khi Genie không khả dụng, đổi tên/xóa sau xác nhận, response
trễ sau đổi session, lịch sử cũ và tự kiểm tra quyền đang provision.
Data test worker kiểm tra thay đổi shop/owner, retry/backoff, publication sau
acceptance, không tạo trùng Space/secret, mapping fail closed, không tạo
metadata chứa mẫu khách hàng, lock concurrent writer và polling native không
đánh thức warehouse. Test Compose kiểm tra credential quản trị chỉ mount vào
worker tùy chọn. `test_genie_worker_setup.py` kiểm tra cấp workspace admin chỉ
cho worker, reuse secret, không sửa runtime chatbot và chặn bootstrap trước E4/
sai workspace/đường dẫn secret. `test_genie_language.py` kiểm tra đối chiếu đúng
cột metric và chỉ dọn hội thoại do lượt nghiệm thu tạo, không ghi token vào report.
Nghiệm thu thực và giới hạn ở [Genie Chatbot](GENIE_CHATBOT.md).

`python -m unittest discover -s tests -v` kiểm tra Compose và Docker build
context thật với credential giả: image backend phải loại `.env`, runtime,
journal và file tạm/lock của Genie, vẫn giữ source và cấu hình mẫu không có secret.

## Regression sau rà soát người dùng

`test_cors.py` dùng preflight thật kiểm tra origin lấy từ cấu hình, bỏ path và
từ chối origin ngoài cấu hình. `cartSafety.test.jsx` kiểm tra checkout khi còn
nháp/đang ghi/hết hàng và giữ nháp dòng khác. `profilePage.test.jsx` và
`buyerFlow.test.jsx` kiểm tra request đang chờ không tạo submit thứ hai.
`orderDetailNavigation.test.jsx` và `productDetailNavigation.test.jsx` kiểm tra
đổi route không giữ đơn/dialog/đánh giá cũ, lỗi không bị hiểu là dữ liệu rỗng.
`components/orders/orderDetails.test.jsx` kiểm tra hai role gọi endpoint chi
tiết, hiển thị snapshot, lỗi quyền/thử lại và Escape; không cấp quyền đánh giá
cho shop/admin. `orderPresentation.test.js` kiểm tra mốc UTC qua ngày Việt Nam.
`chatbot.test.jsx` kiểm tra Enter, Shift+Enter và IME. Các regression giỏ/hồ
sơ/đổi route/CORS đã tái hiện fail trước khi sửa và pass sau sửa.

Kết quả dùng thử và giới hạn ở [Rà soát người dùng](USER_JOURNEY_REVIEW.md).

## Regression giao diện theo vai trò (07/10/2026)

`components/modalDialog.test.jsx` kiểm tra mở native dialog, focus vào form,
Escape đóng và trả focus về nút mở, giữ dialog khi request đang chờ và dọn
native dialog khi unmount. `productImage.test.jsx` kiểm tra ảnh mẫu
`placehold.co` dùng fallback cục bộ, đúng minh họa và vẫn tải URL ảnh thật.
`profilePage.test.jsx` kiểm tra nhãn vai trò dễ đọc, giữ trường role chỉ đọc.
`dashboard.test.jsx` kiểm tra kỳ 7/30/90 ngày đang chọn và bỏ trạng thái chọn
khi đổi sang ngày tùy chỉnh. `siteLayout.test.jsx` kiểm tra theme theo role
cùng các điều hướng được phép. Phạm vi trình duyệt và giới hạn ghi ở
[UI/UX](UI_UX.md#lượt-rà-soát-theo-vai-trò-ngày-07102026).

Modal có test hiển thị lỗi API bên trong. Regression `adminPages.test.jsx`
đã fail trước sửa vì lỗi khóa shop chỉ nằm trên trang nền, rồi pass sau khi
lỗi xuất hiện trong dialog đang mở; trạng thái shop vẫn giữ nguyên khi lỗi.
