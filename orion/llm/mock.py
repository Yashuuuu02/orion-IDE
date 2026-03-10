import json
import os
import hashlib
from typing import Optional

class MockLLM:
    """Mock LLM used for testing and offline development"""

    def __init__(self):
        # Base path relative to this file's location
        # orion/llm/mock.py -> orion/tests/fixtures/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.fixtures_dir = os.path.join(os.path.dirname(current_dir), "tests", "fixtures")

    def get_completion(self, component_name: str, messages: list[dict]) -> str:
        """Loads a fixture from orion/tests/fixtures based on component name."""
        fixture_path = os.path.join(self.fixtures_dir, f"{component_name}.json")
        try:
            with open(fixture_path, 'r', encoding='utf-8') as f:
                # Return raw JSON string as if from an LLM
                return f.read()
        except FileNotFoundError:
            raise ValueError(f"Mock fixture not found: {fixture_path}")

    def get_embedding(self, text: str) -> list[float]:
        """Returns deterministic embedding array based on hash."""
        hash_val = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
        # Create a deterministic array of 1536 floats between 0 and 1
        return [(hash_val * i % 100) / 100.0 for i in range(1536)]
