import pytest
import os
import json
from unittest.mock import patch, AsyncMock
from orion.pipeline.components.c01_intent import c01_intent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode

@pytest.fixture
def mock_redis():
    class MockRedis:
        def __init__(self):
            self.data = {}
        async def get(self, key):
            return self.data.get(key)
        async def setex(self, key, ttl, val):
            self.data[key] = val
    return MockRedis()

@pytest.mark.asyncio
async def test_c01_cache_miss(mock_redis):
    with patch('orion.pipeline.components.c01_intent.get_redis', return_value=mock_redis):
        # MOCK_LLM is enabled by the test environment variables, so llm_manager will use mock.py fixture
        ctx = PipelineContext.create("sess1", "ws1", "Build the mock llm JSON tests", RunMode.PLANNING)
        result = await c01_intent.execute(ctx)

        assert result.intent is not None
        assert result.intent.summary == "Implement a deterministic MockLLM fixture loader."
        assert result.intent.intent_type.value == "FEATURE"
        assert f"intent_cache:{ctx.intent_hash}" in mock_redis.data

@pytest.mark.asyncio
async def test_c01_cache_hit(mock_redis):
    with patch('orion.pipeline.components.c01_intent.get_redis', return_value=mock_redis):
        ctx = PipelineContext.create("sess1", "ws1", "Build the mock llm JSON tests", RunMode.PLANNING)
        # Pre-populate cache
        mock_data = {
            "intent_hash": ctx.intent_hash,
            "intent_type": "BUG_FIX",
            "summary": "Cached summary",
            "affected_files": [],
            "affected_roles": [],
            "complexity": 1,
            "requires_iisg": False,
            "raw_prompt": "Build the mock llm JSON tests"
        }
        await mock_redis.setex(f"intent_cache:{ctx.intent_hash}", 3600, json.dumps(mock_data))

        result = await c01_intent.execute(ctx)
        assert result.intent is not None
        assert result.intent.summary == "Cached summary"
        assert result.intent.intent_type.value == "BUG_FIX"
