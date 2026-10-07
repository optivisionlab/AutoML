"""
Kiểm tra file dataset người dùng tải lên qua khung chat.

Đây là chốt THẬT. Frontend cũng kiểm tra đuôi file và dung lượng để báo lỗi
nhanh, nhưng kiểm tra ở trình duyệt thì ai cũng bỏ qua được - gọi thẳng API là
xong. Nên mọi điều kiện ở đây đều phải được server áp lại.

Hàm thuần: không mạng, không đọc đĩa. Test được mà không cần chạy server.
"""

# Standard libraries
import math
import os
from dataclasses import dataclass


MAX_UPLOAD_MB = 20
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# Đuôi file backend đọc được. Nguồn: data/engine.py - .xls/.xlsx đi qua
# pd.read_excel, còn lại đi qua pd.read_csv.
ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xls")

# Chữ ký đầu file. Đổi tên ảnh.png thành data.xlsx thì đuôi file vẫn đúng,
# nhưng vài byte đầu sẽ lộ ra đó không phải Excel.
_XLSX_MAGIC = b"PK\x03\x04"                          # .xlsx là file zip
_XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"     # .xls là file OLE2 cũ

DATA_TYPES = ("classification", "regression")

_MIME = {
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}


@dataclass
class UploadCheck:
    ok: bool
    status_code: int = 200   # mã HTTP trả về khi trượt
    error: str = ""
    extension: str = ""
    # Tên file đã bỏ phần đường dẫn - KHÔNG dùng tên gốc client gửi lên.
    clean_name: str = ""

    @property
    def mime_type(self) -> str:
        return _MIME.get(self.extension, "application/octet-stream")


def _fail(status_code: int, error: str) -> UploadCheck:
    return UploadCheck(ok=False, status_code=status_code, error=error)


def _looks_like_text(head: bytes) -> bool:
    """
    CSV phải là văn bản. Có byte NUL thì gần như chắc chắn là file nhị phân bị
    đổi đuôi thành .csv.
    """
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        # Có thể chỉ là cắt ngang giữa một ký tự nhiều byte ở cuối đoạn đầu,
        # hoặc file mã hoá cp1252/latin-1. Không coi là lỗi chỉ vì thế.
        return True


def check_dataset_file(filename: str, content: bytes) -> UploadCheck:
    """
    Kiểm tra một file dataset trước khi chuyển cho backend.

    Thứ tự kiểm tra cố ý đi từ rẻ tới đắt: tên file → dung lượng → nội dung.

    Returns:
        UploadCheck. ok=False thì status_code là mã HTTP nên trả về:
          415 sai loại file · 413 quá lớn · 400 file rỗng hoặc tên lỗi
    """
    name = os.path.basename(filename or "").strip()
    if not name:
        return _fail(400, "Thiếu tên file.")

    extension = os.path.splitext(name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        return _fail(
            415,
            f"Chỉ nhận file {', '.join(ALLOWED_EXTENSIONS)}. File '{name}' có đuôi "
            f"'{extension or '(không có)'}'.",
        )

    size = len(content)
    if size == 0:
        return _fail(400, "File rỗng.")
    if size > MAX_UPLOAD_BYTES:
        # Làm tròn LÊN: 20 MB + 1 byte phải hiện là 20.1 chứ không phải 20.0,
        # nếu không thông báo thành "20.0 MB vượt giới hạn 20 MB" - tự mâu thuẫn.
        shown = math.ceil(size / 1024 / 1024 * 10) / 10
        return _fail(413, f"File {shown:.1f} MB vượt giới hạn {MAX_UPLOAD_MB} MB.")

    head = content[:8]
    if extension == ".xlsx" and not head.startswith(_XLSX_MAGIC):
        return _fail(415, f"'{name}' có đuôi .xlsx nhưng nội dung không phải file Excel.")
    if extension == ".xls" and not head.startswith(_XLS_MAGIC):
        return _fail(415, f"'{name}' có đuôi .xls nhưng nội dung không phải file Excel cũ.")
    if extension == ".csv" and not _looks_like_text(content[:4096]):
        return _fail(415, f"'{name}' có đuôi .csv nhưng nội dung là dữ liệu nhị phân.")

    return UploadCheck(ok=True, extension=extension, clean_name=name)


def default_dataset_name(filename: str) -> str:
    """Tên dataset mặc định = tên file bỏ đuôi, ví dụ 'aus_credit_train.csv' → 'aus_credit_train'."""
    stem = os.path.splitext(os.path.basename(filename or ""))[0].strip()
    return stem or "dataset"
