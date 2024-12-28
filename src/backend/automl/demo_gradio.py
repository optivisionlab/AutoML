import pandas as pd
import json
from automl.engine import get_config, train_process
import gradio as gr


def gradio_train_local(file_data, file_config):
    data = pd.read_csv(file_data)
    with open(file_config.name, 'r') as f:
        choose, list_model_search, list_feature, target, matrix, models = get_config(f)
    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_model_search, list_feature, target, matrix, models
    )

    # Chuyển best_params thành chuỗi JSON dễ đọc
    best_params_str = json.dumps(best_params, indent=2)

    # Chuẩn bị dữ liệu cho bảng
    result_df = pd.DataFrame({
        "Model ID": [best_model_id],
        "Model Name": [str(best_model)],
        "Best Score": [best_score],
        "Best Params": [best_params_str]
    })

    # Chuyển model_scores thành DataFrame
    model_scores_df = pd.DataFrame.from_dict(model_scores, orient="index", columns=["Score"])
    model_scores_df.reset_index(inplace=True)
    model_scores_df.columns = ["Model Name", "Score"]

    return result_df, model_scores_df


def run_gradio_demo():
    interface = gr.Interface(
        fn=gradio_train_local,
        inputs=[
            gr.File(label="Upload Data CSV File"),
            gr.File(label="Upload Config File")
        ],
        outputs=[
            gr.DataFrame(label="Best Model Information"),
            gr.DataFrame(label="All Model Scores")
        ]
    )
    interface.launch()


if __name__ == "__main__":
    run_gradio_demo()
