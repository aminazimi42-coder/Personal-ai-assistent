"""
services/context_compiler.py
Context Compiler — compile inspectable context from memories, code/docs,
tasks, and project data with provenance, relevance, token budgets, and
selection explanations.

Design:
- Correctness first: all potentially-relevant context is gathered before
  selection so the compiler can make informed inclusion decisions.
- Minimum Sufficient Context second: rank by relevance, include entries
  until the token budget is exhausted, and record *why* each entry was
  selected (or excluded) so the result is auditable/inspectable.
- Unified Knowledge Layer: every source shares the same security boundary
  (user_id) — no cross-user / cross-tenant retrieval is ever performed.
- Provenance: each entry records source_type, source_id, and how it was
  retrieved so downstream consumers can trace any piece of context.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Data structures
# ------------------------------------------------------------------ #

@dataclass
class ContextEntry:
    """A single compiled context entry with full provenance."""
    source_type: str               # 'memory' | 'task' | 'code' | 'project'
    source_id: str                 # stable identifier within the source
    content: str                   # the actual context text
    relevance_score: float = 0.0   # higher = more relevant
    provenance: str = ""           # human-readable description of origin
    token_count: int = 0           # tokens occupied by this entry
    selected: bool = False          # was this entry included in the budget?
    reason: str = ""                # why it was selected or excluded

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "content": self.content,
            "relevance_score": self.relevance_score,
            "provenance": self.provenance,
            "token_count": self.token_count,
            "selected": self.selected,
            "reason": self.reason,
        }


@dataclass
class ContextCompilation:
    """The full result of a context compilation pass."""
    entries: list[ContextEntry] = field(default_factory=list)
    total_tokens: int = 0          # tokens of *selected* entries
    budget: int = 0                 # the token budget that was requested
    compression_applied: bool = False  # did we truncate any entry?
    explanation: str = ""           # human-readable summary of selection logic
    latency_ms: float = 0.0
    query: str = ""

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "total_tokens": self.total_tokens,
            "budget": self.budget,
            "compression_applied": self.compression_applied,
            "explanation": self.explanation,
            "latency_ms": self.latency_ms,
            "query": self.query,
            "entry_count": len(self.entries),
            "selected_count": sum(1 for e in self.entries if e.selected),
        }


# ------------------------------------------------------------------ #
# Token counting (delegates to code_retrieval for consistency)
# ------------------------------------------------------------------ #

def _count_tokens(text: str) -> int:
    """Count tokens using the same mechanism as code_retrieval."""
    if not text:
        return 0
    try:
        from services.code_retrieval import count_tokens
        return count_tokens(text)
    except Exception:
        # Heuristic fallback: ~4 chars per token
        return max(1, len(text) // 4)


# ------------------------------------------------------------------ #
# Source gatherers — each returns a list[ContextEntry] (all unselected)
# ------------------------------------------------------------------ #

def _gather_memories(user_id: int, query: str, get_connection_fn) -> list[ContextEntry]:
    """Gather memory entries matching the query (user-scoped)."""
    entries: list[ContextEntry] = []
    try:
        from services.memory_engine import search_memories
        mems = search_memories(user_id, query, limit=20, get_connection_fn=get_connection_fn)
        for mem in mems:
            content = f"[Memory:{mem.memory_type}] {mem.key}: {mem.value}"
            entries.append(ContextEntry(
                source_type="memory",
                source_id=f"memory:{mem.memory_type}:{mem.key}",
                content=content,
                relevance_score=mem.relevance_score,
                provenance=f"memory_engine.search_memories(user_id={user_id}, type={mem.memory_type})",
                token_count=_count_tokens(content),
                reason="Matched user memory via keyword search",
            ))
    except Exception as exc:
        logger.warning("Context compiler: memory gather failed: %s", exc)
    return entries


def _gather_tasks(user_id: int, query: str, get_connection_fn) -> list[ContextEntry]:
    """Gather task entries matching the query (user-scoped)."""
    entries: list[ContextEntry] = []
    if not get_connection_fn:
        return entries
    try:
        from psycopg2.extras import RealDictCursor
        from db.pool import return_connection
        conn = get_connection_fn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT id, title, description, status, priority, user_id
                FROM tasks
                WHERE user_id = %s
                  AND (title ILIKE %s OR description ILIKE %s)
                ORDER BY id DESC
                LIMIT 20
            """, (user_id, f"%{query}%", f"%{query}%"))
            rows = cur.fetchall()
        finally:
            cur.close()
            return_connection(conn)

        for row in rows:
            content = f"[Task] {row['title']} — {row.get('description', '')} (status={row.get('status')}, priority={row.get('priority')})"
            entries.append(ContextEntry(
                source_type="task",
                source_id=f"task:{row['id']}",
                content=content,
                relevance_score=0.7,
                provenance=f"tasks table WHERE user_id={user_id} (ILIKE query)",
                token_count=_count_tokens(content),
                reason="Matched user task via keyword search",
            ))
    except Exception as exc:
        logger.warning("Context compiler: task gather failed: %s", exc)
    return entries


def _gather_code(user_id: int, query: str, get_connection_fn) -> list[ContextEntry]:
    """Gather code entries matching the query (repo-scoped; no cross-user)."""
    entries: list[ContextEntry] = []
    try:
        from services.code_retrieval import retrieve_code
        # Code retrieval is repo-scoped, not user-scoped. In production a
        # workspace-to-repo mapping would be consulted. We pass a sensible
        # default and rely on the caller / production wiring to set it.
        result = retrieve_code(".", query, max_tokens=2000, max_results=10)
        if result.context:
            content = result.context
            entries.append(ContextEntry(
                source_type="code",
                source_id="code:repo:current",
                content=content,
                relevance_score=0.6,
                provenance="code_retrieval.retrieve_code(repo=.) — repo-scoped, no cross-user",
                token_count=result.total_tokens,
                reason="Matched code symbols via hybrid keyword+symbol search",
            ))
    except Exception as exc:
        logger.warning("Context compiler: code gather failed: %s", exc)
    return entries


def _gather_projects(user_id: int, query: str, get_connection_fn) -> list[ContextEntry]:
    """Gather workspace/project entries (user-scoped)."""
    entries: list[ContextEntry] = []
    try:
        from services.workspace import list_workspaces, list_projects
        workspaces = list_workspaces(user_id)
        for ws in workspaces:
            ws_id = ws.id or 0
            ws_content = f"[Workspace] {ws.name}: {ws.description}"
            entries.append(ContextEntry(
                source_type="project",
                source_id=f"workspace:{ws.id}",
                content=ws_content,
                relevance_score=0.5,
                provenance=f"workspace.list_workspaces(user_id={user_id})",
                token_count=_count_tokens(ws_content),
                reason="User workspace context",
            ))
            projects = list_projects(ws_id, user_id)
            for proj in projects:
                proj_content = f"[Project] {proj.name}: {proj.description}"
                entries.append(ContextEntry(
                    source_type="project",
                    source_id=f"project:{proj.id}",
                    content=proj_content,
                    relevance_score=0.55,
                    provenance=f"workspace.list_projects(ws={ws.id}, user_id={user_id})",
                    token_count=_count_tokens(proj_content),
                    reason="User project context",
                ))
    except Exception as exc:
        logger.warning("Context compiler: project gather failed: %s", exc)
    return entries


# ------------------------------------------------------------------ #
# Main compilation entry point
# ------------------------------------------------------------------ #

def compile_context(
    user_id: int,
    query: str,
    max_tokens: int = 4000,
    get_connection_fn: Optional[Callable] = None,
) -> ContextCompilation:
    """
    Compile inspectable context from memories, tasks, code, and projects.

    Args:
        user_id: The user requesting context (enforced isolation boundary).
        query: Natural-language query to rank relevance.
        max_tokens: Token budget for *selected* entries.
        get_connection_fn: DB connection provider (optional; falls back to
                           in-memory stores where available).

    Returns:
        ContextCompilation with all gathered entries (selected=True/False),
        total token count of selected entries, compression flag, and a
        human-readable explanation of the selection logic.
    """
    t0 = time.monotonic()

    if not query or not query.strip():
        return ContextCompilation(
            entries=[],
            total_tokens=0,
            budget=max_tokens,
            compression_applied=False,
            explanation="Empty query — no context compiled.",
            latency_ms=0.0,
            query=query or "",
        )

    # ------------------------------------------------------------------ #
    # 1. Gather from all sources (correctness first — gather everything)
    # ------------------------------------------------------------------ #
    all_entries: list[ContextEntry] = []
    all_entries.extend(_gather_memories(user_id, query, get_connection_fn))
    all_entries.extend(_gather_tasks(user_id, query, get_connection_fn))
    all_entries.extend(_gather_code(user_id, query, get_connection_fn))
    all_entries.extend(_gather_projects(user_id, query, get_connection_fn))

    # ------------------------------------------------------------------ #
    # 2. Rank by relevance (Minimum Sufficient Context)
    # ------------------------------------------------------------------ #
    all_entries.sort(key=lambda e: e.relevance_score, reverse=True)

    # ------------------------------------------------------------------ #
    # 3. Select entries within token budget
    # ------------------------------------------------------------------ #
    compression_applied = False
    total_tokens = 0
    selected_count = 0
    excluded_count = 0

    for entry in all_entries:
        if total_tokens + entry.token_count <= max_tokens:
            entry.selected = True
            total_tokens += entry.token_count
            selected_count += 1
        else:
            # Try to truncate-fit if the entry is large but highly relevant
            remaining = max_tokens - total_tokens
            if remaining >= 100 and entry.relevance_score >= 0.8:
                # Truncate content to fit remaining budget (conservative estimate)
                target_chars = remaining * 3  # conservative: ~3 chars per token
                if target_chars < len(entry.content):
                    entry.content = entry.content[:target_chars] + "\n… (truncated)"
                    entry.token_count = _count_tokens(entry.content)
                    # Final check: if still over budget, hard-truncate
                    while entry.token_count > remaining and len(entry.content) > 50:
                        entry.content = entry.content[:int(len(entry.content) * 0.8)]
                    entry.content = entry.content + "\n… (truncated)"
                    entry.token_count = _count_tokens(entry.content)
                    entry.selected = True
                    entry.reason = (entry.reason or "") + " [truncated to fit budget]"
                    total_tokens += entry.token_count
                    selected_count += 1
                    compression_applied = True
                    continue
            entry.selected = False
            entry.reason = (entry.reason or "") + f" [excluded: would exceed token budget ({entry.token_count} > {remaining} remaining)]"
            excluded_count += 1

    # ------------------------------------------------------------------ #
    # 4. Build explanation (inspectable selection rationale)
    # ------------------------------------------------------------------ #
    source_counts: dict[str, int] = {}
    for e in all_entries:
        if e.selected:
            source_counts[e.source_type] = source_counts.get(e.source_type, 0) + 1

    explanation_parts = [
        f"Compiled {len(all_entries)} entries from {len(set(e.source_type for e in all_entries))} source types.",
        f"Selected {selected_count} entries ({total_tokens} tokens within {max_tokens}-token budget).",
        f"Excluded {excluded_count} entries due to budget constraints.",
    ]
    if source_counts:
        breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(source_counts.items()))
        explanation_parts.append(f"Selected by source — {breakdown}.")
    if compression_applied:
        explanation_parts.append("Compression applied: at least one high-relevance entry was truncated to fit the budget.")
    explanation_parts.append(
        "Selection policy: entries ranked by relevance_score (descending); "
        "included greedily until token budget exhausted; high-relevance "
        "entries (>=0.8) eligible for truncation-fit."
    )

    latency_ms = round((time.monotonic() - t0) * 1000)

    compilation = ContextCompilation(
        entries=all_entries,
        total_tokens=total_tokens,
        budget=max_tokens,
        compression_applied=compression_applied,
        explanation=" ".join(explanation_parts),
        latency_ms=latency_ms,
        query=query,
    )

    logger.info(
        "context_compiled user=%d entries=%d selected=%d tokens=%d budget=%d latency_ms=%d",
        user_id, len(all_entries), selected_count, total_tokens, max_tokens, latency_ms,
    )

    return compilation
