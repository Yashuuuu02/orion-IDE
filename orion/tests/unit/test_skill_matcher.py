import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from orion.skills.matcher import SkillMatcher, _cosine_similarity
from orion.schemas.skills import SkillRecord, SkillMatch
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode


class MockRedis:
    def __init__(self): self.data = {}
    async def get(self, k): return self.data.get(k)
    async def setex(self, k, t, v): self.data[k] = v


@pytest.mark.asyncio
async def test_score_below_threshold_no_match():
    """Score below 0.82 does not fire."""
    matcher = SkillMatcher()
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)

    skill = SkillRecord(
        skill_id="sk1", name="Low Skill", description="totally unrelated topic xyz",
        instructions=["do something"], source="global"
    )

    # Mock embeddings that produce low cosine similarity
    # Orthogonal vectors → cosine = 0.0
    emb_prompt = [1.0, 0.0, 0.0]
    emb_skill = [0.0, 1.0, 0.0]

    with patch('orion.skills.matcher.llm_manager') as mock_llm, \
         patch('orion.skills.matcher.get_redis', return_value=MockRedis()):
        mock_llm.get_embedding = AsyncMock(side_effect=[emb_prompt, emb_skill])
        result = await matcher.match("test prompt", [skill], ctx)

    assert len(result) == 0, f"Expected no matches for low score, got {len(result)}"
    print("ok: score below threshold does not fire")


@pytest.mark.asyncio
async def test_score_above_threshold_fires():
    """Score above 0.82 fires."""
    matcher = SkillMatcher()
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)

    skill = SkillRecord(
        skill_id="sk1", name="Good Skill", description="very relevant",
        instructions=["do this"], source="global"
    )

    # Identical vectors → cosine = 1.0
    emb = [0.5, 0.5, 0.5]

    with patch('orion.skills.matcher.llm_manager') as mock_llm, \
         patch('orion.skills.matcher.get_redis', return_value=MockRedis()):
        mock_llm.get_embedding = AsyncMock(return_value=emb)
        result = await matcher.match("test prompt", [skill], ctx)

    assert len(result) == 1
    assert result[0].score > 0.82
    print("ok: score above threshold fires")


@pytest.mark.asyncio
async def test_top_2_cap_enforced():
    """Only top 2 returned even with more candidates."""
    matcher = SkillMatcher()
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)

    skills = [
        SkillRecord(skill_id=f"sk{i}", name=f"Skill {i}", description=f"desc {i}",
                     instructions=[f"instr {i}"], source="global")
        for i in range(5)
    ]

    emb = [0.9, 0.9, 0.9]

    with patch('orion.skills.matcher.llm_manager') as mock_llm, \
         patch('orion.skills.matcher.get_redis', return_value=MockRedis()):
        mock_llm.get_embedding = AsyncMock(return_value=emb)
        result = await matcher.match("test prompt", skills, ctx)

    assert len(result) <= 2, f"Expected max 2, got {len(result)}"
    print("ok: top-2 cap enforced")
