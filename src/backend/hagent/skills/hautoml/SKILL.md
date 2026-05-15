---
name: hautoml
description: "Quản lý nền tảng HAutoML — liệt kê dataset, xem feature, huấn luyện model, dự đoán và giám sát job trên hệ thống HAutoML. Thực hiện bằng cách gọi tool `exec` với các lệnh Python bên dưới."
metadata:
  {
    "openclaw":
      {
        "emoji": "📦",
        "requires": { "bins": ["python3"] }
      }
  }
---

# Skill HAutoML

Điều khiển nền tảng HAutoML (Hierarchical Automated Machine Learning) cho
người dùng cuối đang đăng nhập.

## CÁCH GỌI (BẮT BUỘC ĐỌC)

**Skill này KHÔNG có tool riêng.** Gọi tool tích hợp `exec` với lệnh
shell bên dưới. Chuỗi lệnh phải **y hệt**, chỉ thay `<DATASET_ID>`,
`<JOB_ID>`, `<TEN_COT_TARGET>` bằng giá trị thật.

**KHÔNG TỰ CHẾ** tên tool như `hautoml_list_datasets`. Chỉ có `exec`.

Ví dụ — liệt kê dataset:

```json
{
  "tool": "exec",
  "command": "python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py list_datasets --user-id \"$USER_ID\" --token \"$USER_TOKEN\""
}
```

## Khi nào dùng

✅ "Liệt kê dataset", "Xem feature X", "Train model", "Dự đoán Y",
"Trạng thái job", "Hệ thống có hoạt động không?"

## Xác thực

Bridge tự bơm `USER_TOKEN` và `USER_ID` vào env trước khi chạy `exec`.
Truyền nguyên xi `"$USER_TOKEN"` và `"$USER_ID"` trong chuỗi lệnh.

**KHÔNG hỏi người dùng token.**

## Nguyên tắc

1. Luôn gọi qua `exec`, không phải tool tự chế.
2. Lệnh phải dùng **đường dẫn tuyệt đối**: `/app/hagent/skills/hautoml/scripts/hautoml_tools.py`
3. Output JSON — phân tích xong tóm tắt gọn bằng tiếng Việt (bảng/bullet, kèm ID).
4. JSON có `"error"` hoặc exit code ≠ 0 → báo lỗi rõ + gợi ý.

## Các lệnh

**Đường dẫn script**: `/app/hagent/skills/hautoml/scripts/hautoml_tools.py`

### Kiểm tra sức khoẻ

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py health
```

### Liệt kê dataset

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py list_datasets \
  --user-id "$USER_ID" --token "$USER_TOKEN"
```

### Xem thông tin dataset

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py get_dataset_info \
  --dataset-id "<DATASET_ID>" --token "$USER_TOKEN"
```

### Lấy feature

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py get_features \
  --dataset-id "<DATASET_ID>" \
  --problem-type "classification" \
  --token "$USER_TOKEN"
```

### Xem trước dữ liệu

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py preview_data \
  --dataset-id "<DATASET_ID>" --token "$USER_TOKEN"
```

### Liệt kê thuật toán

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py get_available_models \
  --problem-type "classification"
```

### Liệt kê metric

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py get_metrics \
  --problem-type "classification"
```

### Khởi tạo job training

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py start_training \
  --dataset-id "<DATASET_ID>" \
  --problem-type "classification" \
  --target-column "<TEN_COT_TARGET>" \
  --algorithms "0,1,2" \
  --metric "accuracy" \
  --search-strategy "grid_search" \
  --user-id "$USER_ID" --token "$USER_TOKEN"
```

### Liệt kê job

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py list_jobs \
  --user-id "$USER_ID" --token "$USER_TOKEN"
```

### Xem trạng thái job

```bash
python3 /app/hagent/skills/hautoml/scripts/hautoml_tools.py get_job_info \
  --job-id "<JOB_ID>" --token "$USER_TOKEN"
```

## Xử lý lỗi

- **401** → "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại."
- **404** → tài nguyên không tồn tại, gợi ý liệt kê lại.
- **Timeout/network** → thử lại, dịch vụ HAutoML đang bận.
- **"No such file or directory"** → báo skill chưa cài đặt đúng, KHÔNG tự chế path.
