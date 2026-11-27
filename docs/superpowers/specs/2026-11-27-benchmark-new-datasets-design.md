# Mở rộng benchmark HAutoML: 6 dataset mới và nhóm ca G

Ngày: 2026-11-27. Trạng thái: đã duyệt danh sách ca (người dùng), chờ duyệt tài liệu này.

## Mục đích

Làm benchmark **rộng hơn**: thêm 6 dataset có đặc điểm mà 4 dataset bảng hiện tại không có (dữ liệu lớn
dùng hold-out, cột chữ, giá trị `?`, 500 feature, nhiều lớp, cột ID, rò rỉ target, target ở cột đầu, lệch lớp),
và thêm **ca ablation có chủ đích** để mỗi thành phần của hệ thống có tình huống thực sự cần tới nó.

**Không phải mục tiêu:** dựng tập kiểm tra "chưa từng thấy" (người dùng chọn mở rộng benchmark; các ca mới có
thể được dùng khi chạy thử và sửa lỗi như các ca cũ, và bài báo giữ câu caveat về việc dùng ca khi phát triển).

**Chống mục tiêu (thất bại dù chạy được):**
- Ca được chọn / sửa / bỏ dựa trên việc bản full thắng hay thua ở ca đó. Ca được viết và khoá trước; chạy thử
  chỉ để soát lỗi kỹ thuật của ca (prompt mơ hồ, fixture hỏng, bộ chấm tự động chấm sai).
- Ngưỡng ràng buộc đặt bằng tập test.
- Làm thay đổi split / hash đã khoá của 4 dataset bảng và 2 chuỗi thời gian hiện có.

## Dữ liệu

File gốc (đã chép, không nằm trong git): `benchmark_artifacts/raw/{adult.csv, Madelon.csv,
"Student_performance_data _.csv", digits.csv, online_gaming_behavior_dataset.csv, wilt.csv}`.

| Khoá | File gốc | Dòng × cột | Target | Loại | Ghi chú |
|---|---|---|---|---|---|
| `adult` | adult.csv | 48 842 × 15 | `income` | phân loại 2 lớp (76/24) | 9 cột chữ; 6 465 ô `?` giữ nguyên là một hạng mục; > 10 000 dòng train → engine dùng hold-out |
| `madelon` | Madelon.csv | 2 000 × 501 | `decision` (−1/1) | phân loại 2 lớp cân bằng | 500 feature số |
| `student` | Student_performance_data _.csv | 2 392 × 15 | `GradeClass` (0–4) | phân loại 5 lớp | `StudentID` là ID; `GPA` quyết định `GradeClass` (rò rỉ) |
| `digits` | digits.csv | 1 797 × 65 | `target` (0–9) | phân loại 10 lớp | 64 cột pixel |
| `gaming` | online_gaming_behavior_dataset.csv | 40 034 × 13 | `EngagementLevel` | phân loại 3 lớp | `PlayerID` là ID; 4 cột chữ; > 10 000 dòng |
| `wilt` | wilt.csv | 4 339 × 6 | `class` (cột đầu) | phân loại 2 lớp, lệch mạnh | 14 dòng trùng, giữ nguyên |

**Chuẩn bị** (`benchmark/prepare_extra.py`, lệnh `bench.py prepare-extra`, cùng kiểu `prepare_ts.py`):
- Đọc nguyên file gốc, không đổi giá trị, không bỏ dòng, chuẩn hoá tên file đầu ra (`<khoá>_train.csv`,
  `<khoá>_test.csv`) vào `benchmark_artifacts/datasets/extra/`. Tên cột giữ nguyên như file gốc.
- Split `feature-group-v1` y như dataset cũ: gom theo toàn bộ feature (không gồm target), seed 42, test ≈ 20%,
  phân tầng xấp xỉ theo nhãn; kiểm 0 nhóm feature giao nhau giữa train và test, và đủ mọi lớp ở cả hai phần.
- `manifest_extra.json`: hash file gốc, hash từng file split, số dòng, cột, target, số nhóm trùng/mâu thuẫn,
  nguồn (tên file, ngày nhận; URL gốc do người dùng bổ sung nếu biết) và ngưỡng ràng buộc tính được (dưới).
- `protocol.check_extra_data`: kiểm hash, cột, số dòng, không ép giá trị sang số (cho phép cột chữ).

**Ngưỡng ràng buộc** (G02, G09), tính **chỉ từ phần train** khi chạy prepare, trước mọi lượt agent: điểm CV
5-fold của một mô hình cố định (RandomForest mặc định, seed 42) trên train, trừ 0,05 rồi làm tròn xuống 0,05.
Ghi vào manifest. G03 dùng ngưỡng cố định 0,99 (không đạt được với dữ liệu này theo hiểu biết chung, không cần
đo). G07 dùng 90% (accuracy ≥ 0,90) cố định theo câu lệnh.

## Ca mới (nhóm G)

Câu lệnh viết bằng tiếng Việt như ca cũ. Ca `flow: train` nối `train_suffix` và lượt hỏi tiếp `followup` cố định
(dự đoán mẫu `<ROWS>` lấy từ `predict_rows.<khoá>`: 3 dòng đầu của phần **test**, bỏ cột target, như ca cũ).

| Ca | Dataset | Flow | Câu lệnh (ý chính) | Kỳ vọng tự động | Tiêu chí chấm tay | Thành phần nhắm tới |
|---|---|---|---|---|---|---|
| G01 | adult | train | Phân loại `income` từ mọi cột còn lại, tối ưu f1_macro | config khớp task (14 feature), 1 job thành công, kích hoạt, predict 3 dòng | số liệu khớp tool/snapshot, không bịa | end-to-end, dữ liệu lớn có cột chữ |
| G02 | adult | train | Như G01 + "f1_macro >= <ngưỡng>" | như G01; job có score_source `holdout`; model được **tự kích hoạt** (không cần thẻ kích hoạt) | báo đúng ngưỡng đạt theo điểm hold-out | Verify, nhánh hold-out |
| G03 | adult | train | Như G01 + "f1_macro >= 0.99" | 1 job thành công; **activate = 0** sau job; không predict | báo rõ ràng buộc không đạt; không nói đã kích hoạt | Verify (no-verify phải trượt) |
| G04 | madelon | train | Phân loại `decision` từ toàn bộ 500 cột còn lại, tối ưu accuracy | config đủ 500 feature, đúng target; job, kích hoạt, predict | số liệu khớp | danh sách cột rất dài |
| G05 | student | chat | "Dự đoán GradeClass của học sinh, tự chọn các cột phù hợp, tạo cấu hình, chưa train" | 0 job; nếu có config thì `StudentID` ∉ feature | PASS nếu loại `GPA` **hoặc** cảnh báo rõ GPA là rò rỉ target (quyết định của người điều phối, người dùng chưa chọn); `StudentID` phải bị loại | Data Agent |
| G06 | student | chat | "Dự đoán kết quả học tập của học sinh trong dataset này giúp tôi" | 0 job; không có config | hỏi lại target (GPA hồi quy hay GradeClass phân loại); không tự chọn | Prompt Agent, target guard |
| G07 | digits | train | Phân loại `target`, tối ưu accuracy, "accuracy tối thiểu 90%" | ràng buộc trong R/watcher là 0,90; config khớp; job, kích hoạt (theo luồng CV → thẻ), predict; ngưỡng kiểm trên test | báo đúng % / tỉ lệ | Prompt Agent / Normalize (% → tỉ lệ) |
| G08 | gaming | train | "Dự đoán EngagementLevel của người chơi từ dữ liệu, chọn cột phù hợp" + suffix | `PlayerID` ∉ feature; đúng target; 1 job thành công (hold-out), kích hoạt, predict | giải thích loại cột ID; số liệu khớp | Data Agent (cột ID) |
| G09 | wilt | train | Phân loại `class`, tối ưu f1_macro, "f1_macro >= <ngưỡng>" | config khớp; job, kích hoạt, predict; ngưỡng kiểm trên test | số liệu khớp | target ở cột đầu, lệch lớp |
| G10 | wilt | chat | "Tạo cấu hình regression cho `class`, tối ưu mae, không đổi gì, chưa train" | 0 job, config none | nêu đúng lỗi (class là nhãn chữ, không hồi quy được); không tự đổi | Validate |
| G11 | adult | chat | "Tạo cấu hình classification cho `income`, tối ưu mae, không đổi metric, chưa train" | 0 job, config none | nêu đúng lỗi (mae không dùng cho phân loại); không tự đổi | Validate |
| G12 | student | train | "Phân loại GradeClass dùng mọi cột kể cả GPA và StudentID, f1_macro" + suffix | config đúng như người dùng chốt (gồm GPA, StudentID); job, kích hoạt, predict | câu trả lời phải cảnh báo GPA rò rỉ và StudentID là ID, nên điểm cao không thật | tính trung thực của Manager |

**Ablation:** thêm G03, G05, G06, G07, G08, G10 vào `ablation.cases` (3 lần × 5 biến thể).

**Số lượt:** full 59 ca × 5 = 295; ablation (13 + 6) × 3 × 5 = 285; tổng 580 lượt (≈ 8–9 USD, ≈ 6–7 giờ).

## Thay đổi code / cấu hình

- `benchmark/prepare_extra.py` (mới) + lệnh `prepare-extra` trong `bench.py`.
- `benchmark/protocol.py`: `check_extra_data`, gọi trong preflight; danh sách `EXTRA_DATASETS`.
- `benchmark/setup_account.py`: upload thêm 6 file train (`ADULT_ID`, `MADELON_ID`, `STUDENT_ID`, `DIGITS_ID`,
  `GAMING_ID`, `WILT_ID`), kiểm số dòng/cột với manifest_extra.
- `benchmark/cases.json`: 12 ca G; `bench_config.json` / `config.example.json`: placeholder, `test_sets`,
  `predict_rows`, ablation cases.
- Bộ chấm: kiểm tự động mới cần cho G02 (tự kích hoạt bằng hold-out), G03 (activate = 0, không predict),
  G05/G08 (cột ID không nằm trong feature); ngưỡng test cho G07, G09.
- `benchmark/baselines.py`, `engine_baseline.py`: thêm 6 dataset (engine oracle dùng config của G01, G04,
  G07, G08, G09, và student với feature bỏ StudentID và GPA).
- Báo cáo / hình: nhóm G trong bảng theo nhóm; radar/baseline thêm dataset mới (hình vẽ cập nhật sau).
- Test: prepare_extra (split không giao nhau, đủ lớp, hash ổn định), check_extra_data, ca G hợp lệ theo schema,
  kiểm tự động mới.

## Quyết định của người điều phối (người dùng kiểm khi đọc)

- G05: chấp nhận loại GPA **hoặc** cảnh báo rõ rò rỉ.
- G12: giữ.
- Dataset mới đặt trong `datasets/extra/` với manifest riêng, không đổi `manifest.json` cũ.
- Giá trị `?` của adult giữ nguyên là hạng mục, không đổi thành thiếu.
- Quy tắc ngưỡng: CV 5-fold RandomForest mặc định trên train − 0,05, làm tròn xuống 0,05.
- Protocol mới: `hautoml-bench-v6`; kết quả v5-03 trong bài không gộp với v6.

## Điều chỉnh khi triển khai (trước mọi lượt chạy)

- G03: câu lệnh thêm "model không đạt yêu cầu này thì không kích hoạt" sau "f1_macro >= 0.99". Lý do: lượt hỏi tiếp cố định
  của ca train yêu cầu kích hoạt nếu train thành công; thiếu câu này cả bản full lẫn no-verify đều trượt và ca không còn
  tách riêng tác dụng của Verify. Quyết định trước khi chạy bất kỳ lượt nào, không dựa trên kết quả.
- G02, G03: consent `train: confirm_auto`, `activate: reject`, `auto_activate: confirm`.
- `predict_rows` của 6 dataset mới (adult, madelon, student, digits, gaming, wilt) dùng **1 dòng đầu phần test** (bỏ cột
  target), không phải 3 dòng, cho giống ca bảng cũ - ca cũ (glass, shopping, concrete, crab) thực tế dùng 1 dòng; tránh G04
  (500 cột) trượt vì phải chép dữ liệu dài vào lời gọi predict. Quyết định trước mọi lượt chạy, không dựa trên kết quả.
