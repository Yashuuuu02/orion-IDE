import asyncio
import logging
from sqlalchemy import text
from orion.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def cleanup_loop():
    while True:
        try:
            async with AsyncSessionLocal() as db:
                # 1. Prune old WS buffers (2h)
                await db.execute(text("DELETE FROM ws_event_buffer WHERE created_at < NOW() - INTERVAL '2 hours'"))
                
                # 2. Expire disconnected sessions (1h)
                await db.execute(text("UPDATE orion_sessions SET ws_status='disconnected' WHERE ws_status='active' AND ws_last_seen < NOW() - INTERVAL '1 hour'"))
                
                # 3. Clean up expired fast results
                await db.execute(text("UPDATE pipeline_runs SET fast_result=NULL, fast_result_expires_at=NULL WHERE fast_result IS NOT NULL AND fast_result_expires_at < NOW()"))
                
                # 4. Clean up expired approval states
                await db.execute(text("UPDATE pipeline_runs SET approval_state='expired', approval_expires_at=NULL WHERE approval_state='pending' AND approval_expires_at < NOW()"))
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
        
        await asyncio.sleep(60)  # Run every minute

async def start_cleanup_task() -> asyncio.Task:
    logger.info("Starting background cleanup task...")
    return asyncio.create_task(cleanup_loop())

async def stop_cleanup_task(task: asyncio.Task):
    logger.info("Stopping background cleanup task...")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
