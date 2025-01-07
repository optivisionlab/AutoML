import pandas as pd
import json
from automl.engine import get_config, train_process
import gradio as gr

def gradio_train_local(file_data, file_config):
    data = pd.read_csv(file_data)

    with open(file_config.name, 'r') as f:
        choose, list_feature, target, metric_list, metric_sort, models = get_config(f)

    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_feature, target, metric_list, metric_sort , models
    )
    
    model_results = []
    for result in model_scores:
        model_name = result["model_name"]
        scores = result["scores"]
        row = {"Model": model_name}
        for metric in metric_list:
            row[metric] = scores.get(metric, 'N/A')
        model_results.append(row)
    
    model_results_df = pd.DataFrame(model_results)
    best_params_str = json.dumps(best_params, indent=2)
    best_model_info = {
        "Best Model ID": best_model_id,
        "Best Model Name": best_model.__class__.__name__,
        "Best Score": best_score,
        "Best Params": best_params_str
    }
    return pd.DataFrame([best_model_info]), model_results_df

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
