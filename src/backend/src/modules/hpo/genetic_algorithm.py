# Standard Libraries
import logging
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import BaseCrossValidator, ParameterGrid

# Local Libraries
from src.modules.hpo.base import BaseSearchCV, TrialPruned


# Logging
logger = logging.getLogger(__name__)


class GeneticAlgorithmSearch(BaseSearchCV):
    """
    Hyperparameter optimization using Genetic Algorithm (GA)
    """

    def __init__(
        self,
        estimator: BaseEstimator,
        param_grid: list[dict[str, Any]] | dict[str, Any],
        population_size: int = 10,
        n_generations: int = 5,
        mutation_rate: float = 0.2,
        crossover_rate: float = 0.8,
        elite_size: int = 2,
        tournament_size: int = 3,
        patience: int | None = 2,
        min_delta: float = 1e-4,
        enable_pruning: bool = False,
        cv: BaseCrossValidator | int = 5,
        scoring: dict[str, Any] | None = None,
        refit: str = "accuracy",
        random_state: int | None = 42,
        n_jobs: int = 1,
        verbose: int = 1,
    ):
        super().__init__(
            estimator=estimator,
            param_grid=param_grid,
            patience=patience,
            min_delta=min_delta,
            enable_pruning=enable_pruning,
            cv=cv,
            scoring=scoring,
            refit=refit,
            random_state=random_state,
            n_jobs=n_jobs,
            verbose=verbose,
        )
        self.population_size = max(2, population_size)
        self.n_generations = max(1, n_generations)
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_size = min(elite_size, self.population_size - 1)
        self.tournament_size = min(tournament_size, self.population_size)

    def _sample_individual(self, grid: dict[str, Any], rng: np.random.Generator) -> dict[str, Any]:
        """
        Samples a single individual (hyperparameter configuration) from the search grid
        """
        return {
            k: rng.choice(v) if isinstance(v, (list, tuple, np.ndarray)) and len(v) > 0 else v
            for k, v in grid.items()
        }

    def _crossover(
        self,
        parent1: dict[str, Any],
        parent2: dict[str, Any],
        rng: np.random.Generator,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Performs crossover between two parent individuals
        """
        if rng.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()

        child1, child2 = {}, {}
        for key in set(parent1) | set(parent2):
            v1, v2 = parent1.get(key), parent2.get(key)
            child1[key], child2[key] = (v1, v2) if rng.random() < 0.5 else (v2, v1)

        return child1, child2

    def _mutate(
        self,
        individual: dict[str, Any],
        grid: dict[str, Any],
        rng: np.random.Generator,
    ) -> dict[str, Any]:
        """
        Mutates genes of an individual with mutation_rate probability
        """
        mutated = individual.copy()
        for k, v in grid.items():
            if isinstance(v, (list, tuple, np.ndarray)) and len(v) > 1 and rng.random() < self.mutation_rate:
                mutated[k] = rng.choice(v)

        return mutated

    def _tournament_selection(
        self,
        population: list[dict[str, Any]],
        fitness_scores: list[float],
        rng: np.random.Generator,
    ) -> dict[str, Any]:
        """
        Selects the best individual via tournament selection
        """
        contestants = rng.choice(len(population), size=self.tournament_size, replace=False)
        winner_idx = contestants[np.argmax([fitness_scores[i] for i in contestants])]
        return population[winner_idx].copy()

    def _evolve_generation(
        self,
        population: list[dict[str, Any]],
        fitness_scores: list[float],
        grid: dict[str, Any],
        rng: np.random.Generator,
    ) -> list[dict[str, Any]]:
        """
        Evolves the population to the next generation via selection, crossover, and mutation
        """
        next_population: list[dict[str, Any]] = []

        # Elitism: preserve top performers
        if self.elite_size > 0:
            elite_indices = np.argsort(fitness_scores)[::-1][: self.elite_size]
            next_population.extend(population[i].copy() for i in elite_indices)

        # Breed remaining individuals
        while len(next_population) < self.population_size:
            parent1 = self._tournament_selection(population, fitness_scores, rng)
            parent2 = self._tournament_selection(population, fitness_scores, rng)
            child1, child2 = self._crossover(parent1, parent2, rng)

            next_population.append(self._mutate(child1, grid, rng))
            if len(next_population) < self.population_size:
                next_population.append(self._mutate(child2, grid, rng))

        return next_population[: self.population_size]

    def fit(self, X: np.ndarray, y: np.ndarray) -> "GeneticAlgorithmSearch":
        """
        Executes Genetic Algorithm search over generations
        """
        rng = np.random.default_rng(self.random_state)
        self._init_search(X, y)
        param_grids = self._normalize_param_grid()

        total_possible_combos = len(list(ParameterGrid(self.param_grid))) or 1
        total_trials_estimate = min(self.population_size * self.n_generations * len(param_grids), total_possible_combos)
        trial_counter = 0
        cache: dict[tuple, tuple[dict[str, float], dict[str, float], float, float]] = {}

        for grid_idx, grid in enumerate(param_grids, start=1):
            population = [self._sample_individual(grid, rng) for _ in range(self.population_size)]

            for gen in range(self.n_generations):
                fitness_scores: list[float] = []

                for individual in population:
                    param_key = tuple(sorted((k, str(v)) for k, v in individual.items()))
                    if param_key in cache:
                        mean_scores, std_scores, fit_time, score_time = cache[param_key]
                    else:
                        trial_counter += 1
                        try:
                            mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                                candidate_params=individual,
                                X=X,
                                y=y,
                                trial_num=trial_counter,
                                total_trials=total_trials_estimate,
                            )
                            self._record_trial(individual, mean_scores, std_scores, fit_time, score_time, is_pruned=False)
                            cache[param_key] = (mean_scores, std_scores, fit_time, score_time)
                        except TrialPruned:
                            zero_scores = {m: 0.0 for m in self.scoring}
                            self._record_trial(individual, zero_scores, zero_scores, 0.0, 0.0, is_pruned=True)
                            cache[param_key] = (zero_scores, zero_scores, 0.0, 0.0)
                            mean_scores = zero_scores

                    fitness_scores.append(float(mean_scores.get(self.refit, 0.0)))

                best_fitness = max(fitness_scores)
                mean_fitness = float(np.mean(fitness_scores))

                if self.verbose > 0:
                    logger.info(
                        f"[GeneticAlgorithm] Gen {gen + 1}/{self.n_generations} | Best {self.refit}: {best_fitness:.4f} | Mean: {mean_fitness:.4f}"
                    )

                # Early stopping check on population best fitness
                if self._check_early_stopping(best_fitness):
                    break

                if gen < self.n_generations - 1 and grid:
                    population = self._evolve_generation(population, fitness_scores, grid, rng)

        self._finalize_search(X, y)
        return self
