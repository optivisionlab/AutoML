"""
Client HTTP gọi tới backend HAutoML.

Tách riêng khỏi tầng agent/LLM để chạy và test được độc lập. Token sau khi
login được giữ trong instance và tự động gắn vào header của các request sau.
"""

# Standard libraries
import os

# Third party libraries
import httpx
from dotenv import load_dotenv


# Load file .env
load_dotenv()


DEFAULT_BASE_URL = os.getenv("HAUTOML_BASE_URL", "http://localhost:9996")


class ApiError(Exception):
    """Lỗi từ backend. status_code = 0 nghĩa là không gọi được tới server."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


def _extract_detail(response: httpx.Response) -> str:
    """
    FastAPI trả lỗi dạng {"detail": ...}, nhưng detail có thể là list (lỗi validate
    của pydantic) chứ không phải lúc nào cũng là string.
    """
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]

    detail = body.get("detail", body) if isinstance(body, dict) else body
    if isinstance(detail, str):
        return detail
    return str(detail)[:500]


class HAutoMLClient:
    """Bọc các endpoint xác thực của backend HAutoML."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout)
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        # Cache sau lần gọi /me đầu tiên. Nhiều endpoint dữ liệu cần user_id,
        # giữ ở đây để LLM không phải truyền qua lại (và không thể bịa sai).
        self.user_id: str | None = None

    def __enter__(self) -> "HAutoMLClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.RequestError as error:
            raise ApiError(0, f"Không kết nối được tới {self.base_url} ({error})") from error

        if response.status_code >= 400:
            raise ApiError(response.status_code, _extract_detail(response))

        return response.json() if response.content else {}

    def signup(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str,
        gender: str,
        date: str,
        number: str,
    ) -> dict:
        """POST /signup. Tài khoản tạo ra luôn có is_verified = False."""
        return self._request("POST", "/signup", json={
            "username": username,
            "email": email,
            "password": password,
            "fullName": full_name,
            "gender": gender,
            "date": date,
            "number": number,
        })

    def login(self, username: str, password: str) -> dict:
        """POST /login. Lưu token vào client và trả về payload gốc."""
        token = self._request("POST", "/login", json={
            "username": username,
            "password": password,
        })
        self.access_token = token.get("access_token")
        self.refresh_token = token.get("refresh_token")
        return token

    def get_me(self) -> dict:
        """GET /me. Cần đã login trước đó. Cache lại user_id."""
        user = self._request("GET", "/me")
        self.user_id = user.get("_id") or user.get("id")
        return user

    def logout(self) -> dict:
        """POST /logout và xoá token khỏi client."""
        result = self._request("POST", "/logout")
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        return result

    def list_datasets(self, owner_id: str) -> list:
        """POST /get-list-data-by-userid - dataset của một user."""
        return self._request("POST", "/get-list-data-by-userid", params={"id": owner_id})

    def get_dataset_info(self, dataset_id: str) -> dict:
        """GET /get-data-info - metadata một dataset (không có tên cột)."""
        return self._request("GET", "/get-data-info", params={"id": dataset_id})

    def upload_dataset(
        self,
        user_id: str,
        data_name: str,
        data_type: str,
        file_path: str,
        timeout: float = 60.0,
    ) -> dict:
        """
        POST /upload-dataset - tải một file CSV/Excel lên.

        Endpoint này nhận multipart form chứ không phải JSON như các endpoint
        khác, nên không dùng được `json=` của _request.
        """
        with open(file_path, "rb") as file:
            return self._request(
                "POST",
                "/upload-dataset",
                params={"user_id": user_id},
                data={"data_name": data_name, "data_type": data_type},
                files={"file_data": (os.path.basename(file_path), file, "text/csv")},
                timeout=timeout,
            )

    def get_dataset_features(self, dataset_id: str, problem_type: str) -> dict:
        """
        GET /v2/auto/features - danh sách cột kèm cờ có làm target được không.

        Trả {"features": {tên_cột: bool}}. Key là TẤT CẢ cột của dataset; value
        cho biết cột đó có phù hợp làm biến mục tiêu với problem_type đã chọn.
        Backend loại sẵn các cột dạng ID và cột hằng (gán False).
        """
        return self._request("GET", "/v2/auto/features", params={
            "id_data": dataset_id,
            "problem_type": problem_type,
        })

    def get_dataset_preview(self, dataset_id: str) -> dict:
        """GET /v2/auto/data - tổng số dòng và 50 dòng đầu."""
        return self._request("GET", "/v2/auto/data", params={"id_data": dataset_id})

    def get_metrics(self, problem_type: str) -> dict:
        """GET /v2/auto/metrics - danh sách metric hợp lệ cho loại bài toán."""
        return self._request("GET", "/v2/auto/metrics", params={"problem_type": problem_type})

    def start_training(self, dataset_id: str, user_id: str, config: dict) -> dict:
        """
        POST /v2/auto/jobs/training - đẩy job vào Kafka.

        Trả về ngay kèm job_id, KHÔNG chờ train xong. Theo dõi tiến độ bằng
        get_job_info.
        """
        return self._request("POST", "/v2/auto/jobs/training", json={
            "id_data": dataset_id,
            "id_user": user_id,
            "config": config,
        })

    def list_jobs(self, user_id: str) -> list:
        """POST /get-list-job-by-userId - các job huấn luyện của một user."""
        return self._request("POST", "/get-list-job-by-userId", params={"user_id": user_id})

    def get_job_info(self, job_id: str) -> dict:
        """POST /get-job-info - chi tiết một job huấn luyện."""
        return self._request("POST", "/get-job-info", params={"id": job_id})

    def resend_verification_email(self, email: str) -> dict:
        """POST /auth/token/verifications - gửi lại email xác thực."""
        return self._request("POST", "/auth/token/verifications", json={"email": email})

    def verify_email(self, token: str) -> dict:
        """POST /auth/verifications - xác thực bằng token lấy từ link trong email."""
        result = self._request("POST", "/auth/verifications", json={"token": token})
        self.access_token = result.get("access_token")
        self.refresh_token = result.get("refresh_token")
        return result
