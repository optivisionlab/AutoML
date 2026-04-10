import copy
import logging
import random
from datetime import datetime
from typing import List, Dict, Any, Tuple

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_validate

from automl.search.strategy.base import SearchStrategy, normalize_param_grid

# Cấu hình logger cho module này
logger = logging.getLogger(__name__)


class GeneticAlgorithm(SearchStrategy):
    """Triển khai Thuật toán di truyền (Genetic Algorithm) để tối ưu hóa siêu tham số"""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Lấy cấu hình mặc định bằng cách tải từ file YAML."""
        config = SearchStrategy.get_default_config()

        # Tải cấu hình GA từ file YAML (sử dụng method từ base class)
        ga_config = SearchStrategy._load_yaml_config('genetic_algorithm')

        if ga_config:
            config.update(ga_config)

        return config

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.param_bounds = {}
        self.param_types = {}
        self._decode_cache = {}  # Bộ nhớ đệm cho các tham số đã giải mã
        self._evaluation_cache = {}  # Bộ nhớ đệm toàn cục cho đánh giá độ thích nghi
        self._cache_hits = 0  # Theo dõi hiệu quả bộ nhớ đệm
        self._total_evaluations = 0

    @staticmethod
    def _make_hashable(individual: Dict[str, float]) -> tuple:
        """Chuyển đổi cá thể sang định dạng có thể hash để lưu vào bộ nhớ đệm."""
        return tuple(sorted(individual.items()))

    def _encode_parameters(self, param_grid: Dict[str, Any]) -> Dict[str, Any]:
        """Mã hóa lưới tham số cho thuật toán di truyền.
        
        Hỗ trợ list-of-dicts format. Mỗi grid có encoding riêng để đảm bảo
        decode đúng giá trị.
        """
        # Xóa dữ liệu cũ
        self.param_bounds.clear()
        self.param_types.clear()

        # Chuẩn hóa param_grid về list-of-dicts format
        param_grid_list = normalize_param_grid(param_grid)

        # Lọc bỏ các grid rỗng
        param_grid_list = [grid for grid in param_grid_list if grid]

        # Nếu không còn grid nào (model không có hyperparameter), giữ lại 1 grid rỗng
        # để GA có thể đánh giá model với default params
        if not param_grid_list:
            param_grid_list = [{}]

        # Lưu danh sách các grid
        self._param_grid_list = param_grid_list
        self._num_grids = len(param_grid_list)

        # Tạo encoding riêng cho từng grid
        self._grid_encodings = []
        for grid_idx, single_grid in enumerate(param_grid_list):
            grid_encoding = {
                'param_bounds': {},
                'param_types': {}
            }
            for param_name, param_values in single_grid.items():
                if isinstance(param_values, list):
                    grid_encoding['param_bounds'][param_name] = (0, len(param_values) - 1)
                    grid_encoding['param_types'][param_name] = ('categorical', param_values)
                elif isinstance(param_values, tuple) and len(param_values) == 2:
                    min_val, max_val = param_values
                    grid_encoding['param_bounds'][param_name] = (min_val, max_val)
                    if isinstance(min_val, int) and isinstance(max_val, int):
                        grid_encoding['param_types'][param_name] = ('integer', None)
                    else:
                        grid_encoding['param_types'][param_name] = ('continuous', None)
            self._grid_encodings.append(grid_encoding)

        # Tạo param_bounds và param_types tổng hợp (cho compatibility)
        # Sử dụng grid đầu tiên làm mặc định
        if self._grid_encodings:
            self.param_bounds = self._grid_encodings[0]['param_bounds'].copy()
            self.param_types = self._grid_encodings[0]['param_types'].copy()

        return {}

    def _decode_individual(self, individual: Dict[str, float]) -> Dict[str, Any]:
        """Giải mã cá thể từ biểu diễn di truyền sang giá trị tham số thực tế."""
        # Kiểm tra bộ nhớ đệm trước
        cache_key = self._make_hashable(individual)
        if cache_key in self._decode_cache:
            return self._decode_cache[cache_key].copy()

        decoded = {}

        # Lấy grid_idx từ cá thể
        grid_idx = int(individual.get('_grid_idx', 0))

        # Lấy encoding của grid này
        if hasattr(self, '_grid_encodings') and grid_idx < len(self._grid_encodings):
            grid_encoding = self._grid_encodings[grid_idx]
            param_types = grid_encoding['param_types']
        else:
            param_types = self.param_types

        for param_name, value in individual.items():
            if param_name == '_grid_idx':
                continue

            if param_name not in param_types:
                continue

            param_type, param_values = param_types[param_name]

            if param_type == 'categorical':
                index = int(round(value))
                index = max(0, min(index, len(param_values) - 1))
                decoded[param_name] = param_values[index]
            elif param_type == 'integer':
                decoded[param_name] = int(round(value))
            else:
                decoded[param_name] = float(value)

        decoded = SearchStrategy.convert_numpy_types(decoded)
        self._decode_cache[cache_key] = decoded
        return decoded

    def _create_individual(self, grid_idx: int = None) -> Dict[str, float]:
        """Tạo một cá thể cho thuật toán di truyền.
        
        Args:
            grid_idx: Chỉ số của grid trong list-of-dicts. Nếu None, chọn ngẫu nhiên.
            
        Returns:
            Dict[str, float]: Cá thể với các tham số được mã hóa.
            
        Raises:
            ValueError: Nếu không có grid nào được định nghĩa.
        """
        # Kiểm tra xem có grid nào không
        if self._num_grids == 0:
            raise ValueError("Không thể tạo cá thể: không có grid tham số nào được định nghĩa.")

        individual = {}

        # Chọn grid_idx nếu chưa được chỉ định
        if grid_idx is None:
            grid_idx = random.randint(0, self._num_grids - 1)

        # Lưu grid_idx vào cá thể
        individual['_grid_idx'] = float(grid_idx)

        # Lấy encoding của grid được chọn
        if hasattr(self, '_grid_encodings') and grid_idx < len(self._grid_encodings):
            grid_encoding = self._grid_encodings[grid_idx]
            param_bounds = grid_encoding['param_bounds']
        else:
            param_bounds = self.param_bounds

        # Tạo giá trị ngẫu nhiên cho các tham số của grid này
        for param_name, (min_val, max_val) in param_bounds.items():
            individual[param_name] = random.uniform(min_val, max_val)

        return individual

    def _create_smart_population(self, size: int) -> List[Dict[str, float]]:
        """Tạo quần thể ban đầu sử dụng khởi tạo thông minh."""
        population = []

        # Phân bổ đều số cá thể cho mỗi grid
        individuals_per_grid = max(1, size // self._num_grids) if self._num_grids > 0 else size

        for grid_idx in range(self._num_grids):
            for _ in range(individuals_per_grid):
                if len(population) >= size:
                    break
                population.append(self._create_individual(grid_idx))

        # Điền phần còn lại bằng các cá thể ngẫu nhiên
        while len(population) < size:
            population.append(self._create_individual())

        return population[:size]

    def _evaluate_individual(self, individual: Dict[str, float], model: BaseEstimator, X: np.ndarray,
                             y: np.ndarray) -> dict:
        """Đánh giá cá thể sử dụng cross-validation với bộ nhớ đệm toàn cục."""
        self._total_evaluations += 1

        # Kiểm tra bộ nhớ đệm toàn cục nếu được bật
        if self.config.get('use_global_cache', True):
            cache_key = self._make_hashable(individual)
            if cache_key in self._evaluation_cache:
                self._cache_hits += 1
                return self._evaluation_cache[cache_key].copy()

        try:
            params = self._decode_individual(individual)

            model.set_params(**params)

            # Lấy cấu hình điểm số (dict từ engine.py)
            scoring_config = self.config.get('scoring')
            scoring_metrics = scoring_config
            metric_names = list(scoring_config.keys())

            # sử dụng cross_validate thay vì cross_val_score để lấy điểm của mỗi fold
            scores = cross_validate(
                model, X, y,
                cv=self.config['cv'],
                scoring=scoring_metrics,
                n_jobs=self.config['n_jobs'],
                error_score=self.config['error_score']
            )

            # Xây dựng dictionary kết quả
            result = {}
            for metric_name in metric_names:
                result[metric_name] = float(np.mean(scores[f'test_{metric_name}']))

            # Lưu kết quả vào bộ nhớ đệm nếu được bật
            if self.config.get('use_global_cache', True):
                cache_key = self._make_hashable(individual)
                # Quản lý kích thước bộ nhớ đệm
                max_cache_size = self.config.get('max_cache_size', 500)
                if len(self._evaluation_cache) >= max_cache_size:
                    # Loại bỏ các mục cũ nhất (FIFO)
                    keys_to_remove = list(self._evaluation_cache.keys())[:max_cache_size // 4]
                    for key in keys_to_remove:
                        del self._evaluation_cache[key]
                self._evaluation_cache[cache_key] = result.copy()

            return result

        except (ValueError, TypeError, KeyError):
            # Trả về giá trị 0 cho tất cả chỉ số khi đánh giá thất bại
            # Lỗi thường gặp: tham số không hợp lệ, kiểu không khớp, thiếu key
            scoring = self.config.get('scoring', {})
            if isinstance(scoring, dict) and scoring:
                return {metric: -float('inf') for metric in scoring.keys()}
            else:
                return {'accuracy': -float('inf')}

    def _get_adaptive_tournament_size(self, diversity: float, population_size: int) -> int:
        """
        Tính tournament size thích ứng dựa trên diversity.
        
        - Diversity thấp: giảm tournament size để tăng exploration
        - Diversity cao: tăng tournament size để tăng exploitation
        
        Args:
            diversity: Độ đa dạng của quần thể (0-1)
            population_size: Kích thước quần thể
            
        Returns:
            int: Tournament size tối ưu
        """
        base_size = self.config.get('tournament_size', 3)

        if not self.config.get('adaptive_tournament_size', False):
            return min(base_size, population_size)

        if diversity < 0.1:
            # Diversity thấp: giảm selection pressure để tăng exploration
            adaptive_size = max(2, base_size - 1)
        elif diversity > 0.5:
            # Diversity cao: tăng selection pressure để tăng exploitation
            adaptive_size = min(population_size // 2, base_size + 1)
        else:
            adaptive_size = base_size

        return min(adaptive_size, population_size)

    def _tournament_selection(self, population: List[Dict[str, float]], fitness_scores, diversity: float = None) -> Dict[str, float]:
        """
        Chọn cá thể sử dụng chọn lọc đấu trường với tối ưu hóa numpy.
        
        Args:
            population: Danh sách các cá thể
            fitness_scores: Điểm fitness của từng cá thể
            diversity: Độ đa dạng quần thể (optional, cho adaptive tournament size)
        """
        # Xử lý cả kiểu numpy array và list
        if not population:
            raise ValueError("Quần thể không thể trống")
        if isinstance(fitness_scores, np.ndarray):
            if fitness_scores.size == 0:
                raise ValueError("Điểm độ thích nghi không thể trống")
        elif not fitness_scores:
            raise ValueError("Điểm độ thích nghi không thể trống")

        # Sử dụng adaptive tournament size nếu có diversity
        if diversity is not None and self.config.get('adaptive_tournament_size', False):
            tournament_size = self._get_adaptive_tournament_size(diversity, len(population))
        else:
            tournament_size = min(self.config['tournament_size'], len(population))

        # Sử dụng numpy để chọn nhanh hơn
        tournament_indices = np.random.choice(len(population), size=tournament_size, replace=False)
        winner_index = tournament_indices[np.argmax(fitness_scores[tournament_indices])]
        # Trả về bản sao nông vì sẽ deepcopy khi cần
        return population[winner_index].copy()

    def _crossover(self, parent1: Dict[str, float], parent2: Dict[str, float]) -> Tuple[
        Dict[str, float], Dict[str, float]]:
        """Thực hiện lai ghép giữa hai cá thể sử dụng chiến lược khác nhau dựa trên kiểu tham số.
        
        Chỉ thực hiện lai ghép nếu hai cá thể thuộc cùng một grid group.
        """
        if random.random() > self.config['crossover_rate']:
            return parent1.copy(), parent2.copy()

        # Kiểm tra xem hai cá thể có thuộc cùng grid group không
        grid_idx1 = int(parent1.get('_grid_idx', 0))
        grid_idx2 = int(parent2.get('_grid_idx', 0))

        # Nếu khác grid group, không lai ghép - trả về bản sao
        if grid_idx1 != grid_idx2:
            return parent1.copy(), parent2.copy()

        # Lấy encoding của grid
        if hasattr(self, '_grid_encodings') and grid_idx1 < len(self._grid_encodings):
            grid_encoding = self._grid_encodings[grid_idx1]
            param_bounds = grid_encoding['param_bounds']
            param_types = grid_encoding['param_types']
        else:
            param_bounds = self.param_bounds
            param_types = self.param_types

        # Lai ghép đơn giản siêu nhanh
        if self.config.get('simple_crossover', False):
            child1 = parent1.copy()
            child2 = parent2.copy()
            params = [p for p in parent1.keys() if p != '_grid_idx']
            if len(params) > 1:
                swap_point = len(params) // 2
                for param in params[:swap_point]:
                    child1[param], child2[param] = child2[param], child1[param]
            return child1, child2

        child1 = parent1.copy()
        child2 = parent2.copy()

        for param_name in parent1.keys():
            if param_name == '_grid_idx':
                continue

            if param_name not in param_types:
                continue

            param_type, param_values = param_types[param_name]

            if param_type == 'categorical':
                if random.random() < 0.5:
                    child1[param_name], child2[param_name] = child2[param_name], child1[param_name]
            else:
                alpha = self.config.get('alpha', 0.5)
                min_val = min(parent1[param_name], parent2[param_name])
                max_val = max(parent1[param_name], parent2[param_name])
                range_val = max_val - min_val

                lower = min_val - alpha * range_val
                upper = max_val + alpha * range_val

                param_min, param_max = param_bounds[param_name]
                lower = max(lower, param_min)
                upper = min(upper, param_max)

                child1[param_name] = random.uniform(lower, upper)
                child2[param_name] = random.uniform(lower, upper)

        return child1, child2

    def _mutate(self, individual: Dict[str, float], generation: int = 0, max_generation: int = None) -> Dict[
        str, float]:
        """Đột biến cá thể với cường độ đột biến thích nghi."""
        mutated = individual.copy()

        # Lấy grid_idx và encoding tương ứng
        grid_idx = int(individual.get('_grid_idx', 0))
        if hasattr(self, '_grid_encodings') and grid_idx < len(self._grid_encodings):
            grid_encoding = self._grid_encodings[grid_idx]
            param_bounds = grid_encoding['param_bounds']
            param_types = grid_encoding['param_types']
        else:
            param_bounds = self.param_bounds
            param_types = self.param_types

        # Tỷ lệ đột biến thích nghi
        if max_generation and max_generation > 0:
            adaptive_rate = self.config['mutation_rate'] * (1 - generation / max_generation)
        else:
            adaptive_rate = self.config['mutation_rate']

        for param_name in mutated.keys():
            if param_name == '_grid_idx':
                continue

            if param_name not in param_bounds or param_name not in param_types:
                continue

            if random.random() < adaptive_rate:
                min_val, max_val = param_bounds[param_name]
                param_type, param_values = param_types[param_name]
                current_val = mutated[param_name]

                if param_type == 'categorical':
                    possible_values = list(range(int(min_val), int(max_val) + 1))
                    if len(possible_values) > 1:
                        possible_values.remove(int(round(current_val)))
                        mutated[param_name] = float(random.choice(possible_values))
                else:
                    mutation_strength = (max_val - min_val) * (
                        0.2 * (1 - generation / (max_generation + 1)) if max_generation else 0.1)
                    new_val = current_val + random.gauss(0, mutation_strength)
                    mutated[param_name] = max(min_val, min(new_val, max_val))

        return mutated

    def _inject_diversity(self, population: List[Dict[str, float]], injection_rate: float = 0.3) -> List[
        Dict[str, float]]:
        """Tiêm các cá thể ngẫu nhiên mới để tăng đa dạng khi quần thể trì trệ.
        
        Args:
            population: Quần thể hiện tại
            injection_rate: Tỷ lệ quần thể được thay thế bằng các cá thể ngẫu nhiên mới
        
        Returns:
            Quần thể đã tiêm đa dạng
        """
        num_to_inject = int(len(population) * injection_rate)
        if num_to_inject == 0:
            return population

        # Sắp xếp quần thể theo độ thích nghi (giữ những cái tốt nhất)
        # Lưu ý: Điều này giả định chúng ta có quyền truy cập điểm độ thích nghi, vì vậy sẽ cần truyền chúng
        # Hiện tại, chúng ta sẽ chỉ thay thế các cá thể ngẫu nhiên
        new_population = population.copy()

        # Thay thế các cá thể tệ nhất bằng các cá thể ngẫu nhiên mới
        injection_indices = random.sample(range(len(population)), num_to_inject)
        for idx in injection_indices:
            new_population[idx] = self._create_individual()

        return new_population

    def _create_next_generation(self, population: List[Dict[str, float]], fitness_scores: np.ndarray, diversity: float,
                                generation: int, population_size: int) -> List[Dict[str, float]]:
        """Tạo thế hệ tiếp theo từ quần thể hiện tại.
        
        Args:
            population: Quần thể hiện tại
            fitness_scores: Điểm fitness của từng cá thể
            diversity: Độ đa dạng của quần thể
            generation: Số thế hệ hiện tại
            population_size: Kích thước quần thể mục tiêu
            
        Returns:
            Quần thể mới cho thế hệ tiếp theo
        """
        new_population = []

        # Elitism: Giữ lại các cá thể tốt nhất
        if self.config['elite_size'] > 0:
            elite_indices = np.argpartition(fitness_scores, -self.config['elite_size'])[-self.config['elite_size']:]
            for idx in elite_indices:
                new_population.append(population[idx].copy())

        # Tỷ lệ lai ghép thích ứng dựa trên đa dạng
        adaptive_crossover_rate = self.config['crossover_rate']
        if diversity < 0.1:
            adaptive_crossover_rate = min(1.0, adaptive_crossover_rate * 1.2)

        # Điền phần còn lại bằng selection + crossover + mutation
        while len(new_population) < population_size:
            # Truyền diversity cho adaptive tournament selection
            parent1 = self._tournament_selection(population, fitness_scores, diversity)
            parent2 = self._tournament_selection(population, fitness_scores, diversity)

            # Tạm thời sử dụng tỷ lệ lai ghép thích ứng
            original_rate = self.config['crossover_rate']
            self.config['crossover_rate'] = adaptive_crossover_rate
            child1, child2 = self._crossover(parent1, parent2)
            self.config['crossover_rate'] = original_rate

            # Áp dụng đột biến
            child1 = self._mutate(child1, generation, self.config['generation'])
            child2 = self._mutate(child2, generation, self.config['generation'])

            if len(new_population) < population_size:
                new_population.append(child1)
            if len(new_population) < population_size:
                new_population.append(child2)

        return new_population

    def _calculate_population_diversity_fast(self, population: List[Dict[str, float]]) -> float:
        """
        Tính độ đa dạng của quần thể với độ phức tạp O(n).
        
        Sử dụng variance của mỗi parameter thay vì so sánh pairwise.
        Nhanh hơn nhiều cho quần thể lớn.
        
        Args:
            population: Danh sách các cá thể
            
        Returns:
            float: Độ đa dạng normalized (0-1)
        """
        if len(population) < 2:
            return 0.0

        # Nhóm cá thể theo grid
        grid_groups = {}
        for ind in population:
            grid_idx = int(ind.get('_grid_idx', 0))
            if grid_idx not in grid_groups:
                grid_groups[grid_idx] = []
            grid_groups[grid_idx].append(ind)

        total_diversity = 0.0
        total_weight = 0

        for grid_idx, group in grid_groups.items():
            if len(group) < 2:
                continue

            # Lấy encoding của grid
            if hasattr(self, '_grid_encodings') and grid_idx < len(self._grid_encodings):
                param_bounds = self._grid_encodings[grid_idx]['param_bounds']
                param_types = self._grid_encodings[grid_idx]['param_types']
            else:
                param_bounds = self.param_bounds
                param_types = self.param_types

            # Tính variance cho mỗi parameter
            param_diversities = []
            for param_name in param_bounds.keys():
                if param_name == '_grid_idx':
                    continue

                values = [ind.get(param_name, 0) for ind in group]
                param_type, _ = param_types.get(param_name, ('continuous', None))

                if param_type == 'categorical':
                    # Cho categorical: tính tỷ lệ unique values
                    unique_ratio = len(set(values)) / len(values)
                    param_diversities.append(unique_ratio)
                else:
                    # Cho continuous/integer: tính normalized variance
                    min_val, max_val = param_bounds[param_name]
                    if max_val != min_val:
                        normalized_values = [(v - min_val) / (max_val - min_val) for v in values]
                        variance = np.var(normalized_values)
                        # Chuẩn hóa phương sai (phương sai lý thuyết tối đa là 0.25 đối với phân phối đều)
                        param_diversities.append(min(1.0, variance * 4))
                    else:
                        param_diversities.append(0.0)

            if param_diversities:
                group_diversity = np.mean(param_diversities)
                total_diversity += group_diversity * len(group)
                total_weight += len(group)

        # Thêm diversity từ việc có nhiều grids
        if len(grid_groups) > 1:
            grid_diversity = len(grid_groups) / self._num_grids if self._num_grids > 0 else 0
            weighted_diversity = total_diversity / total_weight if total_weight > 0 else 0
            total_diversity = weighted_diversity * 0.7 + grid_diversity * 0.3
        elif total_weight > 0:
            total_diversity = total_diversity / total_weight

        return total_diversity

    def _calculate_population_diversity(self, population: List[Dict[str, float]]) -> float:
        """
        Tính độ đa dạng của quần thể.
        
        Tự động chọn phương pháp tối ưu dựa trên kích thước quần thể:
        - Quần thể nhỏ (< 20): sử dụng pairwise comparison (chính xác hơn)
        - Quần thể lớn (>= 20): sử dụng variance-based (nhanh hơn)
        """
        if len(population) < 2:
            return 0.0

        # Sử dụng fast method cho quần thể lớn
        use_fast = self.config.get('fast_diversity', True)
        if use_fast and len(population) >= 20:
            return self._calculate_population_diversity_fast(population)

        # Pairwise comparison cho quần thể nhỏ (chính xác hơn)
        total_distance = 0
        count = 0

        for i in range(len(population)):
            for j in range(i + 1, len(population)):
                # Chỉ so sánh cá thể cùng grid
                grid_i = int(population[i].get('_grid_idx', 0))
                grid_j = int(population[j].get('_grid_idx', 0))

                if grid_i != grid_j:
                    distance = 1.0  # Khác grid = khoảng cách tối đa
                else:
                    # Lấy encoding của grid
                    if hasattr(self, '_grid_encodings') and grid_i < len(self._grid_encodings):
                        param_bounds = self._grid_encodings[grid_i]['param_bounds']
                        param_types = self._grid_encodings[grid_i]['param_types']
                    else:
                        param_bounds = self.param_bounds
                        param_types = self.param_types

                    distance = 0
                    param_count = 0
                    for param_name in population[i].keys():
                        if param_name == '_grid_idx':
                            continue
                        if param_name not in param_types:
                            continue

                        param_type, _ = param_types[param_name]
                        param_count += 1
                        if param_type == 'categorical':
                            distance += 0 if population[i][param_name] == population[j][param_name] else 1
                        else:
                            min_val, max_val = param_bounds[param_name]
                            if max_val != min_val:
                                normalized_diff = abs(population[i][param_name] - population[j][param_name]) / (max_val - min_val)
                                distance += normalized_diff

                    if param_count > 0:
                        distance = distance / param_count

                total_distance += distance
                count += 1

        return total_distance / count if count > 0 else 0.0

    def _evaluate_population_parallel(self, population: List[Dict[str, float]], model: BaseEstimator, X: np.ndarray,
                                      y: np.ndarray) -> List[Dict[str, float]]:
        """Đánh giá tất cả các cá thể song song với tối ưu hóa thông minh.
        
        Giới hạn thời gian được kiểm tra ở cấp độ thế hệ trong search(), không phải ở đây.
        """
        n_jobs = self.config.get('n_jobs', -1)

        # Nếu n_jobs = 1, chạy tuần tự
        if n_jobs == 1:
            results = []
            for individual in population:
                results.append(self._evaluate_individual(individual, model, X, y))
            return results

        # Quyết định song song thông minh dựa trên kích thước quần thể và số fold CV
        cv = self.config.get('cv', 5)
        if hasattr(cv, 'n_splits'):
            cv_folds = cv.n_splits
        elif hasattr(cv, 'get_n_splits'):
            cv_folds = cv.get_n_splits()
        else:
            cv_folds = cv if isinstance(cv, int) else 5

        if n_jobs == -1:
            import multiprocessing
            n_jobs = multiprocessing.cpu_count()

        # Tính tổng đơn vị công việc (quần thể * cv_folds)
        total_work = len(population) * cv_folds

        # Chỉ sử dụng song song nếu có đủ công việc để biện minh cho overhead
        if total_work >= (n_jobs * 2) and len(population) > 4:
            optimal_jobs = min(n_jobs, len(population))
            backend = 'threading' if cv_folds <= 3 else 'loky'

            results = Parallel(n_jobs=optimal_jobs, backend=backend)(
                delayed(self._evaluate_individual)(individual, copy.deepcopy(model), X, y) for individual in population)
            return results
        else:
            # Tuần tự cho quần thể nhỏ
            results = []
            for individual in population:
                results.append(self._evaluate_individual(individual, model, X, y))
            return results

    def search(self, model: BaseEstimator, param_grid: List[Dict[str, Any]], X: np.ndarray, y: np.ndarray, **kwargs):
        """Thực thi tìm kiếm thuật toán di truyền với các tính năng vòng lặp nâng cao.

               Args:
                   model: The estimator to search over
                   param_grid: Dictionary with parameters names as keys and ranges/lists as values
                   X: Training data features
                   y: Training data targets
                   **kwargs: Additional configuration parameters

               Returns:
                   tuple: (best_params, best_score, best_all_scores, cv_results)
                       - best_params: Từ điển các tham số tốt nhất
                       - best_score: Điểm số tốt nhất đạt được
                       - best_all_scores: Từ điển với tất cả điểm số metric cho tham số tốt nhất
                       - cv_results: Từ điển với kết quả cross-validation chi tiết
        """
        # Cập nhật cấu hình của thuật toán với bất kỳ đối số keyword nào được cung cấp
        self.set_config(**{k: v for k, v in kwargs.items() if k in self.config})
        self._start_timer()  # Bắt đầu đếm thời gian

        # Đặt seed ngẫu nhiên để tái tạo được kết quả
        if self.config.get('random_state') is not None:
            random.seed(self.config['random_state'])
            np.random.seed(self.config['random_state'])

        # Xác thực cấu hình
        if self.config['population_size'] < 2:
            raise ValueError("Population size must be at least 2")
        if self.config['elite_size'] >= self.config['population_size']:
            self.config['elite_size'] = max(1, self.config['population_size'] // 4)

        # Tạo đường dẫn file log sử dụng phương thức lớp cơ sở
        log_file = self.create_log_file_path(model, 'genetic_algorithm')

        # Chuyển đổi lưới siêu tham số sang định dạng phù hợp cho thuật toán di truyền
        self._encode_parameters(param_grid)

        # Tính tổng số tổ hợp tham số cho không gian categorical nhỏ
        total_grid_combinations = 0
        is_all_categorical = True
        for grid in self._param_grid_list:
            if not grid:
                total_grid_combinations += 1
                continue
            grid_combos = 1
            for param_name, param_values in grid.items():
                if isinstance(param_values, list):
                    grid_combos *= len(param_values)
                else:
                    is_all_categorical = False
                    break
            if not is_all_categorical:
                break
            total_grid_combinations += grid_combos

        # Điều chỉnh kích thước quần thể dựa trên độ phức tạp không gian tham số
        if self.config.get('adaptive_population', True) and self.config.get('fast_mode', True):
            # Tính kích thước không gian tham số
            param_space_size = 1
            for param_name, (min_val, max_val) in self.param_bounds.items():
                param_type, param_values = self.param_types[param_name]
                if param_type == 'categorical':
                    param_space_size *= (max_val - min_val + 1)
                else:
                    param_space_size *= 10  # Ước lượng cho continuous

            # Điều chỉnh kích thước quần thể với giới hạn chặt hơn để runtime nhanh hơn
            min_pop = self.config.get('min_population', 8)
            max_pop = self.config.get('max_population', 25)
            adaptive_pop_size = min(max_pop, max(min_pop, int(np.log(param_space_size) * 2)))
            actual_population_size = min(adaptive_pop_size, self.config['population_size'])
        else:
            actual_population_size = self.config['population_size']

        # Tự động điều chỉnh cho không gian categorical nhỏ
        # Đảm bảo tổng evaluations (population * generations) >= total_combinations
        # để GA có thể duyệt đủ không gian và tìm kết quả tối ưu giống Grid Search
        if is_all_categorical and total_grid_combinations <= 100:
            min_total_evaluations = total_grid_combinations * 2  # Ít nhất 2x coverage
            current_total = actual_population_size * self.config['generation']
            if current_total < min_total_evaluations:
                # Tăng population hoặc generation để đủ coverage
                new_pop = max(actual_population_size, min(total_grid_combinations, 30))
                new_gen = max(self.config['generation'], (min_total_evaluations // new_pop) + 1)
                logger.info(
                    f"GA: Không gian categorical nhỏ ({total_grid_combinations} tổ hợp). "
                    f"Điều chỉnh population {actual_population_size}→{new_pop}, "
                    f"generation {self.config['generation']}→{new_gen}"
                )
                actual_population_size = new_pop
                self.config['generation'] = new_gen

        # Tạo quần thể ban đầu sử dụng khởi tạo thông minh hoặc ngẫu nhiên
        if self.config.get('ultra_fast_mode', False):
            # Trong chế độ siêu nhanh, sử dụng chủ yếu quần thể ngẫu nhiên
            population = [self._create_individual() for _ in range(actual_population_size)]
        elif self.config.get('init_strategy', 'smart') == 'smart':
            population = self._create_smart_population(actual_population_size)
        else:
            population = [self._create_individual() for _ in range(actual_population_size)]

        # Danh sách để lưu lịch sử của tất cả các cá thể và điểm số của chúng qua tất cả các thế hệ
        all_individuals = []
        all_scores = []
        all_metric_scores = []  # Lưu tất cả điểm số metric cho mỗi cá thể
        generation_history = []  # Lưu lịch sử để logging

        # Khởi tạo các biến để theo dõi giải pháp tốt nhất tìm được cho đến nay
        best_individual = None
        best_score = float('-inf')
        best_all_scores = None  # Theo dõi tất cả metrics cho cá thể tốt nhất

        # Theo dõi dừng sớm
        early_stopping_enabled = self.config.get('early_stopping_enabled', True)
        early_stopping_patience = self.config.get('early_stopping_patience', 5)
        generations_without_improvement = 0
        best_generation = 0

        # Theo dõi hội tụ
        convergence_history = []
        diversity_history = []

        # Thực thi vòng lặp chính của thuật toán di truyền
        verbose = self.config.get('verbose', 1)
        if verbose > 0:
            logger.info(
                f"Starting Genetic Algorithm with {actual_population_size} individuals for {self.config['generation']} generations")
            if verbose > 1:
                logger.info(f"Early stopping: {'Enabled' if early_stopping_enabled else 'Disabled'}" +
                            (f" (patience: {early_stopping_patience})" if early_stopping_enabled else ""))

        for generation in range(self.config['generation']):
            # Kiểm tra time limit trước mỗi thế hệ (sử dụng base.py)
            if not self._should_start_next_iteration():
                logger.info(f"Dừng search tại thế hệ {generation + 1}.")
                break

            generation_start_time = datetime.now()

            # Tính đa dạng quần thể (bỏ qua trong chế độ siêu nhanh)
            if not self.config.get('skip_diversity_check', False):
                diversity = self._calculate_population_diversity(population)
                diversity_history.append(diversity)
            else:
                diversity = 1.0  # Giá trị giả cho chế độ siêu nhanh
                diversity_history.append(diversity)

            # Chỉ báo tiến trình
            if verbose > 0 and (verbose > 1 or generation % 5 == 0 or generation == 0 or generation == self.config[
                'generation'] - 1):
                logger.info(f"Thế hệ {generation + 1}/{self.config['generation']} | Đa dạng: {diversity:.4f}")

            # Đánh giá quần thể (với tối ưu hóa cho chế độ siêu nhanh)
            if self.config.get('ultra_fast_mode', False) and generation > 0:
                # Trong chế độ siêu nhanh sau thế hệ đầu tiên, chỉ đánh giá các cá thể mới/đã thay đổi
                # Sử dụng điểm số đã cache cho các cá thể ưu tú
                all_individual_scores = []
                for idx, individual in enumerate(population):
                    if idx < self.config['elite_size'] and generation > 0:
                        # Các cá thể ưu tú - sử dụng điểm số trước đó nếu có
                        cache_key = self._make_hashable(individual)
                        if cache_key in self._evaluation_cache:
                            all_individual_scores.append(self._evaluation_cache[cache_key].copy())
                        else:
                            all_individual_scores.append(self._evaluate_individual(individual, model, X, y))
                    else:
                        # Các cá thể mới phải được đánh giá
                        all_individual_scores.append(self._evaluate_individual(individual, model, X, y))
            else:
                # Đánh giá bình thường
                all_individual_scores = self._evaluate_population_parallel(population, model, X, y)

            # Xác định metric chính để đánh giá fitness
            primary_metric = self.config.get('metric_sort', 'accuracy')

            # Trích xuất điểm fitness và theo dõi cá thể tốt nhất
            fitness_scores = np.zeros(len(population))  # Sử dụng numpy array để hiệu suất tốt hơn
            generation_best_score = float('-inf')
            generation_improved = False

            for idx, (individual, scores) in enumerate(zip(population, all_individual_scores)):
                score = scores.get(primary_metric, 0.0)
                fitness_scores[idx] = score

                # Ghi lại cho lịch sử
                all_individuals.append(self._decode_individual(individual))
                all_scores.append(score)
                all_metric_scores.append(scores.copy())  # Lưu tất cả điểm số metric

                # Theo dõi tốt nhất của thế hệ
                if score >= generation_best_score:
                    generation_best_score = score

                # Cập nhật tốt nhất toàn cục nếu cải thiện
                if score >= best_score:
                    best_score = score
                    best_individual = copy.deepcopy(individual)
                    best_all_scores = scores.copy()
                    best_generation = generation
                    generation_improved = True
                    generations_without_improvement = 0

                # Lưu vào lịch sử thế hệ để logging
                if self.config['save_log']:
                    history_entry = {
                        'generation': generation + 1,
                        'individual_id': len(generation_history) + 1,
                        'best_params': str(self._decode_individual(individual)),
                        'fitness_score': score,
                        'is_best_so_far': score == best_score,
                        'diversity': diversity,
                        'generation_best': generation_best_score
                    }
                    # Thêm tất cả metrics từ scores
                    for metric_key, metric_value in scores.items():
                        history_entry[metric_key] = metric_value
                    generation_history.append(history_entry)

            # Theo dõi hội tụ với các phép toán numpy
            mean_fitness = fitness_scores.mean()
            std_fitness = fitness_scores.std()
            convergence_history.append(
                {
                    'generation': generation + 1,
                    'best': best_score,
                    'mean': mean_fitness,
                    'std': std_fitness,
                    'diversity': diversity
                })

            # Cập nhật tiến trình với kết quả thế hệ
            generation_time = (datetime.now() - generation_start_time).total_seconds()
            # Cập nhật EMA iteration time trong base.py
            self._should_start_next_iteration(iteration_duration=generation_time)
            if verbose > 0 and (verbose > 1 or generation % 5 == 0 or generation == 0 or generation == self.config[
                'generation'] - 1):
                logger.info(
                    f" | Tốt nhất: {generation_best_score:.4f} | Trung bình: {mean_fitness:.4f} | Độ lệch chuẩn: {std_fitness:.4f} | Thời gian: {generation_time:.2f}s")

                if generation_improved and verbose > 1:
                    logger.info(" ✓ TỐT NHẤT MỚI!")

            # Kiểm tra dừng sớm với ngưỡng hội tụ
            if not generation_improved:
                generations_without_improvement += 1

            # Kiểm tra ngưỡng hội tụ (cải thiện rất nhỏ) - chỉ khi không có time limit
            convergence_threshold = self.config.get('convergence_threshold', 0.001)
            if self._should_apply_early_stopping() and generation > 0 and len(convergence_history) > 1:
                recent_improvement = convergence_history[-1]['best'] - convergence_history[-2]['best']
                if abs(recent_improvement) < convergence_threshold and generations_without_improvement >= 2:
                    logger.info(
                        f"Phát hiện hội tụ tại thế hệ {generation + 1} (cải thiện < {convergence_threshold:.4f})")
                    logger.info(f"Điểm số tốt nhất {best_score:.4f} đạt được tại thế hệ {best_generation + 1}")
                    break

            # Kiểm tra early stopping - chỉ khi không có time limit
            if self._should_apply_early_stopping() and early_stopping_enabled and generations_without_improvement >= early_stopping_patience:
                logger.info(
                    f"Dừng sớm được kích hoạt tại thế hệ {generation + 1} (không cải thiện trong {early_stopping_patience} thế hệ)")
                logger.info(f"Điểm số tốt nhất {best_score:.4f} đạt được tại thế hệ {best_generation + 1}")
                break

            # Lưu log sau mỗi thế hệ
            if self.config['save_log'] and log_file:
                df = pd.DataFrame(generation_history)
                df.to_csv(log_file, index=False)

            # Kiểm tra xem quần thể đã hội tụ (đa dạng thấp) - bỏ qua trong chế độ siêu nhanh
            if not self.config.get('ultra_fast_mode', False):
                stagnation_threshold = 0.05
                if diversity < stagnation_threshold and generations_without_improvement >= 3:
                    logger.warning(
                        f"Phát hiện trì trệ (đa dạng={diversity:.4f}, không cải thiện trong {generations_without_improvement} thế hệ). Tiêm đa dạng...")
                    # Tiêm các cá thể ngẫu nhiên mới để thoát khỏi tối ưu cục bộ
                    population = self._inject_diversity(population, injection_rate=0.2)
                    logger.info(" Hoàn thành tiêm đa dạng!")

            # Tạo thế hệ tiếp theo
            population = self._create_next_generation(population, fitness_scores, diversity, generation, actual_population_size)

        # Sau tất cả các thế hệ, giải mã cá thể tốt nhất tìm được để lấy siêu tham số tốt nhất
        best_params = self._decode_individual(best_individual) if best_individual else {}

        # Biên dịch kết quả cuối cùng theo định dạng tương tự cv_results_ của GridSearchCV
        cv_results = {
            'params': all_individuals,
            'mean_test_score': all_scores,
            'std_test_score': [0.0] * len(all_scores),  # Độ lệch chuẩn không được tính trong thiết lập này
            'rank_test_score': self._compute_ranks(all_scores),
            'convergence_history': convergence_history,
            'diversity_history': diversity_history,
            'best_generation': best_generation + 1,
            'total_evaluations': len(all_individuals)
        }

        # Thêm mean_test_{metric} và std_test_{metric} cho mỗi metric
        # Những thứ này được mong đợi bởi hàm training trong engine.py
        if all_metric_scores:
            # Lấy tất cả tên metric từ kết quả đầu tiên
            metric_names = list(all_metric_scores[0].keys())

            for metric_name in metric_names:
                # Trích xuất điểm số cho metric này từ tất cả các đánh giá
                metric_scores_list = [scores.get(metric_name, 0.0) for scores in all_metric_scores]
                cv_results[f'mean_test_{metric_name}'] = metric_scores_list
                cv_results[f'std_test_{metric_name}'] = [0.0] * len(metric_scores_list)  # Không có std trong GA

                # Thêm xếp hạng cho metric này
                cv_results[f'rank_test_{metric_name}'] = self._compute_ranks(metric_scores_list)

        # Nếu best_all_scores không được đặt (không nên xảy ra), tạo mặc định
        if best_all_scores is None:
            scoring = self.config.get('scoring', {})
            if isinstance(scoring, dict) and scoring:
                best_all_scores = {metric: 0.0 for metric in scoring.keys()}
                # Đặt metric chính bằng best_score
                primary_metric = self.config.get('metric_sort', 'accuracy')
                if primary_metric in best_all_scores:
                    best_all_scores[primary_metric] = best_score
            else:
                best_all_scores = {'accuracy': best_score}

        # Tóm tắt cuối cùng
        logger.info(f"{'=' * 60}")
        logger.info(f"Hoàn thành Tìm kiếm Thuật toán Di truyền!")
        logger.info(f"{'=' * 60}")
        logger.info(f"Tổng số đánh giá: {len(all_individuals)}")
        logger.info(f"Điểm số tốt nhất: {best_score:.4f} (đạt được tại thế hệ {best_generation + 1})")
        logger.info(f"Tham số tốt nhất: {best_params}")
        logger.info(f"Đa dạng quần thể cuối cùng: {diversity_history[-1]:.4f}")

        # Báo cáo hiệu quả cache nếu được bật
        if self.config.get('use_global_cache', True) and self._total_evaluations > 0:
            cache_efficiency = (self._cache_hits / self._total_evaluations) * 100
            logger.info(
                f"Hiệu quả cache: {self._cache_hits}/{self._total_evaluations} ({cache_efficiency:.1f}% tỷ lệ trúng)")
            logger.info(f"Đánh giá duy nhất: {self._total_evaluations - self._cache_hits}")

        # In vị trí file log nếu logging được bật
        if self.config['save_log'] and log_file:
            logger.info(f"Log chi tiết đã lưu vào: {log_file}")

        # Xóa cache và chuyển đổi kiểu numpy trước khi trả về
        return self._finalize_results(best_params, best_score, best_all_scores, cv_results)

    @staticmethod
    def _compute_ranks(scores: List[float]) -> List[int]:
        """Tính xếp hạng cho điểm số (1 = tốt nhất)."""
        if not scores:
            return []

        # Xử lý trường hợp tất cả điểm số giống nhau
        if len(set(scores)) == 1:
            return [1] * len(scores)

        sorted_indices = np.argsort(scores)[::-1]
        ranks = np.empty_like(sorted_indices)
        ranks[sorted_indices] = np.arange(1, len(scores) + 1)
        return ranks.tolist()
