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
  createSeqTracker,
  currentActivity,
  emptyTrace,
  groupConfigErrors,
  mergeJobFromApi,
  type JobView,
  type TurnTrace,
} from "./eventAdapter";
import type { AgentEvent } from "./events";

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
