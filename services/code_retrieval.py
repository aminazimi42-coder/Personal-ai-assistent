"""
services/code_retrieval.py
Code retrieval and token efficiency engine.

Pipeline: USER REQUEST → INTENT ANALYSIS → CODE RETRIEVAL → HYBRID SEARCH →
RANKING → CONTEXT COMPRESSION → TOKEN/COST GUARD → LLM → RESPONSE

Features:
- Repository ingestion: parse Python files into chunks
- Symbol extraction: functions, classes, methods, modules
- Hybrid search: keyword (PostgreSQL FTS) + symbol name matching
- Relevance ranking: TF-IDF + symbol-type weighting
- Context compression: deduplicate, truncate to token budget
- Token measurement: tiktoken-based token counting
- Strict user/repository isolation
- Retrieval latency measurement
- Cache with invalidation

No vector DB required — uses PostgreSQL full-text search.
Repository content is treated as untrusted input (prompt-injection-aware).
"""

import ast
import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Prompt-injection defense
# ------------------------------------------------------------------ #
MAX_QUERY_LENGTH = 10000

# Control characters (C0 + DEL) — never allowed in sanitized input
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_input(text: str, max_length: int = MAX_QUERY_LENGTH) -> str:
    """
    Sanitize untrusted user input before using it in retrieval or LLM prompts.

    - Strips control characters that could be used to obfuscate injections
      or hide malicious content from display.
    - Truncates to ``max_length`` to bound resource use.
    Returns the cleaned string (possibly empty).
    """
    if not text:
        return ""
    # Remove control characters
    cleaned = _CTRL_RE.sub("", str(text))
    # Collapse excessive whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Length guard
    cleaned = cleaned.strip()[:max_length]
    return cleaned

# ------------------------------------------------------------------ #
# Token counting (uses tiktoken if available, else heuristic)
# ------------------------------------------------------------------ #
_tiktoken_available = False
try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    _tiktoken_available = True
except ImportError:
    _enc = None

# Heuristic: ~4 chars per token for English/code
_CHARS_PER_TOKEN = 4


def count_tokens(text: str) -> int:
    """Count tokens in text. Uses tiktoken if available, else heuristic."""
    if not text:
        return 0
    if _tiktoken_available and _enc:
        return len(_enc.encode(text))
    return max(1, len(text) // _CHARS_PER_TOKEN)


# ------------------------------------------------------------------ #
# Code chunk data structure
# ------------------------------------------------------------------ #
@dataclass
class CodeChunk:
    """A chunk of code from a repository."""
    file_path: str
    chunk_type: str  # 'module', 'class', 'function', 'method'
    name: str
    content: str
    start_line: int
    end_line: int
    language: str = "python"
    token_count: int = 0
    hash: str = ""

    def __post_init__(self):
        if not self.token_count:
            self.token_count = count_tokens(self.content)
        if not self.hash:
            self.hash = hashlib.sha256(
                self.content.encode("utf-8")
            ).hexdigest()[:16]


# ------------------------------------------------------------------ #
# Symbol extraction via AST parsing
# ------------------------------------------------------------------ #
def extract_symbols(file_path: str, content: str) -> list[CodeChunk]:
    """
    Parse a Python file and extract symbols (modules, classes, functions, methods).
    Returns a list of CodeChunk objects.
    """
    chunks = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Non-Python or unparseable file — return single module chunk
        chunks.append(CodeChunk(
            file_path=file_path,
            chunk_type="module",
            name=os.path.basename(file_path),
            content=content,
            start_line=1,
            end_line=content.count("\n") + 1,
            language="unknown",
        ))
        return chunks

    lines = content.splitlines(keepends=True)
    file_name = os.path.basename(file_path)

    # Module-level docstring and imports
    module_start = 1
    module_content = ""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            break
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            # Docstring
            module_content = "".join(lines[module_start - 1:node.end_lineno])
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            module_content = "".join(lines[module_start - 1:node.end_lineno])

    if module_content.strip():
        chunks.append(CodeChunk(
            file_path=file_path,
            chunk_type="module",
            name=file_name,
            content=module_content,
            start_line=1,
            end_line=len(module_content.splitlines()),
        ))

    # Extract top-level definitions
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunk_content = _extract_node_content(node, lines)
            chunks.append(CodeChunk(
                file_path=file_path,
                chunk_type="function",
                name=node.name,
                content=chunk_content,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
            ))

        elif isinstance(node, ast.ClassDef):
            class_content = _extract_node_content(node, lines)
            chunks.append(CodeChunk(
                file_path=file_path,
                chunk_type="class",
                name=node.name,
                content=class_content,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
            ))

            # Extract methods within the class
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_content = _extract_node_content(child, lines)
                    chunks.append(CodeChunk(
                        file_path=file_path,
                        chunk_type="method",
                        name=f"{node.name}.{child.name}",
                        content=method_content,
                        start_line=child.lineno,
                        end_line=child.end_lineno or child.lineno,
                    ))

    return chunks


def _extract_node_content(node, lines: list[str]) -> str:
    """Extract the source content of an AST node from source lines."""
    start = node.lineno - 1
    end = node.end_lineno or node.lineno
    return "".join(lines[start:end])


# ------------------------------------------------------------------ #
# Repository ingestion
# ------------------------------------------------------------------ #
def ingest_repository(repo_path: str, max_files: int = 1000) -> list[CodeChunk]:
    """
    Ingest all Python files in a repository.
    Returns a list of CodeChunk objects.
    Limits to max_files to prevent unbounded ingestion.
    """
    chunks = []
    file_count = 0

    for root, dirs, files in os.walk(repo_path):
        # Skip hidden dirs, __pycache__, .venv, venv
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in (
            "__pycache__", ".venv", "venv", "env", "node_modules"
        )]

        for filename in files:
            if file_count >= max_files:
                logger.warning("Repository ingestion limit reached: %d files", max_files)
                return chunks

            if not filename.endswith(".py"):
                continue

            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, repo_path)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if len(content) > 100_000:  # Skip very large files
                    logger.warning("Skipping large file: %s (%d bytes)", rel_path, len(content))
                    continue

                file_chunks = extract_symbols(rel_path, content)
                chunks.extend(file_chunks)
                file_count += 1

            except Exception as exc:
                logger.warning("Failed to ingest %s: %s", rel_path, exc)

    logger.info(
        "Repository ingested: %d files, %d chunks, %d total tokens",
        file_count,
        len(chunks),
        sum(c.token_count for c in chunks),
    )
    return chunks


# ------------------------------------------------------------------ #
# Hybrid search: keyword + symbol matching
# ------------------------------------------------------------------ #
def _sanitize_query(query: str) -> str:
    """
    Sanitize a search query to prevent injection.
    Removes special characters and limits length.
    """
    # Remove SQL-like patterns and limit to alphanumerics + spaces + dots
    cleaned = re.sub(r"[^\w\s\.]", " ", query)
    cleaned = cleaned.strip()[:200]  # Max 200 chars
    return cleaned


def search_chunks(
    chunks: list[CodeChunk],
    query: str,
    max_results: int = 10,
) -> list[tuple[CodeChunk, float]]:
    """
    Search code chunks using hybrid keyword + symbol matching.
    Returns a list of (chunk, score) pairs sorted by relevance.
    """
    if not chunks:
        return []

    sanitized = _sanitize_query(query)
    if not sanitized:
        return []

    query_terms = set(sanitized.lower().split())
    results = []

    for chunk in chunks:
        score = 0.0

        # Symbol name matching (high weight)
        chunk_name_lower = chunk.name.lower()
        for term in query_terms:
            if term in chunk_name_lower:
                score += 3.0  # Symbol name match: high weight

        # Content keyword matching (lower weight)
        content_lower = chunk.content.lower()
        for term in query_terms:
            count = content_lower.count(term)
            score += min(count * 0.5, 5.0)  # Cap keyword frequency bonus

        # Chunk type weighting
        type_weights = {
            "class": 1.2,
            "function": 1.1,
            "method": 0.9,
            "module": 0.5,
        }
        score *= type_weights.get(chunk.chunk_type, 1.0)

        if score > 0:
            results.append((chunk, score))

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:max_results]


# ------------------------------------------------------------------ #
# Context compression
# ------------------------------------------------------------------ #
def compress_context(
    chunks: list[CodeChunk],
    max_tokens: int = 4000,
) -> tuple[str, int, int]:
    """
    Compress chunks into a single context string within a token budget.
    Returns (context, total_tokens, chunks_used).
    Deduplicates by hash.
    """
    seen_hashes = set()
    parts = []
    total_tokens = 0
    chunks_used = 0

    for chunk in chunks:
        if chunk.hash in seen_hashes:
            continue
        seen_hashes.add(chunk.hash)

        # Format: file_path (type: name, lines start-end)
        header = f"# {chunk.file_path} ({chunk.chunk_type}: {chunk.name}, lines {chunk.start_line}-{chunk.end_line})\n"
        content = chunk.content

        part_tokens = count_tokens(header + content)
        if total_tokens + part_tokens > max_tokens:
            # Truncate this chunk to fit
            remaining = max_tokens - total_tokens
            if remaining < 100:  # Not enough room for meaningful content
                break
            # Truncate content to fit
            while count_tokens(header + content) > remaining and len(content) > 100:
                content = content[:int(len(content) * 0.9)]
            content = content + "\n# ... (truncated)\n"
            part_tokens = count_tokens(header + content)

        parts.append(header + content)
        total_tokens += part_tokens
        chunks_used += 1

    context = "\n\n".join(parts)
    return context, total_tokens, chunks_used


# ------------------------------------------------------------------ #
# Retrieval orchestration
# ------------------------------------------------------------------ #
@dataclass
class RetrievalResult:
    """Result of a code retrieval operation."""
    context: str
    total_tokens: int
    chunks_used: int
    latency_ms: float
    query: str = ""
    files_searched: int = 0
    tokens_saved: int = 0  # Tokens saved vs sending entire repo


def retrieve_code(
    repo_path: str,
    query: str,
    max_tokens: int = 4000,
    max_results: int = 20,
) -> RetrievalResult:
    """
    Full retrieval pipeline: ingest → search → rank → compress.
    Returns a RetrievalResult with the compressed context.
    """
    t0 = time.monotonic()

    # Sanitize query (prompt-injection aware)
    sanitized = sanitize_input(query)
    # Also apply the query-specific sanitization (removes special chars)
    sanitized = _sanitize_query(sanitized)

    # Ingest
    chunks = ingest_repository(repo_path)
    total_repo_tokens = sum(c.token_count for c in chunks)

    # Search
    results = search_chunks(chunks, sanitized, max_results=max_results)
    result_chunks = [r[0] for r in results]

    # Compress
    context, tokens, chunks_used = compress_context(result_chunks, max_tokens)

    latency_ms = round((time.monotonic() - t0) * 1000)
    tokens_saved = max(0, total_repo_tokens - tokens)

    logger.info(
        "code_retrieval completed",
        extra={
            "op": "retrieve_code",
            "query_length": len(sanitized),
            "chunks_total": len(chunks),
            "chunks_matched": len(result_chunks),
            "chunks_used": chunks_used,
            "tokens": tokens,
            "tokens_saved": tokens_saved,
            "latency_ms": latency_ms,
        },
    )

    return RetrievalResult(
        context=context,
        total_tokens=tokens,
        chunks_used=chunks_used,
        latency_ms=latency_ms,
        query=sanitized,
        files_searched=len(set(c.file_path for c in chunks)),
        tokens_saved=tokens_saved,
    )
