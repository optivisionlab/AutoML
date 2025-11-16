# Kiến Trúc Design Patterns - HAutoML

## 📋 Tổng Quan

Tài liệu này mô tả chi tiết kiến trúc Design Patterns được sử dụng trong hệ thống HAutoML, đặc biệt tập trung vào cơ chế chuyển đổi linh hoạt giữa các thuật toán tìm kiếm siêu tham số.

## 🎯 Mục Đích

- Giải thích cách hệ thống sử dụng **Factory Pattern** và **Strategy Pattern**
- Minh họa luồng chuyển đổi giữa các thuật toán: Grid Search, Genetic Algorithm, Bayesian Search
- Cung cấp hướng dẫn mở rộng hệ thống với thuật toán mới

## 📚 Nội Dung

### 1. [Requirements](requirements.md)
Định nghĩa các yêu cầu chức năng cho tài liệu kiến trúc:
- Hiểu rõ kiến trúc Design Patterns
- Hiểu cơ chế chuyển đổi thuật toán
- Hiểu cách Strategy hoạt động trong training
- Hiểu toàn bộ kiến trúc hệ thống

### 2. [Design](design.md)
Tài liệu thiết kế chi tiết với:
- **7 sơ đồ Mermaid**: Architecture overview, Class diagram, Sequence diagram, Flow charts, Deployment diagram
- **Code examples đầy đủ**: Factory, Interface, Concrete Strategies
- **Error handling và Testing**: Best practices và examples
- **Extension guide**: Hướng dẫn thêm thuật toán mới
- **Performance comparison**: So sánh các thuật toán

### 3. [Tasks](tasks.md)
Danh sách implementation tasks (đã hoàn thành)

## 🏗️ Kiến Trúc Tổng Quan

```
┌─────────────────────────────────────────────────────────┐
│                     Client Layer                         │
│              (API Request với config)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   Factory Layer                          │
│          SearchStrategyFactory.create_strategy()         │
│                                                          │
│  Normalize name → Check aliases → Create instance       │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│   Grid   │  │ Genetic  │  │ Bayesian │
│ Strategy │  │Algorithm │  │ Strategy │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     └─────────────┼─────────────┘
                   │
                   ▼
        ┌──────────────────┐
        │ SearchStrategy   │
        │   Interface      │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ Training Process │
        └──────────────────┘
```

## 🔑 Điểm Quan Trọng

### Factory Pattern
- **Tách biệt logic tạo đối tượng**: Client không cần biết cách khởi tạo Strategy
- **Hỗ trợ aliases**: 'grid', 'Grid', 'GridSearch' đều tạo cùng một Strategy
- **Dễ mở rộng**: Thêm thuật toán mới chỉ cần update dictionary

### Strategy Pattern
- **Interface thống nhất**: Tất cả strategies implement phương thức `search()`
- **Linh hoạt**: Chuyển đổi thuật toán chỉ bằng cách thay đổi config
- **Polymorphism**: Training engine không cần biết strategy cụ thể

## 🚀 Cách Sử Dụng

### Chuyển Đổi Thuật Toán

Trong file config YAML:

```yaml
# Sử dụng Grid Search (mặc định)
search_algorithm: grid

# Sử dụng Genetic Algorithm
search_algorithm: genetic  # hoặc 'ga', 'GA'

# Sử dụng Bayesian Search
search_algorithm: bayesian  # hoặc 'bayes', 'skopt'
```

### Thêm Thuật Toán Mới

**Bước 1**: Tạo Strategy class

```python
from .search_strategy import SearchStrategy

class MyNewStrategy(SearchStrategy):
    def search(self, model, param_grid, X, y, cv=5, scoring='accuracy'):
        # Implementation
        return {'best_params': {...}, 'best_score': 0.95}
```

**Bước 2**: Đăng ký vào Factory

```python
SearchStrategyFactory._strategies['mynew'] = MyNewStrategy
SearchStrategyFactory._aliases['new'] = 'mynew'
```

**Bước 3**: Sử dụng

```yaml
search_algorithm: mynew
```

## 📊 So Sánh Thuật Toán

| Thuật toán | Thời gian | Chất lượng | Use Case |
|------------|-----------|------------|----------|
| Grid Search | O(n^m) | ⭐⭐⭐⭐⭐ | Không gian nhỏ |
| Genetic Algorithm | O(p×g×k) | ⭐⭐⭐⭐ | Không gian lớn, cần nhanh |
| Bayesian Search | O(n×log n) | ⭐⭐⭐⭐⭐ | Cân bằng tốc độ/chất lượng |

## 🔗 Liên Kết

- [Design Document Chi Tiết](design.md) - Xem tất cả sơ đồ và code examples
- [Requirements](requirements.md) - Xem yêu cầu chi tiết
- [Tasks](tasks.md) - Xem danh sách tasks

## 👥 Đối Tượng Sử Dụng

- **Developers**: Hiểu cách implement và maintain code
- **Architects**: Hiểu quyết định thiết kế và trade-offs
- **Contributors**: Biết cách thêm thuật toán mới
- **Users**: Hiểu cách chọn thuật toán phù hợp

## 📝 Ghi Chú

Tài liệu này được tạo tự động từ spec workflow của Kiro IDE. Mọi thay đổi nên được cập nhật trong các file tương ứng (requirements.md, design.md, tasks.md).

---

**Phiên bản**: 1.0  
**Ngày tạo**: 2025-11-15  
**Tác giả**: HAutoML Team
