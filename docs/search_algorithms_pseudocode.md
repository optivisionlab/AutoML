# 2.2.2. Các chiến lược tìm kiếm siêu tham số

## 2.2.2.1. Phương pháp Grid Search

Chiến lược Grid Search được định nghĩa là một phương pháp tìm kiếm mang tính chất vét cạn, vận hành dựa trên việc quét qua một mạng lưới các giá trị siêu tham số rời rạc đã được thiết lập sẵn. Trong quy trình này, người vận hành sẽ chủ động xác lập các tập giá trị tiềm năng cho từng biến tham số, từ đó thuật toán sẽ kiến tạo toàn bộ các tổ hợp cấu hình thông qua phép tích Descartes và tiến hành kiểm chứng định lượng từng thực thể bằng phương pháp kiểm chứng chéo (cross-validation) [37].

Xét ví dụ cụ thể đối với mô hình cây quyết định, việc thiết lập không gian tìm kiếm được mô hình hóa dựa trên hai siêu tham số chính: "max_depth" với ba giá trị tiềm năng là 5, 10, 15 và "min_samples_split" cũng với ba giá trị là 2, 5, 10.

Dựa trên cấu trúc lưới này, tổng số lượng các cấu hình thực nghiệm mà hệ thống cần thực hiện đánh giá được tính toán là:

$$N = \prod_{j=1}^{m} n_j = 3 \times 3 = 9 \text{ tổ hợp cấu hình}$$

### Các thuật toán phụ trợ

Trước khi trình bày thuật toán chính, hệ thống HAutoML định nghĩa các thủ tục phụ trợ được sử dụng xuyên suốt quá trình Grid Search.

**Thuật toán 2.1.1. Lựa chọn backend thực thi tối ưu**

```
Thuật toán: SelectOptimalBackend
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: N (số tổ hợp tham số), data_size (|D| × số features),
         auto_select_backend (cờ bật/tắt)
Đầu ra:  backend ∈ {"threading", "loky"}

 1:  NẾU auto_select_backend = false THÌ
 2:      TRẢ VỀ "loky"                          ▷ Mặc định khi không auto select
 3:
 4:  ── Threading: overhead thấp, phù hợp tổ hợp ít ──
 5:  NẾU N ≤ 4 THÌ
 6:      TRẢ VỀ "threading"
 7:
 8:  ── Loky (multiprocessing): phù hợp workload lớn ──
 9:  W ← data_size × N                          ▷ Tổng workload
10:  NẾU W > 10⁶ THÌ
11:      TRẢ VỀ "loky"
12:
13:  ── Threading cho các trường hợp trung bình ──
14:  TRẢ VỀ "threading"
```

**Thuật toán 2.1.2. Tạo khóa hash cho bộ nhớ đệm**

```
Thuật toán: GetParamsHash
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: M (mô hình), θ (tổ hợp tham số cần đánh giá)
Đầu ra:  hash_key (chuỗi hash MD5 duy nhất)

 1:  ── Lấy thông tin đầy đủ của class mô hình ──
 2:  class_info ← M.__module__ + "." + M.__class_name__
 3:
 4:  ── Lấy tham số cơ sở hiện tại của mô hình ──
 5:  base_params ← Sorted(M.get_params())
 6:
 7:  ── Tạo chuỗi đầu vào cho hash ──
 8:  hash_input ← class_info + "_" + String(base_params) + "_" + String(Sorted(θ))
 9:
10:  ── Tính MD5 hash ──
11:  hash_key ← MD5(hash_input)
12:  TRẢ VỀ hash_key
```

**Thuật toán 2.1.3. Đánh giá một tổ hợp tham số đơn lẻ (có bộ nhớ đệm)**

```
Thuật toán: EvaluateSingle
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: θ (tổ hợp tham số), M (mô hình), D = (X, y) (dữ liệu),
         cv (cross-validation splitter), scoring (dict các metric),
         cache (bộ nhớ đệm), cache_enabled (cờ bật/tắt)
Đầu ra:  result = {test_scores, params, fit_time, score_time}
         hoặc result lỗi

 1:  THỬ:
 2:      ── Kiểm tra bộ nhớ đệm ──
 3:      key ← GetParamsHash(M, θ)
 4:      NẾU cache_enabled VÀ key ∈ cache THÌ
 5:          TRẢ VỀ cache[key]                   ▷ Cache hit — bỏ qua đánh giá
 6:
 7:      ── Thiết lập tham số cho mô hình ──
 8:      M.set_params(θ)
 9:
10:      ── Thực hiện cross-validation ──
11:      scores ← cross_validate(
12:          estimator = M,
13:          X = X, y = y,
14:          cv = cv,
15:          scoring = scoring,
16:          n_jobs = 1,                          ▷ 1 job vì song song hóa ở mức batch
17:          return_train_score = false,
18:          error_score = "raise"
19:      )
20:
21:      ── Đóng gói kết quả ──
22:      result ← {
23:          test_scores: scores,
24:          params: θ,
25:          fit_time: Mean(scores.fit_time),
26:          score_time: Mean(scores.score_time)
27:      }
28:
29:      ── Lưu vào bộ nhớ đệm ──
30:      NẾU cache_enabled THÌ
31:          cache[key] ← result
32:
33:      TRẢ VỀ result
34:
35:  BẮT LỖI exception e:
36:      ── Trả về kết quả lỗi (không dừng toàn bộ search) ──
37:      TRẢ VỀ {
38:          test_scores: None,
39:          params: θ,
40:          fit_time: 0, score_time: 0,
41:          error: String(e)
42:      }
```

**Thuật toán 2.1.4. Đánh giá một batch tổ hợp tham số (song song/tuần tự)**

```
Thuật toán: EvaluateParamsBatch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: batch (danh sách tổ hợp θ), M (mô hình), D = (X, y),
         cv, scoring, parallel_enabled, n_jobs, model_copies
Đầu ra:  results (danh sách kết quả đánh giá)

 1:  ── Kiểm tra điều kiện song song ──
 2:  NẾU parallel_enabled = true VÀ |batch| > 1 THÌ
 3:      NẾU n_jobs = -1 THÌ
 4:          n_jobs ← CPU_COUNT()
 5:
 6:      NẾU n_jobs > 1 THÌ
 7:          ── Tạo trước bản sao mô hình để quản lý bộ nhớ ──
 8:          actual_jobs ← Min(n_jobs, |batch|)
 9:          NẾU |model_copies| < actual_jobs THÌ
10:              model_copies ← [DeepCopy(M) cho i = 1 đến actual_jobs]
11:
12:          ── Chọn backend tối ưu ──
13:          data_size ← |X|.rows × |X|.columns
14:          backend ← SelectOptimalBackend(|batch|, data_size)
15:
16:          ── Đánh giá song song ──
17:          results ← Parallel(n_jobs, backend)(
18:              VỚI MỖI (i, θ) ∈ Enumerate(batch):
19:                  EvaluateSingle(θ, model_copies[i mod |model_copies|],
20:                                 D, cv, scoring)
21:          )
22:          TRẢ VỀ results
23:
24:  ── Đánh giá tuần tự (fallback) ──
25:  results ← []
26:  VỚI MỖI θ ∈ batch:
27:      results.append(EvaluateSingle(θ, M, D, cv, scoring))
28:  TRẢ VỀ results
```

**Thuật toán 2.1.5. Kiểm tra điều kiện dừng sớm (Early Stopping)**

```
Thuật toán: CheckEarlyStopping
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: s* (điểm tốt nhất hiện tại), best_history (lịch sử điểm tốt nhất),
         max_time, early_stopping_enabled,
         target_score, n_best, no_improve_limit
Đầu ra:  should_stop ∈ {true, false}

 1:  ── Không áp dụng early stopping khi có time limit ──
 2:  NẾU max_time ≠ None THÌ
 3:      TRẢ VỀ false                            ▷ Ưu tiên time limit
 4:
 5:  NẾU early_stopping_enabled = false THÌ
 6:      TRẢ VỀ false
 7:
 8:  ── Kiểm tra ngưỡng score mục tiêu ──
 9:  NẾU target_score ≠ None VÀ s* ≥ target_score THÌ
10:      n_best_default ← Max(1, n_best)
11:      good_count ← |{s ∈ best_history : s ≥ target_score}|
12:      NẾU good_count ≥ n_best_default THÌ
13:          TRẢ VỀ true                          ▷ Đạt đủ số kết quả tốt
14:
15:  ── Kiểm tra không cải thiện liên tiếp ──
16:  NẾU no_improve_limit ≠ None VÀ |best_history| ≥ no_improve_limit THÌ
17:      recent ← best_history[−no_improve_limit:]
18:      NẾU |Set(recent)| = 1 THÌ               ▷ Tất cả bằng nhau → không cải thiện
19:          TRẢ VỀ true
20:
21:  TRẢ VỀ false
```

**Thuật toán 2.1.6. Kiểm tra thời gian proactive (EMA) — Lớp cơ sở SearchStrategy**

```
Thuật toán: ShouldStartNextIteration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: iteration_duration (thời gian iteration vừa hoàn thành, có thể None),
         max_time, search_start_time, ema (EMA hiện tại)
Đầu ra:  should_continue ∈ {true, false}

 1:  ── Tính thời gian còn lại ──
 2:  NẾU max_time = None THÌ
 3:      TRẢ VỀ true                             ▷ Không giới hạn thời gian
 4:
 5:  elapsed ← Time() − search_start_time
 6:  remaining ← Max(0, max_time − elapsed)
 7:
 8:  NẾU elapsed ≥ max_time THÌ
 9:      TRẢ VỀ false                            ▷ Đã vượt quá time limit
10:
11:  ── Cập nhật EMA nếu có iteration_duration ──
12:  NẾU iteration_duration ≠ None THÌ
13:      NẾU ema = None THÌ
14:          ema ← iteration_duration
15:      NGƯỢC LẠI
16:          ema ← 0.7 × iteration_duration + 0.3 × ema
17:
18:  ── Kiểm tra proactive: ước tính iteration tiếp theo ──
19:  NẾU ema ≠ None THÌ
20:      estimated_next ← ema × 1.2              ▷ Safety factor 1.2×
21:      NẾU estimated_next > remaining THÌ
22:          TRẢ VỀ false                         ▷ Dừng proactive
23:
24:  TRẢ VỀ true
```

### Thuật toán chính

**Mã giả 2.1. Thuật toán Grid Search với tối ưu hóa tài nguyên trong HAutoML**

```
Thuật toán: Grid Search với tối ưu hóa tài nguyên
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: Mô hình M, lưới tham số Θ (dict hoặc list-of-dicts),
         dữ liệu D = (X, y), số fold k,
         cấu hình: parallel_evaluation, batch_size, max_time (tùy chọn),
         scoring (dict các metric), metric_sort (metric chính),
         cache_evaluations, early_stopping_enabled,
         early_stopping_score, early_stopping_n_best,
         early_stopping_no_improve
Đầu ra:  θ* (tham số tốt nhất), s* (điểm số tốt nhất),
         all_scores* (tất cả metric cho θ*),
         cv_results_ (kết quả chi tiết),
         time_limit_reached (cờ đánh dấu)

     ── Khởi tạo ──
 1:  StartTimer()                                ▷ Bắt đầu đếm thời gian
 2:  ema ← None                                  ▷ EMA cho ước tính thời gian
 3:  s* ← −∞;  θ* ← ∅;  all_scores* ← ∅
 4:  cache ← ∅;  model_copies ← []
 5:  best_history ← []                           ▷ Lịch sử điểm tốt nhất cho early stopping
 6:  search_log ← []                             ▷ Log chi tiết

     ── Chuẩn hóa param_grid về list-of-dicts ──
 7:  NẾU Θ là dict THÌ
 8:      Θ_list ← [Θ]
 9:  NGƯỢC LẠI NẾU Θ là list THÌ
10:      Θ_list ← Θ
11:  NGƯỢC LẠI
12:      BÁO LỖI "param_grid phải là dict hoặc list of dicts"

     ── Sinh tất cả tổ hợp tham số từ mỗi grid ──
13:  all_params ← []
14:  VỚI MỖI grid ∈ Θ_list:
15:      keys ← Keys(grid)
16:      combos ← CartesianProduct(grid[key] cho mỗi key ∈ keys)
17:      VỚI MỖI combo ∈ combos:
18:          all_params.append(Dict(Zip(keys, combo)))

19:  N ← |all_params|
20:  NẾU N = 0 THÌ
21:      TRẢ VỀ ∅, −∞, ∅, ∅, false               ▷ Không có tổ hợp nào

     ── Điều tiết kích thước batch theo ràng buộc tài nguyên ──
22:  NẾU max_time ≠ None THÌ
23:      b ← 1                                    ▷ batch_size = 1 khi có giới hạn thời gian
24:  NGƯỢC LẠI
25:      b ← batch_size                            ▷ Lấy từ tệp cấu hình hệ thống

     ── Vòng lặp chính theo batch ──
26:  i ← 0;  batch_idx ← 0
27:  early_stopped ← false;  time_stopped ← false

28:  TRONG KHI i < N:
29:      ── Kiểm tra thời gian proactive (EMA) ──
30:      NẾU ShouldStartNextIteration(None, max_time, ...) = false THÌ
31:          time_stopped ← true
32:          DỪNG vòng lặp

33:      ── Lấy batch hiện tại ──
34:      batch_params ← all_params[i : i + b]
35:      t_start ← Time()

36:      ── Đánh giá batch (song song hoặc tuần tự) ──
37:      batch_results ← EvaluateParamsBatch(
38:          batch_params, M, D, cv, scoring,
39:          parallel_evaluation, n_jobs, model_copies
40:      )

41:      t_batch ← Time() − t_start

42:      ── Cập nhật EMA iteration time ──
43:      ShouldStartNextIteration(t_batch, max_time, ...)

44:      ── Xử lý kết quả từng tổ hợp trong batch ──
45:      VỚI MỖI (j, result) ∈ Enumerate(batch_results):
46:          eval_num ← i + j + 1
47:          scores_log ← ∅

48:          NẾU result.test_scores ≠ None THÌ
49:              ── Tính mean score cho mỗi metric ──
50:              VỚI MỖI metric ∈ Keys(scoring):
51:                  test_key ← "test_" + metric
52:                  NẾU test_key ∈ result.test_scores THÌ
53:                      scores_log[metric] ← Mean(result.test_scores[test_key])
54:
55:              ── Kiểm tra cải thiện trên metric chính ──
56:              score ← Mean(result.test_scores["test_" + metric_sort])
57:              NẾU score ≥ s* THÌ
58:                  s* ← score
59:                  θ* ← result.params
60:                  all_scores* ← scores_log
61:          NGƯỢC LẠI
62:              scores_log ← {metric: 0.0 cho mỗi metric ∈ Keys(scoring)}

63:          ── Ghi log đánh giá ──
64:          LogEvaluation(M.__class_name__, "grid_search",
65:                        result.params, scores_log, eval_num, N)

66:      ── Cập nhật lịch sử best score ──
67:      best_history.append(s*)

68:      ── Kiểm tra early stopping ──
69:      NẾU CheckEarlyStopping(s*, best_history, max_time,
70:                              early_stopping_enabled,
71:                              early_stopping_score,
72:                              early_stopping_n_best,
73:                              early_stopping_no_improve) = true THÌ
74:          early_stopped ← true
75:          DỪNG vòng lặp

76:      i ← i + b
77:      batch_idx ← batch_idx + 1

     ── Xây dựng cv_results_ ──
78:  cv_results_ ← BuildCVResults(all_results, scoring, metric_sort)

79:  ── Tính ranking cho mỗi metric ──
80:  VỚI MỖI metric ∈ Keys(scoring):
81:      scores_array ← cv_results_["mean_test_" + metric]
82:      cv_results_["rank_test_" + metric] ← Argsort(−scores_array) + 1

     ── Xóa cache và chuyển đổi kiểu numpy ──
83:  Xóa cache, model_copies, decode_cache
84:  Chuyển đổi tất cả kiểu numpy → Python gốc

85:  TRẢ VỀ θ*, s*, all_scores*, cv_results_, time_stopped
```

Trong kiến trúc của hệ thống HAutoML, phương thức Grid Search đã được nâng cấp vượt xa khỏi các cơ chế tìm kiếm vét cạn thông thường thông qua việc tích hợp các giải pháp tối ưu hóa tài nguyên vật lý. Hệ thống triển khai đồng bộ các kỹ thuật nhằm tiết giảm chi phí điện toán gồm việc lưu trữ đệm (caching) kết quả đánh giá lịch sử thông qua hàm `GetParamsHash` (Thuật toán 2.1.2) và `EvaluateSingle` (Thuật toán 2.1.3), tổ chức xử lý theo lô (batch processing) với kích thước batch tự điều tiết theo ràng buộc thời gian (dòng 22–25 trong Mã giả 2.1), kích hoạt cơ chế đánh giá song song thông qua `EvaluateParamsBatch` (Thuật toán 2.1.4) khi thuộc tính `parallel_evaluation` được xác lập giá trị `true`, hỗ trợ tự động điều phối backend thực thi thông qua `SelectOptimalBackend` (Thuật toán 2.1.1), và thiết lập ngưỡng kiểm soát giới hạn thời gian vận hành thông qua `ShouldStartNextIteration` (Thuật toán 2.1.6) với cơ chế EMA proactive.

*Hình 2.8. Đối chiếu các chiến lược tối ưu hóa siêu tham số*

Một đặc tính kỹ thuật then chốt nằm ở hệ thống early stopping đa tầng của Grid Search (Thuật toán 2.1.5): kiểm tra ngưỡng score mục tiêu (`early_stopping_score`), đếm số kết quả tốt (`early_stopping_n_best`), và phát hiện không cải thiện liên tiếp (`early_stopping_no_improve`). Đặc biệt, tất cả các cơ chế early stopping đều bị vô hiệu hóa khi `max_time` được xác lập (dòng 1–3 trong Thuật toán 2.1.5), đảm bảo ưu tiên sử dụng hết ngân sách thời gian.

Cụ thể, khi tham số `max_time` được xác lập, chiến lược Grid Search sẽ chủ động cấu hình `batch_size` về giá trị đơn vị nhằm tối ưu hóa khả năng kiểm soát ngưỡng thời gian vận hành một cách chính xác (dòng 22–23 trong Mã giả 2.1). Ngược lại, trong điều kiện không bị giới hạn bởi ngân sách thời gian, hệ thống ưu tiên khai thác chỉ số `batch_size` từ tệp cấu hình hệ thống để gia tăng hiệu suất xử lý luồng dữ liệu (dòng 25). Bên cạnh đó, thuộc tính `parallel_evaluation` đóng vai trò là chốt chặn quyết định phương thức vận hành (dòng 1–2 trong Thuật toán 2.1.4); nếu tham số này ở trạng thái tắt, quy trình đánh giá sẽ bắt buộc thực thi theo trình tự tuyến tính ngay cả khi chỉ số `n_jobs` được thiết lập giá trị lớn hơn 1.

Ưu điểm cốt lõi của phương pháp Grid Search nằm ở tính minh bạch, khả năng tái lập cao và đặc biệt phù hợp với các bài toán sở hữu không gian tham số có cấu trúc đơn giản. Tuy nhiên, rào cản kỹ thuật lớn nhất chính là sự bùng nổ của chi phí điện toán theo hàm mũ khi quy mô tham số hoặc số lượng giá trị thành phần gia tăng [37]. Do đó, trong khuôn khổ dự án này, chiến lược Grid Search được định hướng ứng dụng tối ưu cho các mô hình có không gian tham số rời rạc với kích thước hạn chế, điển hình như các thực thể DecisionTreeClassifier, KNeighborsClassifier hoặc các cấu hình thực nghiệm tinh gọn của RandomForestClassifier.

---

## 2.2.2.2. Phương pháp Random Search

Khác với cơ chế duyệt vét cạn, chiến lược Random Search vận hành dựa trên việc lấy mẫu xác suất ngẫu nhiên các thực thể cấu hình xuyên suốt không gian tham số định nghĩa. Thay vì thực thi toàn bộ các tổ hợp tiềm năng, thuật toán chủ động giới hạn phạm vi khai phá dựa trên ngân sách thực nghiệm được xác lập thông qua chỉ số n_iter [37].

**Mã giả 2.2. Thuật toán Random Search cho tối ưu hóa siêu tham số**

```
Thuật toán: Random Search
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: Mô hình M, không gian tham số Θ, dữ liệu D,
         số fold k, ngân sách n_iter
Đầu ra:  θ* (tham số tốt nhất), s* (điểm số tốt nhất)

 1:  s* ← −∞;  θ* ← ∅
 2:  VỚI i = 1 ĐẾN n_iter:
 3:      θᵢ ← RandomSample(Θ)              ▷ Lấy mẫu ngẫu nhiên từ Θ
 4:      sᵢ ← (1/k) × Σⱼ₌₁ᵏ Score(M_θᵢ^(D\Fⱼ), Fⱼ)   ▷ Cross-validation
 5:      NẾU sᵢ > s* THÌ
 6:          s* ← sᵢ;  θ* ← θᵢ
 7:  TRẢ VỀ θ*, s*
```

*Hình 2.9. Minh họa cơ chế lấy mẫu ngẫu nhiên của Random Search trong không gian siêu tham số*

Dựa trên các nghiên cứu của Bergstra và Bengio, chiến lược Random Search được xác định là một baseline sở hữu năng lực vượt trội hơn so với Grid Search trong các không gian tìm kiếm đa chiều. Đặc tính ưu việt này thể hiện rõ nét khi chỉ tồn tại một nhóm nhỏ các siêu tham số có tác động trọng yếu đến hiệu năng thực thi của hệ thống [37]. Trong khi kỹ thuật Grid Search thực hiện phân bổ các điểm thực nghiệm đồng nhất trên mọi phương diện—bao gồm cả những chiều tham số ít giá trị—thì cơ chế Random Search lại chủ động khai phá đa dạng các ngưỡng giá trị khác nhau trên từng chiều độc lập. Nhờ khả năng lấy mẫu linh hoạt này, thuật toán có xác suất cao hơn trong việc định danh các vùng không gian tối ưu với cùng một mức ngân sách đánh giá thực nghiệm [37].

Xét trong khuôn khổ dự án HAutoML, mặc dù phương thức Random Search chưa được phân tách thành một thực thể chiến lược độc lập tại tầng factory, song tư tưởng lấy mẫu ngẫu nhiên vẫn đóng vai trò là hạt nhân kỹ thuật trong nhiều cơ chế vận hành khác. Cụ thể, nguyên lý này được ứng dụng xuyên suốt trong giai đoạn khởi tạo cấu hình của tối ưu hóa Bayesian (dòng 12 trong Mã giả 2.3) cũng như trong các phép toán quần thể, lai ghép và đột biến của thuật toán di truyền. Do đó, Random Search vẫn giữ nguyên giá trị khoa học như một phương pháp nền tảng để tiến hành đánh giá đối chứng và kiểm chứng hiệu năng của các giải pháp tối ưu hóa chuyên sâu hơn trong hệ thống.

---

## 2.2.2.3. Kỹ thuật Tối ưu hóa Bayesian (Bayesian Optimization)

Chiến lược Bayesian Optimization được định vị là giải pháp tối ưu cho các kịch bản thực nghiệm sở hữu chi phí điện toán lớn cho mỗi lần kiểm chứng cấu hình. Thay vì thực thi quét tuyến tính như Grid Search hay lấy mẫu xác suất độc lập như Random Search, phương pháp này thiết lập một mô hình xấp xỉ (surrogate model) nhằm ước lượng mối tương quan phi tuyến giữa hệ thống siêu tham số và hiệu năng thực thi của mô hình [38], [39].

Trong các cấu trúc triển khai phổ biến, kỹ thuật này ứng dụng Gaussian Process để mô hình hóa hàm mục tiêu, cho phép dự báo đồng thời giá trị kỳ vọng của độ đo hiệu năng và định lượng ngưỡng bất định tại các điểm chưa khai phá. Dựa trên tri thức đó, hàm lợi ích (acquisition function) sẽ thực hiện điều phối chiến lược nhằm cân bằng giữa việc khai thác (exploitation) các vùng không gian tiềm năng và khám phá (exploration) những vùng dữ liệu còn thiếu thông tin [38], [40].

*Hình 2.10. Mô hình xấp xỉ và hàm lợi ích trong tối ưu hóa Bayesian*

### Các thuật toán phụ trợ

**Thuật toán 2.3.1. Phát hiện mất cân bằng lớp**

```
Thuật toán: DetectClassImbalance
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: y (mảng nhãn), τ (ngưỡng mất cân bằng, mặc định = 0.3)
Đầu ra:  is_imbalanced ∈ {true, false}

 1:  ── Đếm số lượng mẫu của mỗi lớp ──
 2:  class_counts ← Counter(y)
 3:  total ← |y|
 4:
 5:  ── Tính tỷ lệ mỗi lớp ──
 6:  class_ratios ← {c: count/total cho mỗi (c, count) ∈ class_counts}
 7:
 8:  ── So sánh chênh lệch với ngưỡng ──
 9:  min_ratio ← Min(class_ratios.values)
10:  max_ratio ← Max(class_ratios.values)
11:
12:  TRẢ VỀ (max_ratio − min_ratio) > τ
```

**Thuật toán 2.3.2. Xác định phương pháp tính trung bình**

```
Thuật toán: GetAveragingMethod
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: y (mảng nhãn), averaging_config (cấu hình: "auto"|"macro"|"weighted")
Đầu ra:  method ∈ {"macro", "weighted"}

 1:  NẾU averaging_config = "auto" THÌ
 2:      NẾU DetectClassImbalance(y, τ=0.3) = true THÌ
 3:          TRẢ VỀ "weighted"                   ▷ Dữ liệu mất cân bằng
 4:      NGƯỢC LẠI
 5:          TRẢ VỀ "macro"                      ▷ Dữ liệu cân bằng
 6:  NGƯỢC LẠI NẾU averaging_config ∈ {"macro", "weighted"} THÌ
 7:      TRẢ VỀ averaging_config
 8:  NGƯỢC LẠI
 9:      TRẢ VỀ "macro"                          ▷ Fallback mặc định
```

**Thuật toán 2.3.3. Chuyển đổi không gian tìm kiếm sang định dạng skopt**

```
Thuật toán: ConvertSearchSpace
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: param_grid (dict: tên tham số → giá trị/dimension)
Đầu ra:  search_space (danh sách dimensions), param_names (danh sách tên)

 1:  search_space ← []
 2:  param_names ← []
 3:
 4:  VỚI MỖI (param_name, param_value) ∈ param_grid:
 5:      NẾU param_value là dimension object (Real, Integer, Categorical) THÌ
 6:          ── Gán tên nếu chưa có ──
 7:          NẾU param_value.name = None THÌ
 8:              param_value.name ← param_name
 9:          search_space.append(param_value)
10:          param_names.append(param_name)
11:
12:      NGƯỢC LẠI NẾU param_value là list HOẶC tuple THÌ
13:          ── Chuyển thành Categorical ──
14:          dim ← Categorical(param_value, name=param_name)
15:          search_space.append(dim)
16:          param_names.append(param_name)
17:
18:      NGƯỢC LẠI
19:          BÁO LỖI "Kiểu tham số không hợp lệ: " + Type(param_value)
20:
21:  TRẢ VỀ search_space, param_names
```

**Thuật toán 2.3.4. Tải trạng thái optimizer cho warm start**

```
Thuật toán: LoadOptimizerState
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: search_space_hash (hash không gian tìm kiếm),
         model_name (tên mô hình),
         optimizer_state (bộ nhớ trạng thái),
         warm_start_enabled (cờ bật/tắt)
Đầu ra:  x0, y0 (các điểm + giá trị từ lần chạy trước, hoặc None, None)

 1:  NẾU warm_start_enabled = false THÌ
 2:      TRẢ VỀ None, None
 3:
 4:  key ← model_name + "_" + search_space_hash
 5:
 6:  NẾU key ∈ optimizer_state THÌ
 7:      state ← optimizer_state[key]
 8:      NẾU state.search_space_hash = search_space_hash THÌ
 9:          x0 ← state.x_iters
10:          y0 ← state.func_vals
11:          NẾU x0 ≠ ∅ VÀ y0 ≠ ∅ THÌ
12:              TRẢ VỀ x0, y0              ▷ Warm start với dữ liệu lịch sử
13:
14:  TRẢ VỀ None, None
```

**Thuật toán 2.3.5. Lưu trạng thái optimizer**

```
Thuật toán: SaveOptimizerState
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: result (kết quả gp_minimize), search_space_hash,
         model_name, optimizer_state, save_enabled
Đầu ra:  (cập nhật optimizer_state in-place)

 1:  NẾU save_enabled = false THÌ
 2:      THOÁT
 3:
 4:  state ← {
 5:      x_iters: result.x_iters,
 6:      func_vals: result.func_vals,
 7:      search_space_hash: search_space_hash
 8:  }
 9:
10:  key ← model_name + "_" + search_space_hash
11:  optimizer_state[key] ← state
```

**Thuật toán 2.3.6. Tối ưu hóa trên một grid đơn lẻ (SearchSingleGrid)**

```
Thuật toán: SearchSingleGrid
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: M (mô hình), param_grid (dict một grid đơn lẻ),
         D = (X, y), k (số fold),
         n_calls, n_init, acq_func, acq_optimizer,
         scoring, metric_sort, max_time,
         early_stopping_enabled, early_stopping_patience,
         convergence_threshold,
         warm_start_enabled, save_optimizer_state
Đầu ra:  θ*, s*, all_scores*, cv_results_, time_limit_reached

     ── Chuyển đổi không gian tìm kiếm ──
 1:  search_space, param_names ← ConvertSearchSpace(param_grid)
 2:  cv_results_ ← {params: [], mean_test_score: [], ...}
 3:  best_all_scores ← None
 4:  best_score_history ← []
 5:  last_callback_time ← Time()

     ── Phát hiện mất cân bằng lớp ──
 6:  optimize_for ← GetAveragingMethod(y, "auto")

     ── Định nghĩa hàm mục tiêu với phép nghịch đảo dấu ──
 7:  HÀM Objective(θ):
 8:      M.set_params(θ)
 9:      primary_metric ← metric_sort
10:
11:      cv_results ← cross_validate(
12:          estimator = M, X = X, y = y,
13:          cv = k, n_jobs = n_jobs,
14:          scoring = scoring,
15:          error_score = error_score
16:      )
17:
18:      ── Lưu trữ tất cả metrics ──
19:      last_metrics ← {}
20:      VỚI MỖI key ∈ Keys(scoring):
21:          test_key ← "test_" + key
22:          NẾU test_key ∈ cv_results THÌ
23:              last_metrics[key] ← Mean(cv_results[test_key])
24:
25:      ── Chọn điểm số để tối ưu hóa ──
26:      score ← last_metrics[primary_metric]
27:
28:      ── gp_minimize luôn tối thiểu hóa → đảo dấu ──
29:      TRẢ VỀ −score
30:  KẾT THÚC HÀM

     ── Định nghĩa callback cho mỗi iteration ──
31:  HÀM OnStep(res):
32:      ── Tính thời gian iteration vừa hoàn thành ──
33:      now ← Time()
34:      iteration_duration ← now − last_callback_time
35:      last_callback_time ← now
36:
37:      iteration ← |res.x_iters|
38:
39:      ── Chuyển đổi tham số về kiểu Python gốc ──
40:      current_params ← {}
41:      VỚI MỖI (i, val) ∈ Enumerate(res.x_iters[−1]):
42:          current_params[param_names[i]] ← ConvertNumpyTypes(val)
43:
44:      current_score ← −res.func_vals[−1]
45:      best_so_far ← −res.fun
46:
47:      ── Lấy metrics từ iteration hiện tại ──
48:      metrics ← ConvertNumpyTypes(Objective.last_metrics)
49:
50:      ── Điền dữ liệu vào cv_results_ ──
51:      cv_results_.params.append(current_params)
52:      cv_results_.mean_test_score.append(current_score)
53:      VỚI MỖI metric_key ∈ metric_names:
54:          cv_results_["mean_test_" + metric_key].append(
55:              metrics[metric_key])
56:
57:      ── Cập nhật best_all_scores nếu đây là kết quả tốt nhất ──
58:      NẾU current_score ≥ best_so_far THÌ
59:          best_all_scores ← Copy(metrics)
60:
61:      ── Theo dõi lịch sử điểm số ──
62:      best_score_history.append(best_so_far)
63:
64:      ── Kiểm tra time limit (EMA proactive) ──
65:      NẾU ShouldStartNextIteration(iteration_duration, ...) = false THÌ
66:          TRẢ VỀ true                          ▷ Dừng gp_minimize
67:
68:      ── Kiểm tra early stopping (chỉ khi không có time limit) ──
69:      NẾU early_stopping_enabled VÀ max_time = None
70:          VÀ iteration ≥ early_stopping_patience THÌ
71:
72:          ── Kiểm tra không cải thiện ──
73:          recent ← best_score_history[−patience:]
74:          NẾU |Set(recent)| = 1 THÌ
75:              TRẢ VỀ true                      ▷ Dừng: không cải thiện
76:
77:          ── Kiểm tra ngưỡng hội tụ ──
78:          NẾU |best_score_history| > 1 THÌ
79:              improvement ← best_score_history[−1] − best_score_history[−2]
80:              NẾU |improvement| < convergence_threshold THÌ
81:                  TRẢ VỀ true                  ▷ Dừng: hội tụ
82:
83:      TRẢ VỀ false                             ▷ Tiếp tục tối ưu hóa
84:  KẾT THÚC HÀM

     ── Warm start: tải trạng thái từ lần chạy trước ──
85:  space_hash ← MD5(search_space)[:8]
86:  x0, y0 ← LoadOptimizerState(space_hash, M.__class_name__,
87:                                optimizer_state, warm_start_enabled)
88:
89:  ── Điều chỉnh n_initial_points nếu warm start ──
90:  NẾU x0 ≠ None VÀ y0 ≠ None THÌ
91:      n_init ← Max(1, n_init ÷ 2)             ▷ Giảm 50% điểm khởi tạo

     ── Thực thi tối ưu hóa Bayesian ──
92:  result ← gp_minimize(
93:      func = Objective,
94:      dimensions = search_space,
95:      n_calls = n_calls,
96:      n_initial_points = n_init,
97:      acq_func = acq_func,
98:      acq_optimizer = acq_optimizer,
99:      callback = [OnStep],
100:     x0 = x0, y0 = y0,
101:     random_state = random_state,
102:     n_jobs = n_jobs
103: )
104:
     ── Lưu trạng thái optimizer cho warm start tương lai ──
105: SaveOptimizerState(result, space_hash, M.__class_name__,
106:                     optimizer_state, save_optimizer_state)
107:
     ── Trích xuất kết quả tốt nhất ──
108: θ* ← {param_names[i]: result.x[i] cho mỗi i}
109: θ* ← ConvertNumpyTypes(θ*)
110: s* ← −result.fun                             ▷ Khôi phục dấu dương
111:
     ── Tính ranking cho cv_results_ ──
112: VỚI MỖI metric ∈ metric_names:
113:     scores ← cv_results_["mean_test_" + metric]
114:     cv_results_["rank_test_" + metric] ← Argsort(−scores) + 1
115:
116: TRẢ VỀ θ*, s*, best_all_scores, cv_results_, time_limit_reached
```

### Thuật toán chính

**Mã giả 2.3. Thuật toán Bayesian Optimization trong HAutoML (hỗ trợ multi-grid)**

```
Thuật toán: Bayesian Optimization (sử dụng gp_minimize)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: Mô hình M, không gian tham số Θ (dict hoặc list-of-dicts),
         dữ liệu D = (X, y), số fold k,
         n_calls, n_init, hàm thu nhận α(·), max_time (tùy chọn)
Đầu ra:  θ* (tham số tốt nhất), s* (điểm số tốt nhất),
         all_scores* (tất cả metric), cv_results_,
         time_limit_reached

     ── Khởi tạo ──
 1:  StartTimer()
 2:  optimizer_state ← {}                        ▷ Lưu trạng thái cho warm start

     ── Chuẩn hóa param_grid về list-of-dicts ──
 3:  NẾU Θ là dict THÌ Θ_list ← [Θ]
 4:  NGƯỢC LẠI Θ_list ← Θ

     ── Chạy tối ưu hóa trên từng grid ──
 5:  all_results ← []
 6:  all_cv_results ← []

 7:  VỚI MỖI (grid_idx, single_grid) ∈ Enumerate(Θ_list):
 8:      NẾU single_grid = ∅ THÌ
 9:          ── Model không có hyperparameters → đánh giá default ──
10:          result ← EvaluateDefaultParams(M, X, y, scoring)
11:          all_results.append(result)
12:          all_cv_results.append(result.cv_results_)
13:          TIẾP TỤC                             ▷ Bỏ qua grid này
14:
15:      ── Tối ưu hóa grid đơn lẻ ──
16:      result ← SearchSingleGrid(
17:          M, single_grid, D, k,
18:          n_calls, n_init, α, ...,
19:          max_time, early_stopping_enabled,
20:          early_stopping_patience, convergence_threshold,
21:          warm_start_enabled, save_optimizer_state
22:      )
23:      all_results.append(result)
24:      all_cv_results.append(result.cv_results_)

     ── Chọn kết quả tốt nhất từ tất cả các grid ──
25:  NẾU |all_results| = 0 THÌ
26:      TRẢ VỀ ∅, 0.0, ∅, ∅, false
27:
28:  best_idx ← ArgMax(all_results[i].s* cho mỗi i)
29:  θ*, s*, all_scores* ← all_results[best_idx]

     ── Gộp cv_results từ tất cả các grid ──
30:  combined_cv ← CombineCVResults(all_cv_results)

     ── Xóa cache và chuyển đổi kiểu numpy ──
31:  Chuyển đổi tất cả kiểu numpy → Python gốc
32:  TRẢ VỀ θ*, s*, all_scores*, combined_cv, time_limit_reached
```

Trong kiến trúc vận hành của hệ thống HAutoML, chiến lược Bayesian Search tận dụng hàm `gp_minimize` như một nhân tố cốt lõi để thực hiện hóa quá trình tối ưu hóa. Do bản chất của phương thức này được thiết kế để giải quyết các bài toán tối thiểu hóa, trong khi các chỉ số đo lường hiệu năng then chốt của hệ thống như accuracy, f1 hay r2 thường yêu cầu tối đa hóa giá trị, hàm mục tiêu bắt buộc phải được chuẩn hóa thông qua việc trả về giá trị đối nghịch của điểm số (−score), như được thể hiện tại dòng 28–29 trong Thuật toán 2.3.6.

Nguyên lý chuyển đổi này dựa trên cơ sở logic toán học bền vững:

$$\arg\max_{\boldsymbol{\theta} \in \Theta} \text{Score}(\boldsymbol{\theta}) \;\equiv\; \arg\min_{\boldsymbol{\theta} \in \Theta} \bigl[-\text{Score}(\boldsymbol{\theta})\bigr]$$

Giải pháp trừu tượng hóa này cho phép nền tảng duy trì một cơ chế minimization đồng nhất cho toàn bộ các độ đo metric dạng maximize. Xét dưới góc độ thực nghiệm, nếu cấu hình A đạt accuracy = 0.90 và cấu hình B đạt accuracy = 0.85, các giá trị mục tiêu tương ứng sẽ được ánh xạ thành −0.90 và −0.85. Khi đó, thuật toán tối thiểu hóa sẽ tự động định danh −0.90 là kết quả ưu việt hơn, bảo đảm tính nhất quán với mục tiêu tìm kiếm điểm số cao nhất trên phạm vi toàn cục.

Bên cạnh đó, hệ thống tích hợp cơ chế **phát hiện mất cân bằng lớp tự động** (Thuật toán 2.3.1) với ngưỡng τ = 0.3 để tự động lựa chọn phương pháp tính trung bình phù hợp (macro hoặc weighted) thông qua Thuật toán 2.3.2. Cơ chế **warm start** (Thuật toán 2.3.4–2.3.5) cho phép kế thừa tri thức từ các lần chạy trước bằng cách lưu và tải trạng thái optimizer, giảm 50% số điểm khởi tạo ngẫu nhiên khi có dữ liệu lịch sử.

Quy trình Bayesian Search trong dự án còn tích hợp chặt chẽ các **chốt chặn vận hành** thực tế (dòng 64–81 trong Thuật toán 2.3.6): kiểm tra time limit proactive bằng EMA (dòng 64–66), early stopping khi không cải thiện (dòng 72–75), và kiểm tra hội tụ (dòng 78–81). Trong các kịch bản mà tham số `max_time` được xác lập, hệ thống sẽ ưu tiên tối ưu hóa tài nguyên theo dòng thời gian vật lý. Ngược lại, nếu không có ràng buộc về thời hạn, tính năng early stopping đóng vai trò là bộ lọc thông minh nhằm ngắt tiến trình nếu hiệu năng không ghi nhận sự cải thiện đáng kể.

Một tính năng quan trọng khác là **hỗ trợ multi-grid** (Mã giả 2.3): khi `param_grid` là list-of-dicts (mỗi dict đại diện cho một cấu hình grid con), hệ thống chạy `SearchSingleGrid` trên từng grid rồi chọn kết quả tốt nhất toàn cục (dòng 25–29).

---

## 2.2.2.4. Thuật toán di truyền (Genetic Algorithm)

Thuật toán di truyền (GA) mô phỏng quá trình tiến hóa tự nhiên thông qua ba toán tử chính: **Selection** (chọn lọc), **Crossover** (lai ghép) và **Mutation** (đột biến) [41]. Trong khuôn khổ hệ thống HAutoML, GA được triển khai như một chiến lược tìm kiếm siêu tham số với nhiều cơ chế thích nghi nhằm cân bằng giữa khám phá toàn cục và khai thác cục bộ.

Mỗi cá thể trong quần thể biểu diễn một tổ hợp siêu tham số θ = (θ₁, θ₂, ..., θₘ). Hệ thống hỗ trợ ba kiểu mã hóa: **categorical** (mã hóa dạng chỉ số [0, n−1]), **integer** (mã hóa liên tục, làm tròn khi giải mã) và **continuous** (mã hóa trực tiếp). Quá trình tiến hóa vận hành qua G thế hệ, mỗi thế hệ bao gồm các pha: đánh giá fitness, chọn lọc đấu trường, lai ghép BLX-α, đột biến Gaussian thích nghi, và kiểm soát đa dạng quần thể.

### Các thuật toán phụ trợ

**Thuật toán 2.4.1. Mã hóa lưới tham số cho thuật toán di truyền**

```
Thuật toán: EncodeParameters
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: param_grid (dict hoặc list-of-dicts)
Đầu ra:  grid_encodings (danh sách encoding cho mỗi grid),
         num_grids (số lượng grid)

 1:  ── Chuẩn hóa về list-of-dicts ──
 2:  param_grid_list ← NormalizeParamGrid(param_grid)
 3:  param_grid_list ← [g cho g ∈ param_grid_list nếu g ≠ ∅]
 4:  NẾU |param_grid_list| = 0 THÌ
 5:      param_grid_list ← [∅]                   ▷ Model không có hyperparameter

 6:  grid_encodings ← []
 7:  num_grids ← |param_grid_list|

 8:  VỚI MỖI (grid_idx, single_grid) ∈ Enumerate(param_grid_list):
 9:      encoding ← {param_bounds: {}, param_types: {}}

10:      VỚI MỖI (param_name, param_values) ∈ single_grid:
11:          NẾU param_values là list THÌ
12:              ── Categorical: mã hóa dạng chỉ số ──
13:              encoding.param_bounds[param_name] ← (0, |param_values| − 1)
14:              encoding.param_types[param_name] ← ("categorical", param_values)
15:
16:          NGƯỢC LẠI NẾU param_values là tuple (min, max) THÌ
17:              encoding.param_bounds[param_name] ← (min, max)
18:              NẾU min VÀ max đều là integer THÌ
19:                  encoding.param_types[param_name] ← ("integer", None)
20:              NGƯỢC LẠI
21:                  encoding.param_types[param_name] ← ("continuous", None)

22:      grid_encodings.append(encoding)

23:  TRẢ VỀ grid_encodings, num_grids
```

**Thuật toán 2.4.2. Giải mã cá thể từ biểu diễn di truyền (có bộ nhớ đệm)**

```
Thuật toán: DecodeIndividual
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: individual (dict: tên tham số → giá trị mã hóa),
         grid_encodings (danh sách encoding),
         decode_cache (bộ nhớ đệm)
Đầu ra:  decoded (dict: tên tham số → giá trị thực tế)

 1:  ── Kiểm tra bộ nhớ đệm ──
 2:  cache_key ← MakeHashable(individual)
 3:  NẾU cache_key ∈ decode_cache THÌ
 4:      TRẢ VỀ decode_cache[cache_key]

 5:  decoded ← {}
 6:  grid_idx ← Int(individual["_grid_idx"])
 7:  param_types ← grid_encodings[grid_idx].param_types

 8:  VỚI MỖI (param_name, value) ∈ individual:
 9:      NẾU param_name = "_grid_idx" THÌ TIẾP TỤC
10:      NẾU param_name ∉ param_types THÌ TIẾP TỤC

11:      (type, values) ← param_types[param_name]

12:      NẾU type = "categorical" THÌ
13:          index ← Clip(Round(value), 0, |values| − 1)
14:          decoded[param_name] ← values[index]
15:      NGƯỢC LẠI NẾU type = "integer" THÌ
16:          decoded[param_name] ← Int(Round(value))
17:      NGƯỢC LẠI
18:          decoded[param_name] ← Float(value)

19:  decoded ← ConvertNumpyTypes(decoded)
20:  decode_cache[cache_key] ← decoded
21:  TRẢ VỀ decoded
```

**Thuật toán 2.4.3. Tạo một cá thể ngẫu nhiên**

```
Thuật toán: CreateIndividual
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: grid_idx (chỉ số grid, có thể None),
         num_grids, grid_encodings
Đầu ra:  individual (dict biểu diễn cá thể)

 1:  individual ← {}

 2:  ── Chọn grid_idx nếu chưa có ──
 3:  NẾU grid_idx = None THÌ
 4:      grid_idx ← RandomInt(0, num_grids − 1)

 5:  individual["_grid_idx"] ← Float(grid_idx)

 6:  ── Tạo giá trị ngẫu nhiên cho mỗi tham số ──
 7:  param_bounds ← grid_encodings[grid_idx].param_bounds
 8:  VỚI MỖI (param_name, (min_val, max_val)) ∈ param_bounds:
 9:      individual[param_name] ← RandomUniform(min_val, max_val)

10:  TRẢ VỀ individual
```

**Thuật toán 2.4.4. Khởi tạo quần thể thông minh (Smart Initialization)**

```
Thuật toán: SmartInitialization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: P (kích thước quần thể), num_grids, grid_encodings
Đầu ra:  population (danh sách P cá thể)

 1:  population ← []

     ── Phân bổ đều số cá thể cho mỗi grid ──
 2:  per_grid ← Max(1, P ÷ num_grids)

 3:  VỚI grid_idx = 0 ĐẾN num_grids − 1:
 4:      VỚI j = 1 ĐẾN per_grid:
 5:          NẾU |population| ≥ P THÌ DỪNG
 6:          population.append(CreateIndividual(grid_idx, ...))

     ── Điền phần còn lại bằng cá thể ngẫu nhiên ──
 7:  TRONG KHI |population| < P:
 8:      population.append(CreateIndividual(None, ...))

 9:  TRẢ VỀ population[:P]
```

**Thuật toán 2.4.5. Đánh giá cá thể với bộ nhớ đệm toàn cục**

```
Thuật toán: EvaluateIndividual
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: individual (cá thể), M (mô hình), D = (X, y),
         scoring, cv, n_jobs, error_score,
         eval_cache (bộ nhớ đệm toàn cục),
         use_global_cache, max_cache_size
Đầu ra:  result (dict: metric_name → score)

 1:  total_evaluations ← total_evaluations + 1

     ── Kiểm tra bộ nhớ đệm toàn cục ──
 2:  NẾU use_global_cache = true THÌ
 3:      cache_key ← MakeHashable(individual)
 4:      NẾU cache_key ∈ eval_cache THÌ
 5:          cache_hits ← cache_hits + 1
 6:          TRẢ VỀ eval_cache[cache_key]          ▷ Cache hit

 7:  THỬ:
 8:      ── Giải mã cá thể → tham số thực tế ──
 9:      params ← DecodeIndividual(individual, ...)
10:      M.set_params(params)
11:
12:      ── Cross-validation ──
13:      scores ← cross_validate(M, X, y, cv=cv,
14:                               scoring=scoring,
15:                               n_jobs=n_jobs,
16:                               error_score=error_score)
17:
18:      ── Tính mean score cho mỗi metric ──
19:      result ← {}
20:      VỚI MỖI metric_name ∈ Keys(scoring):
21:          result[metric_name] ← Mean(scores["test_" + metric_name])
22:
23:      ── Lưu vào bộ nhớ đệm (quản lý kích thước FIFO) ──
24:      NẾU use_global_cache = true THÌ
25:          NẾU |eval_cache| ≥ max_cache_size THÌ
26:              ── Loại bỏ 25% mục cũ nhất ──
27:              keys_to_remove ← Keys(eval_cache)[:max_cache_size ÷ 4]
28:              VỚI MỖI key ∈ keys_to_remove:
29:                  Xóa eval_cache[key]
30:          eval_cache[cache_key] ← Copy(result)
31:
32:      TRẢ VỀ result
33:
34:  BẮT LỖI (ValueError, TypeError, KeyError):
35:      TRẢ VỀ {metric: −∞ cho mỗi metric ∈ Keys(scoring)}
```

**Thuật toán 2.4.6. Chọn lọc đấu trường thích ứng (Adaptive Tournament Selection)**

```
Thuật toán: AdaptiveTournamentSize
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: d (diversity), P (kích thước quần thể),
         k_t (tournament size cơ sở),
         adaptive_enabled (cờ bật/tắt)
Đầu ra:  k_t_adapt (tournament size thích ứng)

 1:  NẾU adaptive_enabled = false THÌ
 2:      TRẢ VỀ Min(k_t, P)

 3:  NẾU d < 0.1 THÌ
 4:      ── Diversity thấp: giảm áp lực chọn lọc → tăng exploration ──
 5:      k_t_adapt ← Max(2, k_t − 1)
 6:  NGƯỢC LẠI NẾU d > 0.5 THÌ
 7:      ── Diversity cao: tăng áp lực chọn lọc → tăng exploitation ──
 8:      k_t_adapt ← Min(P ÷ 2, k_t + 1)
 9:  NGƯỢC LẠI
10:      k_t_adapt ← k_t

11:  TRẢ VỀ Min(k_t_adapt, P)
```

```
Thuật toán: TournamentSelection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: population, fitness_scores (numpy array),
         d (diversity, có thể None), k_t, adaptive_enabled
Đầu ra:  winner (cá thể chiến thắng, bản sao)

 1:  ── Xác định tournament size ──
 2:  NẾU d ≠ None VÀ adaptive_enabled = true THÌ
 3:      t_size ← AdaptiveTournamentSize(d, |population|, k_t, true)
 4:  NGƯỢC LẠI
 5:      t_size ← Min(k_t, |population|)

 6:  ── Chọn ngẫu nhiên t_size cá thể (không trùng) ──
 7:  indices ← RandomChoice(|population|, size=t_size, replace=false)

 8:  ── Chọn cá thể có fitness cao nhất ──
 9:  winner_idx ← indices[ArgMax(fitness_scores[indices])]

10:  TRẢ VỀ Copy(population[winner_idx])
```

**Thuật toán 2.4.7. Lai ghép BLX-α (hỗ trợ cả continuous và categorical)**

```
Thuật toán: BLXαCrossover
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: parent1, parent2 (hai cá thể bố mẹ),
         p_c (tỷ lệ lai ghép), α (hệ số BLX, mặc định = 0.5),
         grid_encodings, simple_crossover (cờ chế độ đơn giản)
Đầu ra:  child1, child2 (hai cá thể con)

 1:  ── Kiểm tra xác suất lai ghép ──
 2:  NẾU Random() > p_c THÌ
 3:      TRẢ VỀ Copy(parent1), Copy(parent2)     ▷ Không lai ghép

 4:  ── Kiểm tra cùng grid group ──
 5:  grid1 ← Int(parent1["_grid_idx"])
 6:  grid2 ← Int(parent2["_grid_idx"])
 7:  NẾU grid1 ≠ grid2 THÌ
 8:      TRẢ VỀ Copy(parent1), Copy(parent2)     ▷ Khác grid → không lai ghép

 9:  param_bounds ← grid_encodings[grid1].param_bounds
10:  param_types ← grid_encodings[grid1].param_types

     ── Chế độ lai ghép đơn giản (simple crossover) ──
11:  NẾU simple_crossover = true THÌ
12:      child1 ← Copy(parent1); child2 ← Copy(parent2)
13:      params ← [p cho p ∈ Keys(parent1) nếu p ≠ "_grid_idx"]
14:      NẾU |params| > 1 THÌ
15:          swap_point ← |params| ÷ 2
16:          VỚI MỖI param ∈ params[:swap_point]:
17:              Hoán đổi child1[param] ↔ child2[param]
18:      TRẢ VỀ child1, child2

     ── Lai ghép BLX-α đầy đủ ──
19:  child1 ← Copy(parent1); child2 ← Copy(parent2)

20:  VỚI MỖI param_name ∈ Keys(parent1):
21:      NẾU param_name = "_grid_idx" THÌ TIẾP TỤC
22:      NẾU param_name ∉ param_types THÌ TIẾP TỤC
23:
24:      (type, values) ← param_types[param_name]
25:
26:      NẾU type = "categorical" THÌ
27:          ── Hoán đổi ngẫu nhiên với xác suất 0.5 ──
28:          NẾU Random() < 0.5 THÌ
29:              Hoán đổi child1[param_name] ↔ child2[param_name]
30:
31:      NGƯỢC LẠI                                ▷ continuous hoặc integer
32:          ── BLX-α: mở rộng miền tìm kiếm ──
33:          p₁ ← Min(parent1[param_name], parent2[param_name])
34:          p₂ ← Max(parent1[param_name], parent2[param_name])
35:          I ← p₂ − p₁
36:
37:          lower ← Max(p₁ − α × I, param_bounds[param_name].min)
38:          upper ← Min(p₂ + α × I, param_bounds[param_name].max)
39:
40:          child1[param_name] ← RandomUniform(lower, upper)
41:          child2[param_name] ← RandomUniform(lower, upper)

42:  TRẢ VỀ child1, child2
```

**Thuật toán 2.4.8. Đột biến Gaussian thích nghi**

```
Thuật toán: AdaptiveMutate
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: individual (cá thể), g (thế hệ hiện tại),
         G (tổng số thế hệ), p_m (tỷ lệ đột biến cơ sở),
         grid_encodings
Đầu ra:  mutated (cá thể đã đột biến)

 1:  mutated ← Copy(individual)
 2:  grid_idx ← Int(individual["_grid_idx"])
 3:  param_bounds ← grid_encodings[grid_idx].param_bounds
 4:  param_types ← grid_encodings[grid_idx].param_types

     ── Tỷ lệ đột biến thích nghi: giảm dần theo thế hệ ──
 5:  NẾU G > 0 THÌ
 6:      adaptive_rate ← p_m × (1 − g / G)
 7:  NGƯỢC LẠI
 8:      adaptive_rate ← p_m

 9:  VỚI MỖI param_name ∈ Keys(mutated):
10:      NẾU param_name = "_grid_idx" THÌ TIẾP TỤC
11:      NẾU param_name ∉ param_bounds THÌ TIẾP TỤC

12:      NẾU Random() < adaptive_rate THÌ
13:          (min_val, max_val) ← param_bounds[param_name]
14:          (type, values) ← param_types[param_name]
15:          current ← mutated[param_name]

16:          NẾU type = "categorical" THÌ
17:              ── Thay thế bằng giá trị khác ngẫu nhiên ──
18:              possible ← [0, 1, ..., max_val] \ {Round(current)}
19:              NẾU |possible| > 0 THÌ
20:                  mutated[param_name] ← Float(RandomChoice(possible))

21:          NGƯỢC LẠI                            ▷ continuous hoặc integer
22:              ── Gaussian mutation: cường độ giảm thích nghi ──
23:              σ ← (max_val − min_val) × 0.2 × (1 − g / (G + 1))
24:              new_val ← current + Gaussian(0, σ)
25:              mutated[param_name] ← Clip(new_val, min_val, max_val)

26:  TRẢ VỀ mutated
```

**Thuật toán 2.4.9. Tính độ đa dạng quần thể — Variance-based O(n)**

```
Thuật toán: CalculateDiversityFast
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: population, grid_encodings, num_grids
Đầu ra:  d (diversity, 0–1)

 1:  NẾU |population| < 2 THÌ TRẢ VỀ 0.0

     ── Nhóm cá thể theo grid ──
 2:  grid_groups ← {}
 3:  VỚI MỖI ind ∈ population:
 4:      grid_idx ← Int(ind["_grid_idx"])
 5:      grid_groups[grid_idx].append(ind)

 6:  total_diversity ← 0.0; total_weight ← 0

 7:  VỚI MỖI (grid_idx, group) ∈ grid_groups:
 8:      NẾU |group| < 2 THÌ TIẾP TỤC
 9:      param_bounds ← grid_encodings[grid_idx].param_bounds
10:      param_types ← grid_encodings[grid_idx].param_types

11:      param_divs ← []
12:      VỚI MỖI param_name ∈ Keys(param_bounds):
13:          values ← [ind[param_name] cho ind ∈ group]
14:          (type, _) ← param_types[param_name]

15:          NẾU type = "categorical" THÌ
16:              ── Tỷ lệ giá trị unique ──
17:              div ← |Set(values)| / |values|

18:          NGƯỢC LẠI                            ▷ continuous/integer
19:              ── Normalized variance ──
20:              (min_v, max_v) ← param_bounds[param_name]
21:              NẾU max_v ≠ min_v THÌ
22:                  norm_vals ← [(v − min_v)/(max_v − min_v) cho v ∈ values]
23:                  div ← Min(1.0, 4 × Variance(norm_vals))
24:              NGƯỢC LẠI
25:                  div ← 0.0

26:          param_divs.append(div)

27:      NẾU |param_divs| > 0 THÌ
28:          group_div ← Mean(param_divs)
29:          total_diversity ← total_diversity + group_div × |group|
30:          total_weight ← total_weight + |group|

     ── Bổ sung diversity từ việc có nhiều grids ──
31:  NẾU |grid_groups| > 1 THÌ
32:      grid_div ← |grid_groups| / num_grids
33:      weighted_div ← total_diversity / total_weight nếu total_weight > 0
34:      d ← weighted_div × 0.7 + grid_div × 0.3
35:  NGƯỢC LẠI NẾU total_weight > 0 THÌ
36:      d ← total_diversity / total_weight
37:  NGƯỢC LẠI
38:      d ← 0.0

39:  TRẢ VỀ d
```

**Thuật toán 2.4.10. Tính độ đa dạng quần thể — Pairwise O(n²)**

```
Thuật toán: CalculateDiversityPairwise
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: population, grid_encodings
Đầu ra:  d (diversity, 0–1)

 1:  NẾU |population| < 2 THÌ TRẢ VỀ 0.0

 2:  total_distance ← 0; count ← 0

 3:  VỚI i = 0 ĐẾN |population| − 2:
 4:    VỚI j = i + 1 ĐẾN |population| − 1:
 5:      grid_i ← Int(population[i]["_grid_idx"])
 6:      grid_j ← Int(population[j]["_grid_idx"])

 7:      NẾU grid_i ≠ grid_j THÌ
 8:          distance ← 1.0                      ▷ Khác grid = khoảng cách tối đa
 9:      NGƯỢC LẠI
10:          param_bounds ← grid_encodings[grid_i].param_bounds
11:          param_types ← grid_encodings[grid_i].param_types
12:          distance ← 0; param_count ← 0

13:          VỚI MỖI param_name ∈ Keys(population[i]):
14:              NẾU param_name = "_grid_idx" THÌ TIẾP TỤC
15:              NẾU param_name ∉ param_types THÌ TIẾP TỤC
16:              param_count ← param_count + 1
17:              (type, _) ← param_types[param_name]

18:              NẾU type = "categorical" THÌ
19:                  distance ← distance + (0 nếu pop[i][p] = pop[j][p], 1 nếu không)
20:              NGƯỢC LẠI
21:                  (min_v, max_v) ← param_bounds[param_name]
22:                  NẾU max_v ≠ min_v THÌ
23:                      distance ← distance + |pop[i][p] − pop[j][p]| / (max_v − min_v)

24:          NẾU param_count > 0 THÌ
25:              distance ← distance / param_count

26:      total_distance ← total_distance + distance
27:      count ← count + 1

28:  TRẢ VỀ total_distance / count nếu count > 0, 0.0 nếu không
```

**Thuật toán 2.4.11. Tính diversity tự động (auto-switch)**

```
Thuật toán: CalculateDiversity
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: population, grid_encodings, num_grids, fast_diversity
Đầu ra:  d (diversity)

 1:  NẾU |population| < 2 THÌ TRẢ VỀ 0.0

 2:  ── Tự động chọn phương pháp dựa trên kích thước quần thể ──
 3:  NẾU fast_diversity = true VÀ |population| ≥ 20 THÌ
 4:      TRẢ VỀ CalculateDiversityFast(population, ...)     ▷ O(n)
 5:  NGƯỢC LẠI
 6:      TRẢ VỀ CalculateDiversityPairwise(population, ...) ▷ O(n²)
```

**Thuật toán 2.4.12. Tiêm đa dạng khi quần thể trì trệ**

```
Thuật toán: InjectDiversity
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: population, injection_rate (mặc định = 0.2)
Đầu ra:  new_population (quần thể đã tiêm đa dạng)

 1:  num_inject ← Int(|population| × injection_rate)
 2:  NẾU num_inject = 0 THÌ TRẢ VỀ population

 3:  new_population ← Copy(population)

     ── Chọn ngẫu nhiên các vị trí để thay thế ──
 4:  indices ← RandomSample(Range(|population|), num_inject)

 5:  VỚI MỖI idx ∈ indices:
 6:      new_population[idx] ← CreateIndividual(None, ...)

 7:  TRẢ VỀ new_population
```

**Thuật toán 2.4.13. Tạo thế hệ tiếp theo**

```
Thuật toán: CreateNextGeneration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: population, fitness_scores, d (diversity),
         g (thế hệ hiện tại), P (kích thước quần thể mục tiêu),
         e (elite size), p_c (crossover rate), p_m (mutation rate),
         G (tổng số thế hệ), grid_encodings
Đầu ra:  new_population

 1:  new_population ← []

     ── Elitism: giữ lại e cá thể tốt nhất ──
 2:  NẾU e > 0 THÌ
 3:      elite_indices ← TopK(fitness_scores, e)
 4:      VỚI MỖI idx ∈ elite_indices:
 5:          new_population.append(Copy(population[idx]))

     ── Tỷ lệ lai ghép thích ứng ──
 6:  adaptive_p_c ← p_c
 7:  NẾU d < 0.1 THÌ
 8:      adaptive_p_c ← Min(1.0, p_c × 1.2)     ▷ Tăng 20% khi diversity thấp

     ── Điền phần còn lại bằng selection + crossover + mutation ──
 9:  TRONG KHI |new_population| < P:
10:      p₁ ← TournamentSelection(population, fitness_scores, d, ...)
11:      p₂ ← TournamentSelection(population, fitness_scores, d, ...)
12:      c₁, c₂ ← BLXαCrossover(p₁, p₂, adaptive_p_c, α, ...)
13:      c₁ ← AdaptiveMutate(c₁, g, G, p_m, ...)
14:      c₂ ← AdaptiveMutate(c₂, g, G, p_m, ...)
15:      NẾU |new_population| < P THÌ new_population.append(c₁)
16:      NẾU |new_population| < P THÌ new_population.append(c₂)

17:  TRẢ VỀ new_population
```

**Thuật toán 2.4.14. Đánh giá quần thể song song**

```
Thuật toán: EvaluatePopulationParallel
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: population, M (mô hình), D = (X, y), n_jobs, cv
Đầu ra:  results (danh sách dict scores cho mỗi cá thể)

 1:  ── Tuần tự nếu n_jobs = 1 ──
 2:  NẾU n_jobs = 1 THÌ
 3:      results ← []
 4:      VỚI MỖI ind ∈ population:
 5:          results.append(EvaluateIndividual(ind, M, X, y, ...))
 6:      TRẢ VỀ results

 7:  ── Tính tổng đơn vị công việc ──
 8:  cv_folds ← cv.n_splits
 9:  NẾU n_jobs = -1 THÌ n_jobs ← CPU_COUNT()
10:  total_work ← |population| × cv_folds

     ── Song song nếu có đủ workload ──
11:  NẾU total_work ≥ n_jobs × 2 VÀ |population| > 4 THÌ
12:      optimal_jobs ← Min(n_jobs, |population|)
13:      backend ← "threading" nếu cv_folds ≤ 3, "loky" nếu không
14:
15:      results ← Parallel(optimal_jobs, backend)(
16:          VỚI MỖI ind ∈ population:
17:              EvaluateIndividual(ind, DeepCopy(M), X, y, ...)
18:      )
19:      TRẢ VỀ results

     ── Tuần tự cho quần thể nhỏ ──
20:  results ← []
21:  VỚI MỖI ind ∈ population:
22:      results.append(EvaluateIndividual(ind, M, X, y, ...))
23:  TRẢ VỀ results
```

### Thuật toán chính

**Mã giả 2.4. Genetic Algorithm cho tối ưu hóa siêu tham số trong HAutoML**

```
Thuật toán: Genetic Algorithm cho tối ưu hóa siêu tham số
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Đầu vào: Mô hình M, lưới tham số Θ, dữ liệu D = (X, y),
         P (kích thước quần thể), G (số thế hệ),
         p_m (tỷ lệ đột biến), p_c (tỷ lệ lai ghép), e (elite size),
         k_t (tournament size), α (BLX-α, mặc định = 0.5),
         scoring, metric_sort,
         max_time (tùy chọn), random_state,
         early_stopping_enabled, early_stopping_patience,
         convergence_threshold,
         adaptive_population, adaptive_tournament_size,
         fast_mode, ultra_fast_mode, fast_diversity,
         simple_crossover, skip_diversity_check,
         use_global_cache, max_cache_size,
         min_population, max_population
Đầu ra:  θ* (tham số tốt nhất), s* (điểm số tốt nhất),
         all_scores* (tất cả metric), cv_results_,
         time_limit_reached

     ═══════════════════════════════════════════
     GIAI ĐOẠN 1: KHỞI TẠO
     ═══════════════════════════════════════════

     ── Khởi tạo timer và seed ──
 1:  StartTimer()
 2:  NẾU random_state ≠ None THÌ
 3:      SetSeed(random_state)

     ── Xác thực cấu hình ──
 4:  NẾU P < 2 THÌ BÁO LỖI "Population size phải ≥ 2"
 5:  NẾU e ≥ P THÌ e ← Max(1, P ÷ 4)

     ── Mã hóa lưới tham số ──
 6:  grid_encodings, num_grids ← EncodeParameters(Θ)

     ── Tính tổng tổ hợp cho không gian categorical nhỏ ──
 7:  total_combos ← 0; is_all_categorical ← true
 8:  VỚI MỖI grid ∈ param_grid_list:
 9:      NẾU grid = ∅ THÌ total_combos ← total_combos + 1; TIẾP TỤC
10:      grid_combos ← 1
11:      VỚI MỖI (name, values) ∈ grid:
12:          NẾU values là list THÌ
13:              grid_combos ← grid_combos × |values|
14:          NGƯỢC LẠI
15:              is_all_categorical ← false; DỪNG
16:      NẾU is_all_categorical THÌ
17:          total_combos ← total_combos + grid_combos

     ── Điều chỉnh kích thước quần thể thích ứng ──
18:  NẾU adaptive_population = true VÀ fast_mode = true THÌ
19:      param_space_size ← 1
20:      VỚI MỖI (name, (min, max)) ∈ param_bounds:
21:          (type, values) ← param_types[name]
22:          NẾU type = "categorical" THÌ
23:              param_space_size ← param_space_size × (max − min + 1)
24:          NGƯỢC LẠI
25:              param_space_size ← param_space_size × 10
26:      P_actual ← Min(max_population,
27:                      Max(min_population, Int(Ln(param_space_size) × 2)))
28:      P_actual ← Min(P_actual, P)
29:  NGƯỢC LẠI
30:      P_actual ← P

     ── Tự động điều chỉnh cho không gian categorical nhỏ ──
31:  NẾU is_all_categorical VÀ total_combos ≤ 100 THÌ
32:      min_evals ← total_combos × 2            ▷ Ít nhất 2× coverage
33:      current_total ← P_actual × G
34:      NẾU current_total < min_evals THÌ
35:          P_actual ← Max(P_actual, Min(total_combos, 30))
36:          G ← Max(G, (min_evals ÷ P_actual) + 1)

     ── Khởi tạo quần thể ──
37:  NẾU ultra_fast_mode = true THÌ
38:      Pop₀ ← [CreateIndividual(None) cho i = 1 đến P_actual]
39:  NGƯỢC LẠI
40:      Pop₀ ← SmartInitialization(P_actual, num_grids, grid_encodings)

     ── Khởi tạo tracking ──
41:  s* ← −∞;  θ*_ind ← None; all_scores* ← None
42:  patience ← 0; best_generation ← 0
43:  convergence_history ← []; diversity_history ← []
44:  all_individuals ← []; all_scores ← []; all_metric_scores ← []
45:  eval_cache ← {}; decode_cache ← {}
46:  cache_hits ← 0; total_evaluations ← 0

     ═══════════════════════════════════════════
     GIAI ĐOẠN 2: VÒNG LẶP TIẾN HÓA
     ═══════════════════════════════════════════

47:  VỚI g = 0 ĐẾN G − 1:

         ── 2a. Kiểm tra time limit proactive (EMA) ──
48:      NẾU ShouldStartNextIteration(None, ...) = false THÌ
49:          DỪNG vòng lặp

50:      t_gen_start ← Time()

         ── 2b. Tính đa dạng quần thể ──
51:      NẾU skip_diversity_check = false THÌ
52:          d ← CalculateDiversity(Pop_g, grid_encodings,
53:                                  num_grids, fast_diversity)
54:      NGƯỢC LẠI
55:          d ← 1.0                              ▷ Giá trị giả cho ultra_fast

56:      diversity_history.append(d)

         ── 2c. Đánh giá fitness quần thể ──
57:      NẾU ultra_fast_mode VÀ g > 0 THÌ
58:          ── Chỉ đánh giá cá thể mới, dùng cache cho elite ──
59:          scores_list ← []
60:          VỚI MỖI (idx, ind) ∈ Enumerate(Pop_g):
61:              NẾU idx < e VÀ MakeHashable(ind) ∈ eval_cache THÌ
62:                  scores_list.append(eval_cache[MakeHashable(ind)])
63:              NGƯỢC LẠI
64:                  scores_list.append(EvaluateIndividual(ind, M, X, y, ...))
65:      NGƯỢC LẠI
66:          scores_list ← EvaluatePopulationParallel(Pop_g, M, D, ...)

         ── 2d. Trích xuất fitness và cập nhật best ──
67:      primary_metric ← metric_sort
68:      fitness ← Array(|Pop_g|)                 ▷ Numpy array
69:      gen_best_score ← −∞
70:      gen_improved ← false

71:      VỚI MỖI (idx, (ind, scores)) ∈ Enumerate(Zip(Pop_g, scores_list)):
72:          score ← scores[primary_metric]
73:          fitness[idx] ← score

74:          ── Ghi vào lịch sử ──
75:          all_individuals.append(DecodeIndividual(ind, ...))
76:          all_scores.append(score)
77:          all_metric_scores.append(Copy(scores))

78:          ── Theo dõi best thế hệ ──
79:          NẾU score ≥ gen_best_score THÌ
80:              gen_best_score ← score

81:          ── Cập nhật best toàn cục ──
82:          NẾU score ≥ s* THÌ
83:              s* ← score
84:              θ*_ind ← DeepCopy(ind)
85:              all_scores* ← Copy(scores)
86:              best_generation ← g
87:              gen_improved ← true
88:              patience ← 0

         ── 2e. Theo dõi hội tụ ──
89:      mean_fit ← Mean(fitness); std_fit ← Std(fitness)
90:      convergence_history.append({
91:          generation: g+1, best: s*,
92:          mean: mean_fit, std: std_fit, diversity: d
93:      })

94:      t_gen ← Time() − t_gen_start
95:      ── Cập nhật EMA ──
96:      ShouldStartNextIteration(t_gen, ...)

         ── 2f. Cập nhật patience ──
97:      NẾU gen_improved = false THÌ
98:          patience ← patience + 1

         ── 2g. Kiểm tra hội tụ (chỉ khi không có time limit) ──
99:      NẾU max_time = None VÀ g > 0 VÀ |convergence_history| > 1 THÌ
100:         improvement ← convergence_history[−1].best − convergence_history[−2].best
101:         NẾU |improvement| < convergence_threshold VÀ patience ≥ 2 THÌ
102:             DỪNG vòng lặp                    ▷ Hội tụ

         ── 2h. Kiểm tra early stopping (chỉ khi không có time limit) ──
103:     NẾU max_time = None VÀ early_stopping_enabled
104:         VÀ patience ≥ early_stopping_patience THÌ
105:         DỪNG vòng lặp                        ▷ Early stopping

         ── 2i. Kiểm tra trì trệ và tiêm đa dạng ──
106:     NẾU ultra_fast_mode = false THÌ
107:         NẾU d < 0.05 VÀ patience ≥ 3 THÌ
108:             Pop_g ← InjectDiversity(Pop_g, injection_rate=0.2)

         ── 2j. Tạo thế hệ tiếp theo ──
109:     Pop_{g+1} ← CreateNextGeneration(
110:         Pop_g, fitness, d, g, P_actual,
111:         e, p_c, p_m, G, grid_encodings
112:     )

     ═══════════════════════════════════════════
     GIAI ĐOẠN 3: TỔNG HỢP KẾT QUẢ
     ═══════════════════════════════════════════

     ── Giải mã cá thể tốt nhất ──
113: θ* ← DecodeIndividual(θ*_ind, ...) nếu θ*_ind ≠ None, ∅ nếu không

     ── Xây dựng cv_results_ ──
114: cv_results_ ← {
115:     params: all_individuals,
116:     mean_test_score: all_scores,
117:     std_test_score: [0.0] × |all_scores|,
118:     rank_test_score: ComputeRanks(all_scores),
119:     convergence_history: convergence_history,
120:     diversity_history: diversity_history,
121:     best_generation: best_generation + 1,
122:     total_evaluations: |all_individuals|
123: }

     ── Thêm mean/std/rank cho mỗi metric ──
124: VỚI MỖI metric_name ∈ Keys(all_metric_scores[0]):
125:     metric_list ← [s[metric_name] cho s ∈ all_metric_scores]
126:     cv_results_["mean_test_" + metric_name] ← metric_list
127:     cv_results_["std_test_" + metric_name] ← [0.0] × |metric_list|
128:     cv_results_["rank_test_" + metric_name] ← ComputeRanks(metric_list)

     ── Xóa cache và chuyển đổi kiểu numpy ──
129: Xóa eval_cache, decode_cache, model_copies
130: Chuyển đổi tất cả kiểu numpy → Python gốc

131: TRẢ VỀ θ*, s*, all_scores*, cv_results_, time_limit_reached
```

Trong mã giả trên, quy trình khởi tạo (Giai đoạn 1, dòng 1–46) bao gồm các bước: xác thực cấu hình (dòng 4–5), mã hóa tham số thông qua `EncodeParameters` (Thuật toán 2.4.1, dòng 6), **tự động điều chỉnh kích thước quần thể** dựa trên độ phức tạp không gian tham số (dòng 18–30), và **đặc biệt xử lý không gian categorical nhỏ** bằng cách tăng coverage để GA có thể duyệt đủ không gian (dòng 31–36). Quần thể được khởi tạo bằng `SmartInitialization` (Thuật toán 2.4.4) — phân bổ đều cá thể cho mỗi grid con.

Vòng lặp tiến hóa (Giai đoạn 2, dòng 47–112) thực hiện các pha chính trong mỗi thế hệ:
- **Kiểm tra time limit proactive** bằng EMA (dòng 48–49, sử dụng Thuật toán 2.1.6)
- **Tính đa dạng quần thể** tự động chọn O(n) hoặc O(n²) (dòng 51–55, Thuật toán 2.4.11)
- **Đánh giá fitness** với tối ưu hóa ultra_fast_mode (dòng 57–66, Thuật toán 2.4.14)
- **Kiểm tra hội tụ** và **early stopping** — chỉ khi không có time limit (dòng 99–105)
- **Tiêm đa dạng** khi quần thể trì trệ (dòng 106–108, Thuật toán 2.4.12)
- **Tạo thế hệ mới** thông qua elitism, chọn lọc đấu trường thích ứng, lai ghép BLX-α, và đột biến Gaussian (dòng 109–112, Thuật toán 2.4.13)

Đặc biệt, cơ chế **chọn lọc đấu trường thích ứng** (Thuật toán 2.4.6) tự động điều chỉnh kích thước tournament dựa trên diversity: giảm khi d < 0.1 để tăng khám phá, tăng khi d > 0.5 để tăng khai thác. Toán tử **lai ghép BLX-α** (Thuật toán 2.4.7) mở rộng miền tìm kiếm ra ngoài khoảng giữa hai bố mẹ cho tham số liên tục, đồng thời sử dụng hoán đổi ngẫu nhiên cho tham số categorical. Toán tử **đột biến Gaussian thích nghi** (Thuật toán 2.4.8) giảm dần cả tỷ lệ và cường độ đột biến theo thế hệ, chuyển từ khám phá toàn cục sang tinh chỉnh cục bộ.

---

## 2.2.2.5. Đối chiếu và so sánh các kỹ thuật

Các kỹ nghệ tối ưu bao gồm Grid Search, Random Search, Bayesian Optimization và Genetic Algorithm đại diện cho bốn phân tầng chiến lược với năng lực khai phá không gian khác biệt. Trong khi Grid Search vận hành dựa trên nguyên lý duyệt vét cạn toàn diện nhưng tiêu tốn tài nguyên đáng kể, Random Search tối ưu hóa chi phí điện toán thông qua cơ chế lấy mẫu xác suất linh hoạt. Đối với các bài toán đòi hỏi tính hiệu quả chuyên sâu, Bayesian Optimization thiết lập một mô hình xấp xỉ nhằm khai thác tri thức từ lịch sử đánh giá, trong khi Genetic Algorithm mô phỏng quá trình tiến hóa tự nhiên với khả năng thoát tối ưu cục bộ vượt trội [37], [38], [39], [41].

| Phương pháp | Cơ chế xác lập cấu hình | Ưu điểm hệ thống | Hạn chế kỹ thuật | Khả năng ứng dụng Project |
|---|---|---|---|---|
| Grid Search | Quét tuyến tính toàn bộ mạng lưới tổ hợp | Tính minh bạch cao, dễ tái lập kết quả | Bùng nổ chi phí theo quy mô tham số | Tích hợp sẵn batch, cache và song song |
| Random Search | Lấy mẫu xác suất ngẫu nhiên không gian | Hiệu quả với không gian đa chiều lớn | Thiếu khả năng kế thừa tri thức lịch sử | Sử dụng như một baseline đối chứng |
| Bayesian Optimization | Sử dụng surrogate model và hàm lợi ích | Tối ưu cho các tác vụ huấn luyện tốn kém | Phụ thuộc vào cấu trúc mô hình xấp xỉ | Triển khai qua gp_minimize, hỗ trợ dừng sớm |
| Genetic Algorithm | Tiến hóa: Selection, Crossover, Mutation | Thoát local optima tốt, không gian phức tạp | Chi phí quần thể lớn, hội tụ trung bình | Smart init, adaptive operators, diversity injection |

*Bảng 2.1. Đối chiếu các chiến lược tối ưu hóa siêu tham số*

Xét trong hệ sinh thái HAutoML, mỗi chiến lược tối ưu hóa được định vị cho một phân khúc bài toán riêng biệt. Grid Search đóng vai trò là giải pháp ưu tiên cho các kịch bản yêu cầu tính kiểm chứng cao với không gian tham số tinh gọn, nơi tính minh bạch và khả năng tái lập kết quả được đặt lên hàng đầu. Bayesian Optimization khẳng định ưu thế vượt trội khi ngân sách thực nghiệm bị giới hạn bởi thời hạn hoặc chi phí điện toán vật lý, nhờ khả năng khai thác tri thức tích lũy từ lịch sử đánh giá để định hướng xác lập cấu hình tiếp theo một cách thông minh. Genetic Algorithm phù hợp nhất với các không gian tham số phức tạp, đa chiều, nơi nhiều cực trị cục bộ tồn tại và cần cơ chế khám phá toàn cục mạnh mẽ thông qua các toán tử tiến hóa thích nghi. Sự kết hợp bổ trợ giữa ba chiến lược này cho phép hệ thống HAutoML linh hoạt thích ứng với đa dạng các kịch bản thực nghiệm, từ các bài toán đơn giản với vài siêu tham số rời rạc đến các bài toán phức tạp với không gian tìm kiếm hỗn hợp liên tục–rời rạc [37], [38], [39], [41].
