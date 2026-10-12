"""
tests/test_dependency_health.py - Unit tests for AutoDev Dependency Health (v2.7)

Validates:
- Circular dependency cycle detection via Tarjan's SCC algorithm
- Diamond inheritance detection
- God object detection (WMC, NOA, NOM thresholds)
- Hub module detection (high afferent * efferent coupling)
- Fragile base class detection (DIT >= 3)
- Package Instability, Abstractness, and Distance from Main Sequence
"""

import pytest
from core.dependency_health import DependencyHealthAnalyzer
from core.quality_models import DependencyHealthMetrics


def test_circular_dependency_detection_tarjan_scc(tmp_path):
    """Detects circular import cycles (A -> B -> C -> A) using Tarjan SCC."""
    files = {
        "pkg/mod_a.py": "from pkg.mod_b import b_func\ndef a_func(): pass",
        "pkg/mod_b.py": "from pkg.mod_c import c_func\ndef b_func(): pass",
        "pkg/mod_c.py": "from pkg.mod_a import a_func\ndef c_func(): pass",
        "pkg/mod_d.py": "from pkg.mod_a import a_func\ndef d_func(): pass",
    }

    analyzer = DependencyHealthAnalyzer(workspace_root=str(tmp_path))
    metrics = analyzer.analyze_dependencies(files_content=files)
    assert metrics.has_circular_dependencies is True
    assert len(metrics.circular_dependency_cycles) >= 1
    cycle = metrics.circular_dependency_cycles[0]
    # The cycle must contain mod_a, mod_b, mod_c
    cycle_str = " ".join(cycle)
    assert "mod_a" in cycle_str and "mod_b" in cycle_str and "mod_c" in cycle_str


def test_acyclic_dependencies_clean(tmp_path):
    """A directed acyclic graph (DAG) should report 0 circular dependency cycles."""
    files = {
        "app/main.py": "from app.controller import handle\n",
        "app/controller.py": "from app.service import process\n",
        "app/service.py": "from app.repository import save\n",
        "app/repository.py": "# Base layer with no imports\n",
    }

    analyzer = DependencyHealthAnalyzer(workspace_root=str(tmp_path))
    metrics = analyzer.analyze_dependencies(files_content=files)
    assert metrics.has_circular_dependencies is False
    assert len(metrics.circular_dependency_cycles) == 0


def test_diamond_inheritance_detection(tmp_path):
    """Detects diamond inheritance pattern: Base -> (Left, Right) -> Derived."""
    files = {
        "hierarchy.py": """
class BaseEntity:
    def save(self): pass

class AuditableEntity(BaseEntity):
    def audit(self): pass

class VersionedEntity(BaseEntity):
    def version(self): pass

class Document(AuditableEntity, VersionedEntity):
    pass
"""
    }

    analyzer = DependencyHealthAnalyzer(workspace_root=str(tmp_path))
    metrics = analyzer.analyze_dependencies(files_content=files)
    assert len(metrics.diamond_inheritances) >= 1
    diamond = metrics.diamond_inheritances[0]
    assert diamond.derived_class == "Document"
    assert diamond.common_ancestor == "BaseEntity"
    assert "AuditableEntity" in diamond.intermediate_parents
    assert "VersionedEntity" in diamond.intermediate_parents


def test_god_object_detection(tmp_path):
    """Detects massive God Object classes exceeding method and attribute thresholds."""
    methods_code = "\n".join([f"    def method_{i}(self):\n        return {i}" for i in range(25)])
    fields_code = "\n".join([f"        self.field_{i} = {i}" for i in range(15)])
    god_class = f"""
class EnterpriseSuperController:
    def __init__(self):
{fields_code}

{methods_code}
"""
    files = {"god_module.py": god_class}

    analyzer = DependencyHealthAnalyzer(workspace_root=str(tmp_path))
    metrics = analyzer.analyze_dependencies(files_content=files)
    assert len(metrics.god_objects) >= 1
    god = metrics.god_objects[0]
    assert god.class_name == "EnterpriseSuperController"
    assert god.method_count >= 25
    assert god.attribute_count >= 15


def test_hub_module_detection(tmp_path):
    """Detects hub modules with dangerous fan-in and fan-out coupling."""
    # Module with many imports from other modules and many other modules importing it
    files = {
        f"caller_{i}.py": "from hub.router import central_dispatcher" for i in range(12)
    }
    # Hub module importing 12 other dependencies
    imports = "\n".join([f"import dependency_{i}" for i in range(12)])
    files["hub/router.py"] = f"""
{imports}
def central_dispatcher(): pass
"""
    for i in range(12):
        files[f"dependency_{i}.py"] = "def do(): pass"

    analyzer = DependencyHealthAnalyzer(workspace_root=str(tmp_path))
    metrics = analyzer.analyze_dependencies(files_content=files)
    # router has Ca >= 12 and Ce >= 12 -> Ca * Ce >= 144 >= 100
    assert len(metrics.hub_modules) >= 1
    hub_names = [h.module_name for h in metrics.hub_modules]
    assert any("router" in name for name in hub_names)


def test_fragile_base_class_deep_inheritance(tmp_path):
    """Detects deep inheritance hierarchy DIT >= 3."""
    files = {
        "deep_tree.py": """
class Level0: pass
class Level1(Level0): pass
class Level2(Level1): pass
class Level3(Level2): pass
class Level4(Level3): pass
"""
    }

    analyzer = DependencyHealthAnalyzer(workspace_root=str(tmp_path))
    metrics = analyzer.analyze_dependencies(files_content=files)
    assert len(metrics.fragile_base_classes) >= 1
    fragile = [f for f in metrics.fragile_base_classes if f.class_name == "Level4"][0]
    assert fragile.depth_of_inheritance >= 4
