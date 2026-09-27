# Dữ liệu đơn vị hành chính Việt Nam

`vn_admin_units_2025.json` là dữ liệu runtime đóng gói trong backend, gồm 34 đơn vị cấp tỉnh và 3.321 đơn vị cấp xã theo mô hình chính quyền địa phương hai cấp có hiệu lực từ 01/07/2025.

- Căn cứ pháp lý: Quyết định 19/2025/QĐ-TTg.
- Dữ liệu nguồn: `thanglequoc/vietnamese-provinces-database`, bản commit được khóa trong `backend/scripts/build_vn_admin_units.py`, giấy phép MIT.
- Chỉ giữ mã và tên đầy đủ cần cho dropdown; không giữ quận/huyện, tọa độ hoặc mã bưu chính.
- Khi cần cập nhật, sửa commit nguồn có chủ đích, chạy script build rồi chạy test dữ liệu trước khi commit.
