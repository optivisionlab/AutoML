"""
Client HTTP gọi tới backend HAutoML (API v1: src/backend/src/main.py).

Tách riêng khỏi tầng agent/LLM để chạy và test được độc lập. Token sau khi
login được giữ trong instance và tự động gắn vào header của các request sau.

Định dạng của backend v1 - client lo hết, tầng tool không phải biết:

  - Mọi endpoint nằm dưới /api/v1 (đổi bằng HAUTOML_API_PREFIX nếu cần).
  - Thành công: {"success": true, "message", "data", "meta"} -> trả về `data`.
  - Danh sách có phân trang (page_size tối đa 100) -> tự lật hết các trang.
  - Lỗi: {"success": false, "error_code", "detail", "extra"} -> ApiError.
"""

# Standard libraries
import os

# Third party libraries
import httpx
from dotenv import load_dotenv


# Load file .env
load_dotenv()


DEFAULT_BASE_URL = os.getenv("HAUTOML_BASE_URL", "http://localhost:9999")
API_PREFIX = "/" + os.getenv("HAUTOML_API_PREFIX", "/api/v1").strip("/")

# Trần của backend cho page_size.
_PAGE_SIZE = 100
# Chặn vòng lặp vô hạn nếu meta phân trang sai: 50 trang x 100 = 5000 bản ghi.
_MAX_PAGES = 50

# Backend chỉ có một loại dataset dạng bảng; loại bài toán nằm trong config train.
TABLE_DATA_TYPE = "table"


class ApiError(Exception):
    """Lỗi từ backend. status_code = 0 nghĩa là không gọi được tới server."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


def _extract_detail(response: httpx.Response) -> str:
    """
    Lấy thông báo lỗi dễ đọc. Lỗi validate (422) để danh sách trường sai trong
    extra.errors - ghép vào để LLM biết sửa trường nào.
    """
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]

    if not isinstance(body, dict):
        return str(body)[:500]

    detail = body.get("detail", body)
    message = detail if isinstance(detail, str) else str(detail)[:500]

    errors = (body.get("extra") or {}).get("errors") if isinstance(body.get("extra"), dict) else None
    if errors:
        fields = "; ".join(f"{e.get('field')}: {e.get('message')}" for e in errors if isinstance(e, dict))
        message = f"{message} ({fields})"[:500]
    return message


class HAutoMLClient:
    """Bọc các endpoint của backend HAutoML v1."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._http = httpx.Client(base_url=self.base_url + API_PREFIX, timeout=timeout)
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        # Cache sau lần gọi /me đầu tiên. Dùng để kiểm job có đúng của người
        # đang đăng nhập không (tài khoản admin thấy job của mọi người).
        self.user_id: str | None = None

    def __enter__(self) -> "HAutoMLClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _send(self, method: str, path: str, **kwargs):
        """Gửi request, trả body JSON NGUYÊN VẸN (chưa bóc data)."""
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.RequestError as error:
            raise ApiError(0, f"Không kết nối được tới {self.base_url} ({error})") from error

        if response.status_code >= 400:
            raise ApiError(response.status_code, _extract_detail(response))

        if not response.content:
            return {}
        try:
            body = response.json()
        except ValueError as error:
            # 2xx nhưng body không phải JSON (proxy trả trang HTML, backend lỗi
            # giữa chừng): coi là lỗi backend để tool trả {ok: false}.
            raise ApiError(
                response.status_code, f"Backend trả về dữ liệu không phải JSON: {response.text[:200]}"
            ) from error

        if isinstance(body, dict) and body.get("success") is False:
            raise ApiError(response.status_code, str(body.get("detail") or body.get("message") or body)[:500])
        return body

    def _request(self, method: str, path: str, **kwargs):
        """Gửi request, trả `data` trong phong bì {"success", "data", ...}."""
        body = self._send(method, path, **kwargs)
        if isinstance(body, dict) and "success" in body and "data" in body:
            return body["data"]
        return body

    def _paged(self, path: str, params: dict | None = None) -> list:
        """Lật hết các trang của một endpoint danh sách."""
        items: list = []
        page = 1
        while page <= _MAX_PAGES:
            body = self._send(
                "GET", path, params={**(params or {}), "current_page": page, "page_size": _PAGE_SIZE},
            )
            data = body.get("data") if isinstance(body, dict) else body
            items.extend(data or [])

            meta = body.get("meta") if isinstance(body, dict) else None
            total_pages = (meta or {}).get("total_pages") or 0
            if page >= total_pages or not data:
                break
            page += 1
        return items

    # ------------------------------------------------------------ xác thực

    def login(self, username: str, password: str) -> dict:
        """POST /auth/login. Lưu token vào client và trả về payload token."""
        token = self._request("POST", "/auth/login", json={
            "username": username,
            "password": password,
        })
        self.access_token = token.get("access_token")
        self.refresh_token = token.get("refresh_token")
        return token

    def get_me(self) -> dict:
        """GET /auth/me. Cần token. Cache lại user_id."""
        user = self._request("GET", "/auth/me")
        self.user_id = user.get("_id") or user.get("id")
        return user

    # ------------------------------------------------------------- dataset

    def list_datasets(self) -> list:
        """GET /datasets - mọi dataset CỦA người đang đăng nhập (backend tự lọc theo token)."""
        return self._paged("/datasets")

    def get_dataset_info(self, dataset_id: str) -> dict:
        """GET /datasets/{id} - metadata một dataset (không có tên cột)."""
        return self._request("GET", f"/datasets/{dataset_id}")

    def upload_dataset_content(
        self,
        data_name: str,
        filename: str,
        content: bytes,
        mime_type: str = "text/csv",
        description: str | None = None,
        timeout: float = 120.0,
    ) -> dict:
        """
        POST /datasets từ nội dung file trong bộ nhớ (multipart).

        Backend chọn cách đọc theo ĐUÔI của filename (.xls/.xlsx → read_excel,
        còn lại → read_csv), nên filename phải giữ đúng đuôi. timeout dài vì
        backend phải đọc file, chuyển parquet rồi ghi lên MinIO.
        """
        form = {"dataName": data_name, "dataType": TABLE_DATA_TYPE}
        if description:
            form["description"] = description
        return self._request(
            "POST",
            "/datasets",
            data=form,
            files={"file": (filename, content, mime_type)},
            timeout=timeout,
        )

    def get_dataset_features(self, dataset_id: str, problem_type: str) -> dict:
        """
        GET /datasets/{id}/features - {tên_cột: có làm target được không}.

        Key là TẤT CẢ cột của dataset; value cho biết cột đó có phù hợp làm
        biến mục tiêu với problem_type đã chọn. Backend loại sẵn cột dạng ID và
        cột hằng (gán False).
        """
        return self._request("GET", f"/datasets/{dataset_id}/features", params={"problem_type": problem_type})

    def get_dataset_preview(self, dataset_id: str, num_rows: int = 50) -> dict:
        """GET /datasets/{id}/data - {"rows": tổng số dòng, "records": num_rows dòng đầu}."""
        return self._request("GET", f"/datasets/{dataset_id}/data", params={"num_rows": num_rows})

    def start_training(self, dataset_id: str, config: dict) -> dict:
        """
        POST /datasets/{id}/training - đẩy job vào Kafka.

        Trả {"job_id"} ngay, KHÔNG chờ train xong. config theo TrainingConfig
        của backend: target, list_feature, metric_sort, problem_type,
        search_algorithm, timeout (giây).
        """
        return self._request("POST", f"/datasets/{dataset_id}/training", json=config)

    # ------------------------------------------------------- job và model

    def list_jobs(self) -> list:
        """
        GET /inference/jobs - mọi job huấn luyện, mới nhất trước.

        Backend không có endpoint xem MỘT job; bản ghi trong danh sách đã đủ
        trạng thái, điểm và config. Tài khoản admin nhận job của mọi người -
        tools.find_own_job tự lọc lại.
        """
        return self._paged("/inference/jobs")

    def activate_model(self, job_id: str, activate: bool) -> dict:
        """PUT /inference/models/{id}/activation - bật/tắt API dự đoán của model."""
        return self._request(
            "PUT", f"/inference/models/{job_id}/activation", json={"activate": 1 if activate else 0},
        )

    def predict(self, job_id: str, rows: list[dict], timeout: float = 120.0) -> dict:
        """POST /inference/models/{id}/predict - dự đoán các bản ghi JSON."""
        return self._request(
            "POST", f"/inference/models/{job_id}/predict", json={"data": rows}, timeout=timeout,
        )
