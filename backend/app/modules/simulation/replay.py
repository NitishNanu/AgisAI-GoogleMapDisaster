from collections import deque
from datetime import datetime, timezone

import structlog
from pydantic import BaseModel

from app.modules.simulation.schemas import (
    DigitalTwinCityState,
)

logger = structlog.get_logger("aegis_ai.simulation.replay")


class ReplaySnapshot(BaseModel):
    tick: int
    timestamp: str
    random_seed: int
    active_disasters_count: int
    safe_citizens: int
    endangered_citizens: int
    evacuating_citizens: int
    injured_citizens: int
    rescued_citizens: int
    weather_summary: str
    traffic_summary: str
    events_count: int
    state_snapshot: DigitalTwinCityState | None = None


class SimulationReplayManager:
    def __init__(self, max_snapshots: int = 500) -> None:
        self.max_snapshots = max_snapshots
        self._history: deque[ReplaySnapshot] = deque(maxlen=max_snapshots)
        self._checkpoints: dict[str, ReplaySnapshot] = {}

    def record_tick_snapshot(
        self,
        tick: int,
        city_state: DigitalTwinCityState,
        random_seed: int = 42,
    ) -> ReplaySnapshot:
        snapshot = ReplaySnapshot(
            tick=tick,
            timestamp=datetime.now(timezone.utc).isoformat(),
            random_seed=random_seed,
            active_disasters_count=city_state.active_disasters_count,
            safe_citizens=city_state.safe_citizens,
            endangered_citizens=city_state.endangered_citizens,
            evacuating_citizens=city_state.evacuating_citizens,
            injured_citizens=city_state.injured_citizens,
            rescued_citizens=city_state.rescued_citizens,
            weather_summary=f"{city_state.weather.condition} ({city_state.weather.temperature_celsius}C, {city_state.weather.wind_speed_kmh}km/h)",
            traffic_summary=f"congestion x{city_state.traffic.road_congestion_factor} ({city_state.traffic.average_speed_kmh}km/h avg)",
            events_count=len(city_state.recent_events),
            state_snapshot=None,
        )
        self._history.append(snapshot)
        logger.debug("replay_snapshot_recorded", tick=tick, history_len=len(self._history))
        return snapshot

    def get_history(self, limit: int = 50) -> list[ReplaySnapshot]:
        items = list(self._history)[-limit:]
        items.reverse()
        return items

    def get_snapshot_by_tick(self, target_tick: int) -> ReplaySnapshot | None:
        for s in self._history:
            if s.tick == target_tick:
                return s
        return None

    def create_named_checkpoint(self, name: str, snapshot: ReplaySnapshot) -> None:
        self._checkpoints[name] = snapshot
        logger.info("named_checkpoint_saved", name=name, tick=snapshot.tick)

    def get_checkpoint(self, name: str) -> ReplaySnapshot | None:
        return self._checkpoints.get(name)


replay_manager = SimulationReplayManager()
