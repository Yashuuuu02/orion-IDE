import logging
from pathlib import Path
from orion.schemas.skills import OrionMdContext

logger = logging.getLogger(__name__)


class OrionMdLoader:
    GLOBAL_PATH = Path.home() / ".orion" / "ORION.md"
    PROJECT_RELATIVE = Path(".orion") / "ORION.md"

    def load(self, workspace_root: Path) -> OrionMdContext:
        global_content = None
        project_content = None

        global_path = self.GLOBAL_PATH
        project_path = Path(workspace_root) / self.PROJECT_RELATIVE

        if global_path.exists():
            try:
                global_content = global_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to read global ORION.md: {e}")

        if project_path.exists():
            try:
                project_content = project_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to read project ORION.md: {e}")

        merged = self._merge(global_content, project_content)

        return OrionMdContext(
            global_path=str(global_path),
            project_path=str(project_path),
            global_loaded=global_content is not None,
            project_loaded=project_content is not None,
            merged_content=merged,
        )

    def _merge(self, global_content: str | None, project_content: str | None) -> str:
        if global_content is None and project_content is None:
            return ""
        if global_content is None:
            return project_content
        if project_content is None:
            return global_content

        # Both exist — merge by section headings
        global_sections = self._parse_sections(global_content)
        project_sections = self._parse_sections(project_content)

        merged_parts: list[str] = []

        # Preambles: project wins if both have one
        global_preamble = global_sections.pop("__preamble__", "")
        project_preamble = project_sections.pop("__preamble__", "")
        preamble = project_preamble if project_preamble else global_preamble
        if preamble:
            merged_parts.append(preamble)

        all_headings = list(dict.fromkeys(
            list(global_sections.keys()) + list(project_sections.keys())
        ))

        # global-only, project-only, project-override order
        global_only = [h for h in all_headings if h in global_sections and h not in project_sections]
        project_only = [h for h in all_headings if h in project_sections and h not in global_sections]
        overrides = [h for h in all_headings if h in global_sections and h in project_sections]

        for h in global_only:
            merged_parts.append(f"## {h}\n{global_sections[h]}")
        for h in project_only:
            merged_parts.append(f"## {h}\n{project_sections[h]}")
        for h in overrides:
            merged_parts.append(f"## {h}\n{project_sections[h]}")

        return "\n\n".join(merged_parts)

    def _parse_sections(self, content: str) -> dict[str, str]:
        """Split markdown by '## ' headings."""
        sections: dict[str, str] = {}
        current_heading = "__preamble__"
        current_lines: list[str] = []

        for line in content.split("\n"):
            if line.startswith("## "):
                # Save previous section
                sections[current_heading] = "\n".join(current_lines).strip()
                current_heading = line[3:].strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        sections[current_heading] = "\n".join(current_lines).strip()
        return sections
