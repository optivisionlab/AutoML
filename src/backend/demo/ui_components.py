# Standard Libraries
import html
from typing import Any


EMPTY_DATASET_HTML = """
<div class="empty-state-card">
    <div class="empty-state-icon-tag">DATASET METADATA</div>
    <div class="empty-state-title">No Dataset Loaded</div>
    <div class="empty-state-desc">Select a benchmark dataset from the UCI Repository and click <strong>Load Dataset</strong> to inspect samples, features, and evaluation tier.</div>
</div>
"""

EMPTY_RESULTS_HTML = """
<div class="empty-state-card">
    <div class="empty-state-icon-tag">AWAITING TRAINING</div>
    <div class="empty-state-title">No Results Yet</div>
    <div class="empty-state-desc">Choose your primary optimization metric and click <strong>Start Distributed Training</strong> to train multiple ML models in parallel on PyMapReduce.</div>
</div>
"""


def render_training_in_progress_html(metric_sort: str = "accuracy", problem_type: str = "classification") -> str:
    """
    Render visual in-progress indicator when training is running
    """
    models_text = (
        "LinearRegression, RandomForest, GradientBoosting, XGBoost, Ridge, Lasso, SVR, KNeighbors"
        if problem_type == "regression"
        else "LogisticRegression, RandomForest, DecisionTree, SVC, GaussianNB, KNeighbors, XGBoost"
    )
    return f"""
    <div class="champion-card" style="border-color: #818cf8; background: linear-gradient(135deg, rgba(99, 102, 241, 0.06) 0%, rgba(168, 85, 247, 0.06) 100%);">
        <div class="champion-header">
            <div class="champion-title-wrap">
                <span class="champion-tag" style="background: linear-gradient(135deg, #6366f1, #8b5cf6);">TRAINING IN PROGRESS</span>
                <div class="champion-name" style="font-size: 20px; color: #4338ca;">Distributed PyMapReduce Tasks Running...</div>
            </div>
            <div class="champion-score-wrap">
                <div class="champion-score-label">Optimizing For</div>
                <div class="champion-score-val" style="font-size: 20px;">{html.escape(metric_sort.upper())}</div>
            </div>
        </div>
        <div style="padding: 20px 0; text-align: center; color: #64748b; font-size: 14px;">
            <div style="display: inline-block; margin-bottom: 6px; font-weight: 500;">Parallel Model Training & {html.escape(problem_type.capitalize())} Cross-Validation across CPU worker threads...</div>
            <div style="font-size: 12px; color: #94a3b8;">Models being tuned: {html.escape(models_text)}</div>
        </div>
    </div>
    """


def render_dataset_overview_html(
    title: str,
    desc: str,
    n_rows: int,
    n_cols: int,
    target_col: str,
    cv_tier: int,
    cv_desc: str,
    problem_type: str = "classification"
) -> str:
    clean_title = title.replace("### Dataset: ", "").strip()
    badge_class = "dataset-type-regression" if problem_type == "regression" else "dataset-type-badge"
    return f"""
    <div class="dataset-card">
        <div class="dataset-card-header">
            <div>
                <div class="dataset-badge-tag">UCI REPOSITORY</div>
                <div class="dataset-title">{html.escape(clean_title)}</div>
            </div>
            <span class="{badge_class}">{html.escape(problem_type.capitalize())}</span>
        </div>
        
        <div class="stat-grid">
            <div class="stat-item">
                <span class="stat-label">Total Samples</span>
                <span class="stat-value">{n_rows:,}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Features</span>
                <span class="stat-value">{n_cols - 1}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Target Column</span>
                <span class="stat-value target-pill">{html.escape(str(target_col))}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">CV Strategy</span>
                <span class="stat-value">Tier {cv_tier}</span>
            </div>
        </div>

        <div class="cv-badge-container">
            <div class="cv-badge-header">
                <span class="cv-badge-label">Auto-detected Evaluation Strategy</span>
            </div>
            <div class="cv-badge-desc">{html.escape(cv_desc)}</div>
        </div>

        <div class="dataset-desc-box">
            <div class="desc-label">About Dataset</div>
            <div class="desc-content">{html.escape(desc or 'No description provided.')}</div>
        </div>
    </div>
    """


def render_champion_card_html(
    best_model_name: str,
    primary_metric: str,
    primary_score: float,
    all_scores: dict[str, float],
    best_params: dict[str, Any],
    cv_strategy_desc: str,
    total_elapsed: float,
    n_models: int,
    problem_type: str = "classification"
) -> str:
    # Build hyperparameter pills
    param_pills_html = "".join([
        f'<span class="param-pill"><strong>{html.escape(str(k))}</strong>: {html.escape(str(v))}</span>'
        for k, v in best_params.items()
    ]) if best_params else '<span class="param-pill">Default parameters</span>'

    # Format metric cards according to problem type
    if problem_type == "regression":
        metrics_to_show = ["r2", "mse", "mae", "rmse", "mape"]
    else:
        metrics_to_show = ["accuracy", "f1", "precision", "recall"]

    metric_cards_html = ""
    for m in metrics_to_show:
        if m in all_scores:
            val = all_scores.get(m, 0.0)
            is_primary = (m == primary_metric.lower().strip())
            primary_class = "metric-card-primary" if is_primary else ""
            metric_cards_html += f"""
            <div class="metric-card {primary_class}">
                <div class="metric-name">{m.upper()}{' (PRIMARY)' if is_primary else ''}</div>
                <div class="metric-num">{val:.4f}</div>
            </div>
            """

    return f"""
    <div class="champion-card">
        <div class="champion-header">
            <div class="champion-title-wrap">
                <span class="champion-tag">BEST PERFORMING MODEL ({html.escape(problem_type.upper())})</span>
                <div class="champion-name">{html.escape(best_model_name)}</div>
            </div>
            <div class="champion-score-wrap">
                <div class="champion-score-label">Primary Metric ({html.escape(primary_metric.upper())})</div>
                <div class="champion-score-val">{primary_score:.4f}</div>
            </div>
        </div>

        <div class="metric-cards-grid">
            {metric_cards_html}
        </div>

        <div class="hyperparam-section">
            <div class="section-subtitle">Optimal Hyperparameters (GridSearchCV Selection)</div>
            <div class="param-pills-container">
                {param_pills_html}
            </div>
        </div>

        <div class="champion-footer">
            <div class="footer-meta-item">Distributed Engine: <strong>PyMapReduce</strong></div>
            <div class="footer-meta-item">Evaluated: <strong>{n_models} Models</strong></div>
            <div class="footer-meta-item">CV Tier: <strong>{html.escape(cv_strategy_desc.split(':')[0])}</strong></div>
            <div class="footer-meta-item">Duration: <strong>{total_elapsed:.2f}s</strong></div>
        </div>
    </div>
    """
