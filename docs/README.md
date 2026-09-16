# Tài liệu hệ thống Fashion E-Commerce Platform

Thư mục này là điểm bắt đầu để hiểu mục tiêu, thiết kế, trạng thái triển khai và cách phát triển hệ thống.

## Thứ tự đọc đề xuất

1. [`PROPOSAL.md`](PROPOSAL.md) — mục tiêu, phạm vi và kết quả kỳ vọng của đề tài.
2. [`PLANNING.md`](PLANNING.md) — đặc tả nghiệp vụ, kiến trúc dự kiến, timeline và quy trình thực hiện.
3. Các tài liệu kỹ thuật bên dưới — mô tả trạng thái hệ thống đã được triển khai thực tế.

## Danh mục tài liệu

| Tài liệu | Trạng thái | Nội dung |
|---|---|---|
| [`PROPOSAL.md`](PROPOSAL.md) | Có sẵn | Mục tiêu và phạm vi đề tài |
| [`PLANNING.md`](PLANNING.md) | Có sẵn | Kế hoạch và đặc tả triển khai |
| `ARCHITECTURE.md` | Planned | Kiến trúc tổng thể và ranh giới thành phần |
| [`DATABASE.md`](DATABASE.md) | In progress | Schema, quan hệ, constraint và migration |
| `BUSINESS_RULES.md` | Planned | Luồng nghiệp vụ và invariant |
| `API.md` | Planned | Endpoint, role và error contract |
| `DATA_PLATFORM.md` | Planned | Lakebase, Medallion, metric và data quality |
| [`DEVELOPMENT.md`](DEVELOPMENT.md) | In progress | Setup và workflow phát triển |
| [`TESTING.md`](TESTING.md) | In progress | Chiến lược và hướng dẫn chạy test |

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
