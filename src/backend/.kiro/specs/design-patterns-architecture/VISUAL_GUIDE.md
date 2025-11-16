# Visual Guide - Kiến Trúc Design Patterns

## 🎨 Sơ Đồ ASCII Art

### 1. Tổng Quan Kiến Trúc

```
                    ┌─────────────────────────────────┐
                    │      API Request                │
                    │  {search_algorithm: 'genetic'}  │
                    └────────────┬────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────────────┐
                    │    TrainingEngine               │
                    │  - preprocess_data()            │
                    │  - load_models()                │
                    │  - training()                   │
                    └────────────┬────────────────────┘
                                 │
                                 │ create_strategy('genetic')
                                 ▼
        ╔════════════════════════════════════════════════╗
        ║      SearchStrategyFactory (FACTORY)           ║
        ║                                                ║
        ║  _strategies = {                               ║
        ║    'grid': GridSearchStrategy,                 ║
        ║    'genetic': GeneticAlgorithm,                ║
        ║    'bayesian': BayesianSearchStrategy          ║
        ║  }                                             ║
        ║                                                ║
        ║  _aliases = {                                  ║
        ║    'ga': 'genetic',                            ║
        ║    'skopt': 'bayesian', ...                    ║
        ║  }                                             ║
        ╚════════════════════════════════════════════════╝
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │     Grid     │ │   Genetic    │ │   Bayesian   │
        │   Strategy   │ │  Algorithm   │ │   Strategy   │
        │              │ │              │ │              │
        │ GridSearchCV │ │ Population   │ │BayesSearchCV │
        │              │ │ Evolution    │ │              │
        └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
               │                │                │
               └────────────────┼────────────────┘
                                │
                                │ implements
                                ▼
                ┌───────────────────────────────────┐
                │   SearchStrategy (INTERFACE)      │
                │                                   │
                │  + search(model, params, X, y)    │
                │  + convert_numpy_types(obj)       │
                └───────────────────────────────────┘
                                │
                                │ used by
                                ▼
                    ┌───────────────────────┐
                    │   Training Process    │
                    │                       │
                    │  For each model:      │
                    │    - search params    │
                    │    - train model      │
                    │    - save results     │
                    └───────────────────────┘
```

### 2. Luồng Chuyển Đổi Thuật Toán

```
    User Config
        │
        │ search_algorithm: 'GA'
        ▼
    ┌─────────────────┐
    │ Parse Config    │
    │ algorithm = 'GA'│
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────┐
    │ Factory.create_strategy()   │
    └────────┬────────────────────┘
             │
             ▼
    ┌─────────────────────────────┐
    │ _normalize_name('GA')       │
    │   - lowercase: 'ga'         │
    │   - remove special chars    │
    └────────┬────────────────────┘
             │
             ▼
    ┌─────────────────────────────┐
    │ Check in _aliases           │
    │ 'ga' → 'genetic'            │
    └────────┬────────────────────┘
             │
             ▼
    ┌─────────────────────────────┐
    │ Check in _strategies        │
    │ 'genetic' → GeneticAlgorithm│
    └────────┬────────────────────┘
             │
             ▼
    ┌─────────────────────────────┐
    │ Create Instance             │
    │ return GeneticAlgorithm()   │
    └────────┬────────────────────┘
             │
             ▼
    ┌─────────────────────────────┐
    │ Return to Engine            │
    │ Ready to use!               │
    └─────────────────────────────┘
```

### 3. Strategy Pattern trong Action

```
┌──────────────────────────────────────────────────────────────┐
│                    Training Engine                           │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ strategy.search(model, params, X, y)
                              ▼
        ┌─────────────────────────────────────────────┐
        │      SearchStrategy Interface               │
        │      (Polymorphic Call)                     │
        └─────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Grid Strategy │    │ GA Strategy   │    │Bayes Strategy │
├───────────────┤    ├───────────────┤    ├───────────────┤
│               │    │               │    │               │
│ GridSearchCV  │    │ Initialize    │    │BayesSearchCV  │
│   .fit()      │    │ population    │    │   .fit()      │
│               │    │               │    │               │
│ Try all       │    │ For each gen: │    │ Gaussian      │
│ combinations  │    │  - Evaluate   │    │ Process       │
│               │    │  - Select     │    │ Optimization  │
│ Return best   │    │  - Crossover  │    │               │
│               │    │  - Mutate     │    │ Return best   │
│               │    │               │    │               │
│               │    │ Return best   │    │               │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │ {best_params: {...},   │
                │  best_score: 0.95}     │
                └────────────────────────┘
```

### 4. Distributed Training với Factory

```
                        ┌─────────────┐
                        │ API Server  │
                        └──────┬──────┘
                               │
                               │ Distribute work
                               ▼
                        ┌─────────────┐
                        │    Kafka    │
                        └──────┬──────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  Worker 1    │   │  Worker 2    │   │  Worker 3    │
    │              │   │              │   │              │
    │  ┌────────┐  │   │  ┌────────┐  │   │  ┌────────┐  │
    │  │Factory │  │   │  │Factory │  │   │  │Factory │  │
    │  └───┬────┘  │   │  └───┬────┘  │   │  └───┬────┘  │
    │      │       │   │      │       │   │      │       │
    │      ▼       │   │      ▼       │   │      ▼       │
    │  Strategy    │   │  Strategy    │   │  Strategy    │
    │              │   │              │   │              │
    │  Train       │   │  Train       │   │  Train       │
    │  Models 1-3  │   │  Models 4-6  │   │  Models 7-9  │
    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
           │                  │                  │
           └──────────────────┼──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Reduce Results  │
                    │  Select Best     │
                    └──────────────────┘
```

### 5. Class Relationships

```
┌─────────────────────────────────────────────────────────┐
│                SearchStrategy (ABC)                     │
│                                                         │
│  + search(model, param_grid, X, y, cv, scoring): dict  │
│  + convert_numpy_types(obj): Any                       │
└─────────────────────────────────────────────────────────┘
                          △
                          │ implements
          ┌───────────────┼───────────────┐
          │               │               │
┌─────────┴─────────┐ ┌──┴──────────┐ ┌──┴──────────────┐
│GridSearchStrategy │ │GeneticAlgo  │ │BayesianStrategy │
├───────────────────┤ ├─────────────┤ ├─────────────────┤
│+ search()         │ │- pop_size   │ │- n_calls        │
└───────────────────┘ │- generations│ └─────────────────┘
                      │+ search()   │
                      │- _init_pop()│
                      │- _evolve()  │
                      └─────────────┘

┌─────────────────────────────────────────────────────────┐
│           SearchStrategyFactory                         │
│                                                         │
│  - _strategies: Dict[str, Type[SearchStrategy]]        │
│  - _aliases: Dict[str, str]                            │
│                                                         │
│  + create_strategy(name: str): SearchStrategy          │
│  - _normalize_name(name: str): str                     │
└─────────────────────────────────────────────────────────┘
                          │
                          │ creates
                          ▼
                  SearchStrategy
```

### 6. Sequence Flow (Simplified)

```
Client          Engine          Factory         Strategy        Model
  │               │               │               │              │
  │─request──────>│               │               │              │
  │               │               │               │              │
  │               │─create────────>│               │              │
  │               │  ('genetic')  │               │              │
  │               │               │               │              │
  │               │<──return──────│               │              │
  │               │  GA instance  │               │              │
  │               │               │               │              │
  │               │─search────────────────────────>│              │
  │               │  (model, params, X, y)        │              │
  │               │               │               │              │
  │               │               │               │─fit──────────>│
  │               │               │               │              │
  │               │               │               │<─trained─────│
  │               │               │               │              │
  │               │<──result──────────────────────│              │
  │               │  {best_params, best_score}    │              │
  │               │               │               │              │
  │<──response────│               │               │              │
  │               │               │               │              │
```

## 🎯 Decision Tree: Chọn Thuật Toán

```
                    Start
                      │
                      ▼
        ┌─────────────────────────┐
        │ Số combinations < 100?  │
        └─────────┬───────────────┘
                  │
         ┌────────┴────────┐
         │                 │
        YES               NO
         │                 │
         ▼                 ▼
    ┌─────────┐   ┌────────────────┐
    │  GRID   │   │ Có thời gian?  │
    │ SEARCH  │   └────┬───────────┘
    └─────────┘        │
                  ┌────┴────┐
                  │         │
                 YES       NO
                  │         │
                  ▼         ▼
          ┌──────────┐  ┌──────────┐
          │ BAYESIAN │  │ GENETIC  │
          │  SEARCH  │  │ALGORITHM │
          └──────────┘  └──────────┘
```

## 📊 Performance Comparison Visual

```
Thời gian thực thi (càng thấp càng tốt)
│
│  Grid ████████████████████████████████ (longest)
│
│  Bayes ████████████████ (medium)
│
│  GA ██████████ (fastest)
│
└────────────────────────────────────────>

Chất lượng kết quả (càng cao càng tốt)
│
│  Grid ████████████████████████████████ (best)
│
│  Bayes ███████████████████████████ (very good)
│
│  GA ████████████████████ (good)
│
└────────────────────────────────────────>

Độ phức tạp không gian tham số
│
│  Small (<100)    → Grid Search
│  Medium (100-1K) → Bayesian Search
│  Large (>1K)     → Genetic Algorithm
│
└────────────────────────────────────────>
```

## 🔄 State Diagram: Strategy Lifecycle

```
    ┌─────────┐
    │ Created │
    └────┬────┘
         │
         │ initialize
         ▼
    ┌─────────┐
    │  Ready  │
    └────┬────┘
         │
         │ search() called
         ▼
    ┌──────────┐
    │Searching │◄────┐
    └────┬─────┘     │
         │           │
         │ iterate   │
         └───────────┘
         │
         │ found best
         ▼
    ┌──────────┐
    │Completed │
    └────┬─────┘
         │
         │ return result
         ▼
    ┌─────────┐
    │   End   │
    └─────────┘
```

## 💡 Mental Model

Hãy nghĩ về Design Patterns như một nhà hàng:

```
┌────────────────────────────────────────────────────┐
│                   RESTAURANT                       │
│                                                    │
│  Customer (Client)                                 │
│      │                                             │
│      │ "Tôi muốn món Ý" (search_algorithm: 'grid')│
│      ▼                                             │
│  Waiter (Factory)                                  │
│      │                                             │
│      │ Chọn đầu bếp phù hợp                       │
│      ▼                                             │
│  ┌──────────┬──────────┬──────────┐              │
│  │Italian   │Chinese   │Japanese  │              │
│  │Chef      │Chef      │Chef      │              │
│  │(Grid)    │(GA)      │(Bayes)   │              │
│  └──────────┴──────────┴──────────┘              │
│      │                                             │
│      │ Tất cả đều biết nấu ăn (search interface)  │
│      ▼                                             │
│  Dish (Result)                                     │
└────────────────────────────────────────────────────┘

- Customer không cần biết đầu bếp nào sẽ nấu
- Waiter (Factory) quyết định đầu bếp phù hợp
- Tất cả đầu bếp đều biết "nấu ăn" (search)
- Kết quả cuối cùng đều là món ăn (best_params)
```

---

**Lưu ý**: Các sơ đồ này được tạo bằng ASCII art để dễ xem trên mọi thiết bị. Xem [design.md](design.md) để xem sơ đồ Mermaid chi tiết hơn.
