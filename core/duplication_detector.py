"""
AutoDev Duplication Detector (v2.7)
Deterministic AST and token-based detector for exact duplicates, near-duplicates,
repeated conditions, repeated literals, repeated SQL queries, and repeated regex patterns.
"""

from __future__ import annotations

import ast
import hashlib
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.quality_models import CodeLocation, DuplicationBlock

# Regex patterns for detecting SQL and regex literals
SQL_PATTERN = re.compile(r"(?i)\b(SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+.+\s+SET|DELETE\s+FROM|CREATE\s+TABLE)\b")
REGEX_SPECIALS = re.compile(r"[\^$*+?{}\[\]\\|()]")


class ASTNormalizer(ast.NodeTransformer):
    """Normalizes AST tokens by masking variable names and constant values for near-duplicate detection."""

    def visit_Name(self, node: ast.Name) -> ast.AST:
        return ast.copy_location(ast.Name(id="$VAR", ctx=node.ctx), node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        # Preserve type class while normalizing value
        type_tag = type(node.value).__name__
        return ast.copy_location(ast.Constant(value=f"${type_tag}"), node)


class DuplicationDetector:
    """Detects multi-tier code duplications across files and workspaces."""

    def __init__(
        self,
        min_block_lines: int = 4,
        min_literal_occurrences: int = 3,
        min_lines: Optional[int] = None,
        min_token_length: Optional[int] = None,
        similarity_threshold: float = 0.85,
        **kwargs: Any,
    ):
        self.min_block_lines = min_lines if min_lines is not None else min_block_lines
        self.min_literal_occurrences = min_literal_occurrences
        self.similarity_threshold = similarity_threshold
        self.min_token_length = min_token_length

    def detect_duplicates(self, files_content: Dict[str, str]) -> List[DuplicationBlock]:
        """Detects exact and near-duplicate code blocks."""
        exact, near, _ = self._detect_code_blocks(files_content)
        return exact + near

    def detect_repeated_conditions(self, files_content: Dict[str, str]) -> Dict[str, List[CodeLocation]]:
        """Identifies repeated condition expressions across files."""
        blocks = self._detect_repeated_conditions(files_content)
        return {b.code_snippet: b.locations for b in blocks}

    def detect_repeated_literals(self, files_content: Dict[str, str]) -> Dict[str, List[CodeLocation]]:
        """Identifies magic string/number literals repeated across files."""
        blocks = self._detect_repeated_literals(files_content)
        return {b.code_snippet: b.locations for b in blocks if b.duplication_type == "repeated_literal"}

    def detect_repeated_sql(self, files_content: Dict[str, str]) -> Dict[str, List[CodeLocation]]:
        """Identifies raw SQL query literals repeated across files."""
        blocks = self._detect_repeated_literals(files_content)
        return {b.code_snippet: b.locations for b in blocks if b.duplication_type == "repeated_sql"}

    def detect_repeated_regex(self, files_content: Dict[str, str]) -> Dict[str, List[CodeLocation]]:
        """Identifies regex pattern literals repeated across files."""
        blocks = self._detect_repeated_literals(files_content)
        return {b.code_snippet: b.locations for b in blocks if b.duplication_type == "repeated_regex"}

    def scan_files(self, files_content: Dict[str, str]) -> Tuple[List[DuplicationBlock], float]:
        """
        Scans a collection of files (rel_path -> code_str) for duplications.
        Returns: (List[DuplicationBlock], duplication_percentage)
        """
        all_blocks: List[DuplicationBlock] = []
        total_sloc = 0
        duplicated_sloc_lines: Set[Tuple[str, int]] = set()

        # 1. Exact & Near Duplicate Block Detection via Normalized Window Hashes
        exact_blocks, near_blocks, sloc_by_file = self._detect_code_blocks(files_content)
        all_blocks.extend(exact_blocks)
        all_blocks.extend(near_blocks)

        for b in exact_blocks + near_blocks:
            for loc in b.locations:
                for line in range(loc.start_line, loc.end_line + 1):
                    duplicated_sloc_lines.add((loc.file_path, line))

        # 2. Repeated Conditions Detection
        condition_blocks = self._detect_repeated_conditions(files_content)
        all_blocks.extend(condition_blocks)

        # 3. Repeated Literals (Magic numbers, strings, SQL, Regex)
        literal_blocks = self._detect_repeated_literals(files_content)
        all_blocks.extend(literal_blocks)

        total_sloc = sum(sloc_by_file.values())
        dup_percentage = (
            (len(duplicated_sloc_lines) / total_sloc * 100.0)
            if total_sloc > 0
            else 0.0
        )

        return all_blocks, round(min(100.0, dup_percentage), 2)

    def _detect_code_blocks(
        self, files_content: Dict[str, str]
    ) -> Tuple[List[DuplicationBlock], List[DuplicationBlock], Dict[str, int]]:
        """Detects exact and near-duplicate multi-line statement blocks."""
        exact_hashes: Dict[str, List[Tuple[str, int, int, str]]] = {}
        near_hashes: Dict[str, List[Tuple[str, int, int, str]]] = {}
        sloc_by_file: Dict[str, int] = {}

        for file_path, content in files_content.items():
            lines = content.splitlines()
            sloc_lines = [
                (idx + 1, line.strip())
                for idx, line in enumerate(lines)
                if line.strip() and not line.strip().startswith("#")
            ]
            sloc_by_file[file_path] = len(sloc_lines)

            if len(sloc_lines) < self.min_block_lines:
                continue

            # Sliding window over executable statements
            for i in range(len(sloc_lines) - self.min_block_lines + 1):
                window = sloc_lines[i : i + self.min_block_lines]
                start_line = window[0][0]
                end_line = window[-1][0]
                block_str = "\n".join(item[1] for item in window)

                # Exact hash
                h_exact = hashlib.sha256(block_str.encode("utf-8")).hexdigest()
                exact_hashes.setdefault(h_exact, []).append((file_path, start_line, end_line, block_str))

                # Near-duplicate hash (normalize variables/literals with regex)
                norm_str = re.sub(r"\b[a-zA-Z_]\w*\b", "$ID", block_str)
                norm_str = re.sub(r"\b\d+\b", "$NUM", norm_str)
                norm_str = re.sub(r"['\"].*?['\"]", "$STR", norm_str)
                h_near = hashlib.sha256(norm_str.encode("utf-8")).hexdigest()
                near_hashes.setdefault(h_near, []).append((file_path, start_line, end_line, block_str))

        exact_dups: List[DuplicationBlock] = []
        for h, occurrences in exact_hashes.items():
            # Check for occurrences across different locations
            if len(occurrences) > 1:
                # Discard overlapping windows in same file
                filtered = self._filter_overlapping(occurrences)
                if len(filtered) > 1:
                    locations = [
                        CodeLocation(file_path=f, start_line=s, end_line=e)
                        for f, s, e, _ in filtered
                    ]
                    exact_dups.append(
                        DuplicationBlock(
                            locations=locations,
                            line_count=self.min_block_lines,
                            duplication_type="exact",
                            code_snippet=filtered[0][3],
                            similarity_score=1.0,
                        )
                    )

        near_dups: List[DuplicationBlock] = []
        # Exclude blocks already captured in exact duplicates
        for h, occurrences in near_hashes.items():
            if len(occurrences) > 1:
                filtered = self._filter_overlapping(occurrences)
                if len(filtered) > 1:
                    locations = [
                        CodeLocation(file_path=f, start_line=s, end_line=e)
                        for f, s, e, _ in filtered
                    ]
                    # Check if not exact match
                    is_exact = any(
                        filtered[0][3] == filtered[k][3]
                        for k in range(1, len(filtered))
                    )
                    if not is_exact:
                        near_dups.append(
                            DuplicationBlock(
                                locations=locations,
                                line_count=self.min_block_lines,
                                duplication_type="near_duplicate",
                                code_snippet=filtered[0][3],
                                similarity_score=0.85,
                            )
                        )

        return exact_dups, near_dups, sloc_by_file

    def _filter_overlapping(
        self, occurrences: List[Tuple[str, int, int, str]]
    ) -> List[Tuple[str, int, int, str]]:
        """Filters out heavily overlapping sliding windows in the same file."""
        distinct: List[Tuple[str, int, int, str]] = []
        for occ in occurrences:
            file_p, s, e, text = occ
            overlap = any(
                file_p == d[0] and abs(s - d[1]) < self.min_block_lines
                for d in distinct
            )
            if not overlap:
                distinct.append(occ)
        return distinct

    def _detect_repeated_conditions(self, files_content: Dict[str, str]) -> List[DuplicationBlock]:
        """Finds identical boolean conditions used across multiple conditionals."""
        condition_map: Dict[str, List[CodeLocation]] = {}

        for file_path, content in files_content.items():
            try:
                tree = ast.parse(content, filename=file_path)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.IfExp)):
                    try:
                        cond_str = ast.unparse(node.test).strip()
                    except Exception:
                        continue

                    # Ignore trivial boolean constants like True, False, None
                    if cond_str in ("True", "False", "None", "1", "0", ""):
                        continue

                    loc = CodeLocation(
                        file_path=file_path,
                        start_line=getattr(node.test, "lineno", 0),
                        end_line=getattr(node.test, "end_lineno", getattr(node.test, "lineno", 0)),
                    )
                    condition_map.setdefault(cond_str, []).append(loc)

        blocks: List[DuplicationBlock] = []
        for cond_str, locs in condition_map.items():
            if len(locs) >= 2:
                blocks.append(
                    DuplicationBlock(
                        locations=locs,
                        line_count=1,
                        duplication_type="repeated_condition",
                        code_snippet=cond_str,
                        similarity_score=1.0,
                    )
                )
        return blocks

    def _detect_repeated_literals(self, files_content: Dict[str, str]) -> List[DuplicationBlock]:
        """Finds repeated magic constants, SQL queries, and regex literals."""
        literal_map: Dict[str, List[Tuple[CodeLocation, str]]] = {}

        for file_path, content in files_content.items():
            try:
                tree = ast.parse(content, filename=file_path)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Constant):
                    val = node.value
                    if isinstance(val, str) and len(val.strip()) >= 5:
                        val_str = val.strip()
                        lit_type = "repeated_literal"
                        if SQL_PATTERN.search(val_str):
                            lit_type = "repeated_sql"
                        elif len(val_str) > 8 and REGEX_SPECIALS.search(val_str):
                            lit_type = "repeated_regex"

                        loc = CodeLocation(
                            file_path=file_path,
                            start_line=getattr(node, "lineno", 0),
                            end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                        )
                        literal_map.setdefault(val_str, []).append((loc, lit_type))

        blocks: List[DuplicationBlock] = []
        for lit_str, loc_entries in literal_map.items():
            ltype = loc_entries[0][1]
            min_req = 2 if ltype in ("repeated_sql", "repeated_regex") else self.min_literal_occurrences
            if len(loc_entries) >= min_req:
                locs = [entry[0] for entry in loc_entries]
                blocks.append(
                    DuplicationBlock(
                        locations=locs,
                        line_count=1,
                        duplication_type=ltype,
                        code_snippet=lit_str[:120],
                        similarity_score=1.0,
                    )
                )
        return blocks
