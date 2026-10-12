"""
test_architecture_recommender.py - AutoDev Version 3.1
Unit and integration tests for ArchitectureRecommendationEngine across archetypes,
design patterns, database styles, security models, and historical feedback.
"""

from pathlib import Path
import pytest
from core.learning.architecture_recommender import ArchitectureRecommendationEngine


@pytest.fixture
def recommender(tmp_path: Path):
    storage_dir = tmp_path / "recommender"
    return ArchitectureRecommendationEngine(storage_dir=str(storage_dir), auto_persist=True)


def test_recommend_rest_api(recommender: ArchitectureRecommendationEngine):
    req = "Build a scalable REST API endpoint for order management and billing."
    rec = recommender.recommend_architecture(requirement=req, scale="medium")

    assert rec.recommendation_id.startswith("REC-")
    assert "Repository Pattern" in rec.design_patterns
    assert "RESTful" in rec.api_style
    assert "PostgreSQL" in rec.database_recommendation
    assert "Pytest" in rec.testing_strategy
    assert rec.confidence_score >= 0.85
    assert "api" in rec.recommended_folder_structure


def test_recommend_ai_agent(recommender: ArchitectureRecommendationEngine):
    req = "Build an autonomous AI agent with tool execution, memory, and LLM reasoning."
    rec = recommender.recommend_architecture(requirement=req, scale="medium")

    assert "Agent-Tool Interface" in rec.design_patterns or "Pipeline Pattern" in rec.design_patterns
    assert "JSON-RPC / CLI Interface" in rec.api_style or "Local Memory / JSON Store" in rec.database_recommendation
    assert "agents" in rec.recommended_folder_structure


def test_recommend_cli_tool(recommender: ArchitectureRecommendationEngine):
    req = "Build a fast Python CLI developer utility for linting repository code."
    rec = recommender.recommend_architecture(requirement=req, scale="small")

    assert "Command Pattern" in rec.design_patterns
    assert "CLI Arguments / Standard POSIX" in rec.api_style
    assert "None (Stateless) / Local SQLite" in rec.database_recommendation


def test_recommend_microservices_enterprise(recommender: ArchitectureRecommendationEngine):
    req = "Build an enterprise distributed microservices cluster with high availability."
    rec = recommender.recommend_architecture(requirement=req, scale="enterprise")

    assert "Event-Driven / CQRS" in rec.design_patterns
    assert "Distributed Event Store / PostgreSQL" in rec.database_recommendation
    assert "mTLS / OAuth2 / JWT RBAC" in rec.security_model


def test_incorporate_historical_feedback(recommender: ArchitectureRecommendationEngine):
    rec = recommender.recommend_architecture("Build web dashboard", scale="small")
    initial_confidence = rec.confidence_score

    # Positive feedback boosts confidence
    updated_pos = recommender.incorporate_feedback(rec.recommendation_id, success=True, quality_score=98.0)
    assert updated_pos is not None
    assert updated_pos.confidence_score >= initial_confidence

    # Negative feedback adjusts score
    updated_neg = recommender.incorporate_feedback(rec.recommendation_id, success=False, quality_score=40.0)
    assert updated_neg is not None
    assert updated_neg.confidence_score < updated_pos.confidence_score


def test_get_all_recommendations(recommender: ArchitectureRecommendationEngine):
    recommender.recommend_architecture("App 1")
    recommender.recommend_architecture("App 2")
    all_recs = recommender.get_all_recommendations()
    assert len(all_recs) == 2
