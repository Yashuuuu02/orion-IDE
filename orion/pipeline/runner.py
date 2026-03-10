import asyncio
from orion.pipeline.context import PipelineContext
from orion.api.ws import ws_manager

class PipelineRunner:
    """Mock runner to supply missing pipeline runtime functions"""

    async def _wait_for_approval(self, run_id: str, element: str):
        # We simulate the user responding automatically or we block until testing fires event
        if run_id not in ws_manager._approval_events:
            ws_manager._approval_events[run_id] = asyncio.Event()

        await ws_manager._approval_events[run_id].wait()
        return ws_manager._approval_results.get(run_id, {})

    async def _check_cost_gate(self, ctx: PipelineContext):
        pass # Budget check logic dummy

pipeline_runner = PipelineRunner()
