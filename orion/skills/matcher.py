import logging
import hashlib
import math
from orion.schemas.skills import SkillRecord, SkillMatch
from orion.pipeline.context import PipelineContext
from orion.core.config import SKILL_MATCH_THRESHOLD, TOP_K_SKILLS, EMBEDDING_MODEL
from orion.llm.manager import llm_manager
from orion.core.database import AsyncSessionLocal
from sqlalchemy import text
from datetime import datetime, timezone, timedelta

import typing
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

        candidates: list[SkillMatch] = []

        # 2. Score each enabled skill
        for skill in skills:
            if not skill.enabled:
                continue

            # Cache key for skill embedding
            desc_hash = hashlib.sha256(str(skill.description).encode()).hexdigest()
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(text(
                    "SELECT embedding FROM embedding_cache WHERE content_hash=:h AND model=:m AND (expires_at IS NULL OR expires_at > NOW())"
                ), {'h': desc_hash, 'm': EMBEDDING_MODEL})
                row = result.fetchone()
                
                if row:
                    skill_emb = row[0]
                else:
                    skill_emb = await llm_manager.get_embedding(skill.description)
                    expires = datetime.now(timezone.utc) + timedelta(days=7)
                    await db.execute(text(
                        "INSERT INTO embedding_cache(content_hash, model, embedding, expires_at) VALUES (:h, :m, :emb, :exp) ON CONFLICT (content_hash, model) DO UPDATE SET embedding=EXCLUDED.embedding, expires_at=EXCLUDED.expires_at"
                    ), {'h': desc_hash, 'm': EMBEDDING_MODEL, 'emb': str(skill_emb), 'exp': expires})
                    await db.commit()

            import json
            if isinstance(skill_emb, str):
                try:
                    skill_emb = json.loads(skill_emb)
                except Exception:
                    pass

            score = _cosine_similarity(prompt_emb, typing.cast(list[float], skill_emb))

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
        return candidates[:int(self.TOP_K)]
