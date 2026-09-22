"""
tests/test_knowledge_retrieval.py
Tests for unified knowledge retrieval.
"""

import pytest
from services.knowledge_retrieval import (
    search_knowledge, get_retrieval_summary,
    KnowledgeResult, RetrievalContext, SourceType,
)
from services.memory_engine import set_memory, clear_user_memories


def test_search_empty_query():
    ctx = search_knowledge(1, "")
    assert len(ctx.results) == 0

def test_search_with_memory():
    clear_user_memories(1)
    set_memory(1, "preference", "python", "I love Python programming")
    ctx = search_knowledge(1, "python")
    assert len(ctx.results) > 0
    assert ctx.results[0].source_type == SourceType.MEMORY

def test_search_user_isolation():
    clear_user_memories(1)
    clear_user_memories(2)
    set_memory(1, "preference", "secret", "user1 secret data")
    ctx = search_knowledge(2, "secret")
    assert len(ctx.results) == 0

def test_search_token_budget():
    clear_user_memories(1)
    set_memory(1, "preference", "key", "x" * 500)
    ctx = search_knowledge(1, "key", max_tokens=10)
    assert ctx.total_tokens <= 10 or len(ctx.results) == 0

def test_search_max_results():
    clear_user_memories(1)
    for i in range(10):
        set_memory(1, "preference", f"key{i}", f"value {i}")
    ctx = search_knowledge(1, "value", max_results=3)
    assert len(ctx.results) <= 3

def test_search_latency_measured():
    clear_user_memories(1)
    set_memory(1, "preference", "test", "test value")
    ctx = search_knowledge(1, "test")
    assert ctx.latency_ms >= 0

def test_retrieval_context_to_dict():
    ctx = RetrievalContext()
    d = ctx.to_dict()
    assert "results" in d
    assert "total_tokens" in d
    assert "result_count" in d

def test_retrieval_summary_empty():
    ctx = RetrievalContext()
    summary = get_retrieval_summary(ctx)
    assert "No relevant" in summary

def test_retrieval_summary_with_results():
    results = [KnowledgeResult(
        source_type=SourceType.MEMORY,
        title="test",
        content="test content",
        relevance_score=0.9,
    )]
    ctx = RetrievalContext(results=results, total_tokens=10)
    summary = get_retrieval_summary(ctx)
    assert "1 results" in summary
    assert "memory" in summary.lower()

def test_source_types_exist():
    assert SourceType.CODE.value == "code"
    assert SourceType.MEMORY.value == "memory"
    assert SourceType.TASK.value == "task"
    assert SourceType.NOTE.value == "note"
    assert SourceType.PROJECT.value == "project"
    assert SourceType.DOCUMENT.value == "document"
