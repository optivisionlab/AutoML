# 📚 Index - Tài Liệu Kiến Trúc Design Patterns

## 📖 Danh Mục Tài Liệu

### 🎯 Tài Liệu Chính

| File | Mô Tả | Đối Tượng | Thời Gian Đọc |
|------|-------|-----------|---------------|
| [README.md](README.md) | Tổng quan và điểm vào chính | Tất cả | 5 phút |
| [requirements.md](requirements.md) | Yêu cầu chức năng chi tiết | Architects, PMs | 10 phút |
| [design.md](design.md) | Thiết kế chi tiết với sơ đồ Mermaid | Developers, Architects | 30 phút |
| [tasks.md](tasks.md) | Danh sách implementation tasks | Developers | 5 phút |

### ⚡ Tài Liệu Tham Khảo Nhanh

| File | Mô Tả | Đối Tượng | Thời Gian Đọc |
|------|-------|-----------|---------------|
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Cheat sheet và code snippets | Developers | 3 phút |
| [VISUAL_GUIDE.md](VISUAL_GUIDE.md) | Sơ đồ ASCII art | Tất cả | 10 phút |
| [INDEX.md](INDEX.md) | File này - danh mục tài liệu | Tất cả | 2 phút |

## 🎓 Learning Path

### Người Mới Bắt Đầu

1. **Bắt đầu**: [README.md](README.md) - Hiểu tổng quan
2. **Hình dung**: [VISUAL_GUIDE.md](VISUAL_GUIDE.md) - Xem sơ đồ đơn giản
3. **Thực hành**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Code examples
4. **Chuyên sâu**: [design.md](design.md) - Chi tiết đầy đủ

### Developer Có Kinh Nghiệm

1. **Quick Start**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
2. **Deep Dive**: [design.md](design.md)
3. **Reference**: Quay lại khi cần

### Architect / Tech Lead

1. **Requirements**: [requirements.md](requirements.md)
2. **Design**: [design.md](design.md)
3. **Overview**: [README.md](README.md)

## 📋 Nội Dung Theo Chủ Đề

### Factory Pattern

- **Tổng quan**: [README.md#factory-pattern](README.md#factory-pattern)
- **Chi tiết**: [design.md#searchstrategyfactory](design.md#1-searchstrategyfactory---factory-pattern-implementation)
- **Code**: [QUICK_REFERENCE.md#tạo-strategy](QUICK_REFERENCE.md#tạo-strategy)
- **Visual**: [VISUAL_GUIDE.md#tổng-quan-kiến-trúc](VISUAL_GUIDE.md#1-tổng-quan-kiến-trúc)

### Strategy Pattern

- **Tổng quan**: [README.md#strategy-pattern](README.md#strategy-pattern)
- **Chi tiết**: [design.md#searchstrategy-interface](design.md#2-searchstrategy-interface---strategy-pattern)
- **Code**: [QUICK_REFERENCE.md#code-snippets](QUICK_REFERENCE.md#code-snippets-quan-trọng)
- **Visual**: [VISUAL_GUIDE.md#strategy-pattern](VISUAL_GUIDE.md#3-strategy-pattern-trong-action)

### Concrete Strategies

#### Grid Search
- **Chi tiết**: [design.md#gridsearchstrategy](design.md#gridsearchstrategy---tìm-kiếm-toàn-diện)
- **Config**: [QUICK_REFERENCE.md#grid-search](QUICK_REFERENCE.md#grid-search-toàn-diện)

#### Genetic Algorithm
- **Chi tiết**: [design.md#geneticalgorithm](design.md#geneticalgorithm---tìm-kiếm-tiến-hóa)
- **Config**: [QUICK_REFERENCE.md#genetic-algorithm](QUICK_REFERENCE.md#genetic-algorithm-nhanh)

#### Bayesian Search
- **Chi tiết**: [design.md#bayesiansearchstrategy](design.md#bayesiansearchstrategy---tìm-kiếm-thông-minh)
- **Config**: [QUICK_REFERENCE.md#bayesian-search](QUICK_REFERENCE.md#bayesian-search-cân-bằng)

### Sơ Đồ

#### Mermaid Diagrams (Chuyên Nghiệp)
- **Architecture**: [design.md#1-tổng-quan](design.md#1-tổng-quan-kiến-trúc-design-patterns)
- **Class Diagram**: [design.md#2-class-diagram](design.md#2-class-diagram---mối-quan-hệ-giữa-các-components)
- **Sequence**: [design.md#3-sequence-diagram](design.md#3-sequence-diagram---luồng-tạo-và-sử-dụng-strategy-tổng-thể)
- **Flow Charts**: [design.md#data-models](design.md#data-models)
- **Deployment**: [design.md#deployment-diagram](design.md#deployment-diagram)

#### ASCII Art (Đơn Giản)
- **Architecture**: [VISUAL_GUIDE.md#1-tổng-quan](VISUAL_GUIDE.md#1-tổng-quan-kiến-trúc)
- **Flow**: [VISUAL_GUIDE.md#2-luồng](VISUAL_GUIDE.md#2-luồng-chuyển-đổi-thuật-toán)
- **Strategy**: [VISUAL_GUIDE.md#3-strategy](VISUAL_GUIDE.md#3-strategy-pattern-trong-action)
- **Distributed**: [VISUAL_GUIDE.md#4-distributed](VISUAL_GUIDE.md#4-distributed-training-với-factory)

### Hướng Dẫn Thực Hành

#### Sử Dụng Hệ Thống
- **Chuyển đổi thuật toán**: [README.md#cách-sử-dụng](README.md#cách-sử-dụng)
- **Config examples**: [QUICK_REFERENCE.md#config-examples](QUICK_REFERENCE.md#config-examples)

#### Mở Rộng Hệ Thống
- **Thêm thuật toán mới**: [design.md#thêm-thuật-toán-mới](design.md#thêm-thuật-toán-mới)
- **Quick guide**: [README.md#thêm-thuật-toán-mới](README.md#thêm-thuật-toán-mới)
- **Code example**: [QUICK_REFERENCE.md#thêm-strategy-mới](QUICK_REFERENCE.md#thêm-strategy-mới-3-bước)

#### Testing & Debugging
- **Unit tests**: [design.md#unit-tests](design.md#unit-tests-cho-factory)
- **Integration tests**: [design.md#integration-tests](design.md#integration-tests-cho-strategy)
- **Debug tips**: [QUICK_REFERENCE.md#debugging-tips](QUICK_REFERENCE.md#debugging-tips)

### Performance

- **So sánh thuật toán**: [design.md#so-sánh](design.md#so-sánh-các-thuật-toán)
- **Optimization tips**: [design.md#optimization-tips](design.md#optimization-tips)
- **Decision tree**: [VISUAL_GUIDE.md#decision-tree](VISUAL_GUIDE.md#decision-tree-chọn-thuật-toán)
- **Visual comparison**: [VISUAL_GUIDE.md#performance](VISUAL_GUIDE.md#performance-comparison-visual)

## 🔍 Tìm Kiếm Nhanh

### Tôi muốn...

#### ...hiểu cách hệ thống hoạt động
→ [README.md](README.md) → [VISUAL_GUIDE.md](VISUAL_GUIDE.md)

#### ...xem code examples
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md) → [design.md](design.md)

#### ...thêm thuật toán mới
→ [README.md#thêm-thuật-toán-mới](README.md#thêm-thuật-toán-mới) → [design.md#extending](design.md#extending-the-system)

#### ...chọn thuật toán phù hợp
→ [README.md#so-sánh](README.md#so-sánh-thuật-toán) → [VISUAL_GUIDE.md#decision-tree](VISUAL_GUIDE.md#decision-tree-chọn-thuật-toán)

#### ...debug lỗi
→ [QUICK_REFERENCE.md#debugging](QUICK_REFERENCE.md#debugging-tips) → [design.md#error-handling](design.md#error-handling)

#### ...xem sơ đồ
→ [VISUAL_GUIDE.md](VISUAL_GUIDE.md) (ASCII) hoặc [design.md](design.md) (Mermaid)

#### ...hiểu design decisions
→ [requirements.md](requirements.md) → [design.md](design.md)

## 📊 Thống Kê Tài Liệu

| Metric | Value |
|--------|-------|
| Tổng số files | 7 |
| Tổng số sơ đồ | 12+ (Mermaid + ASCII) |
| Code examples | 20+ |
| Thời gian đọc tổng | ~65 phút |
| Độ phủ | 100% |

## 🎯 Use Cases

### Use Case 1: Developer mới join team

**Mục tiêu**: Hiểu nhanh kiến trúc và bắt đầu code

**Path**:
1. [README.md](README.md) - 5 phút
2. [VISUAL_GUIDE.md](VISUAL_GUIDE.md) - 10 phút
3. [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - 3 phút
4. Bắt đầu code!

**Tổng thời gian**: 18 phút

### Use Case 2: Thêm thuật toán Random Search

**Mục tiêu**: Extend hệ thống với thuật toán mới

**Path**:
1. [QUICK_REFERENCE.md#thêm-strategy-mới](QUICK_REFERENCE.md#thêm-strategy-mới-3-bước) - Code template
2. [design.md#thêm-thuật-toán-mới](design.md#thêm-thuật-toán-mới) - Chi tiết đầy đủ
3. [design.md#testing](design.md#testing-strategy) - Test cases

**Tổng thời gian**: 15 phút đọc + implementation

### Use Case 3: Debug lỗi "Unknown strategy"

**Mục tiêu**: Fix lỗi khi tạo strategy

**Path**:
1. [QUICK_REFERENCE.md#debugging-tips](QUICK_REFERENCE.md#debugging-tips) - Quick check
2. [QUICK_REFERENCE.md#aliases](QUICK_REFERENCE.md#aliases-được-hỗ-trợ) - Xem aliases
3. [design.md#error-handling](design.md#error-handling) - Error handling code

**Tổng thời gian**: 5 phút

### Use Case 4: Chọn thuật toán cho dataset lớn

**Mục tiêu**: Quyết định thuật toán phù hợp

**Path**:
1. [README.md#so-sánh-thuật-toán](README.md#so-sánh-thuật-toán) - Quick comparison
2. [VISUAL_GUIDE.md#decision-tree](VISUAL_GUIDE.md#decision-tree-chọn-thuật-toán) - Decision tree
3. [design.md#performance](design.md#performance-considerations) - Chi tiết

**Tổng thời gian**: 10 phút

## 🔗 External Links

- [Scikit-learn GridSearchCV](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GridSearchCV.html)
- [Scikit-optimize BayesSearchCV](https://scikit-optimize.github.io/stable/modules/generated/skopt.BayesSearchCV.html)
- [Factory Pattern](https://refactoring.guru/design-patterns/factory-method)
- [Strategy Pattern](https://refactoring.guru/design-patterns/strategy)

## 📝 Ghi Chú

- Tất cả code examples đều có thể chạy được
- Sơ đồ Mermaid cần viewer hỗ trợ (GitHub, VS Code, etc.)
- ASCII art hiển thị tốt trên mọi thiết bị
- Tài liệu được cập nhật theo phiên bản code

## 🤝 Đóng Góp

Nếu bạn muốn cải thiện tài liệu:
1. Đọc [requirements.md](requirements.md) để hiểu yêu cầu
2. Cập nhật file tương ứng
3. Đảm bảo consistency với các file khác
4. Update INDEX.md này nếu thêm nội dung mới

---

**Phiên bản**: 1.0  
**Cập nhật lần cuối**: 2025-11-15  
**Maintainer**: HAutoML Team
