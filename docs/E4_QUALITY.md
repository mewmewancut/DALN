# E4 — gate chất lượng dữ liệu

`data/quality_check.py` chạy đúng năm kiểm tra Planning E4. Chỉ mở Dashboard/
Genie sau khi gate in `PASS E4 gate (5/5)` trên workspace thật.

## Cách chạy

Chờ Job chính hoàn tất, giữ nguồn Lakebase ổn định và không chạy notebook khác
ghi cùng Bronze/Silver/Gold/checkpoint trong lúc nghiệm thu.

```powershell
.venv/Scripts/python.exe data/quality_acceptance.py --profile daln-cdc --warehouse-id 261b45209f3d8a59 --source-catalog daln_source --job-id 712610164863330
```

Python của công cụ cần `data/requirements.txt` (Databricks SDK). Dùng unified
authentication của profile; không truyền token trong code hay argument.
CLI dùng cấu hình Job đang có, không thay Job, lịch hoặc checkpoint. Job phải
có một notebook task, target catalog khớp và không loại shop.

Notebook `04_data_quality_check.py` gọi cùng gate; cần module `quality_check.py`,
`bronze_ingest.py`, `warehouse_sql.py` bên cạnh. Widget `source_catalog` là
catalog Lakebase federation (`daln_source`), khác catalog history CDC của Job.
Đặt `target_catalog=fashion`, `warehouse_id` và đường dẫn `pipeline_notebook`
đã cấu hình E1/E2/E3. Notebook chạy pipeline con hai lần, mỗi lần timeout
1800 giây, truyền catalog đích, `cdc_catalog`, checkpoint và warehouse vào
pipeline con. `excluded_shop_ids` luôn rỗng để nghiệm thu toàn hệ thống.
Không thêm E4 vào lịch pipeline thường xuyên.

## Các điều kiện PASS

1. Tổng doanh thu Gold bằng SUM total_amount của Lakebase orders DELIVERED.
2. Tổng total_orders Gold bằng COUNT orders Lakebase.
3. Count đủ 13 bảng Bronze bằng Lakebase; không thiếu hoặc lặp tên bảng.
4. Hai lượt pipeline thành công liên tiếp giữ nguyên doanh thu và số đơn Gold.
5. Silver fact_inventory không có quantity âm/null; orders tại nguồn, Bronze
   và Silver không có status null hoặc ngoài sáu trạng thái hợp lệ. Kiểm tra
   nguồn/Bronze ngăn dòng lỗi bị Silver loại bỏ rồi gate vẫn báo PASS.

Hai lần đều phải khớp nguồn và hợp lệ; không chỉ kiểm tra lượt cuối. Tiền so
bằng Decimal, không float. Trước khi chạy và trước/sau mỗi lượt đối chiếu,
gate chụp count cùng tổng hash hàng của 13 bảng nguồn để phát hiện thay đổi
có cùng count. Hash là kiểm tra drift bổ sung, không chứng minh snapshot giao
dịch xuyên bảng; cần cửa sổ nghiệm thu nguồn ổn định. Không in nội dung dòng
hoặc fingerprint. Gate đọc dữ liệu; hai lượt Job ghi các tầng theo pipeline
hiện có. E4 không sửa dữ liệu vận hành để tạo kết quả PASS.

In PASS/FAIL cho từng mục khi đã chụp đủ hai lượt. Lỗi Job/query, snapshot thiếu
hoặc nguồn thay đổi làm nghiệm thu fail ngay; không in PASS gate. CLI trả exit
code khác 0. Chạy lại khi đã giải quyết nguyên nhân.

## Kiểm thử

```powershell
docker run --rm -v D:/DALN/data:/data daln-data-test pytest -q tests/test_quality_check.py tests/test_quality_notebook.py tests/test_quality_acceptance.py
```

Test kiểm tra mismatch từng metric/count, tính lặp lại, dữ liệu lỗi trong từng
tầng, nguồn đổi dù count không đổi, Job lỗi, bảng thiếu/trùng, identifier sai và
notebook chỉ trả thành công sau gate PASS. Test Delta chạy SQL fingerprint thật.
Test CLI chặn cấu hình Job sai/loại shop/nhiều task/đang chạy và không báo
success hoặc chạy lượt thứ hai khi Job lỗi.

## Nghiệm thu workspace — 06/10/2026

Lệnh CLI trên đã PASS đủ 5/5 mục. Hai lượt Job `DALN` là
`480490193606600` và `563780134439107`, đều SUCCESS. Nguồn giữ nguyên count và
fingerprint trong cửa sổ nghiệm thu. Cả hai lượt: doanh thu Gold/Lakebase cùng
**12.293.000 VND**, tổng đơn **36**, đủ 13 Bronze khớp nguồn; tồn kho Silver và
status orders tại nguồn/Bronze/Silver hợp lệ. Đủ điều kiện bắt đầu Genie E6.

Đã upload notebook và hai module E4 lên thư mục Workspace cạnh `00_pipeline`.
Module `quality_check.py` export về có SHA256 khớp file local. Gate thật chạy
bằng CLI điều phối Job; notebook wrapper có test local, chưa chạy riêng trên
workspace. Dashboard E5 nằm ngoài yêu cầu chatbot này.
