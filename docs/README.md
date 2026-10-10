# Tài liệu hệ thống Fashion E-Commerce Platform

Thư mục này là điểm bắt đầu để hiểu mục tiêu, thiết kế, trạng thái triển khai và cách phát triển hệ thống.

## Thứ tự đọc đề xuất

1. [`PROPOSAL.md`](PROPOSAL.md) — mục tiêu, phạm vi và kết quả kỳ vọng của đề tài.
2. [`PLANNING.md`](PLANNING.md) — đặc tả nghiệp vụ, kiến trúc dự kiến và quy trình thực hiện.
3. [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) — hướng dẫn cài đặt và chạy local/demo từ đầu cho người mới.
4. Các tài liệu kỹ thuật bên dưới — mô tả trạng thái hệ thống đã được triển khai thực tế.

## Danh mục tài liệu

| Tài liệu | Trạng thái | Nội dung |
|---|---|---|
| [`PROPOSAL.md`](PROPOSAL.md) | Có sẵn | Mục tiêu và phạm vi đề tài |
| [`PLANNING.md`](PLANNING.md) | Có sẵn | Kế hoạch và đặc tả triển khai |
| [`SYSTEM_REPORT.md`](SYSTEM_REPORT.md) | Snapshot 06/10/2026 | Báo cáo tổng hợp toàn hệ thống, sơ đồ, 24 bảng, 76 API, nghiệp vụ, pipeline, chatbot và phần còn Planned; tham chiếu tài liệu chuyên trách |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | In progress | Thành phần backend/frontend (BUYER, SHOP_OWNER, ADMIN) đã chạy và ranh giới với phần còn planned |
| [`DATABASE.md`](DATABASE.md) | Implemented | Schema, quan hệ, constraint, migration, hồ sơ/sổ địa chỉ và seed data |
| [`BUSINESS_RULES.md`](BUSINESS_RULES.md) | In progress | Bất biến backend C3–C10 và P1–P4, gồm sở thích và gợi ý sản phẩm |
| [`API.md`](API.md) | In progress | Endpoint C0–C10 và P1–P4: auth, hồ sơ/địa chỉ, wishlist/sở thích/gợi ý, catalog, vận hành shop, đơn hàng, thống kê, admin, role và error contract |
| [`WEB_DASHBOARDS.md`](WEB_DASHBOARDS.md) | Implemented | Dashboard website admin/shop: mục đích KPI, API, kỳ trước, biểu đồ và ưu tiên vận hành |
| [`UI_UX.md`](UI_UX.md) | Implemented | Font tiếng Việt, layout theo role, responsive, bảng, trạng thái ảnh và kiểm tra giao diện |
| [`SHOP_STOREFRONT.md`](SHOP_STOREFRONT.md) | Implemented | Gian hàng công khai, catalog theo shop, liên kết từ sản phẩm/giỏ/đơn và bảo toàn lịch sử khi khóa shop |
| [`USER_JOURNEY_REVIEW.md`](USER_JOURNEY_REVIEW.md) | Reviewed | Rà soát từ góc nhìn khách/buyer/shop/admin đến chatbot, lỗi đã sửa, bằng chứng và giới hạn |
| [`DATA_PLATFORM.md`](DATA_PLATFORM.md) | Implemented (E1–E4, Genie) | CDC/checkpoint, Job serverless, setup/recovery; liên kết gate E4 và chatbot Genie |
| [`E2_SILVER.md`](E2_SILVER.md) | Implemented | 7 bảng Silver, dependency skip, nghiệp vụ/transaction và kiểm thử |
| [`E3_GOLD.md`](E3_GOLD.md) | Implemented | 6 bảng Gold, metric C9, overwrite, điều phối Spark/warehouse và nghiệm thu |
| [`E4_QUALITY.md`](E4_QUALITY.md) | Implemented | Gate 5 kiểm tra, hai lượt pipeline và đối chiếu Lakebase |
| [`GENIE_CHATBOT.md`](GENIE_CHATBOT.md) | Implemented | Chatbot admin/shop, Space chung và view theo danh tính, worker cấp quyền, lịch sử và nghiệm thu |
| [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) | Implemented | Cài đặt Docker, chọn database local/Lakebase, cutover/rollback, migration, seed và kiểm tra local/demo |
| [`DEVELOPMENT.md`](DEVELOPMENT.md) | In progress | Setup và workflow phát triển |
| [`TESTING.md`](TESTING.md) | In progress | Các lớp test hiện có, hook pre-commit và hướng dẫn chạy |

Các file ở trạng thái `Planned` chỉ được tạo khi phần tương ứng bắt đầu triển khai, tránh tài liệu rỗng hoặc mô tả sai trạng thái thực tế.

## Quy ước trạng thái

- `Planned`: đã có trong thiết kế nhưng chưa bắt đầu triển khai.
- `In progress`: đang được triển khai và tài liệu có thể chưa hoàn chỉnh.
- `Implemented`: đã triển khai, kiểm thử và tài liệu phản ánh code hiện tại.

## Quy tắc cập nhật

- `PROPOSAL.md` và `PLANNING.md` là tài liệu được kiểm soát; chỉ cập nhật khi thay đổi đã được thống nhất.
- Tài liệu kỹ thuật phải được cập nhật trong cùng task và cùng commit với code làm thay đổi hành vi liên quan.
- Mỗi thông tin có một tài liệu làm source of truth; các tài liệu khác dùng liên kết tham chiếu thay vì sao chép nội dung dài.
- Nội dung chưa triển khai phải được đánh dấu rõ, không mô tả như chức năng đã hoạt động.
- Khi thêm, đổi tên hoặc bỏ một tài liệu, phải cập nhật mục lục này.

## Tài liệu ngoài thư mục này

- [`../README.md`](../README.md) — giới thiệu nhanh repository.
- [`../AGENTS.md`](../AGENTS.md) — quy tắc làm việc dành cho coding agent.
