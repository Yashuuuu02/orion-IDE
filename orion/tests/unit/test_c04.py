import pytest
from unittest.mock import patch
from orion.pipeline.components.c04_architect import c04_architect
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode

@pytest.mark.asyncio
async def test_c04_blueprint_population():
    ctx = PipelineContext.create("sess1", "ws1", "test", RunMode.PLANNING)

    result = await c04_architect.execute(ctx)

    assert result.blueprint is not None
    assert "project_name" in result.blueprint
    assert "components" in result.blueprint
    assert len(result.blueprint["components"]) > 0

@pytest.mark.asyncio
async def test_c04_skips_in_fast_mode():
    ctx = PipelineContext.create("sess1", "ws1", "test", RunMode.FAST)
    result = await c04_architect.execute(ctx)
    assert result.blueprint is None
