# Dashboard trên website

Đã triển khai cho `/admin/dashboard` và `/shop/dashboard`. Đây là phần nâng cấp D3/D4 theo yêu cầu người dùng: bổ sung so sánh kỳ trước, biểu đồ và ưu tiên vận hành. Các trang đọc database vận hành qua FastAPI; không đọc Gold và không thay thế AI/BI Dashboard E5. E4–E6 vẫn **Planned**.

## Mục đích từng khối

| Khối | Câu hỏi hỗ trợ quyết định | Phạm vi |
|---|---|---|
| Doanh thu, số đơn, tỷ lệ hủy, AOV và so sánh kỳ trước | Sức bán và chất lượng xử lý đơn đang thay đổi thế nào? | Admin toàn hệ thống; chủ shop chỉ shop của mình |
| Doanh thu theo ngày giao | Ngày nào có doanh thu, ngày nào gián đoạn? | Khoảng ngày đã chọn, ngày thiếu điền 0 |
| Trạng thái đơn tạo trong kỳ | Các đơn tạo trong kỳ hiện đang ở đâu? | Theo ngày tạo; phân bố trạng thái hiện tại, không phải phễu chuyển đổi |
| Sản phẩm bán chạy | Nên chú ý sản phẩm nào đang bán được? | Top 5 số lượng giao thành công trong kỳ, kèm doanh thu giá snapshot |
| Shop đóng góp doanh thu | Hệ thống phụ thuộc shop nào, chất lượng xử lý của các shop đó ra sao? | Admin: top 10 doanh thu, số đơn tạo/hủy, tỷ lệ hủy, AOV |
| Đơn cần tiếp tục xử lý | Còn bao nhiêu đơn cần theo dõi ở mỗi bước? | Tồn đọng hiện tại mọi thời điểm, gồm cả đơn tạo trước kỳ |
| Ưu tiên nhập hàng | Biến thể nào hết hoặc thiếu hàng và đã bán trong kỳ? | Tồn hiện tại của shop, sản phẩm và variant đang hoạt động |

Chủ shop có link sang đơn hàng và tồn kho; admin có link sang đơn hàng và quản lý shop. Link mở trang quản lý hiện có, không tự chuyển trạng thái hay nhập hàng. Không tính lợi nhuận, tỷ lệ chuyển đổi, thời gian giao hay dự báo nhập kho khi dữ liệu chưa đủ cho định nghĩa đó.

## Contract API

`GET /shop/stats/dashboard?from=YYYY-MM-DD&to=YYYY-MM-DD` yêu cầu `SHOP_OWNER`; shop lấy từ user xác thực trong database. Tham số `shop_id` từ client không quyết định phạm vi. `GET /admin/stats/dashboard` cùng tham số yêu cầu `ADMIN`, tính toàn hệ thống. Các endpoint C9/C10 cũ giữ nguyên contract.

Response gồm:

| Trường | Ý nghĩa |
|---|---|
| `from_date`, `to_date` | Hai ngày đầu/cuối, bao gồm cả hai |
| `previous_from`, `previous_to` | Kỳ ngay trước, có cùng số ngày |
| `generated_at` | Thời điểm bắt đầu tổng hợp UTC, giao diện hiển thị giờ Việt Nam |
| `overview`, `previous` | `{revenue, order_count, cancelled_count, cancel_rate, aov}` theo định nghĩa [C9](API.md#số-liệu-thống-kê-shop) |
| `revenue_daily` | Mảng `{date, revenue, order_count}` theo ngày giao ở Việt Nam; `order_count` là số đơn giao |
| `order_statuses` | Sáu dòng `{status, count}` của đơn tạo trong kỳ, kể cả trạng thái có 0 đơn |
| `top_products` | Tối đa 5 dòng `{product_id, product_name, shop_name, total_quantity_sold, total_revenue}` |
| `work_queue` | Bốn dòng `{status, count}`: PENDING, CONFIRMED, PREPARING, SHIPPING; không lọc ngày |
| `stock` | `{tracked_variants, out_of_stock, low_stock, priorities}` |
| `shops` | Admin: tối đa 10 dòng `{shop_id, shop_name, revenue, order_count, cancelled_count, cancel_rate, aov}`; shop: `[]` |

Sai hoặc thiếu token trả `401`, sai role hoặc chủ shop chưa có shop trả `403`. Thiếu/sai định dạng ngày trả `422`; `from > to` hoặc không thể biểu diễn kỳ trước trong kiểu `date` trả `400`. Các truy vấn chỉ đọc, không tạo cảnh báo và không sửa tồn kho.

## Quy tắc tổng hợp và hiển thị

Revenue/AOV dùng ngày `delivered_at` giờ Việt Nam; số đơn/tỷ lệ hủy dùng ngày `created_at` giờ Việt Nam. Hai nhóm có thể khác nhau về số lượng đơn, ví dụ đơn tạo trước kỳ nhưng giao trong kỳ. Backend dùng lại `get_overview()` và cách quy đổi ngày của C9 cho cả kỳ hiện tại và kỳ trước. Tỷ lệ hủy là trạng thái hiện tại của đơn tạo trong kỳ nên có thể thay đổi sau khi kỳ kết thúc.

So sánh doanh thu/số đơn/AOV dùng phần trăm thay đổi so với kỳ trước; nếu mẫu kỳ trước bằng 0 thì ghi rõ phát sinh mới hoặc không đổi, không hiện phần trăm vô hạn. Tỷ lệ hủy so bằng **điểm phần trăm**. Metric `null` giữ `—` và ghi chưa đủ dữ liệu so sánh. AOV không lấy trung bình các AOV theo ngày hay shop.

Sản phẩm bán chạy nhóm theo product hiện tại của variant; giá bán lấy `order_items.unit_price`, không lấy giá variant hiện tại. Lịch sử bán của sản phẩm/shop đã ẩn vẫn được giữ. Sắp xếp số lượng giảm dần rồi product ID. Shop xếp theo doanh thu giảm dần rồi shop ID; dữ liệu lịch sử của shop đã khóa vẫn tính. Tỷ trọng shop dẫn đầu chia cho doanh thu **toàn hệ thống**, không chia tổng top 10.

Tồn kho chỉ theo dõi bản ghi inventory có shop, product và variant đang hoạt động. `out_of_stock` đếm quantity = 0, kể cả ngưỡng bằng 0; `low_stock` đếm 0 < quantity < threshold. Hai nhóm không chồng nhau. `priorities` tối đa 8 dòng `{variant_id, product_name, shop_name, size, color, quantity, threshold, sold_quantity}`. Hết hàng xếp trước; trong mỗi nhóm xếp số lượng giao trong kỳ giảm dần, rồi thiếu hụt so với ngưỡng giảm dần, rồi variant ID. Tổng số biến thể thiếu hàng có thể lớn hơn số dòng hiển thị. Đây là ưu tiên từ dữ liệu quan sát, không phải dự báo nhu cầu.

Sales được tổng hợp theo variant/shop trước khi nối bảng, tránh nhân đôi revenue, số đơn hay số lượng tồn khi một đơn có nhiều item.

Giao diện mặc định 30 ngày theo ngày trình duyệt, có preset 7/30/90 ngày và tùy chọn hai ngày. Chart hiển thị ngày cho kỳ ≤93 ngày, tháng cho kỳ ≤1096 ngày, năm cho kỳ dài hơn. Các nhóm chỉ cộng ngày trong khoảng lọc, kể cả tháng/năm đầu cuối chưa đủ kỳ. Có trục VND và bảng số liệu có thể mở thay cho việc chỉ đọc đồ thị. Không có doanh thu thì hiện trạng thái rỗng.

Đổi kỳ hoặc làm mới sẽ tải lại toàn bộ response; không giữ KPI cũ trong lúc tải/lỗi. Request cũ hoàn thành muộn không ghi đè kỳ mới. Tồn kho và tồn đọng luôn là hiện trạng, có nhãn thời điểm cập nhật; không chịu bộ lọc ngày ngoài sức bán dùng để xếp ưu tiên.

## Kiểm chứng

`backend/app/tests/test_dashboards.py` kiểm tra ngày Việt Nam, kỳ trước, giá snapshot, truy vấn không nhân đôi, phân quyền, catalog đã ẩn, dữ liệu rỗng và lỗi ngày. `frontend/src/components/dashboard/dashboard.test.jsx` cùng các test trang kiểm tra so sánh, phạm vi hiển thị, contribution, preset/làm mới, request race, trạng thái rỗng và dữ liệu chart. Lệnh chuẩn tại [TESTING.md](TESTING.md).
