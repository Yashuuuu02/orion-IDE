import os
from pydantic_settings import BaseSettings

# Create an execution environment with .env variables loaded to verify `Settings` successfully loads.
# Set dummy environment variables to allow pydantic-settings to construct config without errors
os.environ["DATABASE_URL"] = "postgres://dummy"
os.environ["REDIS_URL"] = "redis://dummy"

from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.core.config import settings, SKILL_MATCH_THRESHOLD

# Test pipeline context creation
pc = PipelineContext.create(
    session_id="ses_123",
    workspace_id="ws_456",
    raw_prompt="Hello Orion!",
    mode=RunMode.PLANNING
)

assert pc.run_id is not None
assert isinstance(pc.run_id_int, int)
assert SKILL_MATCH_THRESHOLD == 0.82
print('context + config ok')
