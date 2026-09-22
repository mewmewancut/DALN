# Business rules

**Trạng thái:** In progress
**Phạm vi:** Giỏ hàng C3 đã triển khai. Checkout, chuyển trạng thái đơn, nhập hàng và review vẫn là **Planned** theo các mục C4–C8 trong [`PLANNING.md`](PLANNING.md).

## Giỏ hàng C3

- Mỗi buyer có tối đa một giỏ. Giỏ không có item có `shop_id=NULL`; giỏ có item chỉ chứa variant thuộc cùng một shop.
- Thêm cùng variant cộng số lượng vào dòng hiện có. Sửa số lượng thay thế giá trị hiện tại. Thêm hàng khác shop trả lỗi và không tự xóa giỏ của buyer.
- Giá và thông tin sản phẩm lấy từ database hiện tại. Giỏ không giữ giá và không giữ chỗ tồn kho. Tồn kho có thể giảm sau khi thêm; kiểm tra cứng lúc checkout thuộc C4 và chưa triển khai.
- Mọi thao tác ghi giỏ khóa dòng buyer rồi dòng cart trong một transaction. Khóa buyer bảo vệ cả lần tạo giỏ đầu tiên khi chưa có dòng cart để khóa; các request cùng buyer được xử lý tuần tự. Lỗi nghiệp vụ hoặc database làm rollback toàn bộ thay đổi của thao tác.
- Xóa item cuối cùng hoặc xóa sạch giỏ đặt lại `shop_id=NULL`, cho phép thêm hàng của shop khác. Xóa giỏ nhiều lần không thay đổi tồn kho.
- Chỉ buyer sở hữu giỏ mới được sửa/xóa item. Thêm và đổi số lượng kiểm tra trạng thái hoạt động của variant, sản phẩm và shop, cùng tồn kho hiện tại. Các item đã ngừng bán vẫn được trả về trong giỏ để buyer có thể xóa.

Contract endpoint và mã lỗi nằm tại [`API.md`](API.md#giỏ-hàng). Test và cách chạy nằm tại [`TESTING.md`](TESTING.md).
