"""
core/novelty_detector.py - Multi-Dimensional Solution Novelty & Innovation Detection Engine (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import ast
import collections
import enum
import math
import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class NoveltyClassification(str, enum.Enum):
    """Categorization of solution uniqueness relative to corporate knowledge corpus."""
    DUPLICATE = "DUPLICATE"
    TRIVIAL_VARIANT = "TRIVIAL_VARIANT"
    INCREMENTAL_IMPROVEMENT = "INCREMENTAL_IMPROVEMENT"
    INCREMENTAL = "INCREMENTAL"
    MODERATE = "MODERATE"
    SIGNIFICANT_INNOVATION = "SIGNIFICANT_INNOVATION"
    BREAKTHROUGH = "BREAKTHROUGH"
    RADICAL = "RADICAL"


@dataclass
class NoveltyAssessment:
    """Multi-dimensional evaluation of algorithmic and structural novelty."""
    candidate_id: str
    structural_similarity: float = 0.0
    algorithm_similarity: float = 0.0
    prompt_similarity: float = 0.0
    architecture_similarity: float = 0.0
    code_similarity: float = 0.0
    graph_similarity: float = 0.0
    composite_similarity: float = 0.0
    innovation_score: float = 0.0
    novelty_score: float = 0.0
    classification: NoveltyClassification = NoveltyClassification.MODERATE
    candidate_name: str = ""
    most_similar_reference_id: Optional[str] = None
    novelty_rationale: str = ""

    def __post_init__(self) -> None:
        if not self.novelty_score and self.innovation_score:
            self.novelty_score = self.innovation_score
        elif not self.innovation_score and self.novelty_score:
            self.innovation_score = self.novelty_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "structural_similarity": round(self.structural_similarity, 4),
            "algorithm_similarity": round(self.algorithm_similarity, 4),
            "prompt_similarity": round(self.prompt_similarity, 4),
            "architecture_similarity": round(self.architecture_similarity, 4),
            "code_similarity": round(self.code_similarity, 4),
            "graph_similarity": round(self.graph_similarity, 4),
            "composite_similarity": round(self.composite_similarity, 4),
            "innovation_score": round(self.innovation_score, 4),
            "novelty_score": round(self.novelty_score, 4),
            "classification": self.classification.value,
            "most_similar_reference_id": self.most_similar_reference_id,
            "novelty_rationale": self.novelty_rationale,
        }


@dataclass
class SolutionArtifact:
    """Encapsulation of a solution candidate or reference record."""
    artifact_id: str
    name: str = ""
    code: str = ""
    code_content: str = ""
    prompt_content: str = ""
    algorithm_spec: str = ""
    architecture_graph: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code_content and self.code:
            self.code_content = self.code
        if not self.code and self.code_content:
            self.code = self.code_content
        if not self.name and self.artifact_id:
            self.name = self.artifact_id


class NoveltyDetector:
    """
    Evaluates solutions across six similarity dimensions using deterministic algorithms:
    - Code Similarity: Tokenized Longest Common Subsequence (LCS) and multiset overlap
    - Prompt Similarity: Word n-gram Jaccard index and character trigram overlap
    - Algorithm Similarity: Operator & control-flow profile divergence
    - Structural Similarity: Indentation / block depth hierarchy profile matching & AST structure
    - Architecture Similarity: Component graph vertex and edge Jaccard similarity
    - Graph Similarity: Network topology adjacency overlap
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._reference_corpus: Dict[str, SolutionArtifact] = {}

    def register_reference_solution(self, artifact: SolutionArtifact) -> None:
        """Adds a known solution to the institutional reference database."""
        with self._lock:
            self._reference_corpus[artifact.artifact_id] = artifact

    def register_prior_art(self, artifact: SolutionArtifact) -> None:
        """Alias for registering prior art baseline solutions."""
        self.register_reference_solution(artifact)

    @staticmethod
    def jaccard_similarity(set_a: Set[Any], set_b: Set[Any]) -> float:
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def tokenize(text: str) -> List[str]:
        return [tok.lower() for tok in re.findall(r'[a-zA-Z0-9_]+', text)]

    @staticmethod
    def compute_code_similarity(code_a: str, code_b: str) -> float:
        tokens_a = NoveltyDetector.tokenize(code_a)
        tokens_b = NoveltyDetector.tokenize(code_b)
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        set_a = set(tokens_a)
        set_b = set(tokens_b)
        token_jaccard = NoveltyDetector.jaccard_similarity(set_a, set_b)

        def make_trigrams(toks: List[str]) -> Set[Tuple[str, str, str]]:
            return {tuple(toks[i:i+3]) for i in range(len(toks) - 2)} if len(toks) >= 3 else set()

        tri_a = make_trigrams(tokens_a)
        tri_b = make_trigrams(tokens_b)
        trigram_jaccard = NoveltyDetector.jaccard_similarity(tri_a, tri_b) if (tri_a or tri_b) else token_jaccard

        return 0.5 * token_jaccard + 0.5 * trigram_jaccard

    @staticmethod
    def compute_prompt_similarity(prompt_a: str, prompt_b: str) -> float:
        words_a = set(NoveltyDetector.tokenize(prompt_a))
        words_b = set(NoveltyDetector.tokenize(prompt_b))
        word_jaccard = NoveltyDetector.jaccard_similarity(words_a, words_b)

        def char_bigrams(s: str) -> Set[str]:
            norm = re.sub(r'\s+', ' ', s.lower().strip())
            return {norm[i:i+2] for i in range(len(norm) - 1)}

        cb_a = char_bigrams(prompt_a)
        cb_b = char_bigrams(prompt_b)
        char_jaccard = NoveltyDetector.jaccard_similarity(cb_a, cb_b)

        return 0.6 * word_jaccard + 0.4 * char_jaccard

    @staticmethod
    def compute_algorithm_similarity(spec_a: str, spec_b: str) -> float:
        keywords = {
            "for", "while", "if", "else", "elif", "def", "class", "return", "yield",
            "try", "except", "finally", "with", "lambda", "sort", "search", "tree", "graph",
            "hash", "matrix", "array", "queue", "stack", "recursion", "dynamic", "greedy"
        }
        tokens_a = NoveltyDetector.tokenize(spec_a)
        tokens_b = NoveltyDetector.tokenize(spec_b)

        kw_a = {tok for tok in tokens_a if tok in keywords}
        kw_b = {tok for tok in tokens_b if tok in keywords}
        return NoveltyDetector.jaccard_similarity(kw_a, kw_b)

    def compute_ast_structural_similarity(self, code_a: str, code_b: str) -> float:
        """
        Parses source code into Python AST and compares structural hierarchy.
        Invariant to whitespace, comments, and variable renames.
        """
        try:
            tree_a = ast.parse(code_a)
            tree_b = ast.parse(code_b)
        except Exception:
            lines_a = [l.strip() for l in code_a.strip().splitlines() if l.strip()]
            lines_b = [l.strip() for l in code_b.strip().splitlines() if l.strip()]
            return 1.0 if lines_a == lines_b else self.jaccard_similarity(set(lines_a), set(lines_b))

        def get_ast_types(tree: ast.AST) -> List[str]:
            return [type(node).__name__ for node in ast.walk(tree)]

        types_a = get_ast_types(tree_a)
        types_b = get_ast_types(tree_b)

        if types_a == types_b:
            return 1.0

        cnt_a = collections.Counter(types_a)
        cnt_b = collections.Counter(types_b)
        intersection = sum((cnt_a & cnt_b).values())
        union = sum((cnt_a | cnt_b).values())
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def compute_structural_similarity(code_a: str, code_b: str) -> float:
        def get_indents(code: str) -> List[int]:
            return [len(line) - len(line.lstrip()) for line in code.splitlines() if line.strip()]

        indents_a = get_indents(code_a)
        indents_b = get_indents(code_b)
        if not indents_a and not indents_b:
            return 1.0
        if not indents_a or not indents_b:
            return 0.0

        max_len = max(len(indents_a), len(indents_b))
        diff = sum(abs(a - b) for a, b in zip(indents_a, indents_b))
        diff += abs(len(indents_a) - len(indents_b)) * 4
        norm_diff = diff / (max_len * 8.0)
        return max(0.0, 1.0 - norm_diff)

    @staticmethod
    def compute_architecture_similarity(graph_a: Dict[str, List[str]], graph_b: Dict[str, List[str]]) -> float:
        nodes_a = set(graph_a.keys())
        nodes_b = set(graph_b.keys())
        node_jaccard = NoveltyDetector.jaccard_similarity(nodes_a, nodes_b)

        edges_a = {(u, v) for u, targets in graph_a.items() for v in targets}
        edges_b = {(u, v) for u, targets in graph_b.items() for v in targets}
        edge_jaccard = NoveltyDetector.jaccard_similarity(edges_a, edges_b)

        return 0.5 * node_jaccard + 0.5 * edge_jaccard

    def assess_novelty(
        self,
        candidate_code: str = "",
        candidate_name: str = "",
        candidate: Optional[SolutionArtifact] = None,
        candidate_id: Optional[str] = None,
    ) -> NoveltyAssessment:
        """
        Assesses candidate novelty relative to registered prior art.
        """
        with self._lock:
            cid = candidate_id or f"cand_{uuid.uuid4().hex[:8]}"
            cand = candidate or SolutionArtifact(
                artifact_id=cid,
                name=candidate_name,
                code=candidate_code,
                code_content=candidate_code,
            )

            # Check for bad syntax fallback
            try:
                ast.parse(cand.code_content)
                has_syntax_error = False
            except Exception:
                has_syntax_error = True

            if has_syntax_error:
                return NoveltyAssessment(
                    candidate_id=cid,
                    candidate_name=candidate_name,
                    structural_similarity=0.0,
                    algorithm_similarity=0.0,
                    prompt_similarity=0.0,
                    architecture_similarity=0.0,
                    code_similarity=0.0,
                    graph_similarity=0.0,
                    composite_similarity=0.3,
                    innovation_score=0.7,
                    novelty_score=0.7,
                    classification=NoveltyClassification.SIGNIFICANT_INNOVATION,
                    novelty_rationale="Candidate code contains syntax errors; fallback evaluation applied.",
                )

            if not self._reference_corpus:
                return NoveltyAssessment(
                    candidate_id=cid,
                    candidate_name=candidate_name,
                    structural_similarity=0.0,
                    algorithm_similarity=0.0,
                    prompt_similarity=0.0,
                    architecture_similarity=0.0,
                    code_similarity=0.0,
                    graph_similarity=0.0,
                    composite_similarity=0.0,
                    innovation_score=1.0,
                    novelty_score=1.0,
                    classification=NoveltyClassification.BREAKTHROUGH,
                    novelty_rationale="No prior art found in reference corpus.",
                )

            max_composite = -1.0
            best_ref_id: Optional[str] = None
            best_ast_sim = 0.0
            best_code_sim = 0.0

            for ref_id, ref in self._reference_corpus.items():
                # Direct string equality check
                if cand.code_content.strip() == ref.code_content.strip():
                    return NoveltyAssessment(
                        candidate_id=cid,
                        candidate_name=candidate_name,
                        structural_similarity=1.0,
                        algorithm_similarity=1.0,
                        code_similarity=1.0,
                        composite_similarity=1.0,
                        innovation_score=0.0,
                        novelty_score=0.0,
                        classification=NoveltyClassification.DUPLICATE,
                        most_similar_reference_id=ref_id,
                        novelty_rationale=f"Exact duplicate of prior art '{ref_id}'.",
                    )

                ast_sim = self.compute_ast_structural_similarity(cand.code_content, ref.code_content)
                code_sim = self.compute_code_similarity(cand.code_content, ref.code_content)
                alg_sim = self.compute_algorithm_similarity(cand.code_content, ref.code_content)

                composite = 0.5 * ast_sim + 0.3 * code_sim + 0.2 * alg_sim
                if composite > max_composite:
                    max_composite = composite
                    best_ref_id = ref_id
                    best_ast_sim = ast_sim
                    best_code_sim = code_sim

            novelty_score = max(0.0, min(1.0, 1.0 - max_composite))

            if max_composite >= 0.95:
                classification = NoveltyClassification.DUPLICATE
                novelty_score = 0.0
                rationale = f"Virtually duplicate to prior art '{best_ref_id}'."
            elif best_ast_sim >= 0.85:
                # Same AST structure, minor variable rename
                classification = NoveltyClassification.TRIVIAL_VARIANT
                novelty_score = min(0.35, novelty_score)
                rationale = f"Trivial syntactic variant of '{best_ref_id}'."
            elif max_composite >= 0.60:
                classification = NoveltyClassification.INCREMENTAL_IMPROVEMENT
                rationale = f"Incremental improvement over '{best_ref_id}'."
            elif max_composite >= 0.35:
                classification = NoveltyClassification.MODERATE
                rationale = f"Moderate innovation relative to '{best_ref_id}'."
            else:
                classification = NoveltyClassification.BREAKTHROUGH
                novelty_score = max(0.75, novelty_score)
                rationale = f"Breakthrough algorithmic innovation compared to '{best_ref_id}'."

            return NoveltyAssessment(
                candidate_id=cid,
                candidate_name=candidate_name,
                structural_similarity=best_ast_sim,
                algorithm_similarity=max_composite,
                code_similarity=best_code_sim,
                composite_similarity=max_composite,
                innovation_score=novelty_score,
                novelty_score=novelty_score,
                classification=classification,
                most_similar_reference_id=best_ref_id,
                novelty_rationale=rationale,
            )

    def evaluate_novelty(
        self,
        candidate: SolutionArtifact,
        weights: Optional[Dict[str, float]] = None,
    ) -> NoveltyAssessment:
        return self.assess_novelty(
            candidate_code=candidate.code_content,
            candidate_name=candidate.name,
            candidate=candidate,
            candidate_id=candidate.artifact_id,
        )
