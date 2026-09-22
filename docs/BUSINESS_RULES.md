# Business rules

**Trạng thái:** In progress
**Phạm vi:** Giỏ hàng C3 và checkout C4 đã triển khai. Chuyển trạng thái đơn, nhập hàng và review vẫn là **Planned** theo các mục C5–C8 trong [`PLANNING.md`](PLANNING.md).

## Giỏ hàng C3

- Mỗi buyer có tối đa một giỏ. Giỏ không có item có `shop_id=NULL`; giỏ có item chỉ chứa variant thuộc cùng một shop.
- Thêm cùng variant cộng số lượng vào dòng hiện có. Sửa số lượng thay thế giá trị hiện tại. Thêm hàng khác shop trả lỗi và không tự xóa giỏ của buyer.
- Giá và thông tin sản phẩm lấy từ database hiện tại. Giỏ không giữ giá và không giữ chỗ tồn kho. Tồn kho có thể giảm sau khi thêm; kiểm tra cứng lúc checkout thuộc C4 và chưa triển khai.
- Mọi thao tác ghi giỏ khóa dòng buyer rồi dòng cart trong một transaction. Khóa buyer bảo vệ cả lần tạo giỏ đầu tiên khi chưa có dòng cart để khóa; các request cùng buyer được xử lý tuần tự. Lỗi nghiệp vụ hoặc database làm rollback toàn bộ thay đổi của thao tác.
- Xóa item cuối cùng hoặc xóa sạch giỏ đặt lại `shop_id=NULL`, cho phép thêm hàng của shop khác. Xóa giỏ nhiều lần không thay đổi tồn kho.
- Chỉ buyer sở hữu giỏ mới được sửa/xóa item. Thêm và đổi số lượng kiểm tra trạng thái hoạt động của variant, sản phẩm và shop, cùng tồn kho hiện tại. Các item đã ngừng bán vẫn được trả về trong giỏ để buyer có thể xóa.

Contract endpoint và mã lỗi nằm tại [`API.md`](API.md#giỏ-hàng). Test và cách chạy nằm tại [`TESTING.md`](TESTING.md).

## Checkout C4

- Checkout đọc giỏ và item hiện tại của buyer; giỏ rỗng hoặc chưa tồn tại bị từ chối trước khi mở transaction.
- Toàn bộ thao tác (tạo đơn, trừ kho từng item, ghi order item, ghi lịch sử trạng thái, xóa giỏ) nằm trong một transaction. Bất kỳ item nào lỗi làm rollback toàn bộ: không tạo đơn, không trừ kho item nào, giỏ giữ nguyên.
- Trừ kho dùng `UPDATE inventory SET quantity = quantity - :n WHERE variant_id = :id AND quantity >= :n`, không đọc rồi so sánh rồi ghi. Nếu số dòng bị ảnh hưởng bằng 0 (không đủ hàng), giao dịch rollback và trả lỗi nêu rõ sản phẩm/size/màu. Cách này chống được hai request checkout đồng thời cùng làm âm kho.
- Giá và tên sản phẩm trong `order_items` là snapshot tại thời điểm checkout, lấy bằng truy vấn variant hiện tại trong cùng transaction — không lấy từ giỏ hàng (giỏ không giữ giá) và không lấy từ payload client. Đơn đã tạo không đổi khi shop sửa giá sau đó.
- `total_amount` luôn do backend cộng dồn `unit_price × quantity` của từng order item; schema request checkout không có trường `total_amount` nên client không thể gửi giá trị này.
- Đơn mới luôn ở `status=PENDING` và có đúng một dòng `order_status_history` (`from_status=NULL → to_status=PENDING`). `payment_status=PAID` ngay khi `payment_method=MOCK_CARD`, còn `COD` giữ `UNPAID` đến khi giao hàng (xử lý ở C5, chưa triển khai).
- Sau khi đơn tạo thành công, toàn bộ `cart_items` bị xóa và `cart.shop_id` đặt `NULL` trong cùng transaction — không có bước riêng có thể thất bại giữa chừng.
- Mã đơn (`code`) được gán từ một giá trị tạm duy nhất (UUID) trước, sau đó ghi đè bằng `ORD-{YYYYMMDD}-{order.id}` sau khi `id` đã có — tránh hai transaction đồng thời tranh chấp cùng một giá trị `code` trước khi mỗi đơn có `id` riêng.
- Kiểm tra `low_stock_alerts` sau khi trừ kho thuộc C6 và chưa triển khai trong checkout.

Contract endpoint và mã lỗi nằm tại [`API.md`](API.md#checkout). Test và cách chạy nằm tại [`TESTING.md`](TESTING.md).
