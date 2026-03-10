import time
from abc import ABC, abstractmethod
from orion.pipeline.context import PipelineContext
from orion.api.ws import ws_manager
from orion.core.metrics import component_execution_seconds

class BaseComponent(ABC):
    component_id: str
    component_name: str

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        await self._ws_emit(ctx, "component.started")

        start_time = time.time()
        result_ctx = await self._run(ctx)
        duration_ms = int((time.time() - start_time) * 1000)

        await self._ws_emit(result_ctx, "component.completed", {"duration_ms": duration_ms})

        component_execution_seconds.labels(component_id=self.component_id).observe(duration_ms / 1000)

        return result_ctx

    @abstractmethod
    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        pass

    async def _ws_emit(self, ctx: PipelineContext, event_type: str, extra: dict = None):
        if extra is None:
            extra = {}

        event = {
            "type": event_type,
            "run_id": ctx.run_id,
            "component": self.component_id,
        }
        event.update(extra)
        await ws_manager.emit(ctx.session_id, event)
