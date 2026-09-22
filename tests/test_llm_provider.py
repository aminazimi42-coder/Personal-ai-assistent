"""
tests/test_llm_provider.py
Tests for the provider-neutral LLM boundary.
"""

import pytest
from unittest.mock import MagicMock, patch

from services.llm_provider import (
    LLMError,
    LLMProvider,
    OpenAIProvider,
    register_provider,
    get_provider,
    set_default_provider,
    get_default_provider,
    get_llm_provider,
)


# ------------------------------------------------------------------ #
# Mock OpenAI response helper
# ------------------------------------------------------------------ #

def _make_mock_client(content="Hello!", prompt_tokens=10, completion_tokens=5):
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens
    response.usage = usage
    client.chat.completions.create.return_value = response
    return client


# ------------------------------------------------------------------ #
# Registry tests
# ------------------------------------------------------------------ #

def test_register_and_get_provider():
    """register_provider / get_provider round-trip."""
    provider = OpenAIProvider(client=_make_mock_client(), model="test-model")
    register_provider("test-registry", provider)
    assert get_provider("test-registry") is provider


def test_get_provider_unregistered_raises():
    """Getting an unregistered provider raises LLMError."""
    with pytest.raises(LLMError):
        get_provider("nonexistent-provider-xyz")


def test_set_and_get_default_provider():
    """set_default_provider / get_default_provider."""
    provider = OpenAIProvider(client=_make_mock_client(), model="test-model")
    register_provider("test-default", provider)
    set_default_provider("test-default")
    assert get_default_provider() is provider


def test_get_default_provider_not_registered():
    """Default provider not registered raises LLMError."""
    set_default_provider("nonexistent-xyz")
    with pytest.raises(LLMError):
        get_default_provider()


# ------------------------------------------------------------------ #
# OpenAIProvider chat_completion
# ------------------------------------------------------------------ #

def test_openai_provider_chat_completion_success():
    """OpenAIProvider returns normalized dict with content, usage, model."""
    client = _make_mock_client(content="Hi there!", prompt_tokens=8, completion_tokens=3)
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")
    result = provider.chat_completion(
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=100,
        temperature=0.7,
    )
    assert result["content"] == "Hi there!"
    assert result["model"] == "gpt-4o-mini"
    assert result["usage"]["prompt_tokens"] == 8
    assert result["usage"]["completion_tokens"] == 3
    assert result["usage"]["total_tokens"] == 11


def test_openai_provider_chat_completion_calls_create():
    """Verify the provider calls the underlying client correctly."""
    client = _make_mock_client(content="response text")
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")
    provider.chat_completion(
        messages=[{"role": "user", "content": "test"}],
        max_tokens=256,
        temperature=0.5,
    )
    call_kwargs = client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["max_tokens"] == 256
    assert call_kwargs["temperature"] == 0.5
    assert call_kwargs["messages"] == [{"role": "user", "content": "test"}]


# ------------------------------------------------------------------ #
# Error handling
# ------------------------------------------------------------------ #

def test_openai_provider_chat_completion_api_error():
    """API errors are normalized into LLMError."""
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("API down")
    provider = OpenAIProvider(client=client, model="gpt-4o-mini", max_retries=1, retry_delay=0)
    with pytest.raises(LLMError):
        provider.chat_completion(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
            temperature=0.7,
        )


def test_openai_provider_chat_completion_timeout_error():
    """Timeout errors are normalized into LLMError."""
    client = MagicMock()
    client.chat.completions.create.side_effect = TimeoutError("Request timed out")
    provider = OpenAIProvider(client=client, model="gpt-4o-mini", max_retries=1, retry_delay=0)
    with pytest.raises(LLMError):
        provider.chat_completion(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
            temperature=0.7,
        )


def test_llm_error_preserves_cause():
    """LLMError preserves the original exception as cause."""
    client = MagicMock()
    original = RuntimeError("network failure")
    client.chat.completions.create.side_effect = original
    provider = OpenAIProvider(client=client, model="gpt-4o-mini", max_retries=1, retry_delay=0)
    with pytest.raises(LLMError) as exc_info:
        provider.chat_completion(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
            temperature=0.7,
        )
    assert exc_info.value.cause is original


# ------------------------------------------------------------------ #
# Retry behavior
# ------------------------------------------------------------------ #

def test_openai_provider_retries_on_failure():
    """Provider retries up to max_retries times before raising LLMError."""
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("transient error")
    provider = OpenAIProvider(client=client, model="gpt-4o-mini", max_retries=3, retry_delay=0)
    with pytest.raises(LLMError):
        provider.chat_completion(
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
            temperature=0.7,
        )
    assert client.chat.completions.create.call_count == 3


def test_openai_provider_succeeds_on_retry():
    """Provider succeeds on a later retry attempt."""
    client = MagicMock()
    good_response = MagicMock()
    good_response.choices = [MagicMock()]
    good_response.choices[0].message.content = "Success!"
    usage = MagicMock()
    usage.prompt_tokens = 5
    usage.completion_tokens = 2
    usage.total_tokens = 7
    good_response.usage = usage
    client.chat.completions.create.side_effect = [
        Exception("transient"),
        good_response,
    ]
    provider = OpenAIProvider(client=client, model="gpt-4o-mini", max_retries=2, retry_delay=0)
    result = provider.chat_completion(
        messages=[{"role": "user", "content": "test"}],
        max_tokens=100,
        temperature=0.7,
    )
    assert result["content"] == "Success!"
    assert client.chat.completions.create.call_count == 2


# ------------------------------------------------------------------ #
# Cost metadata / telemetry
# ------------------------------------------------------------------ #

def test_openai_provider_returns_cost_metadata():
    """chat_completion result includes model and token usage."""
    client = _make_mock_client(content="test", prompt_tokens=20, completion_tokens=10)
    provider = OpenAIProvider(client=client, model="gpt-4o-mini")
    result = provider.chat_completion(
        messages=[{"role": "user", "content": "test"}],
        max_tokens=100,
        temperature=0.7,
    )
    assert "model" in result
    assert "usage" in result
    assert result["usage"]["prompt_tokens"] == 20
    assert result["usage"]["completion_tokens"] == 10
    assert result["usage"]["total_tokens"] == 30


# ------------------------------------------------------------------ #
# Transcription
# ------------------------------------------------------------------ #

def test_openai_provider_transcribe_not_supported_by_base():
    """Base LLMProvider.transcribe raises LLMError."""
    class DummyProvider(LLMProvider):
        def chat_completion(self, messages, max_tokens, temperature):
            return {"content": "", "usage": {}, "model": "dummy"}
    dp = DummyProvider()
    with pytest.raises(LLMError):
        dp.transcribe("/tmp/test.wav")


# ------------------------------------------------------------------ #
# ai_service integration — uses provider, not direct OpenAI
# ------------------------------------------------------------------ #

def test_ai_service_uses_provider(mocker):
    """generate_ai_reply goes through get_llm() provider, not direct client."""
    mock_provider = MagicMock()
    mock_provider.chat_completion.return_value = {
        "content": "Hello from provider!",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": "gpt-4o-mini",
    }
    mocker.patch("services.ai_service.get_llm", return_value=mock_provider)

    from services.ai_service import generate_ai_reply
    result = generate_ai_reply("Hi")
    assert "Hello from provider!" in result
    mock_provider.chat_completion.assert_called_once()


def test_ai_service_provider_error_falls_back(mocker):
    """When the provider raises LLMError, ai_service returns a safe fallback."""
    mock_provider = MagicMock()
    mock_provider.chat_completion.side_effect = LLMError("provider down")
    mocker.patch("services.ai_service.get_llm", return_value=mock_provider)

    from services.ai_service import generate_ai_reply
    result = generate_ai_reply("Hi")
    assert isinstance(result, str)
    assert len(result) > 0


def test_ai_service_decide_smart_action_uses_provider(mocker):
    """decide_smart_action goes through the provider."""
    mock_provider = MagicMock()
    mock_provider.chat_completion.return_value = {
        "content": '{"action":"task","title":"Test","description":"Desc","priority":"high","status":"pending","due_date":null,"reply":""}',
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "model": "gpt-4o-mini",
    }
    mocker.patch("services.ai_service.get_llm", return_value=mock_provider)

    from services.ai_service import decide_smart_action
    result = decide_smart_action("Create a test task")
    assert result["action"] == "task"
    assert result["title"] == "Test"
    mock_provider.chat_completion.assert_called_once()


def test_ai_service_extract_task_uses_provider(mocker):
    """extract_task_from_message goes through the provider."""
    mock_provider = MagicMock()
    mock_provider.chat_completion.return_value = {
        "content": '{"title":"Buy milk","description":"Get milk","priority":"medium","status":"pending","due_date":null}',
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "model": "gpt-4o-mini",
    }
    mocker.patch("services.ai_service.get_llm", return_value=mock_provider)

    from services.ai_service import extract_task_from_message
    result = extract_task_from_message("Buy milk")
    assert result["title"] == "Buy milk"
    assert result["priority"] == "medium"
    mock_provider.chat_completion.assert_called_once()
