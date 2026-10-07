# Giao diện website

**Trạng thái:** Implemented
**Phạm vi:** các trang auth, BUYER, SHOP_OWNER và ADMIN thuộc Planning D1–D4.

## Quy ước giao diện

- Font **Be Vietnam Pro**, các weight 400/600/700, được phục vụ từ `frontend/public/fonts/`. Font hỗ trợ tiếng Việt và dùng `font-display: swap`; không cần kết nối Google Fonts khi chạy website. Giấy phép SIL OFL được lưu cùng font.
- Màu, typography, control và header nằm ở `frontend/src/styles/foundation.css`. Catalog/buyer dùng `frontend/src/styles.css`; sidebar, bảng và form quản lý dùng `frontend/src/styles/management.css`; dashboard và chatbot dùng stylesheet riêng.
- Tiêu đề và nội dung dùng cùng font. Tiêu đề trang thông thường khoảng 26–36 px, line-height 1.3; chỉ hero catalog và tên sản phẩm chi tiết dùng chữ lớn hơn. Nhãn dùng chữ thường, tránh giãn chữ làm dấu tiếng Việt khó đọc.
- Header nằm ngoài vùng nội dung. Auth dùng form giới hạn 520 px; các trang rộng dùng tối đa 1360 px. Trên màn hình nhỏ, điều hướng tài khoản cuộn ngang với link đang hoạt động và focus bàn phím rõ ràng.
- Catalog dùng nền trung tính, ảnh và thông tin sản phẩm trực tiếp; khu shop/admin dùng màu navy, sidebar tối và bảng trên nền trắng. Bỏ announcement và nhãn trang trí lặp lại, giữ hướng dẫn thao tác, trạng thái lỗi và cảnh báo hậu quả trong xác nhận.
- Sidebar shop/admin có icon trang trí và nhãn chữ. Dưới 1000 px, sidebar thành một hàng link cuộn ngang phía trên nội dung.
- Bảng có vùng cuộn riêng. Cột tiền/số dùng `numeric-cell` căn phải và chữ số có độ rộng bằng nhau; cột ngày dùng `date-cell`. Không suy đoán kiểu dữ liệu theo số thứ tự cột của các bảng khác nhau. Tên/email dài được phép xuống dòng.
- Checkbox/radio giữ kích thước 18 px, tách khỏi chiều cao 44 px của input văn bản. Nút chính, lỗi, thành công, disabled và focus dùng style chung.
- Card sản phẩm dùng tỷ lệ ảnh 4:5, lazy-load cho card/giỏ/wishlist, tải ngay ảnh chi tiết. `ProductImage` dùng minh họa SVG và nhãn “Chưa có ảnh” khi URL trống, lỗi hoặc thuộc `placehold.co` của dữ liệu demo; tránh hiển thị mã seed trong ảnh mẫu. Đổi URL sẽ thử ảnh mới. URL ảnh thật và giá/tồn kho vẫn do API cung cấp.
- Mục Dành cho bạn giữ thứ tự và tối đa 8 sản phẩm theo API, hiển thị một hàng card ngang nhỏ với ảnh bên cạnh tên/giá. Link và nút yêu thích vẫn truy cập được bằng bàn phím.
- Link “Đến nội dung chính” là điểm focus đầu trang; đích là `<main id="main-content" tabindex="-1">`. Hiệu ứng tiếp tục tôn trọng `prefers-reduced-motion`.
- Dialog dùng `<dialog>` native trong top layer, có chiều cao tối đa theo viewport và cuộn bên trong. `ModalDialog` dùng chung cho form/xác nhận, chặn tương tác nền, hỗ trợ Escape (trừ lúc đang gửi) và trả focus về nút mở. Form sản phẩm có hai cột trên desktop, một cột trên mobile.
- Nút chatbot nổi trên mobile dùng icon tròn 52 px để giảm che nút lưu/thao tác bảng; nhãn hỗ trợ đọc màn hình được giữ. Luồng hội thoại và quyền hiển thị nằm ở [Genie Chatbot](GENIE_CHATBOT.md).

## Nguồn tham khảo

- [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines): nhãn control, focus, nội dung dài, typography cho số, giảm chuyển động và responsive.
- [Anthropic Frontend Design skill](https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design/skills/frontend-design): hệ thống type có chủ đích, giảm trang trí dư và kiểm tra qua screenshot.
- [UNIQLO catalog](https://www.uniqlo.com/vn/en/feature/new/women): tham khảo cách ưu tiên ảnh, thông tin sản phẩm và sắp xếp catalog.
- [Google Fonts — Be Vietnam Pro](https://github.com/google/fonts/tree/main/ofl/bevietnampro): nguồn font và giấy phép.

Các nguồn trên chỉ hướng dẫn trình bày; contract API, phân quyền, chuyển trạng thái đơn và metric tiếp tục theo Planning. Không thêm thư viện UI hoặc thay đổi schema/backend trong lượt nâng cấp này.

## Kiểm tra

Vitest kiểm tra skip link/điều hướng theo role và fallback ảnh, cùng suite auth/buyer/shop/admin hiện có. Lệnh chạy chuẩn nằm ở [Testing](TESTING.md#cách-chạy).

Ảnh kiểm tra trình duyệt và số đo layout được lưu tại `output/playwright/ui-audit/`, được Git bỏ qua. Thư mục này có thể chứa dữ liệu hiển thị từ môi trường đang chạy; không đưa ảnh/snapshot tài khoản vào commit.

### Lượt rà soát ngày 06/10/2026

Đã kiểm tra bằng Codex in-app browser tại `http://localhost:5173`, dùng tài khoản demo và dữ liệu API đang chạy. Mỗi nhóm dưới đây được mở ở **1440 × 1000** và **390 × 844**. Tổng cộng 58 lượt trang/role/kích thước; các lượt cuối đã hết trạng thái tải, có tiêu đề và không tràn ngang toàn trang theo số đo `documentElement.scrollWidth <= innerWidth`. Console ở lượt kiểm tra cuối không có error.

| Nhóm | Trang đã mở | Kết quả |
|---|---|---|
| Khách/auth | `/`, `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`, `/verify-email-sent` | Pass layout; các trang email chỉ kiểm tra form, không gửi email hoặc đổi mật khẩu |
| BUYER | `/`, `/products/45`, `/cart`, `/checkout`, `/wishlist`, `/account/preferences`, `/orders`, `/orders/33`, `/account/profile` | Pass layout với sản phẩm/đơn mẫu; kiểm tra chọn màu/size, giỏ có sản phẩm, checkout và wishlist có item |
| SHOP_OWNER | `/shop/dashboard`, `/shop/products`, `/shop/orders`, `/shop/inventory`, `/shop/alerts`, `/shop/suppliers`, `/shop/purchase-orders`, `/account/profile` | Pass layout; bảng desktop vừa vùng nội dung, bảng mobile cuộn riêng; alerts/phiếu nhập hiện trạng thái rỗng của API |
| ADMIN | `/admin/dashboard`, `/admin/users`, `/admin/shops`, `/admin/orders`, `/account/profile` | Pass layout; bảng desktop vừa vùng nội dung, bảng mobile cuộn riêng |

Modal thêm sản phẩm đã mở/đóng ở cả hai kích thước. Ở mobile, chiều rộng đo được khoảng 335 px, chiều cao 804 px trong viewport 844 px; nội dung dài cuộn trong dialog. Trên trình duyệt, Enter trên skip link chuyển focus đúng tới `MAIN#main-content`.

Giỏ và wishlist của buyer demo được khôi phục về trạng thái trống ban đầu sau kiểm tra. Không đặt đơn, sửa sản phẩm, nhận hàng hay khóa tài khoản/shop. Lượt này kiểm tra trình bày và tương tác được nêu trên; các nhánh transaction/phân quyền/lỗi nghiệp vụ tiếp tục được kiểm tra bằng suite hiện có.

Các lệnh xác minh đã chạy:

```powershell
docker compose --env-file .env.example exec -T frontend npm test -- src/components/productImage.test.jsx src/components/siteLayout.test.jsx
docker compose --env-file .env.example exec -T frontend npm test
docker compose --env-file .env.example exec -T frontend npm run build
docker compose --env-file .env.example exec -T frontend npm run lint
docker compose --env-file .env.example exec -T frontend npm run format:check
git diff --check
```

Test mục tiêu: **7 pass**. Toàn bộ Vitest: **105 pass / 16 file**. Build, ESLint, Prettier và diff check: **Pass**. Backend không có thay đổi trong task này.

Browser end-to-end tự động, thử nghiệm với người dùng và các luồng email thật còn **Planned**. Dữ liệu seed vẫn dùng ảnh placeholder; lượt chỉnh UI không thay ảnh hoặc tạo đơn trên database đang chạy.

### Cải thiện thao tác sau rà soát người dùng

Giỏ hàng giữ số lượng nháp của dòng khác khi cập nhật/xóa một dòng; các thao tác ghi được khóa trong lúc request đang chạy. Thanh toán chỉ mở khi số lượng đã lưu, hợp lệ và đủ tồn kho. Hồ sơ và checkout chặn submit trùng khi đang gửi.

Mã đơn trong bảng shop/admin mở dialog chi tiết bằng API `/orders/{id}` hiện có. Dialog native giữ focus, hỗ trợ Escape, trạng thái tải/lỗi/thử lại và snapshot giao hàng/sản phẩm/lịch sử; backend vẫn quyết định quyền. Buyer dùng chung phần hiển thị snapshot, giữ quyền đánh giá của người mua. Ngày giờ đơn/đánh giá/phiếu nhập luôn hiển thị theo `Asia/Ho_Chi_Minh`, độc lập timezone máy người dùng.

Đổi route chi tiết đơn xóa đơn/dialog đánh giá cũ và bỏ response trễ. Chi tiết sản phẩm có trạng thái tải/lỗi đánh giá riêng; không hiển thị đánh giá của sản phẩm trước hoặc trạng thái rỗng giả khi request thất bại. Phạm vi sử dụng trực tiếp và bằng chứng kiểm tra ở [Rà soát người dùng](USER_JOURNEY_REVIEW.md).

### Lượt rà soát theo vai trò ngày 07/10/2026

Dùng Chromium qua Playwright CLI tại `http://localhost:5173`, API đang chạy và tài khoản demo của từng role. Mở toàn bộ trang dưới đây ở **1440 × 1000** và **390 × 844**: 62 lượt trang/role/kích thước, không tràn ngang toàn trang. Bảng, menu và hàng gợi ý cuộn trong vùng riêng.

| Vai trò | Trang đã mở |
|---|---|
| Khách/auth | Catalog, đăng nhập, đăng ký, quên mật khẩu, đặt lại mật khẩu, xác nhận email, chờ xác nhận email |
| BUYER | Catalog, chi tiết sản phẩm 45, giỏ, checkout, wishlist, sở thích, danh sách đơn, chi tiết đơn 33, hồ sơ/sổ địa chỉ |
| SHOP_OWNER | Dashboard, sản phẩm, đơn, tồn kho, cảnh báo, nhà cung cấp, nhập hàng, chatbot, hồ sơ |
| ADMIN | Dashboard, người dùng, shop, đơn toàn hệ thống, chatbot, hồ sơ |

Các vấn đề đã sửa: hero/catalog và hàng gợi ý quá cao; chữ giới thiệu/nhãn trang trí lặp lại; ảnh placeholder lộ mã seed; mã role thô trong hồ sơ; menu quản lý mobile chiếm nhiều hàng; mã đơn bị bẻ dòng trong bảng; thiếu chỉ báo kỳ dashboard đang chọn; hộp thoại tùy biến thiếu Escape/top layer/focus; nút chatbot mobile che một phần thao tác.

Lỗi API khi xác nhận/hủy/đánh giá được hiển thị ngay trong dialog đang mở, tránh bị backdrop che trên trang nền. Regression xác nhận khóa shop đã tái hiện fail trước sửa và pass sau sửa.

Đã mở/đóng dialog tạo sản phẩm và xác nhận khóa tài khoản, kiểm tra Escape trả focus về nút mở; lọc người dùng theo vai trò. Giỏ ban đầu trống được thêm một biến thể để xem giỏ/checkout ở cả hai kích thước, rồi khôi phục trống. Wishlist có sẵn được giữ nguyên. Không đặt đơn, khóa tài khoản/shop, sửa sản phẩm/nhà cung cấp hoặc nhận phiếu nhập; các nhánh ghi/phân quyền tiếp tục có suite test hiện có. Các form email chỉ kiểm tra hiển thị, không gửi email thật.

Bằng chứng ảnh và script ở `output/playwright/role-review-v2/` (ignored), không đưa snapshot tài khoản vào commit. Ảnh sản phẩm demo vẫn là minh họa trạng thái thiếu ảnh; chất lượng ảnh hàng thật phụ thuộc dữ liệu shop cung cấp. Không thay schema, API, metric hoặc backend trong lượt nâng cấp giao diện này.

Xác minh: `docker compose exec -T frontend npm test` **156 pass / 24 file**;
`npm run build`, `npm run lint`, `npm run format:check` qua cùng container và
`git diff --check` đều **Pass**. Phạm vi regression ở [Testing](TESTING.md#regression-giao-diện-theo-vai-trò-07102026).


## Giỏ hàng ngày 07/10/2026

Khách có link giỏ hàng và thêm variant trước khi đăng nhập. Giỏ chia thành từng nhóm shop; radio cùng nhóm chọn đúng một shop, tóm tắt và checkout chỉ tính nhóm đã chọn. Số lượng chưa lưu hoặc hàng không khả dụng của nhóm đã chọn chặn thanh toán; nhóm khác không chặn. Giỏ tạm giữ qua đăng ký/xác minh và chuyển vào tài khoản sau login. Lỗi chuyển hiển thị giỏ tạm để thử lại hoặc chỉnh hàng bị từ chối; chưa xác định kết quả do mất mạng thì khóa chỉnh sửa đến khi đồng bộ. Quy tắc ở [Business rules](BUSINESS_RULES.md#giỏ-hàng-c3).

Đã kiểm tra bằng Chromium với catalog/API Lakebase: khách thêm hai variant thuộc hai shop, tải lại vẫn giữ đủ hàng và shop đã chọn; đổi lựa chọn luôn chỉ có một radio được chọn, tổng thanh toán chỉ tính shop đó. Thanh toán chuyển sang đăng nhập; mở đăng ký vẫn giữ giỏ tạm. Giỏ hiển thị ở 1440 × 1000 và 390 × 844, không tràn ngang trên mobile. Ảnh kiểm tra ở `output/playwright/guest-cart/`, không đưa vào commit. Lượt trình duyệt này chưa gửi email thật hoặc đặt đơn thật; luồng đăng ký/xác minh/login/merge/checkout được kiểm tra trong Vitest và API tests.

Xác minh toàn bộ: backend **260 pass**, frontend **177 pass / 26 file**; Ruff, ESLint, Prettier, frontend build, Compose config và `git diff --check` **Pass**. Migration đã áp dụng trên PostgreSQL local và Lakebase; Alembic schema parity **Pass**. Lệnh và phạm vi regression ở [Testing](TESTING.md#giỏ-khách-và-checkout-một-shop).
