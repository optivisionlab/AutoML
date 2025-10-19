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
from joblib import Parallel, delayed
from functools import lru_cache


class GeneticAlgorithm(SearchStrategy):
    """Genetic Algorithm implementation for hyperparameter optimization"""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        config = SearchStrategy.get_default_config()
        config.update({
            'population_size': 10,  # Ultra small for extreme speed
            'generation': 5,  # Very few generations
            'mutation_rate': 0.2,  # Higher for faster exploration
            'crossover_rate': 0.9,  # Very high crossover
            'elite_size': 2,  # Minimal elite
            'tournament_size': 2,  # Minimal tournament
            'log_dir': 'logs',
            'save_log': False,
            'early_stopping_patience': 2,  # Ultra aggressive early stopping
            'early_stopping_enabled': True,
            'parallel_evaluation': True,
            'adaptive_population': True,  # Dynamic population sizing
            'min_population': 4,  # Very small minimum
            'max_population': 12,  # Small maximum
            'convergence_threshold': 0.002,  # Less strict for faster convergence
            'use_global_cache': True,  # Cache evaluations across generations
            'max_cache_size': 1000,  # Larger cache
            'fast_mode': True,  # Enable all speed optimizations
            'n_initial_random': 3,  # Minimal random evaluations
            'ultra_fast_mode': True,  # New: Enable ultra fast mode
            'skip_diversity_check': True,  # Skip diversity calculations for speed
            'simple_crossover': True,  # Use simpler crossover for speed
        })
        return config

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.param_bounds = {}
        self.param_types = {}
        self._decode_cache = {}  # Cache for decoded parameters
        self._evaluation_cache = {}  # Global cache for fitness evaluations
        self._cache_hits = 0  # Track cache efficiency
        self._total_evaluations = 0
    
    def _convert_numpy_types(self, obj):
        """Convert numpy types to native Python types recursively."""
        import numpy as np
        
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._convert_numpy_types(item) for item in obj)
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        else:
            return obj

    def _make_hashable(self, individual: Dict[str, float]) -> tuple:
        """Convert individual to hashable format for caching."""
        return tuple(sorted(individual.items()))

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
        """Decode                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       an individual from genetic representation to actual parameter values with caching."""
        # Check cache first
        cache_key = self._make_hashable(individual)
        if cache_key in self._decode_cache:
            return self._decode_cache[cache_key].copy()
        
        decoded = {}

        for param_name, value in individual.items():
            param_type, param_values = self.param_types[param_name]

            if param_type == 'categorical':
                index = int(round(value))
                index = max(0, min(index, len(param_values) - 1))
                param_value = param_values[index]
                # Convert numpy types to native Python types
                if isinstance(param_value, np.integer):
                    decoded[param_name] = int(param_value)
                elif isinstance(param_value, np.floating):
                    decoded[param_name] = float(param_value)
                else:
                    decoded[param_name] = param_value
            elif param_type == 'integer':
                decoded[param_name] = int(round(value))
            else:
                decoded[param_name] = float(value)

        # Cache the result
        self._decode_cache[cache_key] = decoded
        return decoded

    def _create_individual(self) -> Dict[str, float]:
        """Create an individual for genetic algorithm."""
        individual = {}

        for param_name, (min_val, max_val) in self.param_bounds.items():
            individual[param_name] = random.uniform(min_val, max_val)

        return individual
    
    def _create_smart_population(self, size: int) -> List[Dict[str, float]]:
        """Create an initial population using smart initialization (grid and random)."""
        population = []
        
        # Create a mini-grid for each parameter (2-3 points per parameter)
        grid_points = {}
        for param_name, (min_val, max_val) in self.param_bounds.items():
            param_type, _ = self.param_types[param_name]
            if param_type == 'categorical':
                # For categorical, sample evenly
                n_values = int(max_val - min_val + 1)
                if n_values <= 3:
                    grid_points[param_name] = [float(i) for i in range(int(min_val), int(max_val) + 1)]
                else:
                    # Sample 3 points
                    grid_points[param_name] = [min_val, (min_val + max_val) / 2, max_val]
            else:
                # For continuous/integer, use 3 points: min, mid, max
                grid_points[param_name] = [min_val, (min_val + max_val) / 2, max_val]
        
        # Create grid combinations (but limit to population size)
        import itertools
        all_combinations = list(itertools.product(*[grid_points[p] for p in self.param_bounds.keys()]))
        
        # If we have fewer combinations than population size, use all
        if len(all_combinations) <= size:
            for combo in all_combinations:
                individual = dict(zip(self.param_bounds.keys(), combo))
                population.append(individual)
        else:
            # Sample from combinations
            selected_indices = random.sample(range(len(all_combinations)), min(size // 2, len(all_combinations)))
            for idx in selected_indices:
                combo = all_combinations[idx]
                individual = dict(zip(self.param_bounds.keys(), combo))
                population.append(individual)
        
        # Fill the rest with random individuals
        while len(population) < size:
            population.append(self._create_individual())
        
        return population[:size]

    def _evaluate_individual(self, individual: Dict[str, float], model: BaseEstimator, X: np.ndarray,
                             y: np.ndarray) -> dict:
        """Evaluate an individual using cross-validation with global caching."""
        self._total_evaluations += 1
        
        # Check global cache if enabled
        if self.config.get('use_global_cache', True):
            cache_key = self._make_hashable(individual)
            if cache_key in self._evaluation_cache:
                self._cache_hits += 1
                return self._evaluation_cache[cache_key].copy()
        
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
                    result[metric_name] = float(np.mean(scores[f'test_{metric_name}']))
            else:
                # Default mapping for backward compatibility
                result = {
                    'accuracy': float(np.mean(scores['test_accuracy'])),
                    'precision': float(np.mean(scores['test_precision_macro'])),
                    'recall': float(np.mean(scores['test_recall_macro'])),
                    'f1': float(np.mean(scores['test_f1_macro']))
                }
            
            # Cache the result if enabled
            if self.config.get('use_global_cache', True):
                cache_key = self._make_hashable(individual)
                # Manage cache size
                max_cache_size = self.config.get('max_cache_size', 500)
                if len(self._evaluation_cache) >= max_cache_size:
                    # Remove oldest entries (FIFO)
                    keys_to_remove = list(self._evaluation_cache.keys())[:max_cache_size // 4]
                    for key in keys_to_remove:
                        del self._evaluation_cache[key]
                self._evaluation_cache[cache_key] = result.copy()
            
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

    def _tournament_selection(self, population: List[Dict[str, float]], fitness_scores) -> Dict[
        str, float]:
        """Select an individual using tournament selection with numpy optimization."""
        # Handle both numpy array and list types
        if not population:
            raise ValueError("Population cannot be empty")
        if isinstance(fitness_scores, np.ndarray):
            if fitness_scores.size == 0:
                raise ValueError("Fitness scores cannot be empty")
        elif not fitness_scores:
            raise ValueError("Fitness scores cannot be empty")
        
        # Ensure tournament size doesn't exceed population size
        tournament_size = min(self.config['tournament_size'], len(population))
        # Use numpy for faster selection if fitness_scores is a numpy array
        if isinstance(fitness_scores, np.ndarray):
            tournament_indices = np.random.choice(len(population), size=tournament_size, replace=False)
            winner_index = tournament_indices[np.argmax(fitness_scores[tournament_indices])]
        else:
            tournament_indices = random.sample(range(len(population)), tournament_size)
            tournament_fitness = [fitness_scores[i] for i in tournament_indices]
            winner_index = tournament_indices[np.argmax(tournament_fitness)]
        # Return a shallow copy since we'll deepcopy when needed
        return population[winner_index].copy()

    def _crossover(self, parent1: Dict[str, float], parent2: Dict[str, float]) -> Tuple[
        Dict[str, float], Dict[str, float]]:
        """Perform a crossover between two individuals using different strategy based on parameter types."""
        if random.random() > self.config['crossover_rate']:
            return parent1.copy(), parent2.copy()

        # Ultra fast simple crossover
        if self.config.get('simple_crossover', False):
            # Simple uniform crossover - just swap half the parameters
            child1 = parent1.copy()
            child2 = parent2.copy()
            params = list(parent1.keys())
            if len(params) > 1:
                swap_point = len(params) // 2
                for param in params[:swap_point]:
                    child1[param], child2[param] = child2[param], child1[param]
            return child1, child2

        child1 = parent1.copy()
        child2 = parent2.copy()

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
        mutated = individual.copy()
        
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

    def _inject_diversity(self, population: List[Dict[str, float]], injection_rate: float = 0.3) -> List[Dict[str, float]]:
        """Inject new random individuals to increase diversity when the population stagnates.
        
        Args:
            population: Current population
            injection_rate: Fraction of population to replace with new random individuals
        
        Returns:
            Population with injected diversity
        """
        num_to_inject = int(len(population) * injection_rate)
        if num_to_inject == 0:
            return population
        
        # Sort population by fitness (keep the best)
        # Note: This assumes we have access to fitness scores, so we'll need to pass them
        # For now, we'll just replace random individuals
        new_population = population.copy()
        
        # Replace the worst individuals with new random ones
        injection_indices = random.sample(range(len(population)), num_to_inject)
        for idx in injection_indices:
            new_population[idx] = self._create_individual()
        
        return new_population
    
    def _calculate_population_diversity(self, population: List[Dict[str, float]]) -> float:
        """Calculate the diversity of the population using average pairwise distance."""
        if len(population) < 2:
            return 0.0
        
        total_distance = 0
        count = 0
        
        for i in range(len(population)):
            for j in range(i + 1, len(population)):
                distance = 0
                for param_name in population[i].keys():
                    param_type, _ = self.param_types[param_name]
                    if param_type == 'categorical':
                        # For categorical, use 0/1 distance
                        distance += 0 if population[i][param_name] == population[j][param_name] else 1
                    else:
                        # For continuous/integer, normalize the distance
                        min_val, max_val = self.param_bounds[param_name]
                        if max_val != min_val:
                            normalized_diff = abs(population[i][param_name] - population[j][param_name]) / (max_val - min_val)
                            distance += normalized_diff
                
                total_distance += distance / len(population[i])  # Average over parameters
                count += 1
        
        return total_distance / count if count > 0 else 0.0

    def _evaluate_population_parallel(self, population: List[Dict[str, float]], model: BaseEstimator, 
                                    X: np.ndarray, y: np.ndarray) -> List[Dict[str, float]]:
        """Evaluate all individuals in parallel with smart optimization."""
        n_jobs = self.config.get('n_jobs', -1)
        
        # If explicitly set to 1, use sequential
        if n_jobs == 1:
            return [self._evaluate_individual(individual, model, X, y) for individual in population]
        
        # Smart parallel decision based on population size and CV folds
        cv_folds = self.config.get('cv', 5)
        min_parallel_work = cv_folds * 3  # Need at least 3x CV work per core to benefit
        
        if n_jobs == -1:
            import multiprocessing
            n_jobs = multiprocessing.cpu_count()
        
        # Calculate total work units (population * cv_folds)
        total_work = len(population) * cv_folds
        
        # Only use parallel if we have enough work to justify the overhead
        # Rule: at least 2 work units per core AND population > 4
        if total_work >= (n_jobs * 2) and len(population) > 4:
            # Use optimal number of jobs (don't use more cores than work units)
            optimal_jobs = min(n_jobs, len(population))
            
            # Choose backend based on model complexity
            # Threading is faster for simple models, loky for complex ones
            backend = 'threading' if cv_folds <= 3 else 'loky'
            
            results = Parallel(n_jobs=optimal_jobs, backend=backend)(
                delayed(self._evaluate_individual)(individual, copy.deepcopy(model), X, y) 
                for individual in population
            )
            return results
        else:
            # Sequential is faster for small populations
            return [self._evaluate_individual(individual, model, X, y) for individual in population]

    def search(self, model: BaseEstimator, param_grid: Dict[str, Any], X: np.ndarray, y: np.ndarray, **kwargs):
        """Execute genetic algorithm search with enhanced loop features.

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

        # Create a log directory and file if needed
        log_file = None
        if self.config['save_log']:
            log_dir = self.config['log_dir']
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_name = model.__class__.__name__
            log_file = os.path.join(log_dir, f'genetic_algorithm_{model_name}_{timestamp}.csv')

        # Convert the hyperparameter grid into a format suitable for the genetic algorithm.
        encoded_grid = self._encode_parameters(param_grid)
        
        # Adaptive population sizing based on parameter space complexity
        if self.config.get('adaptive_population', True) and self.config.get('fast_mode', True):
            # Calculate parameter space size
            param_space_size = 1
            for param_name, (min_val, max_val) in self.param_bounds.items():
                param_type, param_values = self.param_types[param_name]
                if param_type == 'categorical':
                    param_space_size *= (max_val - min_val + 1)
                else:
                    param_space_size *= 10  # Approximate for continuous
            
            # Adapt population size with tighter bounds for faster runtime
            min_pop = self.config.get('min_population', 8)
            max_pop = self.config.get('max_population', 25)
            adaptive_pop_size = min(max_pop, max(min_pop, int(np.log(param_space_size) * 2)))
            actual_population_size = min(adaptive_pop_size, self.config['population_size'])
        else:
            actual_population_size = self.config['population_size']
        
        # Create the initial population using smart or random initialization
        if self.config.get('ultra_fast_mode', False):
            # In ultra fast mode, use mostly random population
            population = [self._create_individual() for _ in range(actual_population_size)]
        elif self.config.get('init_strategy', 'smart') == 'smart':
            population = self._create_smart_population(actual_population_size)
        else:
            population = [self._create_individual() for _ in range(actual_population_size)]

        # Lists to store the history of all individuals and their scores across all generations.
        all_individuals = []
        all_scores = []
        all_metric_scores = []  # Store all metric scores for each individual
        generation_history = []  # Store history for logging

        # Initialize variables to keep track of the best solution found so far.
        best_individual = None
        best_score = float('-inf')
        best_all_scores = None  # Track all metrics for the best individual
        
        # Early stopping tracking
        early_stopping_enabled = self.config.get('early_stopping_enabled', True)
        early_stopping_patience = self.config.get('early_stopping_patience', 5)
        generations_without_improvement = 0
        best_generation = 0
        
        # Convergence tracking
        convergence_history = []
        diversity_history = []

        # Execute the genetic algorithm main loop
        verbose = self.config.get('verbose', 1)
        if verbose > 0:
            print(f"\nStarting Genetic Algorithm with {actual_population_size} individuals for {self.config['generation']} generations")
            if verbose > 1:
                print(f"Early stopping: {'Enabled' if early_stopping_enabled else 'Disabled'}" + 
                      (f" (patience: {early_stopping_patience})" if early_stopping_enabled else ""))
        
        for generation in range(self.config['generation']):
            generation_start_time = datetime.now()
            
            # Calculate population diversity (skip in ultra fast mode)
            if not self.config.get('skip_diversity_check', False):
                diversity = self._calculate_population_diversity(population)
                diversity_history.append(diversity)
            else:
                diversity = 1.0  # Dummy value for ultra fast mode
                diversity_history.append(diversity)
            
            # Progress indicator
            if verbose > 0 and (verbose > 1 or generation % 5 == 0 or generation == 0 or generation == self.config['generation'] - 1):
                print(f"\nGeneration {generation + 1}/{self.config['generation']} | Diversity: {diversity:.4f}", end="")
            
            # Evaluate population (with optimization for ultra fast mode)
            if self.config.get('ultra_fast_mode', False) and generation > 0:
                # In ultra fast mode after first generation, only evaluate new/changed individuals
                # Use cached scores for elite individuals
                all_individual_scores = []
                for idx, individual in enumerate(population):
                    if idx < self.config['elite_size'] and generation > 0:
                        # Elite individuals - use previous scores if available
                        cache_key = self._make_hashable(individual)
                        if cache_key in self._evaluation_cache:
                            all_individual_scores.append(self._evaluation_cache[cache_key].copy())
                        else:
                            all_individual_scores.append(self._evaluate_individual(individual, model, X, y))
                    else:
                        # New individuals - must evaluate
                        all_individual_scores.append(self._evaluate_individual(individual, model, X, y))
            else:
                # Normal evaluation
                all_individual_scores = self._evaluate_population_parallel(population, model, X, y)
            
            # Determine the primary metric for fitness evaluation
            scoring_config = self.config.get('scoring', 'f1')
            if isinstance(scoring_config, dict):
                primary_metric = self.config.get('metric_sort', 'accuracy')
            elif isinstance(scoring_config, str):
                primary_metric = scoring_config.replace('_macro', '').replace('_weighted', '')
            else:
                primary_metric = 'f1'
            
            # Extract fitness scores and track the best individual
            fitness_scores = np.zeros(len(population))  # Use numpy array for better performance
            generation_best_score = float('-inf')
            generation_improved = False
            
            for idx, (individual, scores) in enumerate(zip(population, all_individual_scores)):
                score = scores.get(primary_metric, 0.0)
                fitness_scores[idx] = score
                
                # Record for history
                all_individuals.append(self._decode_individual(individual))
                all_scores.append(score)
                all_metric_scores.append(scores.copy())  # Store all metric scores
                
                # Track generation best
                if score > generation_best_score:
                    generation_best_score = score
                
                # Update global best if improved
                if score > best_score:
                    best_score = score
                    best_individual = copy.deepcopy(individual)
                    best_all_scores = scores.copy()
                    best_generation = generation
                    generation_improved = True
                    generations_without_improvement = 0
                
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
                        'is_best_so_far': score == best_score,
                        'diversity': diversity,
                        'generation_best': generation_best_score
                    }
                    generation_history.append(history_entry)
            
            # Track convergence with numpy operations
            mean_fitness = fitness_scores.mean()
            std_fitness = fitness_scores.std()
            convergence_history.append({
                'generation': generation + 1,
                'best': best_score,
                'mean': mean_fitness,
                'std': std_fitness,
                'diversity': diversity
            })
            
            # Update progress with generation results
            generation_time = (datetime.now() - generation_start_time).total_seconds()
            if verbose > 0 and (verbose > 1 or generation % 5 == 0 or generation == 0 or generation == self.config['generation'] - 1):
                print(f" | Best: {generation_best_score:.4f} | Mean: {mean_fitness:.4f} | Std: {std_fitness:.4f} | Time: {generation_time:.2f}s", end="")
                
                if generation_improved and verbose > 1:
                    print(" ✓ NEW BEST!", end="")
            
            # Check early stopping with convergence threshold
            if not generation_improved:
                generations_without_improvement += 1
            
            # Check convergence threshold (very small improvements)
            convergence_threshold = self.config.get('convergence_threshold', 0.001)
            if generation > 0 and len(convergence_history) > 1:
                recent_improvement = convergence_history[-1]['best'] - convergence_history[-2]['best']
                if abs(recent_improvement) < convergence_threshold and generations_without_improvement >= 2:
                    print(f"\n\n✓ Convergence detected at generation {generation + 1} (improvement < {convergence_threshold:.4f})")
                    print(f"Best score {best_score:.4f} achieved at generation {best_generation + 1}")
                    break
                
            if early_stopping_enabled and generations_without_improvement >= early_stopping_patience:
                print(f"\n\n🛑 Early stopping triggered at generation {generation + 1} (no improvement for {early_stopping_patience} generations)")
                print(f"Best score {best_score:.4f} achieved at generation {best_generation + 1}")
                break
            
            # Save log after each generation
            if self.config['save_log'] and log_file:
                df = pd.DataFrame(generation_history)
                df.to_csv(log_file, index=False)
            
            # Check if population has converged (low diversity) - skip in ultra fast mode
            if not self.config.get('ultra_fast_mode', False):
                stagnation_threshold = 0.05
                if diversity < stagnation_threshold and generations_without_improvement >= 3:
                    print(f"\n⚠️ Stagnation detected (diversity={diversity:.4f}, no improvement for {generations_without_improvement} gen). Injecting diversity...")
                    # Inject new random individuals to escape local optima
                    population = self._inject_diversity(population, injection_rate=0.2)
                    print(" Diversity injection complete!", end="")
            
            # --- Create the next generation ---
            new_population = []
            
            # Elitism: Directly carry over the best individuals to the next generation
            elite_indices = np.argpartition(fitness_scores, -self.config['elite_size'])[-self.config['elite_size']:] if self.config['elite_size'] > 0 else []
            for idx in elite_indices:
                new_population.append(population[idx].copy())  # Shallow copy is sufficient here
            
            # Adaptive crossover rate based on diversity
            adaptive_crossover_rate = self.config['crossover_rate']
            if diversity < 0.1:  # Low diversity, increase exploration
                adaptive_crossover_rate = min(1.0, adaptive_crossover_rate * 1.2)
            
            # Fill the rest with the new population using selection, crossover, and mutation
            while len(new_population) < actual_population_size:
                # Select two parent individuals from the old population
                parent1 = self._tournament_selection(population, fitness_scores)
                parent2 = self._tournament_selection(population, fitness_scores)
                
                # Save original crossover rate and temporarily use adaptive rate
                original_rate = self.config['crossover_rate']
                self.config['crossover_rate'] = adaptive_crossover_rate
                
                # Create two offspring by performing crossover on the parents
                child1, child2 = self._crossover(parent1, parent2)
                
                # Restore original rate
                self.config['crossover_rate'] = original_rate
                
                # Apply mutation to the offspring to introduce genetic diversity
                child1 = self._mutate(child1, generation, self.config['generation'])
                child2 = self._mutate(child2, generation, self.config['generation'])
                
                # Add offspring to the next generation
                if len(new_population) < actual_population_size:
                    new_population.append(child1)
                if len(new_population) < actual_population_size:
                    new_population.append(child2)
            
            # Replace the old population with the newly created one
            population = new_population

        # After all generations, decode the best individual found to get the best hyperparameters
        best_params = self._decode_individual(best_individual) if best_individual else {}

        # Compile the final results in a format similar to GridSearchCV's cv_results_
        cv_results = {
            'params': all_individuals,
            'mean_test_score': all_scores,
            'std_test_score': [0.0] * len(all_scores),  # Std deviation is not calculated in this setup.
            'rank_test_score': self._compute_ranks(all_scores),
            'convergence_history': convergence_history,
            'diversity_history': diversity_history,
            'best_generation': best_generation + 1,
            'total_evaluations': len(all_individuals)
        }
        
        # Add mean_test_{metric} and std_test_{metric} for each metric
        # These are expected by the training function in engine.py
        if all_metric_scores:
            # Get all metric names from the first result
            metric_names = list(all_metric_scores[0].keys())
            
            for metric_name in metric_names:
                # Extract scores for this metric from all evaluations
                metric_scores_list = [scores.get(metric_name, 0.0) for scores in all_metric_scores]
                cv_results[f'mean_test_{metric_name}'] = metric_scores_list
                cv_results[f'std_test_{metric_name}'] = [0.0] * len(metric_scores_list)  # No std in GA
                
                # Add ranking for this metric
                cv_results[f'rank_test_{metric_name}'] = self._compute_ranks(metric_scores_list)

        # If best_all_scores was not set (shouldn't happen), create default
        if best_all_scores is None:
            best_all_scores = {
                'accuracy': best_score,
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0
            }
        
        # Final summary
        print(f"\n\n{'=' * 60}")
        print(f"Genetic Algorithm Search Complete!")
        print(f"{'=' * 60}")
        print(f"Total evaluations: {len(all_individuals)}")
        print(f"Best score: {best_score:.4f} (achieved at generation {best_generation + 1})")
        print(f"Best parameters: {best_params}")
        print(f"Final population diversity: {diversity_history[-1]:.4f}")
        
        # Report cache efficiency if enabled
        if self.config.get('use_global_cache', True) and self._total_evaluations > 0:
            cache_efficiency = (self._cache_hits / self._total_evaluations) * 100
            print(f"Cache efficiency: {self._cache_hits}/{self._total_evaluations} ({cache_efficiency:.1f}% hit rate)")
            print(f"Unique evaluations: {self._total_evaluations - self._cache_hits}")
        
        # Print the log file location if logging is enabled
        if self.config['save_log'] and log_file:
            print(f"\nDetailed log saved to: {log_file}")
        
        # Clear caches after the search completes
        self._decode_cache.clear()
        if hasattr(self, '_evaluation_cache'):
            self._evaluation_cache.clear()
        if hasattr(self, '_model_copies'):
            self._model_copies.clear()
        
        # Convert all numpy types to native Python types before returning
        best_params = self._convert_numpy_types(best_params)
        best_score = self._convert_numpy_types(best_score)
        best_all_scores = self._convert_numpy_types(best_all_scores)
        cv_results = self._convert_numpy_types(cv_results)
        
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