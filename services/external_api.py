"""
services/external_api.py
Centralized external API integration layer.

All external HTTP calls go through here for:
  - Deliberate timeouts
  - Bounded safe retries (only on transient failures)
  - Graceful degradation (safe fallbacks, never crash)
  - Structured logs (no secrets logged)
  - Secret protection (API keys never in URLs or logs)
"""

import logging
import time
from typing import Any

import requests

from config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Retry configuration
# ------------------------------------------------------------------ #
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 0.5  # exponential: 0.5, 1.0, 2.0
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
DEFAULT_TIMEOUT = 10  # seconds


class ExternalAPIError(Exception):
    """Raised when an external API call fails after retries."""


def _is_retryable(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


def _request_with_retry(
    method: str,
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    **kwargs,
) -> requests.Response:
    """
    Execute an HTTP request with bounded retries on transient failures.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Full URL (must not contain secrets)
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts (0 = no retry)
        **kwargs: Passed to requests.request()

    Returns:
        requests.Response on success (2xx)

    Raises:
        ExternalAPIError on permanent failure or after all retries exhausted
    """
    last_exc = None
    last_response = None

    for attempt in range(max_retries + 1):
        t0 = time.monotonic()
        try:
            response = requests.request(
                method, url, timeout=timeout, **kwargs
            )
            logger.info(
                "external_api request completed",
                extra={
                    "url": _redact_url(url),
                    "method": method,
                    "status": response.status_code,
                    "attempt": attempt + 1,
                    "duration_ms": round((time.monotonic() - t0) * 1000),
                },
            )

            # Success — return response
            if response.ok:
                return response

            # Retryable status code — retry
            if _is_retryable(response.status_code) and attempt < max_retries:
                backoff = RETRY_BACKOFF_SECONDS * (2 ** attempt)
                logger.warning(
                    "external_api retryable status %d, retrying in %.1fs (attempt %d/%d)",
                    response.status_code, backoff, attempt + 1, max_retries,
                    extra={"url": _redact_url(url), "method": method},
                )
                last_response = response
                time.sleep(backoff)
                continue

            # Non-retryable failure — raise immediately
            raise ExternalAPIError(
                f"External API returned {response.status_code}"
            )

        except requests.exceptions.Timeout as exc:
            last_exc = exc
            if attempt < max_retries:
                backoff = RETRY_BACKOFF_SECONDS * (2 ** attempt)
                logger.warning(
                    "external_api timeout, retrying in %.1fs (attempt %d/%d)",
                    backoff, attempt + 1, max_retries,
                    extra={"url": _redact_url(url), "method": method},
                )
                time.sleep(backoff)
                continue
            raise ExternalAPIError("External API timed out") from exc

        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            if attempt < max_retries:
                backoff = RETRY_BACKOFF_SECONDS * (2 ** attempt)
                logger.warning(
                    "external_api connection error, retrying in %.1fs (attempt %d/%d)",
                    backoff, attempt + 1, max_retries,
                    extra={"url": _redact_url(url), "method": method},
                )
                time.sleep(backoff)
                continue
            raise ExternalAPIError("External API connection failed") from exc

        except ExternalAPIError:
            raise
        except Exception as exc:
            # Unexpected error — don't retry
            logger.error("external_api unexpected error: %s", exc, exc_info=True)
            raise ExternalAPIError("External API unexpected error") from exc

    # Should not reach here, but just in case
    raise ExternalAPIError(
        f"External API failed after {max_retries} retries"
    ) from last_exc


def _redact_url(url: str) -> str:
    """Remove any query params that might contain secrets from logged URLs."""
    if "?" in url:
        return url.split("?")[0] + "?[redacted]"
    return url


# ------------------------------------------------------------------ #
# Specific API integrations
# ------------------------------------------------------------------ #

def fetch_exchange_rates(
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> dict:
    """
    Fetch USD exchange rates from Frankfurter API.

    Returns dict with 'base', 'date', 'rates' keys.
    Raises ExternalAPIError on failure.
    """
    url = (
        "https://api.frankfurter.app/latest"
        "?from=USD&to=EUR,GBP,CAD,AUD,JPY,TRY,AED"
    )
    response = _request_with_retry(
        "GET", url, timeout=timeout, max_retries=max_retries
    )
    data = response.json()
    return {
        "base": data.get("base", "USD"),
        "date": data.get("date"),
        "rates": data.get("rates", {}),
    }
