# Third-party Libraries
import gradio as gr

# Local Libraries
from demo.config import AVAILABLE_DATASETS
from demo.data_fetcher import fetch_uci_dataset


# ================= CÁC HÀM XỬ LÝ SỰ KIỆN =================

def on_fetch_clicked(dataset_choice):
    """Sự kiện khi bấm nút Kéo dữ liệu"""
    title, desc, df_preview, df_full = fetch_uci_dataset(dataset_choice)
    
    # Nếu df_full không None (tức là kéo thành công), thì mở khóa nút Train
    is_ready = df_full is not None
    
    return title, desc, df_preview, df_full, gr.update(interactive=is_ready)

def on_train_clicked(df_full):
    """
    Sự kiện khi bấm nút Huấn luyện.
    (Tạm thời in log. Tương lai sẽ import hàm xử lý thật từ src/ vào đây)
    """
    if df_full is None or df_full.empty:
        return "Lỗi: Không tìm thấy dữ liệu trên RAM!"
    
    rows, cols = df_full.shape
    
    # --- TODO TƯƠNG LAI: Import từ thư mục src/ ---
    # from src.ml_core.pipeline import auto_train
    # model, accuracy = auto_train(df_full)
    # ----------------------------------------------
    
    return f"[PLACEHOLDER] Sẵn sàng chuyển {rows} dòng & {cols} cột này vào thư mục src/ để tiền xử lý và huấn luyện thực tế!"

# ================= GIAO DIỆN UI GRADIO =================

with gr.Blocks(theme=gr.themes.Soft(), title="HAutoML Demo") as demo:
    gr.Markdown("# 🚀 HAutoML Demo: Tự động tải dữ liệu UCI")
    
    # Thanh RAM ảo để lưu dataframe
    ram_dataset_state = gr.State(None) 
    
    with gr.Row():
        # CỘT TRÁI: Thao tác
        with gr.Column(scale=1):
            uci_dropdown = gr.Dropdown(
                choices=AVAILABLE_DATASETS, 
                label="Chọn UCI Dataset (Chỉ hỗ trợ dữ liệu Bảng)", 
                value=AVAILABLE_DATASETS[0]
            )
            fetch_btn = gr.Button("⬇️ Tải Dữ Liệu", variant="primary")
            
            gr.Markdown("---")
            train_btn = gr.Button("⚙️ Huấn luyện Mô hình", variant="secondary", interactive=False)
            train_result = gr.Textbox(label="Kết quả từ hệ thống lõi", lines=4)
            
        # CỘT PHẢI: Hiển thị
        with gr.Column(scale=2):
            ds_title = gr.Markdown("### Tên Dataset: Chưa có dữ liệu")
            ds_desc = gr.Textbox(label="Mô tả tóm tắt", interactive=False)
            ds_table = gr.Dataframe(label="Dữ liệu xem trước (15 dòng đầu)", max_height=350)

    # --- Kết nối UI với Hàm logic ---
    fetch_btn.click(
        fn=on_fetch_clicked,
        inputs=[uci_dropdown],
        outputs=[ds_title, ds_desc, ds_table, ram_dataset_state, train_btn]
    )
    
    train_btn.click(
        fn=on_train_clicked,
        inputs=[ram_dataset_state],
        outputs=[train_result]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860) # Mở cổng cố định để dễ quản lý
