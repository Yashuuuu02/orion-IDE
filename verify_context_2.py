import os
os.environ["DATABASE_URL"] = "postgres://dummy"
os.environ["REDIS_URL"] = "redis://dummy"

from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.core.config import (
    SKILL_MATCH_THRESHOLD, TOP_K_SKILLS, FAST_MODE_SINGLE_AGENT_TOKEN_LIMIT,
    CIRCUIT_BREAKER_LLM_THRESHOLD, CIRCUIT_BREAKER_LLM_WINDOW_SECONDS,
    CIRCUIT_BREAKER_MCP_THRESHOLD, RETRY_MAX_ATTEMPTS, RETRY_BACKOFF_SEQUENCE,
    SEED_SUPPORTED_PROVIDERS
)

assert SKILL_MATCH_THRESHOLD == 0.82, f'FAIL: threshold is {SKILL_MATCH_THRESHOLD}'
assert TOP_K_SKILLS == 2, f'FAIL: top_k is {TOP_K_SKILLS}'
assert FAST_MODE_SINGLE_AGENT_TOKEN_LIMIT == 80_000
assert CIRCUIT_BREAKER_LLM_THRESHOLD == 3
assert CIRCUIT_BREAKER_LLM_WINDOW_SECONDS == 60
assert CIRCUIT_BREAKER_MCP_THRESHOLD == 5
assert RETRY_MAX_ATTEMPTS == 5
assert RETRY_BACKOFF_SEQUENCE == [1, 2, 4, 8, 16]
assert 'anthropic' not in SEED_SUPPORTED_PROVIDERS
assert 'openai' in SEED_SUPPORTED_PROVIDERS
print('ok: all constants correct')

ctx1 = PipelineContext.create('sess1', 'ws1', 'add login endpoint', RunMode.PLANNING)
ctx2 = PipelineContext.create('sess1', 'ws1', 'add login endpoint', RunMode.PLANNING)
assert ctx1.run_id == ctx2.run_id, f'FAIL: same inputs produced different run_ids\n  ctx1: {ctx1.run_id}\n  ctx2: {ctx2.run_id}'
assert ctx1.run_id_int == ctx2.run_id_int
print('ok: run_id is deterministic (UUID5)')

ctx3 = PipelineContext.create('sess1', 'ws1', 'delete the database', RunMode.PLANNING)
assert ctx1.run_id != ctx3.run_id, 'FAIL: different prompts produced same run_id'
print('ok: different prompts produce different run_ids')

assert isinstance(ctx1.run_id_int, int) and ctx1.run_id_int > 0
print('ok: run_id_int is positive int')

assert ctx1.mode == RunMode.PLANNING
assert ctx1.cancelled == False
assert ctx1.cost_actual == 0.0
print('ok: PipelineContext defaults correct')

print('--- all checks passed ---')
