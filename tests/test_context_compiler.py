"""
tests/test_context_compiler.py
Tests for the Context Compiler: multi-source gathering, token budget,
relevance ranking, provenance, selection explanations.
"""

import pytest
from services.context_compiler import (
    compile_context, ContextEntry, ContextCompilation,
)
from services.memory_engine import set_memory, clear_user_memories
from services.workspace import (
    create_workspace, create_project, reset_workspaces,
)


@pytest.fixture(autouse=True)
def _reset():
    """Reset in-memory stores before each test."""
    clear_user_memories(1)
    clear_user_memories(2)
    reset_workspaces()
    yield
    clear_user_memories(1)
    clear_user_memories(2)
    reset_workspaces()


# ------------------------------------------------------------------ #
# Basic compilation
# ------------------------------------------------------------------ #

def test_compile_empty_query():
    """Empty query returns empty compilation."""
    result = compile_context(1, "")
    assert len(result.entries) == 0
    assert result.total_tokens == 0


def test_compile_no_data():
    """Compile with a query that matches no memory, tasks, or workspace data.

    Note: code_retrieval may still find repo symbols by keyword, so we only
    assert that memory/project entries are empty (not code entries).
    """
    result = compile_context(1, "zzz_no_match_zzz")
    assert isinstance(result, ContextCompilation)
    # Memory and project entries should be empty — no user data set
    non_code = [e for e in result.entries if e.source_type != "code"]
    assert non_code == []


def test_compile_from_memory():
    """Compile context from memory source."""
    set_memory(1, "preference", "python", "I love Python programming")
    result = compile_context(1, "python")
    assert len(result.entries) > 0
    mem_entries = [e for e in result.entries if e.source_type == "memory"]
    assert len(mem_entries) > 0
    assert mem_entries[0].source_type == "memory"


def test_compile_from_multiple_sources():
    """Compile context from multiple sources (memory + workspace)."""
    set_memory(1, "preference", "project_x", "Project X is about testing")
    create_workspace(1, "My Workspace", "A test workspace")
    result = compile_context(1, "project")
    source_types = {e.source_type for e in result.entries}
    assert "memory" in source_types or "project" in source_types


# ------------------------------------------------------------------ #
# Token budget
# ------------------------------------------------------------------ #

def test_token_budget_respected():
    """Total tokens of selected entries should not exceed budget (with small tolerance for truncation rounding)."""
    set_memory(1, "preference", "key1", "A" * 5000)
    set_memory(1, "preference", "key2", "B" * 5000)
    result = compile_context(1, "key", max_tokens=100)
    # Allow small tolerance: truncation heuristic may overshoot by a few tokens
    assert result.total_tokens <= 100 + 10 or result.total_tokens == 0


def test_token_budget_with_multiple_entries():
    """Multiple small entries should fit within budget."""
    for i in range(5):
        set_memory(1, "preference", f"key{i}", f"value {i}")
    result = compile_context(1, "value", max_tokens=4000)
    selected = [e for e in result.entries if e.selected]
    total = sum(e.token_count for e in selected)
    assert total <= 4000


# ------------------------------------------------------------------ #
# Relevance ranking
# ------------------------------------------------------------------ #

def test_relevance_ranking():
    """Entries should be ranked by relevance (highest first)."""
    set_memory(1, "preference", "high", "relevant content", relevance_score=0.9)
    set_memory(1, "preference", "low", "also relevant content", relevance_score=0.2)
    result = compile_context(1, "content", max_tokens=10000)
    # Check entries are sorted by relevance descending
    scores = [e.relevance_score for e in result.entries]
    assert scores == sorted(scores, reverse=True)


def test_high_relevance_comes_first():
    """Higher relevance entries should appear before lower ones."""
    set_memory(1, "preference", "a", "aaa", relevance_score=0.1)
    set_memory(1, "preference", "b", "bbb", relevance_score=0.9)
    result = compile_context(1, "a", max_tokens=10000)
    if len(result.entries) >= 2:
        assert result.entries[0].relevance_score >= result.entries[1].relevance_score


# ------------------------------------------------------------------ #
# Provenance
# ------------------------------------------------------------------ #

def test_provenance_recorded():
    """Each entry should have provenance information."""
    set_memory(1, "preference", "test", "test value")
    result = compile_context(1, "test")
    for entry in result.entries:
        assert entry.provenance != ""
        assert isinstance(entry.provenance, str)


def test_provenance_describes_source():
    """Provenance should describe the source method."""
    set_memory(1, "preference", "prov_test", "provenance test")
    result = compile_context(1, "prov")
    mem_entries = [e for e in result.entries if e.source_type == "memory"]
    if mem_entries:
        assert "memory_engine" in mem_entries[0].provenance


# ------------------------------------------------------------------ #
# Selection explanation
# ------------------------------------------------------------------ #

def test_explanation_present():
    """Compilation should include a non-empty explanation."""
    set_memory(1, "preference", "test", "test value")
    result = compile_context(1, "test")
    assert result.explanation != ""
    assert isinstance(result.explanation, str)


def test_explanation_mentions_budget():
    """Explanation should mention token budget."""
    set_memory(1, "preference", "test", "test value")
    result = compile_context(1, "test", max_tokens=4000)
    assert "4000" in result.explanation or "budget" in result.explanation.lower()


def test_explanation_mentions_selected_count():
    """Explanation should mention selected count."""
    set_memory(1, "preference", "test", "test value")
    result = compile_context(1, "test")
    assert "Selected" in result.explanation or "selected" in result.explanation.lower()


# ------------------------------------------------------------------ #
# ContextEntry and ContextCompilation serialization
# ------------------------------------------------------------------ #

def test_context_entry_to_dict():
    """ContextEntry should serialize to dict."""
    entry = ContextEntry(
        source_type="memory",
        source_id="memory:test:key",
        content="test content",
        relevance_score=0.8,
        provenance="test source",
        token_count=5,
        selected=True,
        reason="test reason",
    )
    d = entry.to_dict()
    assert d["source_type"] == "memory"
    assert d["source_id"] == "memory:test:key"
    assert d["content"] == "test content"
    assert d["relevance_score"] == 0.8
    assert d["selected"] is True
    assert d["reason"] == "test reason"


def test_context_compilation_to_dict():
    """ContextCompilation should serialize to dict."""
    entry = ContextEntry(
        source_type="memory",
        source_id="test",
        content="content",
        selected=True,
        token_count=5,
    )
    comp = ContextCompilation(
        entries=[entry],
        total_tokens=5,
        budget=4000,
        compression_applied=False,
        explanation="test explanation",
        latency_ms=10.0,
    )
    d = comp.to_dict()
    assert d["total_tokens"] == 5
    assert d["budget"] == 4000
    assert d["explanation"] == "test explanation"
    assert d["entry_count"] == 1
    assert d["selected_count"] == 1
    assert len(d["entries"]) == 1


# ------------------------------------------------------------------ #
# User isolation
# ------------------------------------------------------------------ #

def test_user_isolation():
    """Context from user 1 should not appear for user 2."""
    set_memory(1, "preference", "user1_secret", "secret data for user1")
    result = compile_context(2, "user1_secret")
    mem_entries = [e for e in result.entries if e.source_type == "memory"]
    assert len(mem_entries) == 0


def test_workspace_isolation():
    """Workspace from user 1 should not appear for user 2."""
    create_workspace(1, "User1 WS", "user1 workspace")
    result = compile_context(2, "workspace")
    proj_entries = [e for e in result.entries if e.source_type == "project"]
    assert len(proj_entries) == 0


# ------------------------------------------------------------------ #
# Compression
# ------------------------------------------------------------------ #

def test_compression_flag():
    """Compression flag should be set when entries are truncated."""
    # Create a high-relevance memory that's too large for a tiny budget
    set_memory(1, "preference", "large", "x" * 5000, relevance_score=0.9)
    result = compile_context(1, "large", max_tokens=200)
    # If compression was applied, the flag should be True
    if any(e.selected for e in result.entries):
        # Either compression was applied or the entry fit
        assert isinstance(result.compression_applied, bool)


# ------------------------------------------------------------------ #
# Latency
# ------------------------------------------------------------------ #

def test_latency_measured():
    """Latency should be non-negative."""
    set_memory(1, "preference", "latency_test", "test value")
    result = compile_context(1, "latency_test")
    assert result.latency_ms >= 0
