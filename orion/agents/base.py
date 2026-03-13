import json
import re
import time
import logging
from abc import ABC
from orion.schemas.agent import AgentRole, AgentOutput
from orion.pipeline.context import PipelineContext
from orion.core.config import SEED_SUPPORTED_PROVIDERS
from orion.llm.manager import llm_manager
from orion.core.metrics import agent_token_usage_total

logger = logging.getLogger(__name__)

# ── JSON schema the LLM must return ────────────────────────────────
AGENT_SYSTEM_PROMPT = """You are the {role} agent for Orion IDE.
Your task: read the user's request and produce code files.

You MUST respond with ONLY a valid JSON object in this exact format (no markdown, no explanation outside the JSON):

{{
  "success": true,
  "file_changes": [
    {{
      "file_path": "relative/path/to/file.ext",
      "operation": "create",
      "content": "full file content here"
    }}
  ]
}}

Rules:
- "operation" is one of: "create", "modify", "delete"
- "file_path" is relative to the workspace root
- "content" is the FULL file content (not a diff)
- You may include multiple file_changes
- Return ONLY the JSON object, nothing else
"""


def _extract_json_from_response(raw: str) -> dict | None:
    """Try to extract a JSON object from an LLM response that may contain markdown fences."""
    # Try direct parse first
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ``` blocks
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    brace_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _extract_files_from_freetext(raw: str, prompt: str) -> list[dict]:
    """Last-resort parser: extract code blocks and create file_changes from freeform LLM output."""
    files = []

    # Pattern: ```language\n...code...\n``` with optional filename comment before
    pattern = r'(?:#\s*(\S+)|(?:file|filename|File)[:\s]+(\S+))?\s*```\w*\n(.*?)```'
    matches = re.findall(pattern, raw, re.DOTALL)

    if matches:
        for i, (name1, name2, content) in enumerate(matches):
            filename = name1 or name2 or f"file_{i+1}.txt"
            files.append({
                "file_path": filename,
                "operation": "create",
                "content": content.strip(),
            })
    elif raw.strip():
        # If it's just raw code with no fences, treat the entire output as a single file
        ext = _guess_extension(prompt)
        files.append({
            "file_path": f"output{ext}",
            "operation": "create",
            "content": raw.strip(),
        })

    return files


def _guess_extension(prompt: str) -> str:
    """Guess file extension from prompt keywords."""
    lower = prompt.lower()
    if any(w in lower for w in ["fastify", "express", "node", "javascript", "js"]):
        return ".js"
    if any(w in lower for w in ["typescript", "ts"]):
        return ".ts"
    if any(w in lower for w in ["python", "py", "flask", "django", "fastapi"]):
        return ".py"
    if any(w in lower for w in ["dockerfile", "docker"]):
        return ""  # Dockerfile has no extension
    if any(w in lower for w in ["html", "webpage"]):
        return ".html"
    if any(w in lower for w in ["css", "style"]):
        return ".css"
    return ".txt"


class BaseAgent(ABC):
    role: AgentRole
    TOKEN_LIMIT: int = 0

    async def run(self, ctx: PipelineContext, context_str: str) -> AgentOutput:
        if ctx.cancelled:
            return self._build_error_output(ctx, "Pipeline is cancelled")

        if not ctx.permission_write:
            return self._build_error_output(ctx, "permission_write is False")

        start_time = time.time()

        try:
            response_str = await self._call_llm(ctx, context_str)
            duration_ms = int((time.time() - start_time) * 1000)

            # Try structured JSON extraction first
            parsed = _extract_json_from_response(response_str)

            if parsed and isinstance(parsed, dict) and "file_changes" in parsed:
                # Structured response — use as-is
                logger.info(f"Agent {self.role.value}: parsed structured JSON with {len(parsed['file_changes'])} file changes")
            else:
                # Fallback: extract code blocks from freeform text
                logger.warning(f"Agent {self.role.value}: LLM returned non-JSON, using freetext parser")
                file_changes = _extract_files_from_freetext(response_str, ctx.raw_prompt)
                parsed = {
                    "file_changes": file_changes,
                    "success": len(file_changes) > 0,
                }
                logger.info(f"Agent {self.role.value}: extracted {len(file_changes)} files from freetext")

            # Inject role and run_id
            parsed["agent_role"] = self.role.value
            if "run_id" not in parsed:
                parsed["run_id"] = ctx.run_id

            # Provide defaults for any missing fields
            if "success" not in parsed: parsed["success"] = True
            if "file_changes" not in parsed: parsed["file_changes"] = []
            if "iisg_satisfied" not in parsed: parsed["iisg_satisfied"] = []
            if "tokens_used" not in parsed: parsed["tokens_used"] = 150
            if "duration_ms" not in parsed: parsed["duration_ms"] = duration_ms

            provider = ctx.active_provider or "unknown"
            agent_token_usage_total.labels(
                agent_role=self.role.value,
                provider=provider
            ).inc(parsed["tokens_used"])

            return AgentOutput(**parsed)

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return self._build_error_output(ctx, str(e), duration_ms=duration_ms)

    async def _call_llm(self, ctx: PipelineContext, context_str: str) -> str:
        token_limit = ctx.run_config.get_token_limit(self.role)
        if token_limit == 0 and hasattr(self, 'TOKEN_LIMIT'):
            token_limit = self.TOKEN_LIMIT

        model = self._get_model(ctx)
        messages = self._build_messages(ctx, context_str)
        seed_param = self._seed_param(ctx)

        component_name = f"agent_{self.role.value}"
        if "backend" in component_name:
            component_name = "agent_backend"

        return await llm_manager.get_completion(
            model=model,
            messages=messages,
            max_tokens=token_limit,
            temperature=0,
            seed=seed_param.get("seed"),
            component_name=component_name
        )

    def _seed_param(self, ctx: PipelineContext) -> dict:
        if ctx.active_provider in SEED_SUPPORTED_PROVIDERS:
            return {"seed": ctx.run_id_int}
        return {}

    def _get_model(self, ctx: PipelineContext) -> str:
        return ctx.mode.value

    def _build_messages(self, ctx: PipelineContext, context_str: str) -> list[dict]:
        return [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT.format(role=self.role.value)},
            {"role": "user", "content": f"{ctx.raw_prompt}\n\n---\nWorkspace context:\n{context_str}"}
        ]

    def _build_error_output(self, ctx: PipelineContext, error_msg: str, duration_ms: int = 0) -> AgentOutput:
        return AgentOutput(
            agent_role=self.role,
            run_id=ctx.run_id,
            success=False,
            file_changes=[],
            iisg_satisfied=[],
            tokens_used=0,
            duration_ms=duration_ms,
            error=error_msg
        )
