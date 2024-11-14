import pandas as pd
from automl.engine import get_config, train_process
import gradio as gr


def gradio_train_local(file_data, file_config):
    data = pd.read_csv(file_data)
    with open(file_config.name, 'r') as f:
        choose, list_model_search, list_feature, target, matrix, models = get_config(f)
    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_model_search, list_feature, target, matrix, models
    )

    return {
        "best_model_id": best_model_id,
        "best_model": str(best_model),
        "best_params": best_params,
        "best_score": best_score,
        "orther_model_scores": model_scores
    }


def run_gradio_demo():
    interface = gr.Interface(
        fn=gradio_train_local,
        inputs=[
            gr.File(label="Upload Data CSV File"),
            gr.File(label="Upload Config File")
        ],
        outputs="json"
    )
    interface.launch()

if __name__ == "__main__":
    run_gradio_demo()