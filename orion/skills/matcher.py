import logging
import hashlib
import math
from orion.schemas.skills import SkillRecord, SkillMatch
from orion.pipeline.context import PipelineContext
from orion.core.config import SKILL_MATCH_THRESHOLD, TOP_K_SKILLS, EMBEDDING_MODEL
from orion.core.redis_client import get_redis
from orion.llm.manager import llm_manager

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity without numpy."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SkillMatcher:
    THRESHOLD = SKILL_MATCH_THRESHOLD  # 0.82
    TOP_K = TOP_K_SKILLS               # 2

    async def match(
        self,
        prompt: str,
        skills: list[SkillRecord],
        ctx: PipelineContext,
    ) -> list[SkillMatch]:
        if not skills:
            return []

        # 1. Embed prompt
        prompt_emb = await llm_manager.get_embedding(prompt)

        # 2. Score each enabled skill
        candidates: list[SkillMatch] = []
        redis = get_redis()

        for skill in skills:
            if not skill.enabled:
                continue

            # Cache key for skill embedding
            desc_hash = hashlib.sha256(skill.description.encode()).hexdigest()[:8]
            cache_key = f"skill_emb:{EMBEDDING_MODEL}:{skill.skill_id}:{desc_hash}"

            cached_emb = await redis.get(cache_key)
            if cached_emb:
                import json
                skill_emb = json.loads(cached_emb)
            else:
                skill_emb = await llm_manager.get_embedding(skill.description)
                import json
                await redis.setex(cache_key, 7 * 24 * 3600, json.dumps(skill_emb))

            score = _cosine_similarity(prompt_emb, skill_emb)

            if score > self.THRESHOLD:
                candidates.append(SkillMatch(
                    skill_id=skill.skill_id,
                    skill_name=skill.name,
                    score=score,
                    instructions=skill.instructions,
                ))

        # 3. Sort descending by score
        candidates.sort(key=lambda c: c.score, reverse=True)

        # 4. Return top-K
        return candidates[:self.TOP_K]
