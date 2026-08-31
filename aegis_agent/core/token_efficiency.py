from __future__ import annotations

import ast
import hashlib
import json
from typing import Any


class TokenEfficiencyEngine:
    """Optimizes context payloads through AST normalization and repeated-response caching."""

    def __init__(self, max_cache_entries: int = 512) -> None:
        self.max_cache_entries = max_cache_entries
        self.cache: dict[str, dict[str, Any]] = {}

    def compress_ast(self, source: str) -> str:
        text = (source or "").strip()
        if not text:
            return ""

        try:
            parsed = ast.parse(text)
            return ast.unparse(parsed).strip()
        except SyntaxError:
            return " ".join(text.split())

    def build_cache_key(self, payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def optimize_prompt(self, prompt: str) -> dict[str, Any]:
        original = prompt or ""
        compressed = self.compress_ast(original)
        key = self.build_cache_key({"prompt": compressed})

        hit = key in self.cache
        if hit:
            cached = self.cache[key]
            cached["hits"] = int(cached.get("hits", 0)) + 1
            return {
                "success": True,
                "cache_hit": True,
                "original_tokens": len(original.split()),
                "compressed_tokens": len(compressed.split()),
                "compression_ratio": round((1 - (len(compressed) / max(len(original), 1))) if original else 0.0, 4),
                "cached_result": cached,
            }

        result = {
            "prompt": compressed,
            "token_count": len(compressed.split()),
            "hits": 1,
        }

        if len(self.cache) >= self.max_cache_entries:
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = result

        return {
            "success": True,
            "cache_hit": False,
            "original_tokens": len(original.split()),
            "compressed_tokens": len(compressed.split()),
            "compression_ratio": round((1 - (len(compressed) / max(len(original), 1))) if original else 0.0, 4),
            "cached_result": result,
        }

    def compute_cache_hit_rate(self) -> float:
        if not self.cache:
            return 0.0

        total_hits = sum(int(item.get("hits", 0)) for item in self.cache.values())
        return round(total_hits / max(len(self.cache), 1), 4)
