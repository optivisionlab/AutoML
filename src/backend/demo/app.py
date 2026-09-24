# Standard Libraries
import gc
import sys
import time
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Third-party Libraries
import gradio as gr
import pandas as pd

# Local Libraries
from demo.config import (
    CLASSIFICATION_DATASETS,
    REGRESSION_DATASETS
)
from demo.data_fetcher import fetch_uci_dataset
from demo.ui_components import (
    EMPTY_DATASET_HTML,
    EMPTY_RESULTS_HTML,
    render_training_in_progress_html,
    render_dataset_overview_html,
    render_champion_card_html,
)
from src.shared import search_space
from src.modules.models.service import LOWER_IS_BETTER_METRICS
from src.modules.preprocessing.service import TabularPreprocessor
from src.modules.trainings.service import TrainingService


# Logging
logger = logging.getLogger("demo_app")


# Load Custom CSS from external style.css
CSS_PATH = Path(__file__).resolve().parent / "style.css"
CUSTOM_CSS = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.exists() else ""


def on_problem_type_change(problem_type: str):
    """
    Handle event when user switches between Classification and Regression.
    Updates available datasets, primary metric options, and resets state to free memory.
    """
    is_regression = (problem_type.lower() == "regression")
    datasets = REGRESSION_DATASETS if is_regression else CLASSIFICATION_DATASETS
    metrics = search_space.REGRESSION_METRIC_LIST if is_regression else search_space.CLASSIFICATION_METRIC_LIST
    default_metric = "r2" if is_regression else "accuracy"
    default_dataset = datasets[0] if datasets else None

    # Free memory from previous dataset / model artifacts
    gc.collect()

    return (
        gr.update(choices=datasets, value=default_dataset),
        gr.update(choices=metrics, value=default_metric),
        None,  # Reset dataset_state
        gr.update(interactive=False),  # Disable train button
        f"Switched to {problem_type}. Please click 'Load Dataset' to fetch data from UCI Repository.",
        EMPTY_DATASET_HTML,
        pd.DataFrame(),
        EMPTY_RESULTS_HTML,
        gr.update(visible=False),
        {},
    )


def on_dataset_change(dataset_choice: str):
    """
    Handle event when user changes dataset in dropdown.
    """
    # Free memory from previously held dataframes
    gc.collect()

    clean_title = dataset_choice.split(" - ")[0] if dataset_choice and " - " in dataset_choice else (dataset_choice or "Dataset")
    return (
        None,  # Reset dataset_state so user cannot train stale data
        gr.update(interactive=False),  # Disable train button
        f"Selected '{clean_title}'. Please click 'Load Dataset' to fetch data from UCI Repository.",
        EMPTY_DATASET_HTML,
        pd.DataFrame(),
        EMPTY_RESULTS_HTML,
        gr.update(visible=False),
        {},
    )


def on_dataset_select(dataset_choice: str, problem_type: str, progress: gr.Progress = gr.Progress()):
    """
    Handle event when user clicks 'Load Dataset' to download and process data from UCI Repository.
    """
    if not dataset_choice:
        return (
            EMPTY_DATASET_HTML,
            pd.DataFrame(),
            None,
            gr.update(interactive=False),
            "Please select a dataset to load.",
            EMPTY_RESULTS_HTML,
            gr.update(visible=False),
            {},
        )

    progress(0.2, desc="Downloading dataset from UCI Machine Learning Repository...")
    title, desc, df_preview, df_full = fetch_uci_dataset(dataset_choice)
    if df_full is None or df_full.empty:
        return (
            EMPTY_DATASET_HTML,
            pd.DataFrame(),
            None,
            gr.update(interactive=False),
            f"Failed to load dataset '{dataset_choice}' from UCI repository. Please check your network connection.",
            EMPTY_RESULTS_HTML,
            gr.update(visible=False),
            {},
        )

    progress(0.7, desc="Calculating summary statistics and evaluation tier...")
    n_rows, n_cols = df_full.shape
    target_col = df_full.columns[-1]

    # Automatically determine CV strategy according to dataset size and problem type
    prob_type_clean = problem_type.lower()
    cv_config = TabularPreprocessor.determine_cv_tier(n_rows, problem_type=prob_type_clean)

    # Render rich HTML dataset card
    dataset_overview_html = render_dataset_overview_html(
        title=title,
        desc=desc,
        n_rows=n_rows,
        n_cols=n_cols,
        target_col=target_col,
        cv_tier=cv_config.tier,
        cv_desc=cv_config.description,
        problem_type=prob_type_clean,
    )

    clean_title = title.replace("### Dataset: ", "").strip()
    status_text = f"Loaded '{clean_title}' ({n_rows:,} rows, {n_cols - 1} features) for {problem_type}. Ready for training."
    progress(1.0, desc="Dataset ready.")

    return (
        dataset_overview_html,
        df_preview,
        df_full,
        gr.update(interactive=True),
        status_text,
        EMPTY_RESULTS_HTML,
        gr.update(visible=False),
        {},
    )


async def execute_demo_training(
    df_full: pd.DataFrame,
    metric_sort: str,
    problem_type: str,
    progress: gr.Progress = gr.Progress(),
):
    """
    Execute distributed AutoML training pipeline using PyMapReduce via TrainingService.
    """
    if df_full is None or df_full.empty:
        yield (
            EMPTY_RESULTS_HTML,
            pd.DataFrame(),
            gr.update(visible=False),
            {},
            "Please select a dataset and click 'Load Dataset' before starting training."
        )
        return

    prob_type_clean = problem_type.lower()

    try:
        # Immediate UI Yield: Visual feedback confirming training started
        yield (
            render_training_in_progress_html(metric_sort, problem_type=prob_type_clean),
            pd.DataFrame(),
            gr.update(visible=False),
            {"status": "IN_PROGRESS", "metric": metric_sort, "problem_type": prob_type_clean},
            f"Training started... Preprocessing data and dispatching parallel PyMapReduce tasks for {metric_sort.upper()} optimization ({problem_type})."
        )

        progress(0.15, desc="Preprocessing tabular features and encoding data...")
        start_time = time.time()
        logger.info(f"Starting distributed AutoML pipeline on PyMapReduce for {problem_type}...")

        progress(0.40, desc="Training candidate models in parallel on PyMapReduce...")
        target_col = str(df_full.columns[-1])
        pipeline_result = await TrainingService.train_automl_pipeline(
            df=df_full,
            target_col=target_col,
            metric_sort=metric_sort,
            problem_type=prob_type_clean,
        )

        progress(0.85, desc="Evaluating cross-validation metrics and ranking models...")
        total_elapsed = time.time() - start_time

        # Sort model scores based on whether lower or higher is better
        normalized_metric = metric_sort.strip().lower().replace(" ", "_")
        is_lower_better = normalized_metric in LOWER_IS_BETTER_METRICS

        sorted_scores = sorted(
            pipeline_result.model_scores,
            key=lambda x: x.scores.get(normalized_metric, float("inf") if is_lower_better else -float("inf")),
            reverse=not is_lower_better,
        )

        # Format Wide Leaderboard DataFrame
        metric_pool = (
            search_space.REGRESSION_METRIC_LIST
            if prob_type_clean == "regression"
            else search_space.CLASSIFICATION_METRIC_LIST
        )

        leaderboard_rows = []
        for idx, r in enumerate(sorted_scores):
            primary_val = r.scores.get(normalized_metric, 0.0)
            row = {
                "Rank": f"#{idx + 1}",
                "Model Name": r.model_name,
                f"{metric_sort.upper()} (Primary)": f"{primary_val:.4f}",
            }
            for m in metric_pool:
                m_key = m.strip().lower().replace(" ", "_")
                if m_key != normalized_metric and m_key in r.scores:
                    row[m.upper()] = f"{r.scores[m_key]:.4f}"
            leaderboard_rows.append(row)

        leaderboard_df = pd.DataFrame(leaderboard_rows)

        # Extract Champion Model details
        best_model_name = pipeline_result.best_model
        best_score = pipeline_result.best_score
        best_params = pipeline_result.best_params
        best_entry = next((s for s in pipeline_result.model_scores if s.model_name == best_model_name), None)
        all_scores = best_entry.scores if best_entry else {}

        # Render Champion Hero Card HTML
        champion_html = render_champion_card_html(
            best_model_name=best_model_name,
            primary_metric=metric_sort,
            primary_score=best_score,
            all_scores=all_scores,
            best_params=best_params,
            cv_strategy_desc=pipeline_result.cv_strategy.description,
            total_elapsed=total_elapsed,
            n_models=len(sorted_scores),
            problem_type=prob_type_clean,
        )

        # Prepare raw JSON summary for inspection tab
        raw_json_summary = {
            "status": "COMPLETED",
            "problem_type": prob_type_clean,
            "best_model": best_model_name,
            "primary_metric": f"{metric_sort.upper()} = {best_score:.4f}",
            "all_metrics": {k: round(v, 4) for k, v in all_scores.items()},
            "best_hyperparameters": best_params,
            "cv_strategy": pipeline_result.cv_strategy.description,
            "distributed_engine": "PyMapReduce (Task Parallelism - Multi-core Local Cluster)",
            "total_latency_seconds": round(total_elapsed, 2)
        }

        progress(1.0, desc="AutoML training finished.")
        status_msg = f"Distributed {problem_type} training completed in {total_elapsed:.2f}s across {len(sorted_scores)} models."

        # Final UI Yield: Completed champion card and wide leaderboard
        yield champion_html, leaderboard_df, gr.update(visible=True), raw_json_summary, status_msg

    except Exception as e:
        logger.error(f"Error during demo training execution: {e}", exc_info=True)
        error_html = f"""
        <div class="glass-card" style="border: 1px solid #f87171; background: #fef2f2; color: #991b1b; padding: 20px; border-radius: 12px;">
            <div style="font-weight: 700; font-size: 16px; margin-bottom: 8px;">Training Execution Interrupted</div>
            <div style="font-size: 13px; font-family: monospace; line-height: 1.5;">{str(e)}</div>
        </div>
        """
        yield (
            error_html,
            pd.DataFrame(),
            gr.update(visible=False),
            {"error": str(e)},
            f"Training failed or was interrupted: {str(e)}"
        )
    finally:
        # Explicitly release references and free memory
        gc.collect()


# GRADIO UI DEFINITION
with gr.Blocks(title="HAutoML ToolKit") as demo:
    # Header Centered
    with gr.Row(elem_classes=["main-header"]):
        with gr.Column():
            gr.HTML(
                """
                <div style="text-align: center;">
                    <div class="brand-title">HAutoML ToolKit</div>
                    <div class="brand-subtitle">Distributed AutoML Pipeline for Tabular Data and Parallel Hyperparameter Tuning</div>
                    <div class="badge-row">
                        <span class="tech-badge badge-purple">PyMapReduce Engine</span>
                        <span class="tech-badge badge-blue">Classification and Regression</span>
                        <span class="tech-badge badge-emerald">Continuous Stratified CV</span>
                    </div>
                </div>
                """
            )

    # Full DataFrame State Storage
    dataset_state = gr.State(None)

    # Main 2-Column Dashboard Layout
    with gr.Row(elem_classes=["main-dashboard-row"]):
        with gr.Column(scale=4, min_width=380, elem_classes=["glass-card"]):
            gr.HTML('<div class="section-title"><span class="step-num">1</span> Problem Objective</div>')
            problem_type_selector = gr.Radio(
                choices=["Classification", "Regression"],
                value="Classification",
                label="Machine Learning Problem Type",
                elem_classes=["problem-type-radio"]
            )

            gr.HTML('<div class="section-title" style="margin-top: 16px;"><span class="step-num">2</span> Benchmark Data Source</div>')
            dataset_dropdown = gr.Dropdown(
                choices=CLASSIFICATION_DATASETS,
                label="Select benchmark dataset from UCI Repository",
                value=CLASSIFICATION_DATASETS[0]
            )
            load_btn = gr.Button("Load Dataset", variant="secondary", elem_classes=["btn-secondary-action"])

            gr.HTML('<div class="section-title" style="margin-top: 20px;"><span class="step-num">3</span> Training Settings</div>')
            metric_selector = gr.Dropdown(
                choices=search_space.CLASSIFICATION_METRIC_LIST,
                label="Primary Optimization Metric",
                value="accuracy"
            )

            train_btn = gr.Button("Start Distributed Training", variant="primary", interactive=False, elem_classes=["btn-primary-action"])
            status_output = gr.Textbox(
                label="System Status",
                value="Select a dataset and click 'Load Dataset' to fetch data from UCI Repository...",
                interactive=False,
                lines=1,
                elem_classes=["status-box"]
            )

            # Dataset Overview Rich Card
            dataset_overview_html = gr.HTML(value=EMPTY_DATASET_HTML)

        with gr.Column(scale=7, elem_classes=["glass-card"]):
            with gr.Tabs():
                with gr.TabItem("AutoML Leaderboard and Champion Model"):
                    champion_model_html = gr.HTML(value=EMPTY_RESULTS_HTML)

                    # Hidden initially until training finishes
                    with gr.Column(visible=False) as leaderboard_section:
                        gr.HTML('<div class="section-title" style="margin-top: 14px; margin-bottom: 12px;">Model Comparison Leaderboard</div>')
                        leaderboard_table = gr.Dataframe(
                            show_label=False,
                            interactive=False,
                            wrap=False,
                            elem_classes=["custom-dataframe"]
                        )

                with gr.TabItem("Data Exploration and Preview"):
                    gr.HTML('<div class="section-title" style="margin-top: 14px; margin-bottom: 14px;">First 15 Rows Preview</div>')
                    data_preview_table = gr.Dataframe(
                        show_label=False,
                        wrap=False,
                        max_height=650,
                        elem_classes=["custom-dataframe"]
                    )

                with gr.TabItem("Pipeline Metadata and Raw JSON"):
                    raw_json_output = gr.JSON(label="Pipeline Execution Metadata and Hyperparameters")

    # EVENT HANDLERS
    problem_type_selector.change(
        fn=on_problem_type_change,
        inputs=[problem_type_selector],
        outputs=[
            dataset_dropdown,
            metric_selector,
            dataset_state,
            train_btn,
            status_output,
            dataset_overview_html,
            data_preview_table,
            champion_model_html,
            leaderboard_section,
            raw_json_output,
        ]
    )

    dataset_dropdown.change(
        fn=on_dataset_change,
        inputs=[dataset_dropdown],
        outputs=[
            dataset_state,
            train_btn,
            status_output,
            dataset_overview_html,
            data_preview_table,
            champion_model_html,
            leaderboard_section,
            raw_json_output
        ]
    )

    load_btn.click(
        fn=on_dataset_select,
        inputs=[dataset_dropdown, problem_type_selector],
        outputs=[
            dataset_overview_html,
            data_preview_table,
            dataset_state,
            train_btn,
            status_output,
            champion_model_html,
            leaderboard_section,
            raw_json_output
        ]
    )

    train_btn.click(
        fn=execute_demo_training,
        inputs=[dataset_state, metric_selector, problem_type_selector],
        outputs=[
            champion_model_html,
            leaderboard_table,
            leaderboard_section,
            raw_json_output,
            status_output
        ]
    )


# APPLICATION LAUNCHER
def cleanup_demo_session():
    """
    Clean up temporary demo WAL session logs and free RAM upon launch and exit
    """
    import os
    for p in ["/tmp/wal.log", "/tmp/pymapreduce/snapshot.bin", "/tmp/pymapreduce/snapshot.bin.tmp"]:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
    gc.collect()


if __name__ == "__main__":
    cleanup_demo_session()
    PORT = 7860
    logger.info(f"Starting HAutoML ToolKit Demo at http://127.0.0.1:{PORT}...")
    try:
        demo.launch(
            server_name="127.0.0.1",
            server_port=PORT,
            theme=gr.themes.Base(),
            css=CUSTOM_CSS,
            inbrowser=True
        )
    finally:
        cleanup_demo_session()
