# Quy tắc cho coding agent — Fashion E-Commerce

File này áp dụng cho toàn bộ repository. Mục tiêu là triển khai đúng `docs/PLANNING.md`, giữ các bất biến nghiệp vụ và giao lại một thay đổi có thể kiểm tra được.

## 1. Nguồn sự thật và phạm vi

- Trước mỗi task, đọc mục liên quan trong `docs/PLANNING.md`, sau đó đọc code, test và tài liệu kỹ thuật hiện có. Dùng `docs/PROPOSAL.md` và `README.md` để hiểu bối cảnh; khi có khác biệt, ưu tiên `docs/PLANNING.md`.
- Chỉ triển khai phần được yêu cầu và Definition of Done tương ứng. Không tự bắt đầu giai đoạn sau, thêm tính năng dự đoán, đổi quy tắc nghiệp vụ hoặc mở rộng API ngoài kế hoạch.
- Chỉ hỏi người dùng khi điểm chưa rõ có thể thay đổi schema, API contract, quyền truy cập, metric, bảo mật hoặc hành vi nghiệp vụ. Với quyết định kỹ thuật nhỏ không ảnh hưởng các mặt đó, tự chọn cách đơn giản nhất và ghi rõ giả định.
- Không sửa `docs/PROPOSAL.md` hoặc `docs/PLANNING.md` nếu chưa được người dùng cho phép rõ ràng. Nếu code hiện tại khác kế hoạch, nêu khác biệt trước khi thay đổi thiết kế.
- Khi phần được yêu cầu hoàn thành và đã kiểm tra, dừng đúng phạm vi; báo riêng phần còn planned hoặc đang bị chặn.

## 2. Cách làm việc

1. Xác định yêu cầu, bất biến, quyền truy cập, nhánh lỗi và test bắt buộc từ Planning.
2. Kiểm tra implementation và test hiện có trước khi sửa.
3. Tạo thay đổi nhỏ nhất nhưng hoàn chỉnh. Tận dụng pattern hiện có; chỉ tách helper khi có logic thực sự lặp lại hoặc cần bảo vệ cùng một bất biến.
4. Không refactor phần không liên quan, không dọn code tiện tay, không thêm dependency nếu chưa có nhu cầu cụ thể.
5. Chạy test phù hợp, cập nhật tài liệu kỹ thuật liên quan, rồi xem lại toàn bộ diff trước khi báo hoàn thành.

## 3. Kiến trúc và bảo mật backend

- FastAPI router chỉ nhận request, gọi service và trả response. Logic nghiệp vụ nằm trong `backend/app/services/`; SQLAlchemy model trong `backend/app/models/`, Pydantic schema trong `backend/app/schemas/`.
- Endpoint của shop owner lấy `shop_id` từ user đã xác thực và database; không tin `shop_id` do client gửi hoặc chỉ dựa vào claim trong token. Kiểm tra quyền sở hữu cho mọi tài nguyên được sửa.
- Nghiệp vụ sửa nhiều bảng phải dùng một transaction và rollback toàn bộ khi lỗi. Không commit từng phần của cùng một thao tác.
- Checkout trừ tồn kho bằng conditional update nguyên tử; không kiểm tra tồn kho kiểu đọc rồi ghi. Giá và tổng tiền lấy từ database, không lấy từ giá client gửi.
- Order item lưu snapshot tên sản phẩm, thuộc tính variant và giá tại lúc checkout. Xóa sản phẩm là soft delete để giữ dữ liệu lịch sử.
- Mọi thay đổi trạng thái đơn hàng đi qua một order transition service và ghi status history trong cùng transaction.
- Hủy đơn và nhận purchase order phải idempotent đối với thay đổi tồn kho.
- Lưu timestamp theo UTC với timezone. Chỉ chuyển sang ngày Việt Nam tại nơi Planning chỉ định, đặc biệt ở Silver layer.
- Không đưa secret, mật khẩu hoặc token thật vào code, log, test fixture được commit hoặc tài liệu. Chỉ dùng giá trị giả rõ ràng cho demo và test.

## 4. Dữ liệu và metric

- Bronze ingestion phải idempotent và dùng `MERGE`, không append mù.
- Gold dùng định nghĩa metric ở Planning C9. Revenue là tổng `total_amount` của đơn `DELIVERED`, gán theo `delivered_at` ở giờ Việt Nam.
- Chỉ bắt đầu Dashboard hoặc Genie sau khi toàn bộ kiểm tra ở Planning E4 đạt. Genie chỉ nhận Gold tables trừ khi thay đổi thiết kế đã được phê duyệt.

## 5. Frontend

- Frontend gọi API qua Axios client dùng chung; không đặt URL hoặc xử lý token rải rác trong page.
- Route theo role chỉ phục vụ trải nghiệm; backend vẫn là nơi quyết định quyền thật. Không coi việc ẩn nút là kiểm tra phân quyền.
- Hiển thị lỗi API và các trạng thái tải, rỗng hoặc thất bại khi có liên quan. Không tạo nút trông như đã hoạt động nếu API hoặc nghiệp vụ phía sau chưa có.
- Tiền hiển thị theo định dạng VND đã quy định; giá và tồn kho hiển thị phải lấy từ dữ liệu API của đúng variant.

## 6. Quy tắc test bắt buộc

**Mọi chức năng hoặc hành vi mới, cũng như mọi thay đổi hành vi, phải có test có ý nghĩa trong cùng task và commit.** Quy tắc này áp dụng cho API, service, model/constraint, migration, component/route frontend, script và cấu hình có hành vi.

- Test kết quả quan sát được và các nhánh lỗi, phân quyền, biên, transaction, idempotency hoặc concurrency liên quan. Không viết test chỉ lặp lại chi tiết implementation.
- Bug fix phải có regression test tái hiện lỗi trước khi sửa nếu thực tế có thể làm được.
- Thay đổi chỉ về tài liệu hoặc giao diện không đổi hành vi cần kiểm tra phù hợp, tối thiểu `git diff --check`; không thêm test giả tạo.
- Chạy test mục tiêu trước. Chạy suite rộng hơn khi sửa service dùng chung, schema, migration, auth, checkout, inventory hoặc order transition. Với thay đổi frontend, chạy Vitest và build.
- Không bỏ qua, tắt, làm yếu hoặc xóa test đang fail chỉ để suite xanh. Nếu không chạy được, báo lệnh, nguyên nhân và phần chưa xác minh; không ghi là đã pass.
- Hook `.githooks/pre-commit` là cổng kiểm tra trước commit; không dùng `--no-verify` để né lỗi. Các lớp test hiện có và lớp còn planned được ghi tại `docs/TESTING.md`.

## 7. Tài liệu

- Tài liệu kỹ thuật mô tả đúng phần đã triển khai. Đánh dấu phần chưa chạy là `Planned`; không trình bày kế hoạch như tính năng hoàn chỉnh.
- Khi đổi hành vi công khai, kiến trúc, schema, API contract, luồng nghiệp vụ, setup hoặc lệnh test, cập nhật tài liệu tương ứng trong cùng task và commit.
- `docs/README.md` là mục lục tài liệu và phải được cập nhật khi thêm, đổi tên hoặc bỏ tài liệu. Mỗi thông tin có một nơi chuẩn; nơi khác liên kết tới đó thay vì sao chép dài.
- Không tự ghi một quyết định kiến trúc hoặc nghiệp vụ mới vào tài liệu khi quyết định đó chưa có trong Planning hoặc chưa được người dùng duyệt.

## 8. Kiểm tra trước khi bàn giao

1. Chạy test mới và test liên quan; ghi đúng lệnh và kết quả.
2. Kiểm tra diff để tìm thay đổi không liên quan, migration thiếu, lỗ hổng phân quyền, giá/`shop_id` tin từ client, lỗi transaction và tài liệu lỗi thời.
3. Chạy `git diff --check`; kiểm tra file mới và `git status` để không bỏ sót thay đổi.
4. Nêu rõ giới hạn chưa triển khai hoặc rủi ro chưa xác minh. Không tuyên bố hoàn thành nếu Definition of Done chưa đạt.

## 9. Git và commit

- Mỗi commit nên chứa một thay đổi logic cùng test và tài liệu của nó. Không trộn file không liên quan vào checkpoint.
- Chỉ tạo commit khi người dùng yêu cầu rõ ràng. Trước khi đề xuất commit, bảo đảm thay đổi hoàn chỉnh, test liên quan pass và diff đã được kiểm tra.
- Nhắc người dùng commit sau một task hoàn chỉnh hoặc trước khi chuyển sang task lớn khác; luôn đề xuất message tiếng Việt ngắn gọn, ở thể mệnh lệnh.
- Không đề xuất commit trạng thái đang hỏng hoặc dở dang, trừ khi người dùng yêu cầu checkpoint WIP.

## 10. Lệnh thường dùng

```powershell
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example up -d
docker compose --env-file .env.example exec -T backend pytest -q
docker compose --env-file .env.example exec -T frontend npm test
docker compose --env-file .env.example exec -T frontend npm run build
docker compose --env-file .env.example exec -T frontend npm audit --audit-level=moderate
git diff --check
```

## 11. Cách báo kết quả

- Mở đầu bằng kết quả thực tế đạt được.
- Liệt kê file quan trọng đã sửa, test/check đã chạy cùng trạng thái pass/fail.
- Nêu blocker hoặc rủi ro còn lại một cách cụ thể.
- Nếu thay đổi đã thành checkpoint sạch, đề xuất commit kèm message tiếng Việt; không tự commit khi chưa được yêu cầu.
