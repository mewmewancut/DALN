# Gian hàng công khai của shop

Đã triển khai ngày 07/10/2026 theo C2/D2 trong [Planning](PLANNING.md). Không có migration hoặc dependency mới.

## Luồng người mua

Khách và BUYER vào `/shops/:id` từ tên shop ở card sản phẩm (kể cả mục gợi ý), chi tiết sản phẩm, từng nhóm giỏ hàng, hoặc nút **Xem shop** ở danh sách/chi tiết đơn của mình. Trang hiện tên, mô tả và tháng tham gia theo giờ Việt Nam; icon cửa hàng dùng chung, không coi đó là logo shop đã upload.

Catalog gian hàng có tìm kiếm theo tên, danh mục, khoảng giá, ba thứ tự mới nhất/giá tăng/giá giảm và phân trang 20 sản phẩm. Tất cả request có `shop_id` cố định từ shop đã tải; query string không được ghi đè scope này. Filter được lưu trong URL để chia sẻ, tải lại hoặc Back từ chi tiết sản phẩm. Đổi filter trở về trang 1; xóa filter vẫn ở gian hàng hiện tại. Thay shop dọn thông tin/catalog cũ và bỏ phản hồi đang chờ.

Buyer dùng wishlist như catalog chung; khách bấm tim chuyển tới đăng nhập. Mở sản phẩm để chọn màu/size, xem giá/tồn kho đúng variant và thêm vào giỏ theo luồng hiện có. Không hiển thị gợi ý sản phẩm shop khác trong gian hàng. Route ADMIN/SHOP_OWNER giữ UX của catalog: chuyển về khu quản trị của role; API đọc gian hàng vẫn public cho mọi người.

## API và ranh giới dữ liệu

Contract chuẩn tại [API — Shop và catalog](API.md#shop-và-catalog). `GET /shops/{id}` chỉ đọc shop hoạt động, chỉ công khai ID, tên, mô tả và thời điểm tạo. Không lộ ID chủ shop, email, điện thoại, đơn của người khác, doanh thu hoặc tồn kho quản trị. Mô tả hiển thị văn bản thuần, giữ xuống dòng, không render HTML.

Sản phẩm dùng `GET /products` hiện có, chỉ product/shop đang hoạt động. Giá lọc/sort/hiển thị dùng giá thấp nhất của variant đang hoạt động, giữ đúng định nghĩa C2; tồn kho và giá biến thể cụ thể nằm ở chi tiết. Thông tin tên/mô tả gian hàng là dữ liệu hiện tại; không thêm snapshot shop vào đơn hàng.

Shop bị khóa và shop không tồn tại cùng trả `404`; frontend báo gian hàng không khả dụng, không tải catalog và dẫn về sản phẩm chung. ID sai trả `422` ở API, đường dẫn sai bị frontend chặn trước request. Shop đang hoạt động nhưng chưa có sản phẩm khác với tìm kiếm không có kết quả. Lỗi kết nối tải shop/sản phẩm có nút thử lại; lỗi danh mục hiện riêng và không chặn kết quả sản phẩm.

Đơn cũ tải độc lập, không phụ thuộc endpoint gian hàng. Khóa shop hoặc sửa giá/tên sản phẩm không đổi snapshot đơn, lịch sử trạng thái hoặc quyền xem/đánh giá. Link **Xem shop** dùng `shop_id` sẵn có trong đơn; không bổ sung dữ liệu hay quyền vào API đơn hàng.

## Cấu trúc triển khai

- Backend: router `shops.py` → `get_public_shop` trong `shop_service.py` → schema whitelist `PublicShopResponse`.
- Frontend: `ShopStorefrontPage` tải profile trước khi mount catalog; `ProductCatalog` dùng chung với `ProductListPage`; `useCatalogFilters` lưu URL riêng cho gian hàng, giữ hành vi filter local của catalog chung.
- `ShopLink` dùng chung cho tên shop; card tách link sản phẩm và link shop, không lồng hai thẻ link.

Test/lệnh chuẩn ở [Testing](TESTING.md#gian-hàng-công-khai). Kiểm tra browser và giới hạn ở [UI/UX](UI_UX.md#gian-hàng-công-khai).

## Phạm vi tiếp theo

Planned: logo/banner tùy chỉnh, theo dõi shop, chat với shop, đánh giá riêng cho shop. Các chức năng này chưa có trong bản gian hàng hiện tại.
