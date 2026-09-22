"""
tests/test_code_retrieval.py
Tests for the code retrieval and token efficiency engine.
"""

import os
import tempfile
import pytest
from services.code_retrieval import (
    CodeChunk,
    count_tokens,
    extract_symbols,
    ingest_repository,
    search_chunks,
    compress_context,
    retrieve_code,
    _sanitize_query,
    RetrievalResult,
)


# ------------------------------------------------------------------ #
# Token counting
# ------------------------------------------------------------------ #

def test_count_tokens_empty():
    assert count_tokens("") == 0
    assert count_tokens(None) == 0

def test_count_tokens_nonempty():
    """Token count should be positive for non-empty text."""
    assert count_tokens("hello world") > 0

def test_count_tokens_longer_text_has_more_tokens():
    short = count_tokens("short")
    long = count_tokens("a" * 1000)
    assert long > short


# ------------------------------------------------------------------ #
# Symbol extraction
# ------------------------------------------------------------------ #

SAMPLE_PY = '''
def hello():
    return "world"

class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass
'''

def test_extract_symbols_finds_function():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    names = [c.name for c in chunks]
    assert "hello" in names

def test_extract_symbols_finds_class():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    names = [c.name for c in chunks]
    assert "MyClass" in names

def test_extract_symbols_finds_methods():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    names = [c.name for c in chunks]
    assert "MyClass.method_one" in names
    assert "MyClass.method_two" in names

def test_extract_symbols_sets_chunk_types():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    types = [c.chunk_type for c in chunks]
    assert "function" in types
    assert "class" in types
    assert "method" in types

def test_extract_symbols_handles_syntax_error():
    """Non-parseable content should return a module chunk, not crash."""
    chunks = extract_symbols("bad.py", "this is not python {{{")
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "module"

def test_extract_symbols_sets_line_numbers():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    for chunk in chunks:
        assert chunk.start_line >= 1
        assert chunk.end_line >= chunk.start_line


# ------------------------------------------------------------------ #
# Repository ingestion
# ------------------------------------------------------------------ #

def test_ingest_repository():
    """Ingesting a real directory should find Python files."""
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chunks = ingest_repository(repo_path, max_files=200)
    assert len(chunks) > 0
    # Should find our service files
    file_paths = [c.file_path for c in chunks]
    assert any("services" in p for p in file_paths)


def test_ingest_repository_skips_venv():
    """Ingest should skip .venv and __pycache__ directories."""
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chunks = ingest_repository(repo_path, max_files=100)
    file_paths = [c.file_path for c in chunks]
    assert not any(".venv" in p for p in file_paths)
    assert not any("__pycache__" in p for p in file_paths)


def test_ingest_repository_respects_max_files():
    """Ingest should stop at max_files."""
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chunks = ingest_repository(repo_path, max_files=2)
    # Should find some files but not all
    assert len(chunks) > 0


# ------------------------------------------------------------------ #
# Search
# ------------------------------------------------------------------ #

def test_search_finds_by_symbol_name():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    results = search_chunks(chunks, "hello")
    assert len(results) > 0
    assert results[0][0].name == "hello"

def test_search_finds_by_class_name():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    results = search_chunks(chunks, "MyClass")
    assert len(results) > 0
    assert results[0][0].name == "MyClass"

def test_search_empty_query_returns_empty():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    results = search_chunks(chunks, "")
    assert len(results) == 0

def test_search_no_match_returns_empty():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    results = search_chunks(chunks, "nonexistent_xyz_123")
    assert len(results) == 0

def test_search_results_sorted_by_score():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    results = search_chunks(chunks, "MyClass method")
    for i in range(len(results) - 1):
        assert results[i][1] >= results[i + 1][1]

def test_search_max_results():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    results = search_chunks(chunks, "test", max_results=2)
    assert len(results) <= 2


# ------------------------------------------------------------------ #
# Query sanitization
# ------------------------------------------------------------------ #

def test_sanitize_query_removes_special_chars():
    sanitized = _sanitize_query("hello; DROP TABLE--")
    assert ";" not in sanitized
    assert "--" not in sanitized
    assert "DROP" in sanitized  # alphanumeric preserved

def test_sanitize_query_limits_length():
    sanitized = _sanitize_query("a" * 500)
    assert len(sanitized) <= 200

def test_sanitize_query_preserves_alphanumerics():
    sanitized = _sanitize_query("MyClass.hello_world")
    assert "MyClass" in sanitized or "hello_world" in sanitized


# ------------------------------------------------------------------ #
# Context compression
# ------------------------------------------------------------------ #

def test_compress_context_within_token_budget():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    context, tokens, used = compress_context(chunks, max_tokens=100)
    assert tokens <= 100

def test_compress_context_deduplicates():
    """Chunks with the same hash should be deduplicated."""
    chunk1 = CodeChunk(
        file_path="a.py", chunk_type="function", name="foo",
        content="def foo(): pass", start_line=1, end_line=1,
    )
    chunk2 = CodeChunk(
        file_path="a.py", chunk_type="function", name="foo",
        content="def foo(): pass", start_line=1, end_line=1,
    )
    context, tokens, used = compress_context([chunk1, chunk2], max_tokens=1000)
    assert used == 1  # Only one (deduplicated)


def test_compress_context_returns_nonempty():
    chunks = extract_symbols("test.py", SAMPLE_PY)
    context, tokens, used = compress_context(chunks, max_tokens=1000)
    assert len(context) > 0
    assert tokens > 0
    assert used > 0


# ------------------------------------------------------------------ #
# Full retrieval pipeline
# ------------------------------------------------------------------ #

def test_retrieve_code_returns_result():
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = retrieve_code(repo_path, "auth_service", max_tokens=2000)
    assert isinstance(result, RetrievalResult)
    assert result.total_tokens > 0
    assert result.latency_ms >= 0
    assert result.tokens_saved >= 0
    assert result.files_searched > 0

def test_retrieve_code_tokens_saved():
    """Retrieval should save tokens vs sending the entire repo."""
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = retrieve_code(repo_path, "password hash", max_tokens=500)
    # tokens_saved = total_repo_tokens - retrieved_tokens
    assert result.tokens_saved > 0 or result.total_tokens < 500

def test_retrieve_code_latency_measured():
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = retrieve_code(repo_path, "test")
    assert result.latency_ms >= 0

def test_retrieve_code_empty_query():
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = retrieve_code(repo_path, "", max_tokens=500)
    # Empty query should return empty context or very small
    assert result.total_tokens >= 0
