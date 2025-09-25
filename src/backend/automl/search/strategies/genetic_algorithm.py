import os
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_val_score, cross_validate
from ..base import SearchStrategy
import random
import copy


class GeneticAlgorithm(SearchStrategy):
    """Genetic Algorithm implementation for hyperparameter optimization"""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        config = SearchStrategy.get_default_config()
        config.update({
            # Kích thước quần thể dùng để search
            'population_size': 100,  # Increased for better exploration
            # Số thế hệ (số lần thuật toán sẽ tiến hóa quần thể)
            'generation': 50,        # More generations to allow evolution
            # Tý lệ đột biến (Xác suất mỗi tham số cá thể bị thay đổi ngẫu nhiên)
            'mutation_rate': 0.5,    # Higher rate for more diversity
            # Tỷ lệ lai ghép (Xác suất hai cá thể cha mẹ sẽ trao đổi gen để tạo ra con)
            'crossover_rate': 0.8,
            # Số lượng cá thể được giữ lại không qua lai ghép, đột biến
            'elite_size': 2,
            # Kích thước giải đấu (Số cá thể tham gia mỗi vòng chọn lọc để làm cha mẹ)
            'tournament_size': 5,    # Larger tournament for better selection
        })
        return config

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.param_bounds = {}
        self.param_types = {}

    def _encode_parameters(self, param_grid: Dict[str, Any]) -> Dict[str, Any]:
        """Encode parameter grid for genetic algorithm."""
        # Clear previous parameter bounds and types to avoid cross-contamination between models
        self.param_bounds.clear()
        self.param_types.clear()

        encoded_grid = {}

        for param_name, param_values in param_grid.items():
            if isinstance(param_values, list):
                encoded_grid[param_name] = list(range(len(param_values)))
                self.param_bounds[param_name] = (0, len(param_values) - 1)
                self.param_types[param_name] = ('categorical', param_values)
            elif isinstance(param_values, tuple) and len(param_values) == 2:
                min_val, max_val = param_values
                encoded_grid[param_name] = (min_val, max_val)
                self.param_bounds[param_name] = (min_val, max_val)
                if isinstance(min_val, int) and isinstance(max_val, int):
                    self.param_types[param_name] = ('integer', None)
                else:
                    self.param_types[param_name] = ('continuous', None)
            else:
                raise ValueError(f"Unsupported parameter type for {param_name}: {type(param_values)}")

        return encoded_grid

    def _decode_individual(self, individual: Dict[str, float]) -> Dict[str, Any]:
        """Decode individual from genetic representation to actual parameter values."""
        decoded = {}

        for param_name, value in individual.items():
            param_type, param_values = self.param_types[param_name]

            if param_type == 'categorical':
                index = int(round(value))
                index = max(0, min(index, len(param_values) - 1))
                decoded[param_name] = param_values[index]
            elif param_type == 'integer':
                decoded[param_name] = int(round(value))
            else:
                decoded[param_name] = float(value)

        return decoded

    def _create_individual(self) -> Dict[str, float]:
        """Create an individual for genetic algorithm."""
        individual = {}

        for param_name, (min_val, max_val) in self.param_bounds.items():
            individual[param_name] = random.uniform(min_val, max_val)

        return individual

    def _evaluate_individual(self, individual: Dict[str, float], model: BaseEstimator, X: np.ndarray,
                             y: np.ndarray) -> dict:
        """Evaluate an individual using cross-validation."""
        try:
            params = self._decode_individual(individual)

            model.set_params(**params)

            scoring_metrics = ['accuracy', 'precision_macro', 'recall_macro', 'f1_macro']

            # use cross_validate instead of cross_val_score to get scores for each fold
            scores = cross_validate(
                model, X, y,
                cv=self.config['cv'],
                scoring=scoring_metrics,
                n_jobs=self.config['n_jobs'],
                error_score=self.config['error_score']
            )

            return {
                'accuracy': np.mean(scores['test_accuracy']),
                'precision': np.mean(scores['test_precision_macro']),
                'recall': np.mean(scores['test_recall_macro']),
                'f1': np.mean(scores['test_f1_macro'])
            }

        except Exception:
            return {
                'accuracy': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0
            }

    def _tournament_selection(self, population: List[Dict[str, float]], fitness_scores: List[float]) -> Dict[
        str, float]:
        """Select an individual using tournament selection."""
        tournament_indices = random.sample(range(len(population)), min(self.config['tournament_size'], len(population)))
        tournament_fitness = [fitness_scores[i] for i in tournament_indices]
        winner_index = tournament_indices[np.argmax(tournament_fitness)]
        return copy.deepcopy(population[winner_index])

    def _crossover(self, parent1: Dict[str, float], parent2: Dict[str, float]) -> Tuple[
        Dict[str, float], Dict[str, float]]:
        """Perform a crossover between two individuals."""
        if random.random() > self.config['crossover_rate']:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)

        for param_name in parent1.keys():
            if random.random() < 0.5:
                child1[param_name], child2[param_name] = child2[param_name], child1[param_name]

        return child1, child2

    def _mutate(self, individual: Dict[str, float]) -> Dict[str, float]:
        """Mutate an individual."""
        mutated = copy.deepcopy(individual)

        for param_name in mutated.keys():
            if random.random() < self.config['mutation_rate']:
                min_val, max_val = self.param_bounds[param_name]
                param_type, param_values = self.param_types[param_name]

                if param_type == 'categorical':
                    # For categorical parameters, randomly select a new value
                    mutated[param_name] = random.uniform(min_val, max_val)
                else:
                    # For continuous/integer parameters, use stronger mutation
                    current_val = mutated[param_name]
                    mutation_strength = (max_val - min_val) * 0.3
                    new_val = current_val + random.gauss(0, mutation_strength)
                    mutated[param_name] = max(min_val, min(new_val, max_val))

        return mutated

    def search(self, model: BaseEstimator, param_grid: Dict[str, Any], X: np.ndarray, y: np.ndarray, **kwargs):
        """Execute genetic algorithm search.

               Args:
                   model: The estimator to search over
                   param_grid: Dictionary with parameters names as keys and ranges/lists as values
                   X: Training data features
                   y: Training data targets
                   **kwargs: Additional configuration parameters

               Returns:
                   tuple: (best_params, best_score, cv_results)
        """
        # Update the algorithm's configuration with any provided keyword arguments
        self.set_config(**{k: v for k, v in kwargs.items() if k in self.config})

        # Convert the hyperparameter grid into a format suitable for the genetic algorithm.
        encoded_grid = self._encode_parameters(param_grid)
        # Create the initial population of individuals (potential solutions).
        population = [self._create_individual() for _ in range(self.config['population_size'])]

        # Lists to store the history of all individuals and their scores across all generations.
        all_individuals = []
        all_scores = []

        # List to store the history of all generations.
        generation_history = []

        # Initialize variables to keep track of the best solution found so far.
        best_individual = None
        best_score = float('-inf')

        # Execute the genetic algorithm.
        for generation in range(self.config['generation']):
            # Lists to store the fitness scores for the current generation.
            fitness_scores = []
            all_scores_in_generation = []

            # Evaluate each individual in the current population.
            for individual in population:
                # Calculate performance metrics (accuracy, precision, recall, f1, ...) for the current individual.
                scores = self._evaluate_individual(individual, model, X, y)
                all_scores_in_generation.append(scores)

                # Determine the primary metric for fitness evaluation. (e.g., accuracy, f1, ...)
                primary_metric = self.config.get('scoring', 'f1').replace('_macro', '')
                # Get the score for the primary metric to use as the individual's fitness'.
                score = scores.get(primary_metric, 0.0)
                fitness_scores.append(score)

                # Record the decoded parameters and score for historical tracking.
                all_individuals.append(self._decode_individual(individual))
                all_scores.append(score)

                # If the current individual is better than the best so far, update the best solution.
                if score > best_score:
                    best_score = score
                    best_individual = copy.deepcopy(individual)

            best_idx_in_generation = np.argmax(fitness_scores)
            best_individual_in_generation = population[best_idx_in_generation]
            best_params_in_generation = self._decode_individual(best_individual_in_generation)
            best_score_in_generation = all_scores_in_generation[best_idx_in_generation]

            generation_log_entry = {
                 'model': model.__class__.__name__,
                'run_type': f'genetic_algorithm_gen_{generation + 1}',
                'best_params': str(best_params_in_generation),
                'accuracy': best_score_in_generation['accuracy'],
                'precision': best_score_in_generation['precision'],
                'recall': best_score_in_generation['recall'],
                'f1': best_score_in_generation['f1']
            }
            generation_history.append(generation_log_entry)

            # --- Create the next generation ---
            new_population = []

            # Elitism: Directly carry over the best individuals to the next generation.
            elite_indices = np.argsort(fitness_scores)[-self.config['elite_size']:]
            for idx in elite_indices:
                new_population.append(copy.deepcopy(population[idx]))

            # Fill the rest with the new population using selection, crossover, and mutation.
            while len(new_population) < self.config['population_size']:
                # Select two parent individuals from the old population.
                parent1 = self._tournament_selection(population, fitness_scores)
                parent2 = self._tournament_selection(population, fitness_scores)

                # Create two offspring by performing crossover on the parents.
                child1, child2 = self._crossover(parent1, parent2)
                # Apply mutation to the offspring to introduce genetic diversity.
                child1 = self._mutate(child1)
                child2 = self._mutate(child2)

                # Add the new offspring to the next generation's population.
                new_population.extend([child1, child2])

            # Replace the old population with the newly created one.
            population = new_population[:self.config['population_size']]

        # After all generations, decode the best individual found to get the best hyperparameters.
        best_params = self._decode_individual(best_individual) if best_individual else {}

        # Compile the final results in a format similar to GridSearchCV's cv_results_.
        cv_results = {
            'params': all_individuals,
            'mean_test_score': all_scores,
            'std_test_score': [0.0] * len(all_scores),  # Std deviation is not calculated in this setup.
            'rank_test_score': self._compute_ranks(all_scores)
        }

        if generation_history:
            model_name = model.__class__.__name__
            output_file = f'ga_generation_log_{model_name}.csv'
            df_generation_history = pd.DataFrame(generation_history)
            df_generation_history.to_csv(output_file, index=False)
            print(f"\nAll generation log saved to: {output_file}")

        # Return the best parameters, the best score, and the comprehensive results.
        return best_params, best_score, cv_results

    def _compute_ranks(self, scores: List[float]) -> List[int]:
        """Compute ranks for scores (1 = best)."""
        sorted_indices = np.argsort(scores)[::-1]
        ranks = np.empty_like(sorted_indices)
        ranks[sorted_indices] = np.arange(1, len(scores) + 1)
        return ranks.tolist()