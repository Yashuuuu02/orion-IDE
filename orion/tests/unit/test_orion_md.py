import pytest
from orion.skills.orion_md import OrionMdLoader


def test_project_heading_wins_over_global():
    loader = OrionMdLoader()
    global_content = """## Style Guide
Use tabs.

## Naming
Use snake_case."""

    project_content = """## Style Guide
Use spaces."""

    merged = loader._merge(global_content, project_content)

    # Project's "Style Guide" should win
    assert "Use spaces." in merged
    assert "Use tabs." not in merged
    # Global-only "Naming" should be kept
    assert "snake_case" in merged



def test_non_conflicting_sections_kept():
    loader = OrionMdLoader()
    global_content = """## Logging
Always log errors."""

    project_content = """## Testing
Write unit tests."""

    merged = loader._merge(global_content, project_content)

    assert "Always log errors." in merged
    assert "Write unit tests." in merged



def test_preamble_handling():
    loader = OrionMdLoader()
    global_content = """Global preamble text.

## Section A
Content A"""

    project_content = """Project preamble.

## Section B
Content B"""

    merged = loader._merge(global_content, project_content)
    # Project preamble wins
    assert "Project preamble." in merged
    assert "Content A" in merged
    assert "Content B" in merged



def test_parse_sections():
    loader = OrionMdLoader()
    content = """Preamble here.

## First
Content 1.

## Second
Content 2."""

    sections = loader._parse_sections(content)
    assert "__preamble__" in sections
    assert "Preamble here." in sections["__preamble__"]
    assert "First" in sections
    assert "Content 1." in sections["First"]
    assert "Second" in sections

