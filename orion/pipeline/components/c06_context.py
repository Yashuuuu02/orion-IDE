import logging
import sqlite3
import os
from pathlib import Path
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.skills import SkillMatch, SkillConflict, ConflictSeverity
from orion.skills.loader import SkillLoader
from orion.skills.matcher import SkillMatcher, _cosine_similarity
from orion.skills.orion_md import OrionMdLoader
from orion.llm.manager import llm_manager

logger = logging.getLogger(__name__)

ANTONYM_PAIRS = [
    ("always use", "never use"),
    ("add", "remove"),
    ("enable", "disable"),
    ("include", "exclude"),
    ("console.log", "no console"),
    ("var ", "const "),
]


class ContextCurator(BaseComponent):
    component_id = "c06_context"
    component_name = "Context Curator"

    def __init__(self):
        super().__init__()
        self._skill_loader = SkillLoader()
        self._skill_matcher = SkillMatcher()
        self._orion_md_loader = OrionMdLoader()

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        # 1. Load ORION.md
        ctx.orion_md = self._orion_md_loader.load(Path(ctx.workspace_id))
        logger.info(f"C06: ORION.md loaded (global={ctx.orion_md.global_loaded}, project={ctx.orion_md.project_loaded})")

        # 2. Load memories from local SQLite
        memories = self._load_memories()

        # 3. Match skills
        all_skills = self._skill_loader.load(ctx.workspace_id)
        matched_skills = await self._skill_matcher.match(ctx.raw_prompt, all_skills, ctx)
        logger.info(f"C06: Matched {len(matched_skills)} skills")

        # 4. Planning mode conflict detection
        if ctx.mode == RunMode.PLANNING and ctx.iisg is not None and matched_skills:
            conflicts = await self._detect_skill_conflicts(ctx, matched_skills)
            ctx.skill_conflicts = conflicts

            hard_conflicts = [c for c in conflicts if c.severity == ConflictSeverity.HARD]
            soft_conflicts = [c for c in conflicts if c.severity == ConflictSeverity.SOFT]

            for c in conflicts:
                await self._ws_emit(ctx, "skill.conflict_warning", {
                    "skill": c.skill_name,
                    "severity": c.severity.value,
                    "instruction": c.skill_instruction,
                    "clause": c.iisg_instruction,
                })

            if hard_conflicts:
                from orion.pipeline.runner import pipeline_runner
                import asyncio
                try:
                    decision = await asyncio.wait_for(
                        pipeline_runner._wait_for_approval(ctx.run_id, "skill_conflict"),
                        timeout=300.0,
                    )
                    if not decision.get("approved"):
                        ctx.cancelled = True
                        return ctx
                except asyncio.TimeoutError:
                    ctx.cancelled = True
                    return ctx

                # Strip conflicting instructions from matched skills
                matched_skills = self._strip_conflicts(matched_skills, hard_conflicts)

        # 5. Assemble context bundle
        context_bundle = {
            "orion_md": ctx.orion_md.merged_content if ctx.orion_md else "",
            "memories": memories,
            "skills": [s.model_dump() for s in matched_skills],
            "context_scope": ctx.context_scope.value,
        }

        # 6. Build per-role context strings
        ctx.contexts = context_bundle

        return ctx

    def _load_memories(self) -> list[str]:
        """Load memories from local SQLite ~/.orion/memories.db."""
        memories = []
        db_path = Path(os.path.expanduser("~/.orion/memories.db"))
        if not db_path.exists():
            return memories
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
            )
            if not cursor.fetchone():
                conn.close()
                return memories
            rows = conn.execute("SELECT content FROM memories").fetchall()
            memories = [r[0] for r in rows]
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to load memories: {e}")
        return memories

    async def _detect_skill_conflicts(
        self, ctx: PipelineContext, matched_skills: list[SkillMatch]
    ) -> list[SkillConflict]:
        """Two-pass conflict detection between skill instructions and IISG clauses."""
        conflicts: list[SkillConflict] = []
        if not ctx.iisg:
            return conflicts

        for skill in matched_skills:
            for instruction in skill.instructions:
                instruction_lower = instruction.lower()
                for clause in ctx.iisg.clauses:
                    assertion_lower = clause.assertion.lower()

                    # Pass 1 — keyword antonyms (HARD)
                    for pos, neg in ANTONYM_PAIRS:
                        if (pos in instruction_lower and neg in assertion_lower) or \
                           (neg in instruction_lower and pos in assertion_lower):
                            conflicts.append(SkillConflict(
                                skill_id=skill.skill_id,
                                skill_name=skill.skill_name,
                                skill_instruction=instruction,
                                conflicting_clause_id=clause.clause_id,
                                iisg_instruction=clause.assertion,
                                severity=ConflictSeverity.HARD,
                            ))
                            break
                    else:
                        # Pass 2 — embedding similarity (SOFT)
                        try:
                            instr_emb = await llm_manager.get_embedding(instruction)
                            clause_emb = await llm_manager.get_embedding(clause.assertion)
                            sim = _cosine_similarity(instr_emb, clause_emb)
                            if sim > 0.85:
                                conflicts.append(SkillConflict(
                                    skill_id=skill.skill_id,
                                    skill_name=skill.skill_name,
                                    skill_instruction=instruction,
                                    conflicting_clause_id=clause.clause_id,
                                    iisg_instruction=clause.assertion,
                                    severity=ConflictSeverity.SOFT,
                                ))
                        except Exception as e:
                            logger.warning(f"Embedding conflict check failed: {e}")

        return conflicts

    def _strip_conflicts(
        self, skills: list[SkillMatch], hard_conflicts: list[SkillConflict]
    ) -> list[SkillMatch]:
        """Remove conflicting instructions from matched skills."""
        conflict_instructions = {c.skill_instruction for c in hard_conflicts}
        stripped = []
        for skill in skills:
            new_instructions = [i for i in skill.instructions if i not in conflict_instructions]
            stripped.append(SkillMatch(
                skill_id=skill.skill_id,
                skill_name=skill.skill_name,
                score=skill.score,
                instructions=new_instructions,
            ))
        return stripped

    def _check_conflict(self, instruction: str, clause) -> ConflictSeverity | None:
        """Check a single instruction against a single clause for conflicts.
        Returns ConflictSeverity.HARD, ConflictSeverity.SOFT, or None."""
        instruction_lower = instruction.lower()
        assertion_lower = clause.assertion.lower()

        # Pass 1 — keyword antonyms (HARD)
        for pos, neg in ANTONYM_PAIRS:
            if (pos in instruction_lower and neg in assertion_lower) or \
               (neg in instruction_lower and pos in assertion_lower):
                return ConflictSeverity.HARD

        return None


c06_context = ContextCurator()
