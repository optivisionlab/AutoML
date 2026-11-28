import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { ModelScoreDetail, PipelineData, TrainingJob } from "@automl/domain";
import {
  buildFallbackPipelineFromJob,
  buildProgressMapFromPipeline,
  isJobActive,
  isJobCancelled,
  isJobCompleted,
  isJobFailed,
  isJobTerminal,
  normalizeNodeStatus,
  normalizePipelineFromJob,
  resolveBestTrial,
  resolveModelBestParams,
  resolveModelScores,
  resolveModelTrialStats,
  resolvePipelineHoldoutScores,
} from "./pipelineGraphBuilder";
import {
  applyPipelineEvent,
  mergePipelineWithSnapshot,
} from "./pipelineRealtimeReducer";

describe("normalizeNodeStatus & job status helpers (v2.0.0 + legacy)", () => {
  it("normalizes all v2.0.0 and legacy statuses per spec section 7.2", () => {
    assert.equal(normalizeNodeStatus("succeeded"), "done");
    assert.equal(normalizeNodeStatus("done"), "done");
    assert.equal(normalizeNodeStatus("success"), "done");
    assert.equal(normalizeNodeStatus("completed"), "done");
    assert.equal(normalizeNodeStatus(1), "done");
    assert.equal(normalizeNodeStatus("1"), "done");

    assert.equal(normalizeNodeStatus("running"), "running");
    assert.equal(normalizeNodeStatus(0), "running");
    assert.equal(normalizeNodeStatus("0"), "running");

    assert.equal(normalizeNodeStatus("failed"), "failed");
    assert.equal(normalizeNodeStatus("error"), "failed");
    assert.equal(normalizeNodeStatus("cancelled"), "failed");
    assert.equal(normalizeNodeStatus(-1), "failed");
    assert.equal(normalizeNodeStatus("-1"), "failed");
    assert.equal(normalizeNodeStatus(-2), "failed");

    assert.equal(normalizeNodeStatus("skipped"), "skipped");

    assert.equal(normalizeNodeStatus("queued"), "pending");
    assert.equal(normalizeNodeStatus("pending"), "pending");
    assert.equal(normalizeNodeStatus(null), "pending");
    assert.equal(normalizeNodeStatus(undefined), "pending");
  });

  it("classifies job statuses accurately", () => {
    assert.equal(isJobCompleted("succeeded"), true);
    assert.equal(isJobCompleted(1), true);
    assert.equal(isJobActive("queued"), true);
    assert.equal(isJobActive("running"), true);
    assert.equal(isJobActive(0), true);
    assert.equal(isJobCancelled("cancelled"), true);
    assert.equal(isJobCancelled(-2), true);
    assert.equal(isJobFailed("failed"), true);
    assert.equal(isJobFailed(-1), true);
    assert.equal(isJobTerminal("succeeded"), true);
    assert.equal(isJobTerminal("failed"), true);
    assert.equal(isJobTerminal("cancelled"), true);
    assert.equal(isJobTerminal("running"), false);
    assert.equal(isJobTerminal("queued"), false);
  });
});

describe("v2.0.0 model resolvers (trials[best_trial], best_scores, holdout_scores)", () => {
  it("reads scores and params from trials[best_trial] in v2.0.0 schema", () => {
    const model: ModelScoreDetail = {
      status: "succeeded" as const,
      best_trial: 1,
      trials: [
        {
          trial_id: 0,
          status: "pruned" as const,
          params: { alpha: 0.01 },
          scores: { mse: 4100.1, r2: 0.25 },
        },
        {
          trial_id: 1,
          status: "succeeded" as const,
          params: { alpha: 0.15, max_iter: 1000 },
          scores: { mse: 2986.89, mae: 44.4, mape: 0.3965, r2: 0.4948 },
        },
        {
          trial_id: 2,
          status: "succeeded" as const,
          params: { alpha: 1.0 },
          scores: { mse: 3200.5, r2: 0.42 },
        },
      ],
      holdout_scores: { mse: 3010.2, r2: 0.489 },
    };

    const best = resolveBestTrial(model);
    assert.equal(best?.trial_id, 1);
    assert.deepEqual(resolveModelScores(model), {
      mse: 2986.89,
      mae: 44.4,
      mape: 0.3965,
      r2: 0.4948,
    });
    assert.deepEqual(resolveModelBestParams(model), { alpha: 0.15, max_iter: 1000 });
    assert.deepEqual(resolveModelTrialStats(model), {
      nTrials: 3,
      nPruned: 1,
      bestTrial: 1,
    });
  });

  it("falls back to best_scores during realtime MQTT updates when trials is null", () => {
    const model = {
      status: "succeeded" as const,
      trials: null,
      best_trial: 1,
      best_scores: { mse: 2986.89, mae: 44.4, mape: 0.3965, r2: 0.4948 },
      n_trials: 3,
      n_pruned: 0,
    };

    assert.equal(resolveBestTrial(model), null);
    assert.equal(resolveModelScores(model).r2, 0.4948);
    assert.deepEqual(resolveModelTrialStats(model), {
      nTrials: 3,
      nPruned: 0,
      bestTrial: 1,
    });
  });

  it("stays backward compatible with v1.0.0 scores and best_params", () => {
    const legacyModel = {
      status: "done" as const,
      best_params: { n_estimators: 200 },
      scores: { r2: 0.8841 },
    };

    assert.equal(resolveModelScores(legacyModel).r2, 0.8841);
    assert.deepEqual(resolveModelBestParams(legacyModel), { n_estimators: 200 });
  });
});

describe("applyPipelineEvent & mergePipelineWithSnapshot (MQTT realtime)", () => {
  const jobId = "6ae5a5402ebdf7162486abf5";

  it("applies node_started, node_finished (including skipped), model_finished, and job_finished", () => {
    let state: PipelineData | undefined = undefined;

    state = applyPipelineEvent(state, {
      event: "node_started",
      job_id: jobId,
      seq: 1,
      node: "read_dataset",
      status: "running",
      at: "2026-11-26T08:22:20Z",
    });
    assert.equal(state.status, "running");
    assert.equal(state.read_dataset?.status, "running");
    assert.equal(state.read_dataset?.name, "Read dataset");

    state = applyPipelineEvent(state, {
      event: "node_finished",
      job_id: jobId,
      seq: 2,
      node: "read_dataset",
      status: "succeeded",
      output: { n_rows: 5000 },
      at: "2026-11-26T08:22:21Z",
    });
    assert.equal(state.read_dataset?.status, "succeeded");
    assert.equal(state.read_dataset?.output?.n_rows, 5000);

    state = applyPipelineEvent(state, {
      event: "node_finished",
      job_id: jobId,
      seq: 3,
      node: "split_holdout_data",
      status: "skipped",
      output: { reason: "rows <= 10000" },
      at: "2026-11-26T08:22:22Z",
    });
    assert.equal(state.split_holdout_data?.status, "skipped");

    state = applyPipelineEvent(state, {
      event: "node_started",
      job_id: jobId,
      seq: 4,
      node: "preprocessing",
      status: "running",
      at: "2026-11-26T08:22:24Z",
    });
    state = applyPipelineEvent(state, {
      event: "node_finished",
      job_id: jobId,
      seq: 5,
      node: "preprocessing",
      status: "succeeded",
      output: { dropped_rows: 0, n_features: 10 },
      at: "2026-11-26T08:22:25Z",
    });
    assert.equal(state.preprocessing?.output?.n_features, 10);

    state = applyPipelineEvent(state, {
      event: "model_finished",
      job_id: jobId,
      seq: 9,
      node: "train",
      model_name: "Lasso",
      status: "succeeded",
      best_trial: 1,
      best_scores: { mse: 2986.89, mae: 44.4, mape: 0.3965, r2: 0.4948 },
      n_trials: 3,
      n_pruned: 0,
    });
    assert.equal(state.train?.status, "running");
    assert.equal(state.train?.output?.models?.Lasso?.status, "succeeded");
    assert.equal(state.train?.output?.models?.Lasso?.best_scores?.r2, 0.4948);

    // node_finished for train with empty output must NOT wipe out models
    state = applyPipelineEvent(state, {
      event: "node_finished",
      job_id: jobId,
      seq: 11,
      node: "train",
      status: "succeeded",
      output: {},
      at: "2026-11-26T08:22:40Z",
    });
    assert.equal(state.train?.status, "succeeded");
    assert.equal(state.train?.output?.models?.Lasso?.best_scores?.r2, 0.4948);

    state = applyPipelineEvent(state, {
      event: "job_finished",
      job_id: jobId,
      seq: 14,
      status: "succeeded",
      best_model: "Lasso",
      error: null,
    });
    assert.equal(state.status, "succeeded");
    assert.equal(state.select_best?.output?.best_model, "Lasso");
  });

  it("merges stale API snapshot without regressing live MQTT progress, and accepts terminal final snapshot", () => {
    const live = applyPipelineEvent(
      applyPipelineEvent(undefined, {
        event: "node_finished",
        job_id: jobId,
        seq: 5,
        node: "preprocessing",
        status: "succeeded",
        output: { dropped_rows: 0, n_features: 10 },
      }),
      {
        event: "model_finished",
        job_id: jobId,
        seq: 9,
        model_name: "Lasso",
        status: "succeeded",
        best_trial: 1,
        best_scores: { r2: 0.4948 },
        n_trials: 3,
        n_pruned: 0,
      },
    );

    const staleSnapshot: PipelineData = {
      job_id: jobId,
      version: "2.0.0",
      status: "running",
      preprocessing: {
        name: "Preprocessing",
        kind: "preprocessing",
        depends_on: ["split_holdout_data"],
        status: "running",
        params: { target: "price", list_feature: ["a", "b"] },
        output: {},
      },
      train: {
        name: "Train models",
        kind: "model_training",
        depends_on: ["model_selection"],
        status: "queued",
        params: {},
        output: { models: { Lasso: { status: "queued", trials: null } } },
      },
    };

    const merged = mergePipelineWithSnapshot(live, staleSnapshot)!;
    // Live progress kept
    assert.equal(merged.preprocessing?.status, "succeeded");
    assert.equal(merged.train?.output?.models?.Lasso?.status, "succeeded");
    // Snapshot params hydrated
    assert.equal(merged.preprocessing?.params?.target, "price");

    // Now final terminal snapshot arrives with full trials & holdout_scores
    const finalSnapshot: PipelineData = {
      ...staleSnapshot,
      status: "succeeded",
      select_best: {
        name: "Select best model",
        kind: "model_selection",
        depends_on: ["train"],
        status: "succeeded",
        params: {},
        output: {
          best_model: "Lasso",
          holdout_scores: { r2: 0.481 },
        },
      },
      train: {
        name: "Train models",
        kind: "model_training",
        depends_on: ["model_selection"],
        status: "succeeded",
        params: {},
        output: {
          models: {
            Lasso: {
              status: "succeeded",
              best_trial: 1,
              trials: [
                { trial_id: 0, status: "pruned", params: { alpha: 0.01 }, scores: { r2: 0.2 } },
                { trial_id: 1, status: "succeeded", params: { alpha: 0.1 }, scores: { r2: 0.4948 } },
              ],
            },
          },
        },
      },
    };

    const finalized = mergePipelineWithSnapshot(merged, finalSnapshot)!;
    assert.equal(finalized.status, "succeeded");
    assert.equal(finalized.train?.output?.models?.Lasso?.trials?.length, 2);
    assert.deepEqual(resolvePipelineHoldoutScores(finalized), { r2: 0.481 });
  });
});

describe("buildProgressMapFromPipeline & buildFallbackPipelineFromJob", () => {
  it("renders skipped nodes, expanded v2.0.0 model nodes, and attaches rawPipeline", () => {
    const pipeline: PipelineData = {
      job_id: "job-v2",
      version: "2.0.0",
      mode: "automl",
      status: "succeeded",
      read_dataset: {
        name: "Read dataset",
        kind: "data_loading",
        depends_on: [],
        status: "succeeded",
        params: {},
        output: {},
      },
      split_holdout_data: {
        name: "Split holdout data",
        kind: "data_splitting",
        depends_on: ["read_dataset"],
        status: "skipped",
        params: {},
        output: {},
      },
      preprocessing: {
        name: "Preprocessing",
        kind: "preprocessing",
        depends_on: ["split_holdout_data"],
        status: "succeeded",
        params: { target: "y" },
        output: { dropped_rows: 0, n_features: 10 },
      },
      model_selection: {
        name: "Model selection",
        kind: "model_selection",
        depends_on: ["preprocessing"],
        status: "succeeded",
        params: { model_names: ["Lasso"], metric_sort: "r2" },
        output: {},
      },
      train: {
        name: "Train models",
        kind: "model_training",
        depends_on: ["model_selection"],
        status: "succeeded",
        params: {},
        output: {
          models: {
            Lasso: {
              status: "succeeded",
              best_trial: 0,
              trials: [{ trial_id: 0, status: "succeeded", params: { alpha: 0.1 }, scores: { r2: 0.77 } }],
            },
          },
        },
      },
      select_best: {
        name: "Select best model",
        kind: "model_selection",
        depends_on: ["train"],
        status: "succeeded",
        params: {},
        output: { best_model: "Lasso" },
      },
    };

    const map = buildProgressMapFromPipeline(pipeline, { mode: "expanded" });
    assert.equal(map.rawPipeline?.job_id, "job-v2");
    assert.equal(map.nodes.find((n) => n.id === "split_holdout_data")?.status, "skipped");
    const lassoNode = map.nodes.find((n) => n.id === "model_Lasso");
    assert.equal(lassoNode?.status, "done");
    assert.equal(lassoNode?.isBestModel, true);
    assert.equal(lassoNode?.result?.r2, 0.77);
    assert.equal(lassoNode?.rawParams?.alpha, 0.1);
  });

  it("synthesizes a fallback pipeline when job.pipeline is null", () => {
    const job: TrainingJob = {
      _id: "job-legacy-1",
      job_id: "job-legacy-1",
      status: 0,
      data: { id: "ds1", name: "housing.csv" },
      config: {
        problem_type: "regression",
        metric_sort: "r2",
        target: "medv",
        list_feature: ["rm", "lstat"],
      },
    };

    const fallback = buildFallbackPipelineFromJob(job);
    assert.equal(fallback.job_id, "job-legacy-1");
    assert.equal(fallback.status, "running");
    assert.equal(fallback.read_dataset?.status, "running");
    assert.equal(fallback.preprocessing?.params?.target, "medv");
  });

  it("normalizes partial/nested pipeline and hydrates models from orther_model_scores", () => {
    const job: TrainingJob = {
      _id: "job-partial-1",
      job_id: "job-partial-1",
      status: 1,
      best_model: "XGBRegressor",
      best_params: { max_depth: 6 },
      orther_model_scores: [
        { model_name: "Lasso", scores: { r2: 0.65 } },
        { model_name: "XGBRegressor", scores: { r2: 0.91 } },
      ],
      pipeline: {
        status: "succeeded",
        nodes: {
          read_dataset: { status: "succeeded", params: {}, output: {} },
          preprocessing: { status: "succeeded", params: {}, output: {} },
          model_selection: { status: "succeeded", params: {}, output: {} },
          train: { status: "succeeded", params: {}, output: {} },
          select_best: { status: "succeeded", params: {}, output: {} },
        },
      } as unknown as PipelineData,
    };

    const normalized = normalizePipelineFromJob(job);
    assert.equal(normalized.read_dataset?.name, "Read dataset");
    assert.deepEqual(normalized.model_selection?.params?.model_names, ["Lasso", "XGBRegressor"]);
    assert.equal(normalized.train?.output?.models?.XGBRegressor?.best_params?.max_depth, 6);
    assert.equal(normalized.select_best?.output?.best_model, "XGBRegressor");
  });

  it("expands preprocessing branches, per-model HPO nodes, holdout arc, and avoids vertical overlap for many models", () => {
    const modelNames = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"];
    const models: Record<string, ModelScoreDetail> = {};
    for (const name of modelNames) {
      models[name] = {
        status: "succeeded",
        best_trial: 0,
        trials: [
          { trial_id: 0, status: "succeeded", params: { alpha: 0.1 }, scores: { r2: 0.85 } },
          { trial_id: 1, status: "pruned", params: { alpha: 1.0 }, scores: { r2: 0.4 } },
        ],
      };
    }

    const pipeline: PipelineData = {
      job_id: "job-detailed",
      version: "2.0.0",
      mode: "automl",
      status: "succeeded",
      read_dataset: { name: "Read dataset", kind: "data_loading", depends_on: [], status: "succeeded", params: {}, output: {} },
      split_holdout_data: {
        name: "Split holdout data",
        kind: "data_splitting",
        depends_on: ["read_dataset"],
        status: "succeeded",
        params: { test_size: 0.2 },
        output: { train_rows: 12000, holdout_rows: 3000 },
      },
      preprocessing: {
        name: "Preprocessing",
        kind: "preprocessing",
        depends_on: ["split_holdout_data"],
        status: "succeeded",
        params: {
          target: "price",
          transformers: {
            numeric: ["SimpleImputer", "StandardScaler"],
            categorical: ["SimpleImputer", "OneHotEncoder"],
            text: [],
          },
        },
        output: {
          column_types: { numeric: ["a", "b"], categorical: ["c"], text: [] },
        },
      },
      model_selection: {
        name: "Model selection",
        kind: "model_selection",
        depends_on: ["preprocessing"],
        status: "succeeded",
        params: { model_names: modelNames, metric_sort: "r2", search_algorithm: "tpe_search" },
        output: {},
      },
      train: {
        name: "Train models",
        kind: "model_training",
        depends_on: ["model_selection"],
        status: "succeeded",
        params: {},
        output: { models },
      },
      select_best: {
        name: "Select best model",
        kind: "model_selection",
        depends_on: ["train"],
        status: "succeeded",
        params: {},
        output: { best_model: "M1", holdout_scores: { r2: 0.84 } },
      },
      save_result: {
        name: "Save result",
        kind: "result_storage",
        depends_on: ["select_best"],
        status: "succeeded",
        params: {},
        output: { object_name: "models/job-detailed/M1.pkl" },
      },
    };

    const map = buildProgressMapFromPipeline(pipeline, { mode: "detailed" });
    // Preprocessing branches present
    assert.ok(map.nodes.find((n) => n.id === "prep_numeric"));
    assert.ok(map.nodes.find((n) => n.id === "prep_categorical"));
    // Per-model HPO nodes present
    assert.ok(map.nodes.find((n) => n.id === "hpo_M1"));
    assert.equal(map.nodes.find((n) => n.id === "model_M1")?.metricBadge, "R2: 0.8500");
    // Holdout dashed edge present on select_best
    assert.deepEqual(map.nodes.find((n) => n.id === "select_best")?.dashedParentIds, ["split_holdout_data"]);
    // All 8 parallel model nodes have unique, well-spaced pixel y coordinates (>= 100px apart)
    const modelYs = modelNames
      .map((name) => map.nodes.find((n) => n.id === `model_${name}`)!.py!)
      .sort((a, b) => a - b);
    for (let i = 1; i < modelYs.length; i++) {
      assert.ok(modelYs[i] - modelYs[i - 1] >= 100, `Expected >= 100px spacing, got ${modelYs[i] - modelYs[i - 1]}`);
    }
    assert.ok((map.canvasHeight ?? 0) > 800);
  });

  it("preserves direct PipelineData returned by GET /api/v1/inference/jobs/{id} without falling back to empty skeleton", () => {
    // Exact shape returned in `response.data` by GET /api/v1/inference/jobs/6b034283f30d823bbef15728
    const directApiPayload: PipelineData = {
      job_id: "6b034283f30d823bbef15728",
      version: "2.0.0",
      mode: "automl",
      source: "tracked",
      status: "succeeded",
      error: null,
      updated_at: "2026-11-22T19:30:49Z",
      read_dataset: {
        name: "Read dataset",
        kind: "data_loading",
        depends_on: [],
        status: "succeeded",
        started_at: "2026-11-22T19:29:07Z",
        finished_at: "2026-11-22T19:29:07Z",
        error: null,
        params: { id_data: "68ea48de4bf89730c022839f", format: "parquet" },
        output: { data_url: "dataset/0/ospid.parquet", n_rows: 12330, n_columns: 18 },
      },
      split_holdout_data: {
        name: "Split holdout data",
        kind: "data_splitting",
        depends_on: ["read_dataset"],
        status: "succeeded",
        params: { method: "train_test_split", test_size: 0.2 },
        output: { train_rows: 9864, holdout_rows: 2466 },
      },
      preprocessing: {
        name: "Preprocessing",
        kind: "preprocessing",
        depends_on: ["split_holdout_data"],
        status: "succeeded",
        params: { target: "Revenue", list_feature: ["Administrative", "Month", "VisitorType"] },
        output: {
          dropped_rows: 0,
          n_features: 28,
          column_types: { numeric: ["Administrative"], categorical: ["Month", "VisitorType"], text: [] },
          class_distribution: { False: 10422, True: 1908 },
        },
      },
      model_selection: {
        name: "Model selection",
        kind: "model_selection",
        depends_on: ["preprocessing"],
        status: "succeeded",
        params: {
          problem_type: "classification",
          search_algorithm: "bayesian_search",
          metric_sort: "accuracy",
          model_names: ["DecisionTreeClassifier", "RandomForestClassifier"],
          metrics: { accuracy: "maximize", f1_macro: "maximize" },
          cv: { name: "TrainTestSplit+StratifiedKFold", n_splits: 5, n_repeats: null },
        },
        output: {},
      },
      train: {
        name: "Train models",
        kind: "model_training",
        depends_on: ["model_selection"],
        status: "succeeded",
        params: {},
        output: {
          models: {
            DecisionTreeClassifier: {
              status: "succeeded",
              error: null,
              best_trial: 0,
              trials: [{ params: { max_depth: 5 }, status: "succeeded", scores: { accuracy: 0.89 } }],
              holdout_scores: { accuracy: 0.885 },
            },
            RandomForestClassifier: {
              status: "succeeded",
              error: null,
              best_trial: 1,
              trials: [
                { params: { n_estimators: 50 }, status: "pruned", scores: { accuracy: null } },
                { params: { n_estimators: 200 }, status: "succeeded", scores: { accuracy: 0.905 } },
              ],
              holdout_scores: { accuracy: 0.9027 },
            },
          },
        },
      },
      select_best: {
        name: "Select best model",
        kind: "model_selection",
        depends_on: ["train"],
        status: "succeeded",
        params: {},
        output: { best_model: "RandomForestClassifier", score_source: "holdout" },
      },
      save_result: {
        name: "Save result",
        kind: "result_storage",
        depends_on: ["select_best"],
        status: "succeeded",
        params: { bucket_name: "models" },
        output: { object_name: "68382f81/6b034283/RandomForestClassifier_1.pkl" },
      },
    };

    const normalized = normalizePipelineFromJob(directApiPayload);
    assert.equal(normalized.source, "tracked");
    assert.deepEqual(normalized.model_selection?.params?.model_names, [
      "DecisionTreeClassifier",
      "RandomForestClassifier",
    ]);
    assert.equal(normalized.train?.output?.models?.RandomForestClassifier?.trials?.length, 2);

    const map = buildProgressMapFromPipeline(normalized, { mode: "detailed" });
    assert.equal(map.nodes.find((n) => n.id === "read_dataset")?.metricBadge, "12,330 × 18 cột");
    assert.ok(map.nodes.find((n) => n.id === "prep_numeric"));
    assert.ok(map.nodes.find((n) => n.id === "prep_categorical"));
    assert.ok(map.nodes.find((n) => n.id === "model_RandomForestClassifier"));
    assert.ok(map.nodes.find((n) => n.id === "hpo_RandomForestClassifier"));
    assert.equal(
      map.nodes.find((n) => n.id === "model_RandomForestClassifier")?.metricBadge,
      "ACCURACY: 0.9050",
    );
    assert.deepEqual(map.nodes.find((n) => n.id === "select_best")?.holdoutScores, {
      accuracy: 0.9027,
    });
    assert.deepEqual(map.nodes.find((n) => n.id === "select_best")?.dashedParentIds, [
      "split_holdout_data",
    ]);
  });
});
