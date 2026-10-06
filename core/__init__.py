"""
Core module for AutoDev.
"""

from core.code_context_retriever import (
    CodeContextResult,
    CodeContextRetriever,
    RelevantFile,
    RelevantSymbol,
)
from core.code_indexer import CodeIndexer
from core.context_injector import ContextInjector, ScoredMemory
from core.impact_analyzer import (
    ImpactAnalyzer,
    ImpactReport,
    RiskLevel,
)
from core.memory_manager import (
    MemoryCategory,
    MemoryEntry,
    MemoryManager,
    MemorySearchResult,
    MemoryStatistics,
    MemoryValidationError,
)
from core.prompt_builder import PromptBuilder
from core.symbol_graph import (
    Dependency,
    IndexStatistics,
    Reference,
    Symbol,
    SymbolGraph,
    SymbolType,
    Visibility,
)

__all__ = [
    "CodeIndexer",
    "SymbolGraph",
    "Symbol",
    "SymbolType",
    "Visibility",
    "Dependency",
    "Reference",
    "IndexStatistics",
    "ContextInjector",
    "ScoredMemory",
    "MemoryCategory",
    "MemoryEntry",
    "MemoryManager",
    "MemorySearchResult",
    "MemoryStatistics",
    "MemoryValidationError",
    "CodeContextRetriever",
    "CodeContextResult",
    "RelevantSymbol",
    "RelevantFile",
    "ImpactAnalyzer",
    "ImpactReport",
    "RiskLevel",
    "PromptBuilder",
]
