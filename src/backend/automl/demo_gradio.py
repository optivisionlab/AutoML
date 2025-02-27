import pandas as pd
import json
from automl.engine import get_config, train_process
import gradio as gr
from pathlib import Path


def read_markdown_file(file_path):  #<-- Function to convert file to str
    with open(file_path, 'r', encoding='utf-8') as file:
        markdown_string = file.read()
    return markdown_string


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

def run_gradio_demo(desc):
    interface = gr.Interface(
        title="HAutoML : Opensouce for Automated Machine Learning by SICT - HaUI",
        description=desc,
        fn=gradio_train_local,
        inputs=[
            gr.File(label="Upload Data CSV File"),
            gr.File(label="Upload Config File")
        ],
        outputs=[
            gr.DataFrame(label="Best Model Information"),
            gr.DataFrame(label="All Model Scores")
        ],
        examples=[
            ["assets/iris.data.csv", "assets/config-data-iris.yaml"],
        ]
    )
    interface.launch(share=True, debug=True, server_name="0.0.0.0")

if __name__ == "__main__":
    desc_md = Path("assets/desc.md") #<-- Path to file with description written in Markdown
    run_gradio_demo(desc=read_markdown_file(desc_md))
