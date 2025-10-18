import os
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_validate
from automl.search.strategy.base import SearchStrategy
import random
import copy
from datetime import datetime


class GeneticAlgorithm(SearchStrategy):
    """Genetic Algorithm implementation for hyperparameter optimization"""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        config = SearchStrategy.get_default_config()
        config.update({
            'population_size': 50,
            'generation': 20,
            'mutation_rate': 0.1,
            'crossover_rate': 0.8,
            'elite_size': 5,
            'tournament_size': 3,
            'log_dir': 'logs',
            'save_log': False,
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

            # Get scoring configuration
            scoring_config = self.config.get('scoring')
            
            # Determine which scoring metrics to use
            if isinstance(scoring_config, dict):
                # Use the provided scorer dict (from engine.py with make_scorer objects)
                scoring_metrics = scoring_config
                # Extract metric names from the dict keys
                metric_names = list(scoring_config.keys())
            else:
                # Default scoring metrics (backward compatibility)
                scoring_metrics = ['accuracy', 'precision_macro', 'recall_macro', 'f1_macro']
                metric_names = ['accuracy', 'precision', 'recall', 'f1']

            # use cross_validate instead of cross_val_score to get scores for each fold
            scores = cross_validate(
                model, X, y,
                cv=self.config['cv'],
                scoring=scoring_metrics,
                n_jobs=self.config['n_jobs'],
                error_score=self.config['error_score']
            )

            # Build result dictionary
            result = {}
            if isinstance(scoring_config, dict):
                # When scoring is a dict, the keys are already the metric names
                for metric_name in metric_names:
                    result[metric_name] = np.mean(scores[f'test_{metric_name}'])
            else:
                # Default mapping for backward compatibility
                result = {
                    'accuracy': np.mean(scores['test_accuracy']),
                    'precision': np.mean(scores['test_precision_macro']),
                    'recall': np.mean(scores['test_recall_macro']),
                    'f1': np.mean(scores['test_f1_macro'])
                }
            
            return result

        except Exception:
            # Return zeros for all metrics
            if isinstance(self.config.get('scoring'), dict):
                return {metric: 0.0 for metric in self.config['scoring'].keys()}
            else:
                return {
                    'accuracy': 0.0,
                    'precision': 0.0,
                    'recall': 0.0,
                    'f1': 0.0
                }

    def _tournament_selection(self, population: List[Dict[str, float]], fitness_scores: List[float]) -> Dict[
        str, float]:
        """Select an individual using tournament selection."""
        if not population or not fitness_scores:
            raise ValueError("Population and fitness scores cannot be empty")
        
        # Ensure tournament size doesn't exceed population size
        tournament_size = min(self.config['tournament_size'], len(population))
        tournament_indices = random.sample(range(len(population)), tournament_size)
        tournament_fitness = [fitness_scores[i] for i in tournament_indices]
        winner_index = tournament_indices[np.argmax(tournament_fitness)]
        return copy.deepcopy(population[winner_index])

    def _crossover(self, parent1: Dict[str, float], parent2: Dict[str, float]) -> Tuple[
        Dict[str, float], Dict[str, float]]:
        """Perform a crossover between two individuals using different strategy based on parameter types."""
        if random.random() > self.config['crossover_rate']:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)

        for param_name in parent1.keys():
            param_type, param_values = self.param_types[param_name]
            
            if param_type == 'categorical':
                # For categorical parameters, use uniform crossover
                if random.random() < 0.5:
                    child1[param_name], child2[param_name] = child2[param_name], child1[param_name]
            else:
                # For continuous/integer parameters, use blend crossover (BLX-α)
                alpha = 0.5  # Blending factor
                min_val = min(parent1[param_name], parent2[param_name])
                max_val = max(parent1[param_name], parent2[param_name])
                range_val = max_val - min_val
                
                # Extend the range by alpha factor on both sides
                lower = min_val - alpha * range_val
                upper = max_val + alpha * range_val
                
                # Ensure bounds are respected
                param_min, param_max = self.param_bounds[param_name]
                lower = max(lower, param_min)
                upper = min(upper, param_max)
                
                # Generate random values within the extended range
                child1[param_name] = random.uniform(lower, upper)
                child2[param_name] = random.uniform(lower, upper)

        return child1, child2

    def _mutate(self, individual: Dict[str, float], generation: int = 0, max_generation: int = None) -> Dict[str, float]:
        """Mutate an individual with adaptive mutation strength.
        
        Args:
            individual: The individual to mutate
            generation: Current generation number (for adaptive mutation)
            max_generation: Maximum number of generations (for adaptive mutation)
        """
        mutated = copy.deepcopy(individual)
        
        # Adaptive mutation rate - decreases as generations progress
        if max_generation and max_generation > 0:
            adaptive_rate = self.config['mutation_rate'] * (1 - generation / max_generation)
        else:
            adaptive_rate = self.config['mutation_rate']

        for param_name in mutated.keys():
            if random.random() < adaptive_rate:
                min_val, max_val = self.param_bounds[param_name]
                param_type, param_values = self.param_types[param_name]
                
                current_val = mutated[param_name]
                
                if param_type == 'categorical':
                    # For categorical, pick a random different value
                    possible_values = list(range(int(min_val), int(max_val) + 1))
                    if len(possible_values) > 1:
                        possible_values.remove(int(round(current_val)))
                        mutated[param_name] = float(random.choice(possible_values))
                else:
                    # For continuous/integer, use gaussian mutation with adaptive strength
                    mutation_strength = (max_val - min_val) * (0.2 * (1 - generation / (max_generation + 1)) if max_generation else 0.1)
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
                   tuple: (best_params, best_score, best_all_scores, cv_results)
                       - best_params: Dictionary of best parameters
                       - best_score: Best score achieved
                       - best_all_scores: Dictionary with all metric scores for best parameters
                       - cv_results: Dictionary with detailed cross-validation results
        """
        # Update the algorithm's configuration with any provided keyword arguments
        self.set_config(**{k: v for k, v in kwargs.items() if k in self.config})
        
        # Validate configuration
        if self.config['population_size'] < 2:
            raise ValueError("Population size must be at least 2")
        if self.config['elite_size'] >= self.config['population_size']:
            self.config['elite_size'] = max(1, self.config['population_size'] // 4)

        # Create log directory and file if needed
        log_file = None
        if self.config['save_log']:
            log_dir = self.config['log_dir']
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_name = model.__class__.__name__
            log_file = os.path.join(log_dir, f'genetic_algorithm_{model_name}_{timestamp}.csv')

        # Convert the hyperparameter grid into a format suitable for the genetic algorithm.
        encoded_grid = self._encode_parameters(param_grid)
        # Create the initial population of individuals (potential solutions).
        population = [self._create_individual() for _ in range(self.config['population_size'])]

        # Lists to store the history of all individuals and their scores across all generations.
        all_individuals = []
        all_scores = []
        generation_history = []  # Store history for logging

        # Initialize variables to keep track of the best solution found so far.
        best_individual = None
        best_score = float('-inf')
        best_all_scores = None  # Track all metrics for the best individual

        # Execute the genetic algorithm.
        for generation in range(self.config['generation']):
            # Lists to store the fitness scores for the current generation.
            fitness_scores = []

            # Evaluate each individual in the current population.
            for individual in population:
                # Calculate performance metrics (accuracy, precision, recall, f1, ...) for the current individual.
                scores = self._evaluate_individual(individual, model, X, y)

                # Determine the primary metric for fitness evaluation. (e.g., accuracy, f1, ...)
                scoring_config = self.config.get('scoring', 'f1')
                
                # Handle both string and dict scoring configurations
                if isinstance(scoring_config, dict):
                    # When scoring is a dict, use metric_sort to determine which metric to optimize
                    primary_metric = self.config.get('metric_sort', 'accuracy')
                elif isinstance(scoring_config, str):
                    # When scoring is a string, extract the base metric name
                    primary_metric = scoring_config.replace('_macro', '').replace('_weighted', '')
                else:
                    # Default fallback
                    primary_metric = 'f1'
                
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
                    best_all_scores = scores.copy()  # Save all metrics for the best individual
                
                # Save to generation history for logging
                if self.config['save_log']:
                    history_entry = {
                        'generation': generation + 1,
                        'individual_id': len(generation_history) + 1,
                        'best_params': str(self._decode_individual(individual)),
                        'accuracy': scores.get('accuracy', 0.0),
                        'precision': scores.get('precision', 0.0),
                        'recall': scores.get('recall', 0.0),
                        'f1': scores.get('f1', 0.0),
                        'fitness_score': score,
                        'is_best_so_far': score == best_score
                    }
                    generation_history.append(history_entry)

            # Save log after each generation
            if self.config['save_log'] and log_file:
                df = pd.DataFrame(generation_history)
                df.to_csv(log_file, index=False)

            # --- Create the next generation ---
            new_population = []

            # Elitism: Directly carry over the best individuals to the next generation.
            elite_indices = np.argsort(fitness_scores)[-self.config['elite_size']:]
            for idx in elite_indices:
                new_population.append(copy.deepcopy(population[idx]))

            # Fill the rest of the new population using selection, crossover, and mutation.
            while len(new_population) < self.config['population_size']:
                # Select two parent individuals from the old population.
                parent1 = self._tournament_selection(population, fitness_scores)
                parent2 = self._tournament_selection(population, fitness_scores)

                # Create two offspring by performing crossover on the parents.
                child1, child2 = self._crossover(parent1, parent2)
                # Apply mutation to the offspring to introduce genetic diversity.
                child1 = self._mutate(child1, generation, self.config['generation'])
                child2 = self._mutate(child2, generation, self.config['generation'])

                # Add offspring to the next generation, being careful not to exceed population size
                if len(new_population) < self.config['population_size']:
                    new_population.append(child1)
                if len(new_population) < self.config['population_size']:
                    new_population.append(child2)

            # Replace the old population with the newly created one.
            population = new_population

        # After all generations, decode the best individual found to get the best hyperparameters.
        best_params = self._decode_individual(best_individual) if best_individual else {}

        # Compile the final results in a format similar to GridSearchCV's cv_results_.
        cv_results = {
            'params': all_individuals,
            'mean_test_score': all_scores,
            'std_test_score': [0.0] * len(all_scores),  # Std deviation is not calculated in this setup.
            'rank_test_score': self._compute_ranks(all_scores)
        }

        # If best_all_scores was not set (shouldn't happen), create default
        if best_all_scores is None:
            best_all_scores = {
                'accuracy': best_score,
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0
            }
        
        # Print log file location if logging is enabled
        if self.config['save_log'] and log_file:
            print(f"\nGenetic Algorithm log saved to: {log_file}")
        
        # Return the best parameters, the best score, all metrics, and the comprehensive results.
        return best_params, best_score, best_all_scores, cv_results

    def _compute_ranks(self, scores: List[float]) -> List[int]:
        """Compute ranks for scores (1 = best)."""
        if not scores:
            return []
        
        # Handle case where all scores are identical
        if len(set(scores)) == 1:
            return [1] * len(scores)
        
        sorted_indices = np.argsort(scores)[::-1]
        ranks = np.empty_like(sorted_indices)
        ranks[sorted_indices] = np.arange(1, len(scores) + 1)
        return ranks.tolist()