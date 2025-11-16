# Requirements Document

## Introduction

Tài liệu này mô tả yêu cầu cho việc tạo tài liệu kiến trúc Design Patterns của hệ thống HAutoML, tập trung vào cơ chế chuyển đổi linh hoạt giữa các thuật toán tìm kiếm (Grid Search, Genetic Algorithm, Bayesian Search). Mục tiêu là cung cấp sơ đồ kiến trúc rõ ràng và giải thích chi tiết về cách hệ thống áp dụng các design patterns để đạt được tính linh hoạt và khả năng mở rộng.

## Glossary

- **HAutoML System**: Hệ thống Automated Machine Learning cho phép người dùng huấn luyện mô hình học máy tự động
- **Search Strategy**: Chiến lược tìm kiếm siêu tham số cho mô hình học máy
- **Factory Pattern**: Mẫu thiết kế tạo đối tượng mà không chỉ định lớp cụ thể
- **Strategy Pattern**: Mẫu thiết kế cho phép chọn thuật toán tại runtime
- **SearchStrategyFactory**: Component tạo các Search Strategy instance
- **Grid Search**: Thuật toán tìm kiếm toàn diện trong không gian siêu tham số
- **Genetic Algorithm**: Thuật toán tìm kiếm dựa trên tiến hóa
- **Bayesian Search**: Thuật toán tìm kiếm dựa trên tối ưu hóa Bayesian

## Requirements

### Requirement 1

**User Story:** Là một developer, tôi muốn hiểu rõ kiến trúc Design Patterns của hệ thống, để có thể bảo trì và mở rộng code một cách hiệu quả

#### Acceptance Criteria

1. THE HAutoML System SHALL cung cấp sơ đồ kiến trúc Mermaid minh họa Factory Pattern và Strategy Pattern
2. THE HAutoML System SHALL cung cấp sơ đồ class diagram thể hiện mối quan hệ giữa SearchStrategyFactory và các Search Strategy
3. THE HAutoML System SHALL cung cấp sơ đồ sequence diagram minh họa luồng tạo và sử dụng Search Strategy
4. THE HAutoML System SHALL cung cấp giải thích chi tiết về vai trò của từng component trong kiến trúc

### Requirement 2

**User Story:** Là một developer, tôi muốn hiểu cơ chế chuyển đổi giữa các thuật toán tìm kiếm, để có thể thêm thuật toán mới hoặc tùy chỉnh thuật toán hiện có

#### Acceptance Criteria

1. WHEN người dùng chỉ định tên thuật toán, THE SearchStrategyFactory SHALL tạo instance của Search Strategy tương ứng
2. THE SearchStrategyFactory SHALL hỗ trợ nhiều alias cho mỗi thuật toán (ví dụ: "grid", "Grid", "GridSearch")
3. THE HAutoML System SHALL cung cấp sơ đồ flow chart minh họa quy trình chuyển đổi từ tên thuật toán sang Strategy instance
4. THE HAutoML System SHALL cung cấp ví dụ code minh họa cách thêm thuật toán mới vào hệ thống

### Requirement 3

**User Story:** Là một developer, tôi muốn hiểu cách các Search Strategy được sử dụng trong quá trình training, để có thể tối ưu hóa hiệu suất hoặc debug khi có lỗi

#### Acceptance Criteria

1. THE HAutoML System SHALL cung cấp sơ đồ activity diagram minh họa quy trình training với Search Strategy
2. THE HAutoML System SHALL giải thích cách mỗi Search Strategy thực hiện tìm kiếm siêu tham số
3. THE HAutoML System SHALL cung cấp so sánh ưu nhược điểm của từng thuật toán tìm kiếm
4. THE HAutoML System SHALL cung cấp ví dụ cấu hình cho từng loại thuật toán

### Requirement 4

**User Story:** Là một architect, tôi muốn hiểu toàn bộ kiến trúc hệ thống từ API đến Training Engine, để có thể đưa ra quyết định thiết kế phù hợp

#### Acceptance Criteria

1. THE HAutoML System SHALL cung cấp sơ đồ component diagram thể hiện các module chính và mối quan hệ giữa chúng
2. THE HAutoML System SHALL cung cấp sơ đồ deployment diagram cho kiến trúc phân tán với Worker nodes
3. THE HAutoML System SHALL giải thích cách MapReduce pattern được áp dụng trong distributed training
4. THE HAutoML System SHALL cung cấp sơ đồ data flow từ API request đến training result
