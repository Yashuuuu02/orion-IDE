import pytest
import os
from unittest.mock import patch
from orion.pipeline.components.c02_stack import c02_stack
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode

@pytest.fixture
def mock_redis():
    class MockRedis:
        def __init__(self): self.data = {}
        async def get(self, key): return self.data.get(key)
        async def setex(self, key, ttl, val): self.data[key] = val
    return MockRedis()

@pytest.mark.asyncio
async def test_c02_tsx_detection(mock_redis, tmp_path):
    # Create sample TSX file for tree-sitter detection
    test_file = tmp_path / "sample.tsx"
    test_file.write_text("import React from 'react';\nconst App = () => <div>Hello</div>;\nexport default App;")

    os.environ["TEST_C02_FILE_PATH"] = str(test_file)

    with patch('orion.pipeline.components.c02_stack.get_redis', return_value=mock_redis):
        ctx = PipelineContext.create("sess1", "ws1", "test", RunMode.PLANNING)
        result = await c02_stack.execute(ctx)

        assert result.stack_lock is not None
        assert result.stack_lock.language == "typescript"
        assert result.stack_lock.framework == "react"

    del os.environ["TEST_C02_FILE_PATH"]
