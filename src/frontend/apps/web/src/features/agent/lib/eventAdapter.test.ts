/**
 * Test cho lớp ánh xạ sự kiện -> trạng thái hiển thị. Sự kiện ở đây chép theo
 * payload thật của agent server (team.py, agent_openai.py, watcher.py).
 *
 * Chạy: npm run test:agent (ở src/frontend). Dùng node:test, không cần thêm
 * thư viện test.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  applyJobEvent,
  applyTurnEvent,
  applyWatchState,
  createSeqTracker,
  currentActivity,
  emptyTrace,
  groupConfigErrors,
  markJobsLost,
  mergeJobFromApi,
  type JobView,
  type TurnTrace,
} from "./eventAdapter";
import type { AgentEvent } from "./events";
import { ORPHAN_MAX_WAIT_MS, ORPHAN_UNCONFIRMED_MS, OrphanTurns } from "./orphanTurns";
import { coerceFeature, featureKinds, shortBackendError, stepUnit, timeSeriesHint } from "./predict";

function run(events: AgentEvent[]) {
  let trace: TurnTrace = emptyTrace();
  let jobs: Record<string, JobView> = {};
  for (const event of events) {
    trace = applyTurnEvent(trace, event);
    jobs = applyJobEvent(jobs, event);
  }
  return { trace, jobs };
}

const TRAINING_TURN: AgentEvent[] = [
  { seq: 1, type: "turn_start", agent: "manager", time: 100 },
  { seq: 2, type: "agent_start", agent: "prompt-agent", task: "Hiểu yêu cầu", time: 101 },
  { seq: 3, type: "agent_done", agent: "prompt-agent", ok: true, missing: [], time: 103 },
  { seq: 4, type: "agent_start", agent: "data-agent", task: "Kiểm tra dữ liệu", time: 104 },
  { seq: 5, type: "tool_start", agent: "data-agent", name: "get_dataset_schema", arguments: { dataset_id: "ds1" }, time: 104 },
  { seq: 6, type: "tool_call", agent: "data-agent", name: "get_dataset_schema", arguments: { dataset_id: "ds1" }, ok: true, time: 105 },
  { seq: 7, type: "agent_done", agent: "data-agent", ok: true, time: 106 },
  { seq: 8, type: "agent_start", agent: "model-agent", task: "Tạo cấu hình", time: 107 },
  { seq: 9, type: "config_checked", agent: "model-agent", ok: false, errors: ["Cột mục tiêu 'x' không có trong dataset."], time: 108 },
  { seq: 10, type: "config_checked", agent: "model-agent", ok: true, errors: [], time: 109 },
  { seq: 11, type: "agent_done", agent: "model-agent", ok: true, time: 110 },
  { seq: 12, type: "agent_start", agent: "operation-agent", task: "Khởi chạy", time: 111 },
  {
    seq: 13,
    type: "job_started",
    agent: "operation-agent",
    job_id: "J1",
    config_id: "cfg_1",
    config: { problem_type: "classification", target: "churn", metric_sort: "f1", list_feature: ["a", "b"] },
    time: 112,
  },
  { seq: 14, type: "agent_done", agent: "operation-agent", ok: true, time: 113 },
  { seq: 15, type: "turn_done", agent: "manager", total_tokens: 1234, time: 114 },
];

test("lượt huấn luyện: timeline tuyến tính theo đúng các agent đã chạy", () => {
  const { trace } = run(TRAINING_TURN);
  assert.deepEqual(
    trace.steps.map((s) => [s.kind, s.agent, s.status]),
    [
      ["agent", "prompt-agent", "success"],
      ["agent", "data-agent", "success"],
      ["agent", "model-agent", "success"],
      ["validation", "model-agent", "failed"],
      ["validation", "model-agent", "success"],
      ["agent", "operation-agent", "success"],
    ],
  );
  assert.equal(trace.datasetId, "ds1");
  assert.deepEqual(trace.jobIds, ["J1"]);
});

test("kiểm định lỗi không thành thành công và không có config_id", () => {
  const { trace } = run(TRAINING_TURN);
  const [invalid, valid] = trace.configs;
  assert.equal(invalid.valid, false);
  assert.equal(invalid.configId, undefined);
  assert.equal(invalid.jobId, undefined);
  assert.equal(valid.valid, true);
  assert.equal(valid.configId, "cfg_1");
  assert.equal(valid.jobId, "J1");
  assert.equal(valid.datasetId, "ds1");
});

test("config hợp lệ có nội dung ngay cả khi chưa chạy được job, job gắn đúng config_id", () => {
  const config = { problem_type: "regression", target: "load", metric_sort: "rmse", list_feature: ["date"] };
  const { trace } = run([
    { seq: 1, type: "turn_start", agent: "agent-manager", time: 1 },
    { seq: 2, type: "config_checked", agent: "model-agent", ok: true, errors: [], config_id: "cfg_a", config, time: 2 },
    { seq: 3, type: "config_checked", agent: "model-agent", ok: true, errors: [], config_id: "cfg_b", config, time: 3 },
  ]);
  assert.equal(trace.configs[0].configId, "cfg_a");
  assert.equal(trace.configs[0].config?.target, "load");
  assert.equal(trace.configs[0].jobId, undefined);

  // Job của config cũ hơn (cfg_a) gắn đúng vào cfg_a, không vào config hợp lệ gần nhất.
  const after = applyTurnEvent(trace, { seq: 4, type: "job_started", agent: "operation-agent", job_id: "J9", config_id: "cfg_a", config, time: 4 });
  assert.equal(after.configs[0].jobId, "J9");
  assert.equal(after.configs[1].jobId, undefined);
});

test("start_training xong chỉ là 'đã gửi', không phải 'hoàn tất'", () => {
  const { jobs } = run(TRAINING_TURN);
  assert.equal(jobs.J1.status, "submitted");
  assert.equal(jobs.J1.metric, "f1");
});

test("Prompt Agent thiếu thông tin -> needs_input, không có job", () => {
  const { trace, jobs } = run([
    { seq: 1, type: "agent_start", agent: "prompt-agent", task: "x", time: 1 },
    { seq: 2, type: "agent_done", agent: "prompt-agent", ok: true, missing: "Bạn muốn dự đoán cột nào?", time: 2 },
  ]);
  assert.equal(trace.steps[0].status, "needs_input");
  assert.deepEqual(trace.steps[0].missing, ["Bạn muốn dự đoán cột nào?"]);
  assert.deepEqual(trace.jobIds, []);
  assert.deepEqual(jobs, {});
});

test("câu hỏi đơn giản không sinh bước huấn luyện giả", () => {
  const { trace } = run([
    { seq: 1, type: "turn_start", agent: "manager", time: 1 },
    { seq: 2, type: "llm_call", agent: "manager", total_tokens: 10, time: 2 },
    { seq: 3, type: "turn_done", agent: "manager", time: 3 },
  ]);
  assert.deepEqual(trace.steps, []);
  assert.deepEqual(trace.configs, []);
});

test("vòng đời job: submitted -> running -> completed, sự kiện muộn không kéo lùi", () => {
  const { jobs } = run([
    ...TRAINING_TURN,
    { seq: 16, type: "job_status", agent: "operation-agent", job_id: "J1", status: 0, elapsed: 5, time: 120 },
    { seq: 17, type: "job_status", agent: "operation-agent", job_id: "J1", status: 1, elapsed: 300, time: 400 },
    {
      seq: 18,
      type: "job_done",
      agent: "operation-agent",
      job_id: "J1",
      status: 1,
      dataset: "churn",
      metric_sort: "f1",
      best_model: "RF",
      best_score: 0.91,
      leaderboard: [
        { model: "RF", f1: 0.91 },
        { model: "LR", f1: 0.85 },
      ],
      models_scored: 2,
      time: 401,
    },
    { seq: 19, type: "job_status", agent: "operation-agent", job_id: "J1", status: 0, elapsed: 5, time: 402 },
  ]);
  const job = jobs.J1;
  assert.equal(job.status, "completed");
  assert.equal(job.bestModel, "RF");
  assert.equal(job.bestScore, 0.91);
  assert.deepEqual(job.leaderboard, [
    { model: "RF", score: 0.91 },
    { model: "LR", score: 0.85 },
  ]);
  assert.equal(job.elapsed, 300);
  assert.equal(job.finishedAt, 401_000);
});

test("job bị huỷ / lỗi / hết thời gian theo dõi", () => {
  const { jobs } = run([
    { seq: 1, type: "job_failed", job_id: "C", status: -2, error: "Job đã bị huỷ.", cancelled: true, time: 1 },
    { seq: 2, type: "job_failed", job_id: "F", status: -1, error: "OOM", time: 2 },
    { seq: 3, type: "job_watch_timeout", job_id: "T", status: 0, error: "Quá thời gian chờ", time: 3 },
    { seq: 4, type: "job_watch_warning", job_id: "W", error: "Phiên đăng nhập hết hạn", time: 4 },
  ]);
  assert.equal(jobs.C.status, "cancelled");
  assert.equal(jobs.F.status, "failed");
  assert.equal(jobs.F.error, "OOM");
  assert.equal(jobs.T.status, "unknown");
  assert.equal(jobs.W.warning, "Phiên đăng nhập hết hạn");
});

test("kết nối lại: sự kiện trùng seq chỉ được nhận một lần", () => {
  const tracker = createSeqTracker();
  const delivered = [1, 2, 3, 2, 3, 4, 1, 5].filter((seq) => tracker.accept(seq));
  assert.deepEqual(delivered, [1, 2, 3, 4, 5]);
  assert.equal(tracker.last, 5);
  assert.equal(tracker.accept(undefined), false);
  tracker.reset();
  assert.equal(tracker.last, 0);
  assert.equal(tracker.accept(1), true);
});

test("làm mới từ API: xếp hạng theo metric, sai số thì nhỏ hơn là tốt hơn", () => {
  const job = mergeJobFromApi(
    { jobId: "J", status: "running" },
    {
      _id: "J",
      status: 1,
      activate: 1,
      data: { id: "ds", name: "house" },
      config: { metric_sort: "rmse" },
      best_model: "XGB",
      best_score: 2.1,
      orther_model_scores: [
        { model_name: "LR", scores: { rmse: 3.5, mae: 2 } },
        { model_name: "XGB", scores: { rmse: 2.1, mae: 1.1 } },
      ],
    },
    1000,
  );
  assert.equal(job.status, "completed");
  assert.equal(job.source, "api");
  assert.equal(job.activated, true);
  assert.equal(job.dataset, "house");
  assert.deepEqual(job.leaderboard?.map((r) => r.model), ["XGB", "LR"]);
  assert.deepEqual(job.bestScores, { rmse: 2.1, mae: 1.1 });
  // API không cho biết thời điểm xong - không được bịa.
  assert.equal(job.finishedAt, undefined);
});

test("lỗi cấu hình được gắn đúng trường", () => {
  const groups = Object.fromEntries(
    groupConfigErrors([
      "Thiếu 'target'.",
      "Các cột đặc trưng không có trong dataset: x.",
      "Cột mục tiêu 'y' không được nằm trong list_feature - để nó vào là mô hình nhìn thấy đáp án.",
      "metric_sort 'abc' không hợp lệ cho classification.",
      "'max_time' quá nhỏ, tối thiểu 60 giây.",
      "problem_type 'z' không hợp lệ.",
      "Lỗi lạ",
    ]),
  );
  assert.equal(groups.target.length, 1);
  assert.equal(groups.features.length, 2);
  assert.equal(groups.metric.length, 1);
  assert.equal(groups.max_time.length, 1);
  assert.equal(groups.problem_type.length, 1);
  assert.equal(groups.general.length, 1);
});

test("'đang làm gì' lấy từ bước và tool đang chạy", () => {
  const { trace } = run([
    { seq: 1, type: "agent_start", agent: "data-agent", task: "x", time: 1 },
    { seq: 2, type: "tool_start", agent: "data-agent", name: "get_dataset_schema", arguments: {}, time: 2 },
  ]);
  assert.deepEqual(currentActivity(trace), { agent: "data-agent", tool: "get_dataset_schema" });
  assert.equal(currentActivity(emptyTrace()), null);
});

test("cảnh báo của validate_config được giữ trên thẻ cấu hình, kể cả sau khi job chạy", () => {
  const config = { problem_type: "time_series", target: "load", metric_sort: "rmse", list_feature: ["date", "temp"] };
  const { trace } = run([
    {
      seq: 1,
      type: "config_checked",
      agent: "model-agent",
      ok: true,
      errors: [],
      warnings: ["Khi dự báo phải biết trước giá trị tương lai của: temp."],
      config_id: "cfg_t",
      config,
      time: 1,
    },
    { seq: 2, type: "job_started", agent: "operation-agent", job_id: "JT", config_id: "cfg_t", config, time: 2 },
  ]);
  assert.deepEqual(trace.configs[0].warnings, ["Khi dự báo phải biết trước giá trị tương lai của: temp."]);
  assert.equal(trace.configs[0].jobId, "JT");
});

test("cảnh báo phiên hết hạn tự xoá khi watcher hỏi được backend trở lại", () => {
  const warned = run([
    { seq: 1, type: "job_started", job_id: "W", config: {}, time: 1 },
    { seq: 2, type: "job_watch_warning", job_id: "W", error: "Phiên đăng nhập hết hạn", time: 2 },
  ]).jobs;
  assert.equal(warned.W.warning, "Phiên đăng nhập hết hạn");
  const resumed = applyJobEvent(warned, { seq: 3, type: "job_watch_resumed", job_id: "W", time: 3 });
  assert.equal(resumed.W.warning, undefined);
  // job_status sau đó cũng xoá cảnh báo (vd cảnh báo tới lại rồi job đổi trạng thái).
  const again = applyJobEvent(warned, { seq: 4, type: "job_status", job_id: "W", status: 0, elapsed: 30, time: 4 });
  assert.equal(again.W.warning, undefined);
  assert.equal(again.W.status, "running");
});

test("job_done kèm kết quả tự kích hoạt model", () => {
  const ok = run([
    { seq: 1, type: "job_started", job_id: "A", config: { metric_sort: "accuracy" }, time: 1 },
    { seq: 2, type: "job_done", job_id: "A", status: 1, best_model: "RF", best_score: 0.9, activation: { ok: true, endpoint_url: "/x" }, time: 2 },
  ]).jobs;
  assert.equal(ok.A.status, "completed");
  assert.equal(ok.A.activated, true);
  assert.deepEqual(ok.A.activation, { ok: true, endpoint_url: "/x" });

  const failed = run([
    { seq: 1, type: "job_done", job_id: "B", status: 1, activation: { ok: false, error: "HTTP 500" }, time: 1 },
  ]).jobs;
  assert.equal(failed.B.activated, undefined);
  assert.equal(failed.B.activation?.error, "HTTP 500");

  // Không yêu cầu kích hoạt thì không có trường activation.
  const plain = run([{ seq: 1, type: "job_done", job_id: "C", status: 1, time: 1 }]).jobs;
  assert.equal(plain.C.activation, undefined);
});

test("job hết giờ chờ rồi được theo dõi lại thì sống lại và nhận kết quả", () => {
  const { jobs } = run([
    { seq: 1, type: "job_started", job_id: "R", config: {}, time: 1 },
    { seq: 2, type: "job_watch_timeout", job_id: "R", status: 0, error: "Quá thời gian chờ", time: 2 },
  ]);
  assert.equal(jobs.R.status, "unknown");
  // Sự kiện trạng thái lẻ của job đã kết thúc thật vẫn bị bỏ qua.
  const done = run([{ seq: 1, type: "job_done", job_id: "D", status: 1, time: 1 }]).jobs;
  assert.equal(applyJobEvent(done, { seq: 2, type: "job_status", job_id: "D", status: 0, time: 2 }), done);

  let next = applyJobEvent(jobs, { seq: 3, type: "job_watch", job_id: "R", time: 3 });
  assert.equal(next.R.status, "running");
  assert.equal(next.R.error, undefined);
  next = applyJobEvent(next, { seq: 4, type: "job_done", job_id: "R", status: 1, best_model: "LR", best_score: 0.8, time: 4 });
  assert.equal(next.R.status, "completed");
  assert.equal(next.R.bestModel, "LR");
});

test("mất phiên: job đang chạy được đánh dấu mất dấu, làm mới từ API thì hết", () => {
  const { jobs } = run([
    { seq: 1, type: "job_started", job_id: "L", config: {}, time: 1 },
    { seq: 2, type: "job_status", job_id: "L", status: 0, time: 2 },
    { seq: 3, type: "job_done", job_id: "K", status: 1, time: 3 },
  ]);
  const lost = markJobsLost(jobs);
  assert.equal(lost.L.status, "unknown");
  assert.equal(lost.L.lost, true);
  // Job đã xong không bị đụng tới.
  assert.equal(lost.K.status, "completed");
  assert.equal(lost.K.lost, undefined);
  // Không có job nào đang chạy thì giữ nguyên object.
  assert.equal(markJobsLost({ K: jobs.K }).K, jobs.K);

  const refreshed = mergeJobFromApi(lost.L, { _id: "L", status: 0, activate: 0 }, 5000);
  assert.equal(refreshed.status, "running");
  assert.equal(refreshed.lost, undefined);

  // Phiên mới theo dõi lại job cũ (watch_job): sống lại.
  const rewatched = applyJobEvent(lost, { seq: 1, type: "job_watch", job_id: "L", time: 9 });
  assert.equal(rewatched.L.status, "running");
  assert.equal(rewatched.L.lost, undefined);
});

test("job_started có config_id không khớp thẻ nào thì thêm thẻ mới, không ghi đè thẻ khác", () => {
  // Config A chốt ở lượt trước; lượt này chốt B rồi lại chạy A.
  const { trace, jobs } = run([
    { seq: 1, type: "tool_start", agent: "model-agent", name: "submit_config", arguments: { dataset_id: "ds-B" }, time: 1 },
    { seq: 2, type: "config_checked", ok: true, config_id: "cfg_B", config: { target: "b" }, warnings: ["wB"], time: 2 },
    { seq: 3, type: "job_started", job_id: "J", config_id: "cfg_A", dataset_id: "ds-A", config: { target: "a" }, time: 3 },
  ]);
  assert.equal(trace.configs.length, 2);
  const [b, a] = trace.configs;
  assert.equal(b.configId, "cfg_B");
  assert.equal(b.jobId, undefined);
  assert.deepEqual(b.warnings, ["wB"]);
  assert.equal(a.configId, "cfg_A");
  assert.equal(a.jobId, "J");
  assert.equal(a.datasetId, "ds-A");
  assert.equal(jobs.J.datasetId, "ds-A");

  // Sự kiện kiểu cũ (không config_id) vẫn gắn vào lần kiểm định hợp lệ gần nhất.
  const legacy = run([
    { seq: 1, type: "config_checked", ok: true, config_id: "cfg_X", config: {}, time: 1 },
    { seq: 2, type: "job_started", job_id: "K", config: {}, time: 2 },
  ]);
  assert.equal(legacy.trace.configs.length, 1);
  assert.equal(legacy.trace.configs[0].jobId, "K");
});

test("form dự đoán ép kiểu theo kiểu thật của cột lúc train", () => {
  const rows = [
    { code: "001", age: 30, city: "A01", empty: null },
    { code: "A01", age: 41.5, city: "B02", empty: null },
  ];
  const kinds = featureKinds(rows, ["code", "age", "city", "empty", "absent"]);
  assert.deepEqual({ ...kinds }, { code: "string", age: "number", city: "string" });

  assert.equal(coerceFeature("001", kinds.code, false), "001"); // giữ số 0 đầu của cột chữ
  assert.equal(coerceFeature(" 42 ", kinds.age, false), 42);
  assert.equal(coerceFeature("12", undefined, false), 12); // chưa biết kiểu: như cũ
  assert.equal(coerceFeature("20250101", "number", true), "20250101"); // time_series luôn gửi chữ
});

test("time_series: mốc cuối lúc train và mốc kế tiếp suy từ preview + tổng số dòng", () => {
  // electricity_MT_301_hourly_train.csv: 4344 dòng theo giờ từ 2014-04-01 00:00, dòng cuối 2014-09-28 23:00.
  const rows = [0, 1, 2].map((h) => ({ date: `2014-04-01T0${h}:00:00`, load_kwh: 55 + h }));
  const hint = timeSeriesHint(rows, ["date"], 4344);
  assert.deepEqual(hint, {
    column: "date",
    last: "2014-09-28 23:00:00",
    next: "2014-09-29 00:00:00",
    stepMs: 3_600_000,
    estimated: true,
  });
  assert.deepEqual(stepUnit(hint!.stepMs), { unit: "hours", n: 1 });

  // Theo ngày: hiện ngày, không kèm giờ.
  const daily = timeSeriesHint([{ d: "2024-01-01" }, { d: "2024-01-02" }], ["d"], 31);
  assert.equal(daily?.last, "2024-01-31");
  assert.equal(daily?.next, "2024-02-01");

  // File giảm dần: dòng đầu là mốc cuối. Không đều hoặc không có cột thời gian: không đoán.
  assert.equal(timeSeriesHint([{ d: "2024-01-05" }, { d: "2024-01-04" }], ["d"], 5)?.last, "2024-01-05");
  assert.equal(timeSeriesHint([{ d: "2024-01-01" }, { d: "2024-01-03" }, { d: "2024-01-04" }], ["d"], 9), null);
  assert.equal(timeSeriesHint([{ x: 1 }, { x: 2 }], ["x"], 9), null);
});

test("lỗi dự đoán kèm traceback của worker chỉ còn câu lỗi cuối", () => {
  const raw =
    "The backend returned an error: Failed to perform prediction: Other Error: Task 57d62b89 failed after 3 retries: " +
    'Execution Failed: App Error: Traceback (most recent call last): File "/app/src/shared/mapreduce_client.py", line 166, ' +
    'in predict return self._predict_df(df_input) File "/app/src/modules/preprocessing/time_series.py", line 243, in predict ' +
    'raise ValueError("Timestamps must come after the last training timestamp, on the same regular interval") ' +
    "ValueError: Timestamps must come after the last training timestamp, on the same regular interval";
  assert.equal(shortBackendError(raw), "Timestamps must come after the last training timestamp, on the same regular interval");
  assert.equal(shortBackendError("HTTP 500"), "HTTP 500");
});

test("time_series: có đủ dataset thì tính đúng như backend, kể cả file không xếp theo thời gian", () => {
  // 100 ngày, xếp xen kẽ: 50 dòng đầu là các ngày lẻ (đều 2 ngày) - preview tưởng là chuỗi 2 ngày.
  const day = (n: number) => new Date(Date.UTC(2024, 0, n)).toISOString().slice(0, 10);
  const order = [...Array.from({ length: 50 }, (_, i) => 1 + 2 * i), ...Array.from({ length: 50 }, (_, i) => 2 + 2 * i)];
  const rows = order.map((n) => ({ d: day(n) }));

  const guessed = timeSeriesHint(rows.slice(0, 50), ["d"], 100);
  assert.equal(guessed?.estimated, true); // chỉ là ước tính - giao diện ghi rõ

  const exact = timeSeriesHint(rows, ["d"], 100);
  assert.equal(exact?.estimated, false);
  assert.equal(exact?.last, day(100));
  assert.equal(exact?.next, day(101));
  assert.equal(exact?.stepMs, 86_400_000);
});

test("time_series: giữ phần lẻ mili giây, lẻ hơn thì không đoán", () => {
  const rows = [{ t: "2024-01-01T00:00:00.500" }, { t: "2024-01-01T00:00:01.500" }];
  const hint = timeSeriesHint(rows, ["t"], 2);
  assert.equal(hint?.last, "2024-01-01 00:00:01.500");
  assert.equal(hint?.next, "2024-01-01 00:00:02.500");
  assert.deepEqual(stepUnit(hint!.stepMs), { unit: "seconds", n: 1 });
  assert.equal(timeSeriesHint([{ t: "2024-01-01T00:00:00.0000005" }, { t: "2024-01-01T00:00:01" }], ["t"], 2), null);
});

test("job mất dấu được làm mới mà vẫn chạy: không hiện như đang được theo dõi, tới khi agent theo dõi lại", () => {
  const { jobs } = run([
    { seq: 1, type: "job_started", job_id: "L", config: {}, time: 1 },
    { seq: 2, type: "job_status", job_id: "L", status: 0, time: 2 },
  ]);
  const lost = markJobsLost(jobs);
  const refreshed = mergeJobFromApi(lost.L, { _id: "L", status: 0, activate: 0, config: { problem_type: "time_series" } }, 5000);
  assert.equal(refreshed.status, "running");
  assert.equal(refreshed.untracked, true);
  assert.equal(refreshed.problemType, "time_series");
  // Job đang được theo dõi bình thường thì Làm mới không gắn cờ này.
  assert.equal(mergeJobFromApi(jobs.L, { _id: "L", status: 0, activate: 0 }, 5000).untracked, undefined);

  const rewatched = applyJobEvent({ L: refreshed }, { seq: 3, type: "job_watch", job_id: "L", time: 6 });
  assert.equal(rewatched.L.untracked, undefined);
});

test("job chỉ biết qua job_watch / job_done vẫn có dataset và loại bài toán cho form dự đoán", () => {
  const { jobs } = run([
    { seq: 1, type: "job_watch", job_id: "W", dataset_id: "ds-9", problem_type: "time_series", time: 1 },
    { seq: 2, type: "job_done", job_id: "W", status: 1, dataset_id: "ds-9", problem_type: "time_series", time: 2 },
  ]);
  assert.equal(jobs.W.datasetId, "ds-9");
  assert.equal(jobs.W.problemType, "time_series");
});

test("chỉ tool gọi thành công mới đổi dataset đang làm việc", () => {
  const { trace } = run([
    { seq: 1, type: "tool_call", agent: "data-agent", name: "get_dataset_schema", arguments: { dataset_id: "good" }, ok: true, time: 1 },
    { seq: 2, type: "tool_start", agent: "data-agent", name: "get_dataset_info", arguments: { dataset_id: "bad" }, time: 2 },
    { seq: 3, type: "tool_call", agent: "data-agent", name: "get_dataset_info", arguments: { dataset_id: "bad" }, ok: false, time: 3 },
  ]);
  assert.equal(trace.activeDatasetId, "good");
});

test("ép kiểu số chỉ nhận số thập phân bình thường, an toàn", () => {
  assert.equal(coerceFeature("1.5", undefined, false), 1.5);
  assert.equal(coerceFeature("-2e3", "number", false), -2000);
  assert.equal(coerceFeature("0x1A", undefined, false), "0x1A");
  assert.equal(coerceFeature("1e400", "number", false), "1e400");
  assert.equal(coerceFeature("12345678901234567890", undefined, false), "12345678901234567890");
  assert.equal(coerceFeature("Infinity", undefined, false), "Infinity");
});

test("job mất dấu / không còn theo dõi: kết quả tới (vd sau khi nhờ agent theo dõi lại) thì hết cờ", () => {
  const base = { jobId: "J", status: "running" as const, untracked: true };
  const done = applyJobEvent({ J: base }, { seq: 1, type: "job_done", job_id: "J", status: 1, time: 1 });
  assert.equal(done.J.status, "completed");
  assert.equal(done.J.untracked, undefined);
  const failed = applyJobEvent({ J: { ...base, lost: true } }, { seq: 2, type: "job_failed", job_id: "J", status: -1, error: "x", time: 2 });
  assert.equal(failed.J.untracked, undefined);
  assert.equal(failed.J.lost, undefined);
});

test("job xong nhưng không đọc được kết quả: thẻ có cảnh báo, không trông như kết quả rỗng", () => {
  const { jobs } = run([
    { seq: 1, type: "job_done", job_id: "S", status: 1, summary_error: "Không đọc được kết quả chi tiết của job.", time: 1 },
  ]);
  assert.equal(jobs.S.status, "completed");
  assert.equal(jobs.S.warning, "Không đọc được kết quả chi tiết của job.");
});

test("lượt bị đứt: kết quả ghép đúng theo turn_id, kể cả nhiều lượt và sự kiện lạ", () => {
  const book = new OrphanTurns();
  book.add("A", 10, true, 0);
  book.add("B", 20, true, 0);
  // turn_done của lượt khác (lượt mới, hoặc phiên khác) không được nhận nhầm.
  assert.equal(book.onEvent({ seq: 1, type: "turn_done", turn_id: "X", reply: "khác" }), null);
  assert.equal(book.onEvent({ seq: 2, type: "turn_done", reply: "không có turn_id" }), null);
  assert.deepEqual(book.onEvent({ seq: 3, type: "turn_failed", turn_id: "B", error: "LLM lỗi" }), {
    kind: "ended",
    end: { error: "LLM lỗi" },
    itemId: 20,
  });
  assert.deepEqual(book.onEvent({ seq: 4, type: "turn_done", turn_id: "A", reply: "Xong" }), {
    kind: "ended",
    end: { reply: "Xong" },
    itemId: 10,
  });
  assert.equal(book.size, 0);
  // Đã ghép rồi thì bản phát lại (trùng) không hiện lần nữa.
  assert.equal(book.onEvent({ seq: 4, type: "turn_done", turn_id: "A", reply: "Xong" }), null);
});

test("lượt bị đứt: chưa xác nhận thì bỏ im lặng, quá lâu thì báo không nhận được câu trả lời", () => {
  const book = new OrphanTurns();
  book.add("net", 1, false, 0);          // lỗi mạng trước khi server trả lời
  book.add("seen", 2, false, 0);
  // server có nhận: item của lượt đó không còn mời "Gửi lại"
  assert.deepEqual(book.onEvent({ seq: 1, type: "turn_start", turn_id: "seen" }), { kind: "confirmed", itemId: 2 });
  assert.equal(book.onEvent({ seq: 2, type: "turn_start", turn_id: "seen" }), null);
  book.add("drop", 3, true, 0);
  assert.deepEqual(book.expire(ORPHAN_UNCONFIRMED_MS + 1), { notify: [], removed: 1 });   // "net" bỏ im lặng
  assert.equal(book.size, 2);
  assert.deepEqual(book.expire(ORPHAN_MAX_WAIT_MS + 1).notify.sort(), [2, 3]);
  assert.equal(book.size, 0);
  book.add("x", 7, true, 0);
  assert.deepEqual(book.clear(), [7]);
});

test("tự kích hoạt hiện trên thẻ job và huỷ được", () => {
  const { jobs } = run([
    { seq: 1, type: "job_started", job_id: "J", config_id: "c", config: {}, auto_activate: true, time: 1 },
  ]);
  assert.equal(jobs.J.autoActivate, true);
  const cancelled = applyJobEvent(jobs, { seq: 2, type: "auto_activate_changed", job_id: "J", enabled: false, time: 2 });
  assert.equal(cancelled.J.autoActivate, false);
  assert.equal(cancelled.J.autoActivateCancelled, true);
  // job_watch (vd theo dõi lại) mang cờ hiện tại.
  const rewatched = applyJobEvent(cancelled, { seq: 3, type: "job_watch", job_id: "J", auto_activate: false, time: 3 });
  assert.equal(rewatched.J.autoActivate, false);
});

test("tự kích hoạt: hết giờ theo dõi thì báo chưa làm; mất dấu hay job xong thì không còn hứa", () => {
  const { jobs } = run([{ seq: 1, type: "job_started", job_id: "T", config: {}, auto_activate: true, time: 1 }]);
  const timedOut = applyJobEvent(jobs, { seq: 2, type: "job_watch_timeout", job_id: "T", auto_activate_skipped: true, error: "x", time: 2 });
  assert.equal(timedOut.T.autoActivate, undefined);
  assert.equal(timedOut.T.autoActivateSkipped, true);
  assert.equal(markJobsLost(jobs).T.autoActivate, undefined);
  const done = applyJobEvent(jobs, { seq: 3, type: "job_done", job_id: "T", status: 1, time: 3 });
  assert.equal(done.T.autoActivate, undefined);
});

test("job_done lặp không xoá kết quả tự kích hoạt; Làm mới không giấu việc tự kích hoạt sắp diễn ra", () => {
  const { jobs } = run([
    { seq: 1, type: "job_started", job_id: "D", config: {}, auto_activate: true, time: 1 },
    { seq: 2, type: "job_done", job_id: "D", status: 1, activation: { ok: true }, time: 2 },
    { seq: 3, type: "job_done", job_id: "D", status: 1, time: 3 },
  ]);
  assert.deepEqual(jobs.D.activation, { ok: true });
  assert.equal(jobs.D.activated, true);

  const running = run([{ seq: 1, type: "job_started", job_id: "R", config: {}, auto_activate: true, time: 1 }]).jobs.R;
  const refreshed = mergeJobFromApi(running, { _id: "R", status: 1, activate: 0 }, 5000);
  assert.equal(refreshed.status, "completed");
  assert.equal(refreshed.autoActivate, true);                 // watcher chưa kịp hỏi: vẫn sẽ tự kích hoạt
  assert.equal(mergeJobFromApi(running, { _id: "R", status: 1, activate: 1 }, 5000).autoActivate, undefined);
});

test("hello / reconnect dựng lại job đang theo dõi và lời hứa tự kích hoạt (sự kiện cũ đã trôi khỏi bộ đệm)", () => {
  const rebuilt = applyWatchState({}, ["W"], { W: true });
  assert.equal(rebuilt.W.status, "running");
  assert.equal(rebuilt.W.autoActivate, true);
  const cancelled = applyWatchState(rebuilt, ["W"], { W: false });
  assert.equal(cancelled.W.autoActivate, undefined);
  // Không có gì đổi thì giữ nguyên object.
  assert.equal(applyWatchState(cancelled, ["W"], { W: false }), cancelled);
  assert.equal(applyWatchState(cancelled, "rác", null), cancelled);
});

test("lời hứa hết hiệu lực khi hết giờ hay mất phiên, kể cả job đã 'xong' theo Làm mới", () => {
  const completed: JobView = { jobId: "C", status: "completed", autoActivate: true };
  const timedOut = applyJobEvent({ C: completed }, { seq: 1, type: "job_watch_timeout", job_id: "C", auto_activate_skipped: true, time: 1 });
  assert.equal(timedOut.C.status, "completed");
  assert.equal(timedOut.C.autoActivate, undefined);
  assert.equal(timedOut.C.autoActivateSkipped, true);
  const lost = markJobsLost({ C: completed });
  assert.equal(lost.C.autoActivate, undefined);
  assert.equal(lost.C.autoActivateSkipped, true);
  assert.equal(lost.C.status, "completed");
});

test("hết giờ theo dõi lần hai vẫn giữ lời nhắc kích hoạt thủ công", () => {
  const first = applyJobEvent({ S: { jobId: "S", status: "running", autoActivate: true } }, {
    seq: 1, type: "job_watch_timeout", job_id: "S", auto_activate_skipped: true, time: 1,
  });
  const rewatched = applyJobEvent(first, { seq: 2, type: "job_watch", job_id: "S", auto_activate: false, time: 2 });
  const second = applyJobEvent(rewatched, { seq: 3, type: "job_watch_timeout", job_id: "S", time: 3 });
  assert.equal(second.S.autoActivateSkipped, true);
});

test("ảnh chụp reconnect cũ không hứa lại trên job đã xong; Làm mới tới muộn không kéo lùi trạng thái", () => {
  const done: JobView = { jobId: "F", status: "completed", activation: { ok: false, error: "không đạt" } };
  assert.equal(applyWatchState({ F: done }, ["F"], { F: true }).F.autoActivate, undefined);
  // Phản hồi Làm mới đọc lúc job còn chạy, tới sau job_done.
  assert.equal(mergeJobFromApi(done, { _id: "F", status: 0, activate: 0 }, 9000), done);
});

test("cột boolean lúc train được gửi dạng true/false", () => {
  const kinds = featureKinds([{ flag: true }, { flag: false }], ["flag"]);
  assert.equal(kinds.flag, "boolean");
  assert.equal(coerceFeature("true", kinds.flag, false), true);
  assert.equal(coerceFeature("Không", kinds.flag, false), false);
  assert.equal(coerceFeature("maybe", kinds.flag, false), "maybe");
});

test("server xác nhận lượt chưa chắc (hello báo đang chạy): chờ tới khi xong, không bỏ sau 90 giây", () => {
  const book = new OrphanTurns();
  book.add("q", 5, false, 0);
  assert.deepEqual(book.confirm("q"), { itemId: 5 });
  assert.equal(book.confirm("q"), null);                         // đã xác nhận rồi
  assert.deepEqual(book.expire(ORPHAN_UNCONFIRMED_MS + 1), { notify: [], removed: 0 });
  assert.equal(book.size, 1);
});

test("thẻ job biết đúng điều kiện sẽ kiểm trước khi tự kích hoạt", () => {
  let jobs = applyJobEvent({}, { type: "job_watch", job_id: "C", auto_activate: true, auto_activate_constraints: [] });
  assert.deepEqual(jobs.C.autoActivateConstraints, []);                 // bất kể điểm
  jobs = applyJobEvent(jobs, {
    type: "auto_activate_changed",
    job_id: "C",
    enabled: true,
    auto_activate_constraints: [{ metric: "accuracy", op: ">=", value: 0.9 }, { metric: 1, op: ">=", value: "x" }],
  });
  assert.deepEqual(jobs.C.autoActivateConstraints, [{ metric: "accuracy", op: ">=", value: 0.9 }]);
  // Sự kiện không mang trường này (job_started) không xoá điều kiện đã biết.
  jobs = applyJobEvent(jobs, { type: "job_started", job_id: "C", auto_activate: true });
  assert.equal(jobs.C.autoActivateConstraints?.length, 1);
});

test("hello / reconnect mang điều kiện tự kích hoạt", () => {
  const rebuilt = applyWatchState({}, ["W"], { W: true }, { W: [{ metric: "r2", op: ">=", value: 0.8 }] });
  assert.deepEqual(rebuilt.W.autoActivateConstraints, [{ metric: "r2", op: ">=", value: 0.8 }]);
  // Cùng điều kiện: giữ nguyên object; server cũ không gửi map: giữ điều kiện đã biết.
  assert.equal(applyWatchState(rebuilt, ["W"], { W: true }, { W: [{ metric: "r2", op: ">=", value: 0.8 }] }), rebuilt);
  assert.equal(applyWatchState(rebuilt, ["W"], { W: true }), rebuilt);
});

test("bật lại tự kích hoạt sau khi lời hứa cũ hết hiệu lực: thẻ không còn báo 'kích hoạt thủ công'", () => {
  let jobs = applyJobEvent({}, { type: "job_watch", job_id: "E", auto_activate: true, auto_activate_constraints: [] });
  jobs = applyJobEvent(jobs, { type: "job_watch_timeout", job_id: "E", auto_activate_skipped: true });
  assert.equal(jobs.E.autoActivateSkipped, true);
  jobs = applyJobEvent(jobs, { type: "job_watch", job_id: "E", auto_activate: false, auto_activate_constraints: [] });
  assert.equal(jobs.E.autoActivateSkipped, true);                    // theo dõi lại: chưa ai yêu cầu lại
  const reenabled = applyJobEvent(jobs, { type: "auto_activate_changed", job_id: "E", enabled: true, auto_activate_constraints: [] });
  assert.equal(reenabled.E.autoActivate, true);
  assert.equal(reenabled.E.autoActivateSkipped, undefined);
  // Dựng lại từ hello / reconnect cũng vậy.
  assert.equal(applyWatchState(jobs, ["E"], { E: true }).E.autoActivateSkipped, undefined);
});
