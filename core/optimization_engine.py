"""
core/optimization_engine.py - Algorithmic Search & Multi-Objective Optimization Engine (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import enum
import itertools
import math
import random
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


class OptimizationStrategy(str, enum.Enum):
    """Supported heuristic, metaheuristic, and multi-objective optimization algorithms."""
    HILL_CLIMBING = "HILL_CLIMBING"
    BEAM_SEARCH = "BEAM_SEARCH"
    GENETIC_ALGORITHM = "GENETIC_ALGORITHM"
    SIMULATED_ANNEALING = "SIMULATED_ANNEALING"
    RANDOM_SEARCH = "RANDOM_SEARCH"
    BAYESIAN_UCB = "BAYESIAN_UCB"
    PARETO_MULTI_OBJECTIVE = "PARETO_MULTI_OBJECTIVE"
    GRID_SEARCH = "GRID_SEARCH"


@dataclass
class ParameterSpec:
    """Specification of a tunable parameter in the search space."""
    name: str
    param_type: str = "float"  # "float", "int", "categorical"
    min_val: Optional[Union[float, int]] = None
    max_val: Optional[Union[float, int]] = None
    min_value: Optional[Union[float, int]] = None
    max_value: Optional[Union[float, int]] = None
    step: Optional[Union[float, int]] = None
    choices: Optional[List[Any]] = None
    default: Optional[Any] = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.min_val is None and self.min_value is not None:
            self.min_val = self.min_value
        if self.max_val is None and self.max_value is not None:
            self.max_val = self.max_value
        if self.min_value is None and self.min_val is not None:
            self.min_value = self.min_val
        if self.max_value is None and self.max_val is not None:
            self.max_value = self.max_val

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "param_type": self.param_type,
            "min_val": self.min_val,
            "max_val": self.max_val,
            "step": self.step,
            "choices": self.choices,
            "default": self.default,
            "description": self.description,
        }


@dataclass
class OptimizationProblem:
    """Defines search space boundaries and fitness evaluation functions."""
    name: str = ""
    bounds: Optional[List[Tuple[float, float]]] = None
    objective_fn: Optional[Callable[[List[float]], float]] = None
    multi_objective_fn: Optional[Callable[[List[float]], List[float]]] = None
    objective_function: Optional[Callable[[Dict[str, Any]], float]] = None
    parameters: List[ParameterSpec] = field(default_factory=list)
    strategy: OptimizationStrategy = OptimizationStrategy.RANDOM_SEARCH
    maximize: bool = True
    max_iterations: int = 100
    seed: Optional[int] = None
    param_names: List[str] = field(default_factory=list)

    @property
    def dimensions(self) -> int:
        if self.bounds is not None:
            return len(self.bounds)
        return len(self.parameters)


@dataclass
class OptimizationResult:
    """Output summary of an algorithmic optimization sweep."""
    strategy: OptimizationStrategy
    best_parameters: Any  # Dict[str, Any] or List[float]
    best_score: float
    iterations_evaluated: int = 0
    convergence_history: List[Tuple[int, float]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    pareto_front: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "best_parameters": self.best_parameters,
            "best_score": round(self.best_score, 6),
            "iterations_evaluated": self.iterations_evaluated,
            "pareto_front_size": len(self.pareto_front) if self.pareto_front else None,
        }


class OptimizationEngine:
    """
    Production-ready search and optimization suite implementing standard heuristic
    and parameter tuning algorithms exclusively using Python standard library.
    """

    def __init__(self, seed: Optional[int] = 42) -> None:
        self._lock = threading.RLock()
        self._seed = seed
        self._rng = random.Random(seed)

    def _clip_to_bounds(self, point: List[float], bounds: List[Tuple[float, float]]) -> List[float]:
        return [max(b[0], min(b[1], p)) for p, b in zip(point, bounds)]

    def _random_point(self, bounds: List[Tuple[float, float]]) -> List[float]:
        return [self._rng.uniform(b[0], b[1]) for b in bounds]

    # -------------------------------------------------------------------------
    # Unified optimize() dispatch
    # -------------------------------------------------------------------------

    def optimize(self, problem: OptimizationProblem) -> OptimizationResult:
        """
        Dispatches optimization across parameter specs or continuous bounds.
        """
        with self._lock:
            if problem.parameters and problem.objective_function:
                return self._optimize_parameter_specs(problem)

            strategy = problem.strategy
            if strategy == OptimizationStrategy.HILL_CLIMBING:
                return self.optimize_hill_climbing(problem, max_iters=problem.max_iterations)
            elif strategy == OptimizationStrategy.BEAM_SEARCH:
                return self.optimize_beam_search(problem, max_iters=problem.max_iterations)
            elif strategy == OptimizationStrategy.GENETIC_ALGORITHM:
                return self.optimize_genetic_algorithm(problem, generations=problem.max_iterations)
            elif strategy == OptimizationStrategy.SIMULATED_ANNEALING:
                return self.optimize_simulated_annealing(problem, max_iters=problem.max_iterations)
            elif strategy == OptimizationStrategy.BAYESIAN_UCB:
                return self.optimize_bayesian_ucb(problem, max_iters=problem.max_iterations)
            elif strategy == OptimizationStrategy.PARETO_MULTI_OBJECTIVE:
                return self.compute_pareto_frontier(problem)
            else:
                return self.optimize_random_search(problem, samples=problem.max_iterations)

    def _optimize_parameter_specs(self, problem: OptimizationProblem) -> OptimizationResult:
        strategy = problem.strategy
        rng = random.Random(problem.seed if problem.seed is not None else self._seed)
        obj_fn = problem.objective_function

        if strategy == OptimizationStrategy.GRID_SEARCH:
            param_grids = []
            param_names = [p.name for p in problem.parameters]

            for p in problem.parameters:
                if p.param_type == "categorical" or p.choices:
                    param_grids.append(p.choices or [])
                elif p.param_type == "int":
                    step = int(p.step or 1)
                    param_grids.append(list(range(int(p.min_val or 0), int(p.max_val or 0) + 1, step)))
                else:
                    step = float(p.step or 1.0)
                    min_v = float(p.min_val or 0.0)
                    max_v = float(p.max_val or 1.0)
                    vals = []
                    curr = min_v
                    while curr <= max_v + 1e-9:
                        vals.append(round(curr, 8))
                        curr += step
                    param_grids.append(vals)

            best_p = None
            best_s = -float("inf") if problem.maximize else float("inf")
            history = []
            evals = 0

            for combo in itertools.product(*param_grids):
                p_dict = dict(zip(param_names, combo))
                s = obj_fn(p_dict)
                evals += 1
                history.append({"parameters": p_dict, "score": s})
                if problem.maximize and s > best_s:
                    best_s = s
                    best_p = p_dict
                elif not problem.maximize and s < best_s:
                    best_s = s
                    best_p = p_dict

            return OptimizationResult(
                strategy=OptimizationStrategy.GRID_SEARCH,
                best_parameters=best_p or {},
                best_score=best_s,
                iterations_evaluated=evals,
                history=history,
            )

        elif strategy == OptimizationStrategy.RANDOM_SEARCH:
            best_p = None
            best_s = -float("inf") if problem.maximize else float("inf")
            history = []

            for _ in range(problem.max_iterations):
                sample = {}
                for p in problem.parameters:
                    if p.param_type == "categorical" or p.choices:
                        sample[p.name] = rng.choice(p.choices)
                    elif p.param_type == "int":
                        step = int(p.step or 1)
                        sample[p.name] = rng.randrange(int(p.min_val), int(p.max_val) + 1, step)
                    else:
                        sample[p.name] = rng.uniform(float(p.min_val), float(p.max_val))

                s = obj_fn(sample)
                history.append({"parameters": sample, "score": s})
                if problem.maximize and s > best_s:
                    best_s = s
                    best_p = sample
                elif not problem.maximize and s < best_s:
                    best_s = s
                    best_p = sample

            return OptimizationResult(
                strategy=OptimizationStrategy.RANDOM_SEARCH,
                best_parameters=best_p or {},
                best_score=best_s,
                iterations_evaluated=problem.max_iterations,
                history=history,
            )

        elif strategy == OptimizationStrategy.HILL_CLIMBING:
            curr = {}
            for p in problem.parameters:
                if p.param_type == "int":
                    curr[p.name] = int((p.min_val + p.max_val) // 2)
                elif p.param_type == "float":
                    curr[p.name] = (float(p.min_val) + float(p.max_val)) / 2.0
                else:
                    curr[p.name] = rng.choice(p.choices or [])

            curr_s = obj_fn(curr)
            best_p = dict(curr)
            best_s = curr_s
            history = [{"parameters": dict(curr), "score": curr_s}]

            for _ in range(problem.max_iterations):
                p = rng.choice(problem.parameters)
                cand = dict(curr)
                if p.param_type == "int":
                    step = int(p.step or 1)
                    val = cand[p.name] + rng.choice([-step, step])
                    val = max(int(p.min_val), min(int(p.max_val), val))
                    cand[p.name] = val
                elif p.param_type == "float":
                    step = float(p.step or 0.1)
                    val = cand[p.name] + rng.choice([-step, step])
                    val = max(float(p.min_val), min(float(p.max_val), val))
                    cand[p.name] = val
                else:
                    cand[p.name] = rng.choice(p.choices or [])

                s = obj_fn(cand)
                history.append({"parameters": cand, "score": s})

                improved = (s > curr_s) if problem.maximize else (s < curr_s)
                if improved:
                    curr = cand
                    curr_s = s
                    if (problem.maximize and curr_s > best_s) or (not problem.maximize and curr_s < best_s):
                        best_s = curr_s
                        best_p = dict(curr)

            return OptimizationResult(
                strategy=OptimizationStrategy.HILL_CLIMBING,
                best_parameters=best_p,
                best_score=best_s,
                iterations_evaluated=len(history),
                history=history,
            )

        elif strategy == OptimizationStrategy.SIMULATED_ANNEALING:
            curr = {}
            for p in problem.parameters:
                if p.param_type == "float":
                    curr[p.name] = (float(p.min_val) + float(p.max_val)) / 2.0
                elif p.param_type == "int":
                    curr[p.name] = int((p.min_val + p.max_val) // 2)
                else:
                    curr[p.name] = rng.choice(p.choices or [])

            curr_s = obj_fn(curr)
            best_p = dict(curr)
            best_s = curr_s
            history = [{"parameters": dict(curr), "score": curr_s}]

            temp = 1.0
            cooling_rate = 0.95

            for _ in range(problem.max_iterations):
                p = rng.choice(problem.parameters)
                cand = dict(curr)
                if p.param_type == "float":
                    delta = rng.uniform(-float(p.step or 0.5), float(p.step or 0.5))
                    val = max(float(p.min_val), min(float(p.max_val), cand[p.name] + delta))
                    cand[p.name] = val
                elif p.param_type == "int":
                    step = int(p.step or 1)
                    val = cand[p.name] + rng.choice([-step, step])
                    val = max(int(p.min_val), min(int(p.max_val), val))
                    cand[p.name] = val
                else:
                    cand[p.name] = rng.choice(p.choices or [])

                s = obj_fn(cand)
                history.append({"parameters": cand, "score": s})

                diff = (s - curr_s) if problem.maximize else (curr_s - s)
                if diff > 0 or (temp > 1e-6 and math.exp(diff / temp) > rng.random()):
                    curr = cand
                    curr_s = s

                if (problem.maximize and curr_s > best_s) or (not problem.maximize and curr_s < best_s):
                    best_s = curr_s
                    best_p = dict(curr)

                temp *= cooling_rate

            return OptimizationResult(
                strategy=OptimizationStrategy.SIMULATED_ANNEALING,
                best_parameters=best_p,
                best_score=best_s,
                iterations_evaluated=len(history),
                history=history,
            )

        return self.optimize_random_search(problem)

    # -------------------------------------------------------------------------
    # 1. Hill Climbing (bounds)
    # -------------------------------------------------------------------------

    def optimize_hill_climbing(
        self,
        problem: OptimizationProblem,
        max_iters: int = 200,
        step_size: float = 0.05,
        neighbors_per_step: int = 15,
        stochastic: bool = False,
    ) -> OptimizationResult:
        if not problem.objective_fn:
            raise ValueError("Hill climbing requires a single-objective function")
        bounds = problem.bounds or []
        curr = self._random_point(bounds)
        curr_score = problem.objective_fn(curr)
        history = [(0, curr_score)]
        total_evals = 1
        current_step = step_size

        for it in range(1, max_iters + 1):
            best_neighbor = None
            best_neighbor_score = -float('inf')

            for _ in range(neighbors_per_step):
                neighbor = []
                for p, b in zip(curr, bounds):
                    delta = self._rng.gauss(0.0, current_step * (b[1] - b[0]))
                    neighbor.append(p + delta)
                neighbor = self._clip_to_bounds(neighbor, bounds)
                sc = problem.objective_fn(neighbor)
                total_evals += 1

                if sc > best_neighbor_score:
                    best_neighbor_score = sc
                    best_neighbor = neighbor

            if best_neighbor and best_neighbor_score > curr_score:
                curr = best_neighbor
                curr_score = best_neighbor_score
            elif stochastic and best_neighbor:
                if self._rng.random() < 0.05:
                    curr = best_neighbor
                    curr_score = best_neighbor_score

            current_step = max(1e-4, current_step * 0.98)
            history.append((it, curr_score))

        return OptimizationResult(
            strategy=OptimizationStrategy.HILL_CLIMBING,
            best_parameters=curr,
            best_score=curr_score,
            iterations_evaluated=total_evals,
            convergence_history=history,
        )

    # -------------------------------------------------------------------------
    # 2. Beam Search
    # -------------------------------------------------------------------------

    def optimize_beam_search(
        self,
        problem: OptimizationProblem,
        beam_width: int = 5,
        max_iters: int = 40,
        expansions_per_beam: int = 8,
    ) -> OptimizationResult:
        if not problem.objective_fn:
            raise ValueError("Beam search requires single-objective function")
        bounds = problem.bounds or []
        beam = [self._random_point(bounds) for _ in range(beam_width)]
        beam_scored = [(cand, problem.objective_fn(cand)) for cand in beam]
        beam_scored.sort(key=lambda t: t[1], reverse=True)
        total_evals = beam_width
        history = [(0, beam_scored[0][1])]

        for it in range(1, max_iters + 1):
            candidates = []
            for parent, _ in beam_scored:
                for _ in range(expansions_per_beam):
                    cand = []
                    for p, b in zip(parent, bounds):
                        step = self._rng.uniform(-0.1, 0.1) * (b[1] - b[0])
                        cand.append(p + step)
                    cand = self._clip_to_bounds(cand, bounds)
                    score = problem.objective_fn(cand)
                    candidates.append((cand, score))
                    total_evals += 1

            candidates.extend(beam_scored)
            candidates.sort(key=lambda t: t[1], reverse=True)
            beam_scored = candidates[:beam_width]
            history.append((it, beam_scored[0][1]))

        return OptimizationResult(
            strategy=OptimizationStrategy.BEAM_SEARCH,
            best_parameters=beam_scored[0][0],
            best_score=beam_scored[0][1],
            iterations_evaluated=total_evals,
            convergence_history=history,
        )

    # -------------------------------------------------------------------------
    # 3. Genetic Algorithm
    # -------------------------------------------------------------------------

    def optimize_genetic_algorithm(
        self,
        problem: OptimizationProblem,
        population_size: int = 30,
        generations: int = 50,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.80,
        elitism_count: int = 2,
    ) -> OptimizationResult:
        if not problem.objective_fn:
            raise ValueError("Genetic algorithm requires single-objective function")
        bounds = problem.bounds or []
        pop = [self._random_point(bounds) for _ in range(population_size)]
        pop_scored = [(ind, problem.objective_fn(ind)) for ind in pop]
        pop_scored.sort(key=lambda t: t[1], reverse=True)
        total_evals = population_size
        history = [(0, pop_scored[0][1])]

        for gen in range(1, generations + 1):
            new_pop = [ind for ind, _ in pop_scored[:elitism_count]]
            while len(new_pop) < population_size:
                p1 = self._tournament_select(pop_scored)
                p2 = self._tournament_select(pop_scored)
                if self._rng.random() < crossover_rate:
                    alpha = self._rng.random()
                    c1 = [alpha * a + (1 - alpha) * b for a, b in zip(p1, p2)]
                else:
                    c1 = list(p1)
                for i in range(len(c1)):
                    if self._rng.random() < mutation_rate:
                        delta = self._rng.gauss(0.0, 0.1 * (bounds[i][1] - bounds[i][0]))
                        c1[i] += delta
                c1 = self._clip_to_bounds(c1, bounds)
                new_pop.append(c1)

            pop_scored = [(ind, problem.objective_fn(ind)) for ind in new_pop]
            pop_scored.sort(key=lambda t: t[1], reverse=True)
            total_evals += population_size - elitism_count
            history.append((gen, pop_scored[0][1]))

        return OptimizationResult(
            strategy=OptimizationStrategy.GENETIC_ALGORITHM,
            best_parameters=pop_scored[0][0],
            best_score=pop_scored[0][1],
            iterations_evaluated=total_evals,
            convergence_history=history,
        )

    def _tournament_select(self, scored_pop: List[Tuple[List[float], float]], k: int = 3) -> List[float]:
        candidates = self._rng.sample(scored_pop, min(k, len(scored_pop)))
        candidates.sort(key=lambda t: t[1], reverse=True)
        return candidates[0][0]

    # -------------------------------------------------------------------------
    # 4. Simulated Annealing
    # -------------------------------------------------------------------------

    def optimize_simulated_annealing(
        self,
        problem: OptimizationProblem,
        max_iters: int = 250,
        initial_temp: float = 10.0,
        cooling_rate: float = 0.97,
    ) -> OptimizationResult:
        if not problem.objective_fn:
            raise ValueError("Simulated annealing requires single-objective function")
        bounds = problem.bounds or []
        curr = self._random_point(bounds)
        curr_score = problem.objective_fn(curr)
        best = list(curr)
        best_score = curr_score
        temp = initial_temp
        total_evals = 1
        history = [(0, best_score)]

        for it in range(1, max_iters + 1):
            cand = []
            for p, b in zip(curr, bounds):
                step = self._rng.gauss(0.0, 0.1 * temp * (b[1] - b[0]))
                cand.append(p + step)
            cand = self._clip_to_bounds(cand, bounds)
            cand_score = problem.objective_fn(cand)
            total_evals += 1

            delta = cand_score - curr_score
            if delta > 0.0 or (temp > 1e-8 and math.exp(delta / temp) > self._rng.random()):
                curr = cand
                curr_score = cand_score
                if curr_score > best_score:
                    best = list(curr)
                    best_score = curr_score

            temp = max(1e-4, temp * cooling_rate)
            history.append((it, best_score))

        return OptimizationResult(
            strategy=OptimizationStrategy.SIMULATED_ANNEALING,
            best_parameters=best,
            best_score=best_score,
            iterations_evaluated=total_evals,
            convergence_history=history,
        )

    # -------------------------------------------------------------------------
    # 5. Random Search
    # -------------------------------------------------------------------------

    def optimize_random_search(
        self,
        problem: OptimizationProblem,
        samples: int = 100,
    ) -> OptimizationResult:
        if not problem.objective_fn:
            raise ValueError("Random search requires single-objective function")
        bounds = problem.bounds or []
        best = None
        best_score = -float('inf')
        history = []

        for it in range(samples):
            cand = self._random_point(bounds)
            score = problem.objective_fn(cand)
            if score > best_score:
                best = cand
                best_score = score
            history.append((it + 1, best_score))

        return OptimizationResult(
            strategy=OptimizationStrategy.RANDOM_SEARCH,
            best_parameters=best or [],
            best_score=best_score,
            iterations_evaluated=samples,
            convergence_history=history,
        )

    # -------------------------------------------------------------------------
    # 6. Bayesian UCB
    # -------------------------------------------------------------------------

    def optimize_bayesian_ucb(
        self,
        problem: OptimizationProblem,
        init_samples: int = 10,
        max_iters: int = 40,
        kappa: float = 2.0,
    ) -> OptimizationResult:
        if not problem.objective_fn:
            raise ValueError("Bayesian UCB requires single-objective function")
        bounds = problem.bounds or []
        X = [self._random_point(bounds) for _ in range(init_samples)]
        Y = [problem.objective_fn(x) for x in X]
        total_evals = init_samples

        best_idx = max(range(len(Y)), key=lambda i: Y[i])
        best_pt = X[best_idx]
        best_score = Y[best_idx]
        history = [(0, best_score)]

        for it in range(1, max_iters + 1):
            candidates = [self._random_point(bounds) for _ in range(50)]
            best_acq = -float('inf')
            best_cand = candidates[0]

            for cand in candidates:
                weights = []
                for pt in X:
                    dist_sq = sum(((c - p) / (b[1] - b[0])) ** 2 for c, p, b in zip(cand, pt, bounds))
                    weights.append(math.exp(-dist_sq * 2.0))

                w_sum = sum(weights)
                if w_sum > 1e-9:
                    mu = sum(w * y for w, y in zip(weights, Y)) / w_sum
                    sigma = 1.0 / (1.0 + w_sum)
                else:
                    mu = sum(Y) / len(Y)
                    sigma = 1.0

                acq_value = mu + kappa * sigma
                if acq_value > best_acq:
                    best_acq = acq_value
                    best_cand = cand

            score = problem.objective_fn(best_cand)
            X.append(best_cand)
            Y.append(score)
            total_evals += 1

            if score > best_score:
                best_pt = best_cand
                best_score = score

            history.append((it, best_score))

        return OptimizationResult(
            strategy=OptimizationStrategy.BAYESIAN_UCB,
            best_parameters=best_pt,
            best_score=best_score,
            iterations_evaluated=total_evals,
            convergence_history=history,
        )

    # -------------------------------------------------------------------------
    # 7. Multi-Objective Optimization & Pareto Frontier
    # -------------------------------------------------------------------------

    def compute_pareto_frontier(
        self,
        problem: OptimizationProblem,
        population_size: int = 50,
        generations: int = 30,
    ) -> OptimizationResult:
        if not problem.multi_objective_fn:
            raise ValueError("Pareto optimization requires multi_objective_fn")
        bounds = problem.bounds or []
        pop = [self._random_point(bounds) for _ in range(population_size)]
        pop_objs = [problem.multi_objective_fn(ind) for ind in pop]
        total_evals = population_size

        for _ in range(generations):
            new_ind = self._random_point(bounds)
            new_objs = problem.multi_objective_fn(new_ind)
            pop.append(new_ind)
            pop_objs.append(new_objs)
            total_evals += 1

        pareto_front = []
        n = len(pop)
        for i in range(n):
            dominated = False
            for j in range(n):
                if i == j:
                    continue
                all_ge = all(pop_objs[j][k] >= pop_objs[i][k] for k in range(len(pop_objs[0])))
                any_gt = any(pop_objs[j][k] > pop_objs[i][k] for k in range(len(pop_objs[0])))
                if all_ge and any_gt:
                    dominated = True
                    break
            if not dominated:
                pareto_front.append({
                    "parameters": [round(p, 6) for p in pop[i]],
                    "objectives": [round(o, 6) for o in pop_objs[i]],
                })

        return OptimizationResult(
            strategy=OptimizationStrategy.PARETO_MULTI_OBJECTIVE,
            best_parameters=pop[0],
            best_score=sum(pop_objs[0]) if pop_objs else 0.0,
            iterations_evaluated=total_evals,
            pareto_front=pareto_front,
        )
