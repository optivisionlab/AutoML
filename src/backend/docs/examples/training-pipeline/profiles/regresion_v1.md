# JSON lịch sử huấn luyện regression v1

Mẫu: [regresion_v1.json](regresion_v1.json).

## Cấu trúc

Ở cấp gốc chỉ có thông tin của job (`job_id`, `version`, `mode`, `status`, `updated_at`) và các node.
Không có lớp bọc `result`, `results` hay `nodes`.
Key của node là định danh dùng để nối đồ thị; `name` là tên hiển thị.

Luồng hiển thị:

```text
read_dataset → split_holdout_data → read_training_data → preprocessing → model_selection → train → select_best → save_result
```

Dữ liệu được tách holdout trước tiền xử lý, nên bộ tiền xử lý chỉ fit trên tập train.

### Một lần gọi API

Toàn bộ trạng thái của job nằm trong một JSON này, kể cả trạng thái từng mô hình trong `train`.
Frontend chỉ cần gọi một API lấy thông tin job (hiện là `POST /get-job-info`) để vẽ cả đồ thị,
không gọi thêm API riêng cho từng node hay từng mô hình.
Khi job đang chạy, frontend gọi lại chính API này; dừng khi `status` ở cấp gốc là trạng thái kết thúc
(`succeeded`, `failed`, `cancelled`). `updated_at` cho biết dữ liệu đã thay đổi so với lần gọi trước hay chưa.

Trong lúc backend chưa xuất JSON này, frontend lấy dữ liệu mẫu từ API mẫu chạy độc lập
[mock_api.py](../mock_api.py): chạy `uvicorn mock_api:app --port 8001` trong thư mục `training-pipeline`,
rồi gọi `POST http://localhost:8001/get-pipeline-sample` với body `{"problem_type": "regression"}`
và header `Authorization: Bearer <token>`. API trả nội dung file mẫu này trong trường `pipeline`.
Chi tiết: [mock_api.md](../mock_api.md).

### Biến chung và biến riêng

Mọi node có cùng một bộ key, theo cùng thứ tự:

```text
name, kind, depends_on, status, started_at, finished_at, error, params, output
```

- 7 key đầu là **biến chung**: giống nhau ở mọi node, frontend dùng một component chung để hiển thị.
- `params` và `output` chứa **biến riêng** của node đó:
  - `params`: cấu hình đầu vào, đã biết khi tạo job, không đổi trong lúc chạy.
  - `output`: kết quả do backend điền khi node chạy xong. `{}` nghĩa là node không có kết quả riêng.

Nguyên tắc tương tự áp dụng cho các phần tử lặp lại bên trong node:

- `preprocessing.params.transformers` và `preprocessing.output.column_types` dùng cùng các key nhóm cột
  (`numeric`, `categorical`, `text`): một bên là bộ biến đổi, một bên là danh sách cột.
- Mỗi mô hình trong `train.output.models` có cùng 4 key: biến chạy `status`, `error`
  và biến kết quả `best_params`, `scores`.

### Mỗi giá trị chỉ lưu ở một chỗ

Để tránh dữ liệu lệch nhau, không lặp lại giá trị đã có ở node khác:

- Cấu hình tìm kiếm và đánh giá dùng chung nằm ở `model_selection.params`; `train` và `select_best` đọc từ đó.
- `select_best.output.best_model` là key trong `train.output.models`.
  Tham số và điểm của mô hình tốt nhất đọc tại `train.output.models.<best_model>`;
  điểm chính là `scores.<metric_sort>`.
- Tiến độ huấn luyện = số mô hình có `status` kết thúc / số key trong `train.output.models`.

Frontend dựng cạnh từ `depends_on`, không dựa vào thứ tự key trong JSON.

## Mô tả các cặp key–value

### Cách đọc tài liệu

- Cột **Giá trị trong mẫu** ghi giá trị đang có trong JSON, không phải kết quả của một lần huấn luyện.
- Kiểu dữ liệu ghi dạng dự kiến khi có dữ liệu thực tế; `null` nghĩa là chưa có thông tin, không đồng nghĩa với `0`, `false` hay thất bại.
- `[]` là mảng rỗng; `{}` là object rỗng. Ví dụ `best_params: {}` cũng có thể là kết quả hợp lệ khi mô hình dùng tham số mặc định.
- Đường dẫn dùng dấu chấm, ví dụ `train.output.models.XGBRegressor.scores.mse`. `<model_name>` đại diện cho một tên mô hình.
- Các quy ước về trạng thái, thời gian và lỗi dưới đây là đề xuất cho hợp đồng JSON; backend hiện chưa tự xuất đầy đủ các trường này.

### 1. Các key ở cấp gốc

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `job_id` | string hoặc null | `null` | Mã định danh phiên huấn luyện. |
| `version` | string | `"1.0.0"` | Phiên bản cấu trúc JSON; không phải phiên bản mô hình hay API. |
| `mode` | string | `"automl"` | Chế độ huấn luyện tự động. |
| `status` | string hoặc null | `null` | Trạng thái của cả job, cùng bảng giá trị với node. Frontend dùng để biết khi nào dừng gọi lại API. |
| `updated_at` | string hoặc null | `null` | Thời điểm JSON được cập nhật gần nhất (ISO 8601). |
| `read_dataset` | object | Node đọc dữ liệu | Thông tin nguồn và việc đọc dataset. |
| `split_holdout_data` | object | Node tách holdout | Chia dataset thành tập train và tập holdout. |
| `read_training_data` | object | Node đọc tập train | Đọc phần train sau khi tách để đưa vào tiền xử lý. |
| `preprocessing` | object | Node tiền xử lý | Chọn cột, xử lý target và biến đổi đặc trưng. |
| `model_selection` | object | Node chọn mô hình ứng viên | Danh sách mô hình cùng cấu hình tìm kiếm và đánh giá. |
| `train` | object | Node huấn luyện | Trạng thái và kết quả từng mô hình. |
| `select_best` | object | Node chọn kết quả tốt nhất | So sánh các kết quả huấn luyện theo metric chính. |
| `save_result` | object | Node lưu kết quả | Vị trí lưu mô hình tốt nhất. |

### 2. Biến chung của node

Các trường này xuất hiện trong cả 8 node ở cấp gốc.

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `name` | string | Ví dụ `"Read dataset"` | Nhãn hiển thị trên giao diện. Key ở cấp gốc mới là định danh dùng để nối node. |
| `kind` | string | Xem bảng bên dưới | Loại xử lý của node. |
| `depends_on` | array<string> | `[]` hoặc danh sách key node | Các node phải được xử lý trước node hiện tại. |
| `status` | string hoặc null | `null` | Trạng thái thực thi, theo bảng trạng thái bên dưới. |
| `started_at` | string hoặc null | `null` | Thời điểm bắt đầu; đề xuất ISO 8601 có múi giờ, ví dụ `"2026-10-01T08:00:00Z"`. |
| `finished_at` | string hoặc null | `null` | Thời điểm kết thúc theo cùng định dạng; có thể chưa có khi node đang chạy. |
| `error` | object hoặc null | `null` | Chi tiết lỗi nếu có; đề xuất `{"message": "Không đọc được dataset"}`. |
| `params` | object | Khác nhau theo node | Biến riêng: cấu hình đầu vào của node. |
| `output` | object | Khác nhau theo node | Biến riêng: kết quả của node, do backend điền. |

Giá trị định danh và phụ thuộc trong mẫu:

| Key node | `name` | `kind` | `depends_on` |
| --- | --- | --- | --- |
| `read_dataset` | `"Read dataset"` | `"data_loading"` | `[]` |
| `split_holdout_data` | `"Split holdout data"` | `"data_splitting"` | `["read_dataset"]` |
| `read_training_data` | `"Read training data"` | `"data_loading"` | `["split_holdout_data"]` |
| `preprocessing` | `"Preprocessing"` | `"preprocessing"` | `["read_training_data"]` |
| `model_selection` | `"Model selection"` | `"model_selection"` | `["preprocessing"]` |
| `train` | `"Train models"` | `"model_training"` | `["model_selection"]` |
| `select_best` | `"Select best model"` | `"model_selection"` | `["train"]` |
| `save_result` | `"Save result"` | `"result_storage"` | `["select_best"]` |

`model_selection` và `select_best` có cùng `kind`, nhưng key node phân biệt việc chọn mô hình ứng viên với chọn kết quả tốt nhất.
Tương tự, `read_dataset` và `read_training_data` cùng `kind: "data_loading"`: một node đọc toàn bộ dataset, một node đọc phần train.

Các giá trị `status` đề xuất (dùng chung cho job, node và từng mô hình trong `train`):

| Giá trị | Ý nghĩa |
| --- | --- |
| `null` | Chưa có thông tin trạng thái. |
| `"queued"` | Đang chờ xử lý. |
| `"running"` | Đang thực thi. |
| `"succeeded"` | Hoàn thành thành công. |
| `"failed"` | Kết thúc do lỗi. |
| `"skipped"` | Bỏ qua bước, ví dụ đã có dữ liệu trong cache. |
| `"cancelled"` | Bị hủy. |

Tóm tắt biến riêng của từng node:

| Node | `params` | `output` |
| --- | --- | --- |
| `read_dataset` | `id_data`, `format` | `data_url`, `cache_hit` |
| `split_holdout_data` | `method`, `test_size`, `shuffle`, `random_state` | `train_rows`, `holdout_rows` |
| `read_training_data` | `split` | `n_rows`, `n_columns` |
| `preprocessing` | `list_feature`, `target`, `transformers` | `cache_hit`, `dropped_rows`, `column_types` |
| `model_selection` | `problem_type`, `model_names`, `search_algorithm`, `max_time`, `metric_sort`, `metrics`, `split` | `{}` |
| `train` | `{}` (dùng `model_selection.params`) | `models` |
| `select_best` | `dependency_policy` | `best_model`, `time_limit_reached` |
| `save_result` | `bucket_name` | `object_name` |

### 3. Node `read_dataset`

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `params.id_data` | string hoặc null | `null` | Mã dataset dùng để tra thông tin lưu trữ. |
| `params.format` | string | `"parquet"` | Định dạng dữ liệu được đọc từ MinIO. |
| `output.data_url` | string hoặc null | `null` | Đường dẫn nguồn dữ liệu đã tra được từ `id_data` (vị trí MinIO), nếu response cung cấp. |
| `output.cache_hit` | boolean hoặc null | `null` | `true`: tái sử dụng dữ liệu đã xử lý; `false`: cần đọc dataset; `null`: chưa có thông tin. |

### 3.1. Node `split_holdout_data`

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `params.method` | string | `"train_test_split"` | Hàm chia dữ liệu (`sklearn.model_selection.train_test_split`). |
| `params.test_size` | number | `0.2` | Tỷ lệ số dòng đưa vào tập holdout; `0.2` là 20%. |
| `params.shuffle` | boolean | `true` | Xáo trộn dòng trước khi chia. |
| `params.random_state` | integer | `42` | Seed cố định để lần chạy lại cho cùng kết quả chia. |
| `output.train_rows` | integer hoặc null | `null` | Số dòng của tập train sau khi chia. |
| `output.holdout_rows` | integer hoặc null | `null` | Số dòng của tập holdout sau khi chia. |

Tập holdout không đi qua tiền xử lý, tìm tham số hay cross-validation; chỉ tập train được đưa sang `read_training_data`.
Bài toán regression không dùng `stratify`.

### 3.2. Node `read_training_data`

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `params.split` | string | `"train"` | Phần dữ liệu được đọc sau khi tách, lấy từ `split_holdout_data`. |
| `output.n_rows` | integer hoặc null | `null` | Số dòng đã đọc; bằng `split_holdout_data.output.train_rows`. |
| `output.n_columns` | integer hoặc null | `null` | Số cột đã đọc, gồm cả cột target, trước khi chọn feature. |

### 4. Node `preprocessing`

JSON chỉ giữ những gì thay đổi theo từng job hoặc phát sinh khi chạy.
Chi tiết cài đặt cố định trong code (tham số của từng transformer, thứ tự thao tác)
không gửi trong JSON mà mô tả ở mục 4.1, để payload realtime nhỏ và không lặp lại ở mọi job.

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `params.list_feature` | array<string> | `[]` | Danh sách cột đầu vào được chọn; mảng rỗng trong mẫu chưa xác định cột, không có nghĩa là tự chọn tất cả cột. Target bị loại khỏi danh sách này nếu có. |
| `params.target` | string hoặc null | `null` | Tên cột giá trị cần dự đoán. |
| `params.transformers` | object<string, array<string>> | 3 nhóm | Các bộ biến đổi áp dụng cho từng nhóm cột, theo thứ tự thực hiện. Key là nhóm cột, giống key trong `output.column_types`. |
| `output.cache_hit` | boolean hoặc null | `null` | Có tái sử dụng kết quả tiền xử lý hay không. |
| `output.dropped_rows` | integer hoặc null | `null` | Số dòng bị loại vì target không chuyển được sang số hoặc bị thiếu. |
| `output.column_types` | object<string, array<string>> | 3 mảng rỗng | Tên các cột thuộc từng nhóm `numeric`, `categorical`, `text`, có sau khi phân loại cột. |

Giá trị `params.transformers` trong mẫu:

| Nhóm | Bộ biến đổi |
| --- | --- |
| `numeric` | `SimpleImputer` → `StandardScaler` |
| `categorical` | `SimpleImputer` → `OneHotEncoder` |
| `text` | `SimpleImputer` → `TfidfVectorizer` |

Nhóm không có cột nào trong `column_types` thì không được áp dụng.

#### 4.1. Cài đặt cố định trong code

Các giá trị dưới đây hard-code trong `process_regression.py`, giống nhau ở mọi job nên không nằm trong JSON.
Khi code đổi các giá trị này thì tăng `version` của JSON.

Thứ tự xử lý:

1. Loại target khỏi `list_feature`, lấy các cột feature.
2. Chuyển target sang số bằng `pandas.to_numeric(errors="coerce")`; loại các dòng có target thiếu (đếm vào `dropped_rows`).
3. Phân loại cột: cột số vào `numeric`; cột object/category có hơn 50 giá trị khác nhau vào `text`, còn lại vào `categorical`.
4. Fit `ColumnTransformer(remainder="passthrough", sparse_threshold=0.3)` trên các dòng của tập train có target hợp lệ,
   trước khi chia fold cross-validation; không dùng dòng holdout.
5. Chuyển kết quả sang mảng dense bằng `toarray()` nếu kết quả là ma trận sparse.

Tham số của từng bộ biến đổi:

| Nhóm | Bộ biến đổi | Tham số | Ý nghĩa |
| --- | --- | --- | --- |
| numeric | `SimpleImputer` | `strategy="median"` | Điền giá trị thiếu bằng trung vị của cột. |
| numeric | `StandardScaler` | mặc định | Chuẩn hóa cột số. |
| categorical | `SimpleImputer` | `strategy="most_frequent"` | Điền giá trị thiếu bằng giá trị xuất hiện nhiều nhất. |
| categorical | `OneHotEncoder` | `handle_unknown="ignore"`, `sparse_output=True` | Mã hóa danh mục; giá trị chưa gặp khi fit thành các số 0. |
| text | `SimpleImputer` | `strategy="constant"`, `fill_value=""` | Thay dữ liệu thiếu bằng chuỗi rỗng. |
| text | `TfidfVectorizer` | `max_features=50`, `preprocessor=convert_to_string` | Biểu diễn text thành tối đa 50 đặc trưng TF-IDF. |

Nhóm text tạo một pipeline riêng cho từng cột (tên `text_<tên_cột>`), và có thêm bước
`FunctionTransformer(to_1d_array)` giữa `SimpleImputer` và `TfidfVectorizer` để đổi dữ liệu một cột thành mảng một chiều.
Bước này chỉ đổi hình dạng dữ liệu nên không liệt kê trong `params.transformers`.

### 5. Node `model_selection`

Đây là nơi duy nhất chứa cấu hình tìm kiếm và đánh giá; `train` và `select_best` dùng chung cấu hình này.

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `params.problem_type` | string | `"regression"` | Bài toán hồi quy. |
| `params.model_names` | array<string> | 5 tên mô hình | Danh sách mô hình ứng viên cần huấn luyện; cũng là các key trong `train.output.models`. |
| `params.search_algorithm` | string hoặc null | `null` | Thuật toán tìm siêu tham số. Các tên chuẩn trong code: `"grid_search"`, `"bayesian_search"`, `"genetic_algorithm"`. |
| `params.max_time` | number hoặc null | `null` | Ngân sách thời gian huấn luyện toàn job, tính bằng giây. Giá trị null trong mẫu chưa xác định cấu hình thực tế. |
| `params.metric_sort` | string hoặc null | `null` | Metric chính để chọn tham số và mô hình tốt nhất; là một key trong `params.metrics`. |
| `params.metrics` | object | Xem bảng metric | Các metric cần đánh giá (key) và hướng tối ưu (`"minimize"` / `"maximize"`). Thứ tự key là thứ tự hiển thị cột. |
| `params.split` | object | Cấu hình KFold | Cách chia dữ liệu để đánh giá cross-validation. |
| `output` | object | `{}` | Node chỉ khai báo cấu hình, không có kết quả riêng. |

Các trường trong `model_selection.params.split`:

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `method` | string | `"KFold"` | Chia dữ liệu thành các phần để lần lượt huấn luyện và đánh giá. |
| `n_splits` | integer | `5` | Số fold đánh giá. |
| `shuffle` | boolean | `true` | Xáo trộn mẫu trước khi chia fold. |
| `random_state` | integer | `42` | Seed cố định cho bước xáo trộn. |

KFold ở đây là đánh giá trong quá trình tìm tham số, chạy trên tập train; tập holdout tách ở `split_holdout_data` không tham gia vào các fold.

### 6. Node `train`

Node `train` bao gồm tìm siêu tham số, đánh giá cross-validation và fit lại từng mô hình
trên toàn bộ tập train đã tiền xử lý. `params` để trống vì cấu hình nằm ở `model_selection.params`.

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `params` | object | `{}` | Không có cấu hình riêng. |
| `output.models` | object | 5 mục mô hình | Trạng thái và kết quả từng mô hình, dùng tên thuật toán làm key. |

Các key của `train.output.models`:

| Key | Thuật toán |
| --- | --- |
| `LinearRegression` | Hồi quy tuyến tính. |
| `DecisionTreeRegressor` | Cây quyết định cho hồi quy. |
| `RandomForestRegressor` | Rừng ngẫu nhiên cho hồi quy. |
| `GradientBoostingRegressor` | Gradient Boosting cho hồi quy. |
| `XGBRegressor` | XGBoost cho hồi quy. |

Mỗi `train.output.models.<model_name>` chỉ giữ 4 key cần cho hiển thị realtime:

| Key | Loại | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- | --- |
| `status` | chạy | string hoặc null | `null` | Trạng thái huấn luyện của mô hình này, theo bảng trạng thái. |
| `error` | chạy | object hoặc null | `null` | Lỗi của riêng mô hình này; mô hình lỗi không làm các mô hình khác dừng. |
| `best_params` | kết quả | object hoặc null | `null` | Bộ siêu tham số tốt nhất tìm được, ví dụ `{"max_depth": 3, "n_estimators": 100}`. Các key phụ thuộc thuật toán. |
| `scores` | kết quả | object hoặc null | `null` | Điểm cross-validation của bộ tham số tốt nhất; key trùng với `model_selection.params.metrics`. |

`best_params` và `scores` giữ `null` cho tới khi mô hình có kết quả, rồi được điền một lần cùng lúc `status` chuyển sang `"succeeded"`.
Nhờ vậy khi đang chạy, mỗi mô hình chỉ có `status` thay đổi; không gửi object điểm toàn `null`.
Sau khi có kết quả, `best_params: {}` là hợp lệ, nghĩa là mô hình dùng tham số mặc định.

Các key đã lược bỏ để tối giản:

- Tên mô hình là key của mục, không lặp lại trong `model_name`.
- Không có `model_id`: backend chỉ đánh số thứ tự khi tổng hợp kết quả (`reduce_results_for_job()`), key tên mô hình đã đủ để nhận diện.
- Không có `started_at`, `finished_at` riêng cho từng mô hình: thời gian của cả bước huấn luyện nằm ở biến chung của node `train`.

Ý nghĩa các key trong `scores` và hướng tối ưu tương ứng trong `model_selection.params.metrics`:

| Key metric | Kiểu giá trị trong `scores` | Giá trị trong mẫu | Hướng tối ưu | Ý nghĩa |
| --- | --- | --- | --- | --- |
| `mse` | number hoặc null | `null` | `"minimize"` | Sai số bình phương trung bình; nhỏ hơn là tốt hơn. |
| `mae` | number hoặc null | `null` | `"minimize"` | Sai số tuyệt đối trung bình; nhỏ hơn là tốt hơn. |
| `mape` | number hoặc null | `null` | `"minimize"` | Sai số phần trăm tuyệt đối trung bình. Code đã nhân 100: giá trị `12.5` hiển thị thành `12.5%`, không nhân 100 lần nữa. |
| `r2` | number hoặc null | `null` | `"maximize"` | Hệ số xác định R²; lớn hơn là tốt hơn, có thể mang giá trị âm. |

Trong `engine.py`, `safe_extract_score()` trả giá trị tuyệt đối cho error metric và đổi NaN/Infinity thành null.
Frontend hiển thị metric null là chưa có điểm hợp lệ, không thay bằng 0.
`models` là object, nên thứ tự key không biểu thị thứ hạng. Muốn hiển thị xếp hạng, dùng `metric_sort` và
hướng trong `metrics`, bỏ qua mục không có `status: "succeeded"` hoặc không có điểm hợp lệ.

### 7. Node `select_best`

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `params.dependency_policy` | string | `"all_terminal"` | Đợi các node trong `depends_on` kết thúc. Ở đây là node `train`; kết thúc không nhất thiết có nghĩa mọi mô hình đều thành công. |
| `output.best_model` | string hoặc null | `null` | Key của mô hình được chọn trong `train.output.models`, ví dụ `"XGBRegressor"`; không chứa object mô hình đã serialize. |
| `output.time_limit_reached` | boolean hoặc null | `null` | Cờ job đạt giới hạn thời gian; trong luồng phân tán lấy từ `tracker.timed_out`. |

Các giá trị của mô hình tốt nhất không lặp lại ở node này, đọc trực tiếp từ `train.output.models.<best_model>`:

| Giá trị cần hiển thị | Đọc từ |
| --- | --- |
| Tham số tốt nhất | `train.output.models.<best_model>.best_params` |
| Điểm tốt nhất | `train.output.models.<best_model>.scores.<metric_sort>` |
| Tiến độ | Số mục trong `train.output.models` có `status` kết thúc / tổng số mục |

### 8. Node `save_result`

| Key | Kiểu dữ liệu | Giá trị trong mẫu | Ý nghĩa |
| --- | --- | --- | --- |
| `params.bucket_name` | string | `"models"` | Bucket MinIO lưu mô hình được chọn. |
| `output.object_name` | string hoặc null | `null` | Đường dẫn object bên trong bucket; luồng hiện tại tạo dạng `<id_user>/<job_id>/<model_name>_1.pkl`. |

`object_name` là key lưu trữ trong bucket, không phải URL tải trực tiếp.
Dữ liệu nhị phân của mô hình không nằm trong JSON lịch sử này.

## Đối chiếu với Python

Đường dẫn dưới đây tính từ thư mục này.

| Node | File / hàm thực hiện |
| --- | --- |
| `read_dataset` | [database/get_dataset.py](../../../../database/get_dataset.py): `MongoDataLoader.get_processed_data()` đọc Parquet từ MinIO. |
| `split_holdout_data` | Chưa có trong code. Backend hiện không tách holdout (không gọi `train_test_split`). |
| `read_training_data` | Chưa có trong code dưới dạng bước riêng trước tiền xử lý. Gần nhất là `LRUDatasetCache.fetch_and_cache()` ở worker, nhưng hàm này nạp X/y đã tiền xử lý từ cache. |
| `preprocessing` | [automl/process_regression.py](../../../../automl/process_regression.py): `preprocess_data()`, các pipeline numeric, categorical và text. |
| `model_selection` | [automl/v2/master.py](../../../../automl/v2/master.py): `get_models()`, `setup_job_tasks()` lấy các mô hình regression và tạo task. Đây là chọn các mô hình ứng viên. |
| `train` | [automl/engine.py](../../../../automl/engine.py): `training_regression()` tạo KFold, gọi `SearchStrategyFactory.create_strategy()` và `search_strategy.search()`, rồi clone mô hình, gán best params và gọi `best_estimator.fit()`. [cluster/worker.py](../../../../cluster/worker.py): `execute_training_task()` lưu artifact của từng mô hình. |
| `select_best` | [automl/v2/master.py](../../../../automl/v2/master.py): `reduce_results_for_job()` so sánh kết quả thành công theo metric. |
| `save_result` | Cùng hàm `reduce_results_for_job()` chuyển artifact tốt nhất vào bucket `models` và gọi `MongoJob.update_success()` trong [database/get_dataset.py](../../../../database/get_dataset.py). |

Danh sách 5 mô hình và miền tham số lấy từ [regression.yml](../../../../assets/system_models/regression.yml).
Ba thuật toán tìm kiếm nằm trong [grid_search.py](../../../../automl/search/strategy/grid_search.py),
[bayesian_search.py](../../../../automl/search/strategy/bayesian_search.py) và
[genetic_algorithm.py](../../../../automl/search/strategy/genetic_algorithm.py).

[kafka_consumer.py](../../../../kafka_consumer.py), hàm `handle_training_job()`, điều phối tiền xử lý và cache.
Khi có cache, việc đọc dataset và fit bộ tiền xử lý được bỏ qua; dữ liệu đã xử lý được tái sử dụng.
Worker nạp X/y từ cache qua `LRUDatasetCache.fetch_and_cache()` trước khi huấn luyện từng nhánh.
Việc nạp này nằm trong nhánh huấn luyện, không phải bước đọc tập train trước tiền xử lý.

API trả JSON này: [app.py](../../../../app.py), `POST /get-job-info` gọi `get_one_job()`.

## Quy ước dữ liệu lịch sử

Đây là mẫu hợp đồng JSON đề xuất, chưa phải response được backend tự động xuất.
`version: "1.0.0"` là phiên bản hợp đồng JSON; nguồn triển khai được đối chiếu là luồng regression phân tán hiện tại.
Backend chưa ghi đầy đủ trạng thái và thời gian riêng cho từng node và từng mô hình trong mẫu.
Các trường `status`, `started_at`, `finished_at`, `error` và giá trị `output` là `null` biểu thị chưa có dữ liệu.
Các mảng rỗng là chỗ điền dữ liệu thực tế, không phải một lịch sử đã chạy thành công.

Khi tích hợp: dùng `queued`, `running`, `succeeded`, `failed`, `skipped`, `cancelled` cho trạng thái;
thời gian dùng ISO 8601, lỗi dùng `{"message": "..."}`.
`skipped` kèm `output.cache_hit: true` biểu thị tái sử dụng dữ liệu.
`select_best` đợi node `train` kết thúc (`all_terminal`), rồi xét các mô hình có `status: "succeeded"` trong `train.output.models`.
Trong response thực tế, `train.output.models` có đủ mọi mô hình trong `model_selection.params.model_names`,
kể cả mô hình thất bại (`status: "failed"`, `error` có nội dung, `best_params` và `scores` giữ `null`), để frontend hiển thị
trạng thái từng mô hình mà không cần gọi API khác.
Nếu không có mô hình thành công thì `select_best` thất bại, `best_model` giữ `null`, `save_result` không chạy (`skipped`).
Dùng key trong `train.output.models` để nhận diện mô hình.

## Khác biệt với hình minh họa

JSON đã có node `split_holdout_data` và `read_training_data` theo hình minh họa, nhưng code hiện tại chưa làm hai bước này.
Khi chưa triển khai, backend ghi hai node này với `status: "skipped"` và `output` giữ `null`.
Code hiện tại dùng KFold 5 phần, shuffle và random_state = 42 trên toàn bộ dataset.
Bộ tiền xử lý hiện được fit trên tất cả dòng có target hợp lệ của toàn bộ dataset, chưa phải chỉ tập train như mô tả ở mục 4.1.
Tập holdout chưa được dùng để chấm điểm mô hình; `scores` trong `train.output.models` vẫn là điểm cross-validation.
Chưa có bước sinh đặc trưng sau tìm siêu tham số hay vòng tối ưu lần 2.
Các thao tác tìm siêu tham số và fit lại được gom trong node `train`, với kết quả từng mô hình ở `train.output.models`.
