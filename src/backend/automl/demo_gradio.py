import pandas as pd
import json
from automl.engine import get_config, train_process
import gradio as gr

def gradio_train_local(file_data, file_config):
    # Đọc dữ liệu từ file CSV
    data = pd.read_csv(file_data)
    
    # Đọc file cấu hình và lấy thông tin cần thiết
    with open(file_config.name, 'r') as f:
        choose, list_feature, target, matrix, matrix_sort, models = get_config(f)
    
    # Huấn luyện và lấy kết quả mô hình
    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_feature, target, matrix, matrix_sort , models
    )
    
    # Tạo bảng kết quả cho từng mô hình theo từng metric
    model_results = []
    for result in model_scores:
        model_name = result["model_name"]
        scores = result["scores"]
        row = {"Model": model_name}
        for metric in matrix:
            row[metric] = scores.get(metric, 'N/A')  # Thêm điểm số của từng metric vào bảng
        model_results.append(row)
    
    # Tạo DataFrame cho kết quả của từng model
    model_results_df = pd.DataFrame(model_results)
    best_params_str = json.dumps(best_params, indent=2)
    # Trả về bảng thông tin về mô hình tốt nhất và bảng kết quả của các mô hình
    best_model_info = {
        "Best Model ID": best_model_id,
        "Best Model Name": best_model.__class__.__name__,
        "Best Score": best_score,
        "Best Params": best_params_str
    }

    # Trả về thông tin mô hình tốt nhất và bảng kết quả của tất cả các mô hình
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
