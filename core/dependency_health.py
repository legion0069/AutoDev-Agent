"""
AutoDev Dependency Health Analyzer (v2.7)
Evaluates topological graph structure: circular dependencies, diamond inheritance,
God objects, Hub modules, fragile base classes, Martin's instability metrics,
and architectural layer violations.
"""

from __future__ import annotations

import ast
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from core.quality_metrics import (
    calculate_abstractness,
    calculate_distance_main_sequence,
    calculate_instability,
    calculate_lcom4,
)
from core.quality_models import (
    DependencyHealthMetrics,
    DiamondInheritance,
    FragileBaseClassFinding,
    GodObjectFinding,
    HubModuleFinding,
)

logger = logging.getLogger(__name__)


class DependencyHealthAnalyzer:
    """Graph-theoretic structural analyzer assessing architectural health and stability."""

    def __init__(self, workspace_path: str = "", workspace_root: Optional[str] = None):
        target = workspace_root if workspace_root is not None else workspace_path
        self.workspace_path = os.path.realpath(os.path.abspath(target or "."))

    def analyze_code(self, source_code: str, file_path: str = "snippet.py") -> DependencyHealthMetrics:
        """
        Analyzes a single code snippet or module for inheritance, LCOM4, and coupling metrics.
        """
        return self.analyze_dependencies({file_path: source_code})

    def analyze_dependencies(self, files_content: Dict[str, str]) -> DependencyHealthMetrics:
        """
        Analyzes the full workspace and returns a unified composite DependencyHealthMetrics object.
        """
        per_module = self.analyze_workspace(files_content)
        if not per_module:
            return DependencyHealthMetrics()

        total_ca = sum(m.afferent_coupling for m in per_module.values())
        total_ce = sum(m.efferent_coupling for m in per_module.values())
        instability = calculate_instability(total_ca, total_ce)

        all_cycles: List[List[str]] = []
        for m in per_module.values():
            for c in m.circular_dependency_cycles:
                if c not in all_cycles:
                    all_cycles.append(c)

        all_diamonds: List[DiamondInheritance] = []
        for m in per_module.values():
            for d in m.diamond_inheritances:
                if d not in all_diamonds:
                    all_diamonds.append(d)

        all_god_objects: List[GodObjectFinding] = []
        for m in per_module.values():
            for g in m.god_objects:
                if g not in all_god_objects:
                    all_god_objects.append(g)

        all_hubs: List[HubModuleFinding] = []
        for m in per_module.values():
            for h in m.hub_modules:
                if h not in all_hubs:
                    all_hubs.append(h)

        all_fragile: List[FragileBaseClassFinding] = []
        for m in per_module.values():
            for f in m.fragile_base_classes:
                if f not in all_fragile:
                    all_fragile.append(f)

        max_dit = max((m.depth_of_inheritance for m in per_module.values()), default=0)
        max_lcom4 = max((m.lack_of_cohesion_lcom4 for m in per_module.values()), default=1)

        avg_abstractness = sum(m.abstractness for m in per_module.values()) / len(per_module)
        distance = calculate_distance_main_sequence(avg_abstractness, instability)

        return DependencyHealthMetrics(
            afferent_coupling=total_ca,
            efferent_coupling=total_ce,
            instability=instability,
            abstractness=round(avg_abstractness, 4),
            distance_main_sequence=distance,
            has_circular_dependencies=len(all_cycles) > 0,
            circular_dependency_cycles=all_cycles,
            diamond_inheritance_count=len(all_diamonds),
            diamond_inheritances=all_diamonds,
            god_objects=all_god_objects,
            hub_modules=all_hubs,
            fragile_base_classes=all_fragile,
            is_god_object=len(all_god_objects) > 0,
            is_hub_module=len(all_hubs) > 0,
            depth_of_inheritance=max_dit,
            lack_of_cohesion_lcom4=max_lcom4,
        )

    def analyze_workspace(self, files_content: Dict[str, str]) -> Dict[str, DependencyHealthMetrics]:
        """
        Analyzes the full workspace dependency graph and returns per-module DependencyHealthMetrics.
        """
        import_graph: Dict[str, Set[str]] = {}
        class_inheritance_graph: Dict[str, List[str]] = {}
        class_methods: Dict[str, List[str]] = {}
        class_field_accesses: Dict[str, Dict[str, Set[str]]] = {}
        abstract_classes: Set[str] = set()
        all_classes: Set[str] = set()

        for file_path, content in files_content.items():
            mod_name = self._file_to_module_name(file_path)
            import_graph.setdefault(mod_name, set())

            try:
                tree = ast.parse(content, filename=file_path)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        target = self._normalize_import_name(alias.name)
                        if target:
                            import_graph[mod_name].add(target)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        target = self._normalize_import_name(node.module)
                        if target:
                            import_graph[mod_name].add(target)

                elif isinstance(node, ast.ClassDef):
                    cls_full = node.name
                    all_classes.add(cls_full)
                    bases = []
                    for b in node.bases:
                        if isinstance(b, ast.Name):
                            bases.append(b.id)
                        elif isinstance(b, ast.Attribute):
                            bases.append(b.attr)
                    class_inheritance_graph[cls_full] = bases

                    methods = []
                    field_map: Dict[str, Set[str]] = {}
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            methods.append(item.name)
                            for dec in item.decorator_list:
                                if (isinstance(dec, ast.Name) and "abstract" in dec.id.lower()) or (
                                    isinstance(dec, ast.Attribute) and "abstract" in dec.attr.lower()
                                ):
                                    abstract_classes.add(cls_full)

                            fields = set()
                            for subnode in ast.walk(item):
                                if (
                                    isinstance(subnode, ast.Attribute)
                                    and isinstance(subnode.value, ast.Name)
                                    and subnode.value.id == "self"
                                ):
                                    fields.add(subnode.attr)
                            field_map[item.name] = fields

                    class_methods[cls_full] = methods
                    class_field_accesses[cls_full] = field_map

        # Detect SCC Cycles
        internal_modules = set(import_graph.keys())
        scc_cycles = self._find_strongly_connected_components(import_graph, internal_modules)

        # Detect Diamond Inheritances
        diamond_findings = self._detect_diamond_inheritance_findings(class_inheritance_graph)

        # Detect God Objects
        god_findings = []
        for cls, methods in class_methods.items():
            all_fields: Set[str] = set()
            for fset in class_field_accesses.get(cls, {}).values():
                all_fields.update(fset)
            if len(methods) >= 20 or len(all_fields) >= 10:
                god_findings.append(
                    GodObjectFinding(
                        class_name=cls,
                        method_count=len(methods),
                        attribute_count=len(all_fields),
                    )
                )

        # Detect Fragile Base Classes
        fragile_findings = []
        for cls in all_classes:
            dit = self._calculate_dit(cls, class_inheritance_graph)
            if dit >= 3:
                fragile_findings.append(
                    FragileBaseClassFinding(
                        class_name=cls,
                        depth_of_inheritance=dit,
                    )
                )

        results: Dict[str, DependencyHealthMetrics] = {}

        for mod_name, outgoing in import_graph.items():
            ce = len([t for t in outgoing if t in internal_modules and t != mod_name])
            ca = sum(
                1
                for other_mod, other_out in import_graph.items()
                if other_mod != mod_name and mod_name in other_out
            )

            instability = calculate_instability(ca, ce)
            mod_classes = [c for c in all_classes if c.startswith(mod_name) or "." not in c]
            mod_abstract = [c for c in mod_classes if c in abstract_classes]

            abstractness = calculate_abstractness(len(mod_abstract), len(mod_classes))
            distance = calculate_distance_main_sequence(abstractness, instability)

            mod_cycles = [c for c in scc_cycles if mod_name in c]
            has_cycles = len(mod_cycles) > 0

            hub_findings = []
            if (ca * ce) >= 100 or (ca >= 8 and ce >= 8):
                hub_findings.append(
                    HubModuleFinding(
                        module_name=mod_name,
                        afferent_coupling=ca,
                        efferent_coupling=ce,
                    )
                )

            max_lcom4 = 1
            max_dit = 0
            for cls_name in mod_classes:
                methods = class_methods.get(cls_name, [])
                field_map = class_field_accesses.get(cls_name, {})
                lcom4 = calculate_lcom4(methods, field_map)
                if lcom4 > max_lcom4:
                    max_lcom4 = lcom4

                dit = self._calculate_dit(cls_name, class_inheritance_graph)
                if dit > max_dit:
                    max_dit = dit

            results[mod_name] = DependencyHealthMetrics(
                afferent_coupling=ca,
                efferent_coupling=ce,
                instability=instability,
                abstractness=abstractness,
                distance_main_sequence=distance,
                has_circular_dependencies=has_cycles,
                circular_dependency_cycles=mod_cycles,
                diamond_inheritance_count=len(diamond_findings),
                diamond_inheritances=diamond_findings,
                god_objects=god_findings,
                hub_modules=hub_findings,
                fragile_base_classes=fragile_findings,
                is_god_object=len(god_findings) > 0,
                is_hub_module=len(hub_findings) > 0,
                depth_of_inheritance=max_dit,
                lack_of_cohesion_lcom4=max_lcom4,
            )

        return results

    def _normalize_import_name(self, raw_import: str) -> str:
        """Normalizes import target name to match relative paths."""
        return raw_import.replace(".", "/")

    def _file_to_module_name(self, file_path: str) -> str:
        clean = file_path.replace("\\", "/").replace(".py", "")
        clean = clean.lstrip("./")
        return clean

    def _find_strongly_connected_components(
        self, graph: Dict[str, Set[str]], internal_nodes: Set[str]
    ) -> List[List[str]]:
        index = 0
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        stack: List[str] = []
        on_stack: Set[str] = set()
        sccs: List[List[str]] = []

        def strongconnect(node: str):
            nonlocal index
            indices[node] = index
            lowlinks[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)

            for target in graph.get(node, set()):
                # Allow partial match for module targets
                matched = [t for t in internal_nodes if t == target or t.endswith(target) or target.endswith(t)]
                for match_node in matched:
                    if match_node not in indices:
                        strongconnect(match_node)
                        lowlinks[node] = min(lowlinks[node], lowlinks[match_node])
                    elif match_node in on_stack:
                        lowlinks[node] = min(lowlinks[node], indices[match_node])

            if lowlinks[node] == indices[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node:
                        break
                if len(scc) > 1:
                    sccs.append(sorted(scc))

        for n in list(internal_nodes):
            if n not in indices:
                strongconnect(n)

        return sccs

    def _detect_diamond_inheritance_findings(
        self, inheritance_graph: Dict[str, List[str]]
    ) -> List[DiamondInheritance]:
        findings: List[DiamondInheritance] = []
        for cls_name, bases in inheritance_graph.items():
            if len(bases) >= 2:
                ancestor_maps: Dict[str, Set[str]] = {}
                for base in bases:
                    ancestors: Set[str] = set()
                    self._collect_ancestors(base, inheritance_graph, ancestors)
                    ancestor_maps[base] = ancestors

                for i in range(len(bases)):
                    for j in range(i + 1, len(bases)):
                        b1 = bases[i]
                        b2 = bases[j]
                        common = ancestor_maps[b1].intersection(ancestor_maps[b2])
                        if common:
                            for c in common:
                                findings.append(
                                    DiamondInheritance(
                                        derived_class=cls_name,
                                        common_ancestor=c,
                                        intermediate_parents=[b1, b2],
                                    )
                                )
        return findings

    def _collect_ancestors(
        self, cls: str, graph: Dict[str, List[str]], visited: Set[str]
    ):
        bases = graph.get(cls, [])
        for b in bases:
            if b not in visited:
                visited.add(b)
                self._collect_ancestors(b, graph, visited)

    def _calculate_dit(self, cls: str, graph: Dict[str, List[str]], depth: int = 0) -> int:
        bases = graph.get(cls, [])
        if not bases:
            return depth
        return max(self._calculate_dit(b, graph, depth + 1) for b in bases)
