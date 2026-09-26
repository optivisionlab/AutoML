# Standard Libraries
import logging
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import BaseCrossValidator

# Local Libraries
from src.modules.hpo.base import BaseSearchCV


# Logging
logger = logging.getLogger(__name__)


class GeneticAlgorithmSearch(BaseSearchCV):
    """
    Hyperparameter optimization using Genetic Algorithm (GA).
    Evolves a population of hyperparameter configurations over multiple generations using
    Tournament Selection, Uniform Crossover, Mutation, and Elitism.
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
            cv=cv,
            scoring=scoring,
            refit=refit,
            n_jobs=n_jobs,
            verbose=verbose,
        )
        self.population_size = max(2, population_size)
        self.n_generations = max(1, n_generations)
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_size = min(elite_size, self.population_size - 1)
        self.tournament_size = min(tournament_size, self.population_size)
        self.random_state = random_state

    def _sample_individual(self, grid: dict[str, Any], rng: np.random.Generator) -> dict[str, Any]:
        """
        Samples a single individual (chromosome) randomly from the parameter grid.
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
        Performs uniform crossover between two parent chromosomes.
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
        Applies random mutation to an individual's genes with mutation_rate probability.
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
        Selects an individual using tournament selection.
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
        Creates the next generation via elitism, selection, crossover, and mutation.
        """
        next_population: list[dict[str, Any]] = []

        # Elitism: preserve top performers directly
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
        Executes Genetic Algorithm search over generations.
        """
        rng = np.random.default_rng(self.random_state)
        self._init_search(X, y)
        param_grids = self._normalize_param_grid()

        total_trials_estimate = self.population_size * self.n_generations * len(param_grids)
        trial_counter = 0
        cache: dict[tuple, tuple[dict[str, float], dict[str, float], float, float]] = {}

        for grid_idx, grid in enumerate(param_grids, start=1):
            population = [self._sample_individual(grid, rng) for _ in range(self.population_size)]

            if self.verbose > 0:
                logger.info(
                    f"[GeneticAlgorithm] Space {grid_idx}/{len(param_grids)}: Population {self.population_size}, Generations {self.n_generations}"
                )

            for gen in range(self.n_generations):
                fitness_scores: list[float] = []

                for individual in population:
                    param_key = tuple(sorted((k, str(v)) for k, v in individual.items()))
                    if param_key in cache:
                        mean_scores, std_scores, fit_time, score_time = cache[param_key]
                    else:
                        trial_counter += 1
                        mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                            candidate_params=individual,
                            X=X,
                            y=y,
                            trial_num=trial_counter,
                            total_trials=total_trials_estimate,
                        )
                        self._record_trial(individual, mean_scores, std_scores, fit_time, score_time)
                        cache[param_key] = (mean_scores, std_scores, fit_time, score_time)

                    fitness_scores.append(float(mean_scores.get(self.refit, 0.0)))

                if self.verbose > 0:
                    best_fitness = max(fitness_scores)
                    mean_fitness = float(np.mean(fitness_scores))
                    logger.info(
                        f"[GeneticAlgorithm] Gen {gen + 1}/{self.n_generations} | Best {self.refit}: {best_fitness:.4f} | Mean: {mean_fitness:.4f}"
                    )

                # Evolve to next generation if not at the final generation
                if gen < self.n_generations - 1 and grid:
                    population = self._evolve_generation(population, fitness_scores, grid, rng)

        self._finalize_search(X, y)
        return self
