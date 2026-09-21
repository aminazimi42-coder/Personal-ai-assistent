"""
services/ai_service.py
Centralized AI orchestration layer.
- Single OpenAI client
- Explicit timeouts and token budgets
- Structured output validation
- Eliminate double-LLM-call for smart-ai
- Safe error handling — never expose SDK internals
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

from openai import OpenAI

from config import settings

logger = logging.getLogger(__name__)

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"pending", "done"}

# ------------------------------------------------------------------ #
# OpenAI client (singleton per process)
# ------------------------------------------------------------------ #
_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.AI_REQUEST_TIMEOUT,
        )
    return _client


def get_chat_model() -> str:
    return settings.OPENAI_CHAT_MODEL


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _normalize_priority(priority) -> str:
    v = str(priority or "medium").strip().lower()
    return v if v in VALID_PRIORITIES else "medium"


def _normalize_status(status) -> str:
    v = str(status or "pending").strip().lower()
    return v if v in VALID_STATUSES else "pending"


def _normalize_due_date(due_date):
    if due_date in (None, "", "null"):
        return None
    if isinstance(due_date, str):
        cleaned = due_date.strip()
        return cleaned if cleaned else None
    return None


def _clean_text(text: str | None) -> str:
    if not text:
        return "Sorry, I could not generate a response."
    return (
        str(text)
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "")
        .strip()
    )


def _extract_json(text: str | None) -> dict | None:
    """Extract the first valid JSON object from text."""
    if not text:
        return None
    text = str(text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except Exception:
                    return None
    return None


def _get_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _language_instruction() -> str:
    return (
        "Detect the user's language from their message and always reply in "
        "the same language."
    )


# ------------------------------------------------------------------ #
# AI functions
# ------------------------------------------------------------------ #

def generate_ai_reply(user_message: str) -> str:
    """Generate a conversational AI reply. Returns safe fallback on any error."""
    t0 = time.monotonic()
    try:
        client = get_openai_client()
        model = get_chat_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful, friendly AI assistant for productivity. "
                        "Be clear, concise, and natural. "
                        f"{_language_instruction()}"
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            max_tokens=settings.AI_MAX_TOKENS,
            temperature=0.7,
        )
        usage = getattr(response, "usage", None)
        logger.info(
            "ai_reply completed",
            extra={
                "op": "generate_ai_reply",
                "model": model,
                "duration_ms": round((time.monotonic() - t0) * 1000),
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            },
        )
        raw = response.choices[0].message.content if response.choices else None
        return _clean_text(raw)
    except Exception:
        logger.error(
            "generate_ai_reply failed",
            extra={"op": "generate_ai_reply", "duration_ms": round((time.monotonic() - t0) * 1000)},
            exc_info=True,
        )
        return "I'm unable to respond right now. Please try again."


def extract_task_from_message(user_message: str) -> dict:
    """
    Extract a structured task from a natural language message.
    Returns a validated task dict. Falls back to a simple task on parse failure.
    """
    try:
        client = get_openai_client()
        prompt = (
            f"Current UTC datetime: {_get_utc_now()}\n"
            f"{_language_instruction()}\n\n"
            "Extract ONE actionable task. Return ONLY valid JSON:\n"
            '{"title":"","description":"","priority":"low|medium|high",'
            '"status":"pending","due_date":"ISO8601 or null"}\n'
            "Rules: title ≤80 chars; description ≤500 chars; "
            "convert relative dates to absolute ISO8601; null if no date.\n\n"
            f"User: {user_message}"
        )
        response = client.chat.completions.create(
            model=get_chat_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.AI_MAX_TOKENS_EXTRACTION,
            temperature=0.1,
        )
        raw = response.choices[0].message.content if response.choices else None
        parsed = _extract_json(_clean_text(raw))

        if not parsed:
            raise ValueError("No JSON in AI response")

        return {
            "title": str(parsed.get("title") or user_message)[:80],
            "description": str(parsed.get("description") or user_message)[:500],
            "priority": _normalize_priority(parsed.get("priority")),
            "status": "pending",
            "due_date": _normalize_due_date(parsed.get("due_date")),
        }
    except Exception:
        logger.warning("extract_task_from_message fallback", exc_info=True)
        return {
            "title": user_message[:80],
            "description": user_message[:500],
            "priority": "medium",
            "status": "pending",
            "due_date": None,
        }


def decide_smart_action(user_message: str) -> dict:
    """
    Decide whether to reply conversationally or create a task.
    Uses a SINGLE LLM call — eliminates the prior double-call pattern.
    """
    t0 = time.monotonic()
    try:
        client = get_openai_client()
        model = get_chat_model()
        prompt = (
            f"Current UTC datetime: {_get_utc_now()}\n"
            f"{_language_instruction()}\n\n"
            "You are a smart assistant. For each user message:\n"
            '- If the user wants to remember/schedule something → action="task"\n'
            '- Otherwise → action="reply"\n\n'
            "Return ONLY valid JSON:\n"
            '{"action":"task|reply","title":"","description":"",'
            '"priority":"low|medium|high","status":"pending",'
            '"due_date":"ISO8601 or null","reply":""}\n\n'
            "Rules: title ≤80 chars; description ≤500 chars; "
            "reply must be natural and helpful; do not over-create tasks.\n\n"
            f"User: {user_message}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.AI_MAX_TOKENS_EXTRACTION,
            temperature=0.2,
        )
        usage = getattr(response, "usage", None)
        logger.info(
            "smart_action completed",
            extra={
                "op": "decide_smart_action",
                "model": model,
                "duration_ms": round((time.monotonic() - t0) * 1000),
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            },
        )
        raw = response.choices[0].message.content if response.choices else None
        parsed = _extract_json(_clean_text(raw))

        if not parsed or parsed.get("action") not in ("task", "reply"):
            raise ValueError("Invalid AI decision output")

        if parsed["action"] == "task":
            return {
                "action": "task",
                "title": str(parsed.get("title") or user_message)[:80],
                "description": str(parsed.get("description") or user_message)[:500],
                "priority": _normalize_priority(parsed.get("priority")),
                "status": "pending",
                "due_date": _normalize_due_date(parsed.get("due_date")),
                "reply": "",
            }

        reply_text = str(parsed.get("reply") or "").strip()
        if not reply_text:
            reply_text = generate_ai_reply(user_message)

        return {
            "action": "reply",
            "title": "",
            "description": "",
            "priority": "medium",
            "status": "pending",
            "due_date": None,
            "reply": reply_text,
        }

    except Exception:
        logger.error(
            "decide_smart_action failed",
            extra={"op": "decide_smart_action", "duration_ms": round((time.monotonic() - t0) * 1000)},
            exc_info=True,
        )
        # Safe fallback: return a reply action without another API call
        return {
            "action": "reply",
            "title": "",
            "description": "",
            "priority": "medium",
            "status": "pending",
            "due_date": None,
            "reply": "I'm unable to process that right now. Please try again.",
        }
