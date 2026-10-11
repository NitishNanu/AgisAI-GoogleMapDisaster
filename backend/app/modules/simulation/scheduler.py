"""
AegisAI Simulation Module â€” Background Scheduler.

Uses APScheduler to run the DigitalTwinEngine tick loop in the background.
Configured as an AsyncIOScheduler since the engine operations are async.
"""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config.settings import settings
from app.modules.simulation.engine import engine

logger = structlog.get_logger("aegis_ai.simulation.scheduler")

# Global scheduler instance
scheduler = AsyncIOScheduler()


async def scheduled_tick() -> None:
    """The background job that triggers the simulation tick."""
    if engine.is_running:
        try:
            await engine.tick()
        except Exception as e:
            logger.error("scheduled_tick_failed", error=str(e), exc_info=True)


def setup_scheduler() -> None:
    """
    Initialize the APScheduler and add the tick job based on config.
    Should be called during application startup.
    """
    if not settings.SIMULATION_AUTO_START:
        logger.info("simulation_scheduler_disabled_in_config")
        return

    # Add the job to run every X seconds
    scheduler.add_job(
        scheduled_tick,
        "interval",
        seconds=settings.SIMULATION_TICK_INTERVAL_SECONDS,
        id="simulation_tick_job",
        replace_existing=True,
    )

    # Start the scheduler (non-blocking)
    scheduler.start()

    # Mark engine as running
    engine.is_running = True

    logger.info(
        "simulation_scheduler_started",
        interval_seconds=settings.SIMULATION_TICK_INTERVAL_SECONDS
    )


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("simulation_scheduler_shutdown")
