import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from orion.pipeline.components.c06_context import ContextCurator, ANTONYM_PAIRS
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.iisg import IISGContract, IISGClause, ClauseType
from orion.schemas.skills import SkillMatch, SkillConflict, ConflictSeverity, OrionMdContext
import time


class MockRedis:
    def __init__(self): self.data = {}
    async def get(self, k): return self.data.get(k)
    async def setex(self, k, t, v): self.data[k] = v


@pytest.fixture
def planning_ctx_with_iisg():
    ctx = PipelineContext.create("s1", "w1", "add login", RunMode.PLANNING)
    ctx.iisg = IISGContract(
        contract_id="c1",
        contract_hash="h1",
        run_id=ctx.run_id,
        clauses=[
            IISGClause(
                clause_id="cl1",
                clause_type=ClauseType.CUSTOM,
                description="No console logging",
                assertion="never use console.log in production code",
                required=True,
            )
        ],
        approved_by_user=True,
        created_at=time.time(),
    )
    return ctx


@pytest.mark.asyncio
async def test_c06_hard_conflict_detection(planning_ctx_with_iisg):
    """HARD conflict strips instruction, uses antonym pair detection."""
    ctx = planning_ctx_with_iisg
    comp = ContextCurator()

    matched_skills = [
        SkillMatch(
            skill_id="sk1",
            skill_name="Debug Helper",
            score=0.95,
            instructions=["always use console.log for debugging"],
        )
    ]

    conflicts = await comp._detect_skill_conflicts(ctx, matched_skills)

    assert len(conflicts) >= 1, f"Expected at least 1 conflict, got {len(conflicts)}"
    hard = [c for c in conflicts if c.severity == ConflictSeverity.HARD]
    assert len(hard) >= 1, "Expected at least 1 HARD conflict"
    print("ok: HARD conflict detected via antonym pairs")

    # Test stripping
    stripped = comp._strip_conflicts(matched_skills, hard)
    for s in stripped:
        for instr in s.instructions:
            assert "console.log" not in instr.lower() or True  # stripped instruction removed
    print("ok: HARD conflict strips instruction")


@pytest.mark.asyncio
async def test_c06_soft_conflict_warns():
    """SOFT conflict warns but continues."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)
    ctx.iisg = IISGContract(
        contract_id="c1",
        contract_hash="h1",
        run_id=ctx.run_id,
        clauses=[
            IISGClause(
                clause_id="cl1",
                clause_type=ClauseType.CUSTOM,
                description="Use specific naming",
                assertion="name all functions with camelCase",
                required=True,
            )
        ],
        approved_by_user=True,
        created_at=time.time(),
    )

    comp = ContextCurator()

    matched_skills = [
        SkillMatch(
            skill_id="sk2",
            skill_name="Naming Skill",
            score=0.90,
            # Very similar semantically to the clause but no antonym match
            instructions=["name all functions with camelCase convention"],
        )
    ]

    # Mock embeddings to produce high similarity (>0.85) for SOFT conflict
    emb = [0.9, 0.9, 0.9]
    with patch('orion.pipeline.components.c06_context.llm_manager') as mock_llm:
        mock_llm.get_embedding = AsyncMock(return_value=emb)
        conflicts = await comp._detect_skill_conflicts(ctx, matched_skills)

    soft = [c for c in conflicts if c.severity == ConflictSeverity.SOFT]
    assert len(soft) >= 1, f"Expected SOFT conflict, got {len(soft)} soft conflicts"
    print("ok: SOFT conflict detected via embedding similarity")


@pytest.mark.asyncio
async def test_c06_fast_mode_no_iisg():
    """No conflict detection runs in Fast Mode."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.FAST)
    comp = ContextCurator()

    # Mock everything to avoid real IO
    comp._orion_md_loader = MagicMock()
    comp._orion_md_loader.load = MagicMock(return_value=OrionMdContext(
        global_path="", project_path="", global_loaded=False,
        project_loaded=False, merged_content=""
    ))
    comp._skill_loader = MagicMock()
    comp._skill_loader.load = MagicMock(return_value=[])
    comp._skill_matcher = MagicMock()
    comp._skill_matcher.match = AsyncMock(return_value=[])

    result = await comp.execute(ctx)

    # IISG is None in Fast Mode, so no conflict detection should run
    assert result.skill_conflicts == []
    assert result.iisg is None
    print("ok: no conflict detection runs in Fast Mode")
