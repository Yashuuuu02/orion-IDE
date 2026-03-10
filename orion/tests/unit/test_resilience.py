import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from orion.core.resilience import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    retry_with_backoff,
    RETRY_MAX_ATTEMPTS
)
from orion.llm.config import config_builder
from orion.schemas.settings import ProviderConfig

@pytest.fixture
def test_circuit():
    return CircuitBreaker("test", threshold=2, window_seconds=10)

async def success_coro():
    return "ok"

async def fail_coro():
    raise ValueError("fail")

@pytest.mark.asyncio
async def test_circuit_starts_closed(test_circuit):
    assert test_circuit.state == CircuitState.CLOSED

@pytest.mark.asyncio
async def test_circuit_opens_after_threshold(test_circuit):
    with pytest.raises(ValueError):
        await test_circuit.call(fail_coro())
    assert test_circuit.state == CircuitState.CLOSED

    with pytest.raises(ValueError):
        await test_circuit.call(fail_coro())
    assert test_circuit.state == CircuitState.OPEN

@pytest.mark.asyncio
async def test_circuit_open_blocks_calls(test_circuit):
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            await test_circuit.call(fail_coro())

    assert test_circuit.state == CircuitState.OPEN

    # Next call must raise CircuitOpenError immediately
    mock_called = False
    async def dummy_coro():
        nonlocal mock_called
        mock_called = True
        return "ok"

    coro = dummy_coro()
    try:
        with pytest.raises(CircuitOpenError):
            await test_circuit.call(coro)
    finally:
        coro.close()

    assert mock_called is False

@pytest.mark.asyncio
async def test_circuit_resets_after_window(test_circuit):
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            await test_circuit.call(fail_coro())

    assert test_circuit.state == CircuitState.OPEN

    # Manually clear failures to simulate window expiry
    test_circuit._failures.clear()
    test_circuit._cleanup_old_failures()

    assert test_circuit.state == CircuitState.HALF_OPEN

@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt():
    attempts = 0
    async def flaky_coro():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ValueError("first try fails")
        return "success"

    with patch("orion.core.resilience.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await retry_with_backoff(flaky_coro)

    assert result == "success"
    assert attempts == 2
    mock_sleep.assert_called_once()

@pytest.mark.asyncio
async def test_retry_reraises_after_max_attempts():
    mock_coro = AsyncMock(side_effect=ValueError("always fails"))

    with patch("orion.core.resilience.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(ValueError, match="always fails"):
            await retry_with_backoff(mock_coro)

    assert mock_coro.call_count == RETRY_MAX_ATTEMPTS

@pytest.mark.asyncio
async def test_retry_does_not_retry_circuit_open():
    mock_coro = AsyncMock(side_effect=CircuitOpenError("open"))

    with patch("orion.core.resilience.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(CircuitOpenError):
            await retry_with_backoff(mock_coro)

    assert mock_coro.call_count == 1
    mock_sleep.assert_not_called()

def test_llm_config_builder_enabled_only():
    providers = [
        ProviderConfig(
            provider="openai",
            api_key="key1",
            model_planning="gpt-4",
            model_fast="gpt-3.5",
            enabled=True
        ),
        ProviderConfig(
            provider="anthropic",
            api_key="key2",
            model_planning="claude-3",
            model_fast="claude-3-haiku",
            enabled=False
        )
    ]

    config = config_builder.build(providers)

    # Should have 2 models for the 1 enabled provider (planning and fast)
    assert len(config["model_list"]) == 2
    assert config["model_list"][0]["litellm_params"]["model"] == "gpt-4"
    assert config["model_list"][1]["litellm_params"]["model"] == "gpt-3.5"

def test_llm_config_builder_empty():
    providers = []
    config = config_builder.build(providers)

    assert len(config["model_list"]) == 0
    assert config["router_settings"]["drop_params"] is True
