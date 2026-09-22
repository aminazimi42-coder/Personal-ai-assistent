"""
tests/test_external_api.py
Tests for external API reliability: timeouts, retries, graceful degradation.
"""

import pytest
from unittest.mock import MagicMock, patch, call
import requests as req
from services.external_api import (
    fetch_exchange_rates,
    _request_with_retry,
    _redact_url,
    ExternalAPIError,
    _is_retryable,
)


def test_redact_url_hides_query_params():
    """URL query params should be redacted in logs."""
    url = "https://api.example.com/data?api_key=secret123&foo=bar"
    redacted = _redact_url(url)
    assert "secret123" not in redacted
    assert "foo=bar" not in redacted
    assert "[redacted]" in redacted


def test_redact_url_no_query_params():
    """URLs without query params should pass through."""
    url = "https://api.example.com/data"
    assert _redact_url(url) == url


def test_is_retryable_status_codes():
    assert _is_retryable(429) is True
    assert _is_retryable(500) is True
    assert _is_retryable(503) is True
    assert _is_retryable(504) is True
    assert _is_retryable(200) is False
    assert _is_retryable(404) is False
    assert _is_retryable(400) is False


def test_fetch_exchange_rates_success(mocker):
    """Successful exchange rate fetch returns data."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "base": "USD",
        "date": "2026-01-01",
        "rates": {"EUR": 0.9},
    }
    mocker.patch("services.external_api.requests.request", return_value=mock_response)

    data = fetch_exchange_rates()
    assert data["base"] == "USD"
    assert data["date"] == "2026-01-01"
    assert "EUR" in data["rates"]


def test_fetch_exchange_rates_502_no_retry(mocker):
    """Non-retryable status should raise immediately."""
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 404
    mocker.patch("services.external_api.requests.request", return_value=mock_response)
    mocker.patch("services.external_api.time.sleep")  # no real sleep

    with pytest.raises(ExternalAPIError):
        fetch_exchange_rates()


def test_fetch_exchange_rates_retry_on_502(mocker):
    """502 should trigger retry, then succeed."""
    fail_response = MagicMock()
    fail_response.ok = False
    fail_response.status_code = 502

    ok_response = MagicMock()
    ok_response.ok = True
    ok_response.status_code = 200
    ok_response.json.return_value = {"base": "USD", "date": "2026-01-01", "rates": {}}

    mocker.patch(
        "services.external_api.requests.request",
        side_effect=[fail_response, ok_response],
    )
    mocker.patch("services.external_api.time.sleep")

    data = fetch_exchange_rates(max_retries=2)
    assert data["base"] == "USD"


def test_fetch_exchange_rates_timeout_retry(mocker):
    """Timeout should trigger retry."""
    ok_response = MagicMock()
    ok_response.ok = True
    ok_response.status_code = 200
    ok_response.json.return_value = {"base": "USD", "date": "2026-01-01", "rates": {}}

    mocker.patch(
        "services.external_api.requests.request",
        side_effect=[req.exceptions.Timeout("timeout"), ok_response],
    )
    mocker.patch("services.external_api.time.sleep")

    data = fetch_exchange_rates(max_retries=2)
    assert data["base"] == "USD"


def test_fetch_exchange_rates_all_retries_exhausted(mocker):
    """After all retries, ExternalAPIError should be raised."""
    fail_response = MagicMock()
    fail_response.ok = False
    fail_response.status_code = 503

    mocker.patch("services.external_api.requests.request", return_value=fail_response)
    mocker.patch("services.external_api.time.sleep")

    with pytest.raises(ExternalAPIError):
        fetch_exchange_rates(max_retries=2)


def test_fetch_exchange_rates_connection_error_retry(mocker):
    """Connection error should trigger retry."""
    ok_response = MagicMock()
    ok_response.ok = True
    ok_response.status_code = 200
    ok_response.json.return_value = {"base": "USD", "date": "2026-01-01", "rates": {}}

    mocker.patch(
        "services.external_api.requests.request",
        side_effect=[req.exceptions.ConnectionError("conn error"), ok_response],
    )
    mocker.patch("services.external_api.time.sleep")

    data = fetch_exchange_rates(max_retries=2)
    assert data["base"] == "USD"
