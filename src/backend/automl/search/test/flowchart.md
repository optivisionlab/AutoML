```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#ffffff', 'primaryTextColor': '#000000', 'primaryBorderColor': '#000000', 'lineColor': '#000000', 'secondaryColor': '#f9f9f9', 'tertiaryColor': '#ffffff'}}}%%
flowchart TD
    A[Bắt đầu] --> B["Khởi tạo cấu hình<br/>population_size=100<br/>generation=50<br/>mutation_rate=0.5<br/>crossover_rate=0.8<br/>elite_size=2<br/>tournament_size=5"]
    B --> C["Mã hóa tham số<br/>_encode_parameters"]
    C --> D{"Loại tham số?"}
    D -->|Categorical| E["Chuyển thành chỉ số<br/>0, 1, 2, ..."]
    D -->|Integer/Continuous| F["Giữ khoảng<br/>(min, max)"]
    E --> G["Tạo quần thể ban đầu<br/>100 cá thể ngẫu nhiên"]
    F --> G
    G --> H["Khởi tạo biến<br/>best_individual = None<br/>best_score = -∞<br/>generation = 0"]
    H --> I{generation < 50?}
    I -->|Không| Z[Kết thúc]
    I -->|Có| J["Đánh giá từng cá thể<br/>trong quần thể"]
    J --> K[Lấy cá thể tiếp theo]
    K --> L["_Giải mã tham số<br/>_decode_individual"]
    L --> M["Huấn luyện model<br/>với tham số đã giải mã"]
    M --> N["Tính toán metrics<br/>accuracy, precision<br/>recall, f1"]
    N --> O[Lưu điểm fitness]
    O --> P{Còn cá thể nào?}
    P -->|Có| K
    P -->|Không| Q["Tìm cá thể tốt nhất<br/>trong thế hệ hiện tại"]
    Q --> R{Tốt hơn best_score?}
    R -->|Có| S["Cập nhật<br/>best_individual<br/>best_score"]
    R -->|Không| T["Ghi nhận thế hệ<br/>vào generation_history"]
    S --> T
    T --> U[Tạo thế hệ mới]
    U --> V["ELITISM<br/>Giữ lại 2 cá thể tốt nhất"]
    V --> W{Đủ quần thể mới?}
    W -->|Có| AA[generation++]
    W -->|Không| X["SELECTION<br/>Tournament Selection<br/>Chọn 2 cha mẹ"]
    X --> Y["CROSSOVER<br/>Lai ghép với xác suất 80%<br/>Tạo 2 con"]
    Y --> BB["MUTATION<br/>Đột biến với xác suất 50%"]
    BB --> CC{Loại tham số?}
    CC -->|Categorical| DD["Chọn giá trị<br/>ngẫu nhiên mới"]
    CC -->|Continuous/Integer| EE["Thêm nhiễu Gaussian<br/>±30% khoảng giá trị"]
    DD --> FF["Thêm con vào<br/>quần thể mới"]
    EE --> FF
    FF --> W
    AA --> I
    Z --> GG["Giải mã best_individual<br/>thành best_params"]
    GG --> HH["Tạo cv_results<br/>với tất cả cá thể đã thử"]
    HH --> II["Lưu generation_history<br/>vào file CSV"]
    II --> JJ["Trả về<br/>best_params, best_score, cv_results"]
    style A fill:#e1f5fe
    style Z fill:#e8f5e8
    style JJ fill:#e8f5e8
    style V fill:#fff3e0
    style X fill:#fce4ec
    style Y fill:#f3e5f5
    style BB fill:#e0f2f1