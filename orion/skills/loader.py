import logging
import os
import sqlite3
import hashlib
from pathlib import Path
from orion.schemas.skills import SkillRecord
from orion.core.config import settings

logger = logging.getLogger(__name__)

class SkillLoader:
    """Loads all installed skills from global and project skill directories."""

    def __init__(self):
        self._memory_db_path = Path(os.path.expanduser("~/.orion/memories.db"))

    def load(self, workspace_root: str) -> list[SkillRecord]:
        skills: list[SkillRecord] = []

        # Load from global path
        global_path = Path(os.path.expanduser(settings.SKILL_GLOBAL_PATH))
        if global_path.exists():
            skills.extend(self._scan_dir(global_path, "global"))

        # Load from project path
        project_path = Path(workspace_root) / ".orion" / "skills"
        if project_path.exists():
            skills.extend(self._scan_dir(project_path, "project"))

        # Check enabled/disabled state from SQLite
        enabled_map = self._load_enabled_state()
        for s in skills:
            if s.skill_id in enabled_map:
                s.enabled = enabled_map[s.skill_id]

        logger.info(f"Loaded {len(skills)} skills ({sum(1 for s in skills if s.enabled)} enabled)")
        return skills

    def _scan_dir(self, base: Path, source: str) -> list[SkillRecord]:
        records = []
        if not base.is_dir():
            return records

        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                name, description, instructions = self._parse_skill_md(content)
                skill_id = hashlib.sha256(f"{source}:{entry.name}".encode()).hexdigest()[:12]
                records.append(SkillRecord(
                    skill_id=skill_id,
                    name=name or entry.name,
                    description=description or "",
                    instructions=instructions,
                    source=source,
                    path=str(skill_md),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse skill at {skill_md}: {e}")

        return records

    def _parse_skill_md(self, content: str) -> tuple[str, str, list[str]]:
        """Parse YAML frontmatter + markdown body from SKILL.md."""
        name = ""
        description = ""
        instructions: list[str] = []

        lines = content.split("\n")
        body_start = 0

        # Check for YAML frontmatter
        if lines and lines[0].strip() == "---":
            end_idx = -1
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    end_idx = i
                    break
            if end_idx > 0:
                for line in lines[1:end_idx]:
                    line = line.strip()
                    if line.startswith("name:"):
                        name = line[5:].strip().strip('"').strip("'")
                    elif line.startswith("description:"):
                        description = line[12:].strip().strip('"').strip("'")
                body_start = end_idx + 1

        # Parse body into instructions (split by headings or numbered steps)
        body_lines = lines[body_start:]
        body_text = "\n".join(body_lines).strip()
        if body_text:
            instructions = [body_text]

        return name, description, instructions

    def _load_enabled_state(self) -> dict[str, bool]:
        """Load skill enabled/disabled state from local SQLite."""
        enabled_map: dict[str, bool] = {}
        if not self._memory_db_path.exists():
            return enabled_map
        try:
            conn = sqlite3.connect(str(self._memory_db_path))
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='skills'"
            )
            if not cursor.fetchone():
                conn.close()
                return enabled_map
            rows = conn.execute("SELECT skill_id, enabled FROM skills").fetchall()
            for skill_id, enabled in rows:
                enabled_map[skill_id] = bool(enabled)
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to read skill state from SQLite: {e}")
        return enabled_map
