from orion.schemas.pipeline import RunMode, ContextScope, RunPreset
from orion.schemas.stack import StackLock
from orion.schemas.settings import OrionSettings, RunConfig
from orion.schemas.skills import ConflictSeverity
import pydantic

# StackLock must be frozen
sl = StackLock(lock_hash='x', language='ts', framework='react', test_runner='jest',
               package_manager='npm', dependencies={}, workspace_root='/tmp', locked_at=0.0)
try:
    sl.language = 'python'
    print('FAIL: StackLock is not frozen')
except Exception:
    print('ok: StackLock frozen')

# OrionSettings default mode must be PLANNING
s = OrionSettings()
assert s.default_mode == RunMode.PLANNING, f'FAIL: default_mode is {s.default_mode}'
print('ok: default_mode is PLANNING')

# Alert thresholds must exist and be strictly below stop thresholds
assert s.budget_session_alert_usd < s.budget_session_usd, 'FAIL: session alert >= stop'
assert s.budget_daily_alert_usd < s.budget_daily_usd, 'FAIL: daily alert >= stop'
assert s.budget_monthly_alert_usd < s.budget_monthly_usd, 'FAIL: monthly alert >= stop'
print('ok: budget alert thresholds below stop thresholds')

# ConflictSeverity string values
assert ConflictSeverity.HARD == 'hard', f'FAIL: HARD is {ConflictSeverity.HARD}'
assert ConflictSeverity.SOFT == 'soft', f'FAIL: SOFT is {ConflictSeverity.SOFT}'
print('ok: ConflictSeverity values correct')

# RunConfig methods must exist and be callable
rc = RunConfig()
from orion.schemas.agent import AgentRole
limit = rc.get_token_limit(AgentRole.BACKEND)
assert isinstance(limit, int), f'FAIL: get_token_limit returned {type(limit)}'
enabled = rc.is_agent_enabled(AgentRole.BACKEND)
assert isinstance(enabled, bool), f'FAIL: is_agent_enabled returned {type(enabled)}'
print('ok: RunConfig methods callable')

print('--- all checks passed ---')
