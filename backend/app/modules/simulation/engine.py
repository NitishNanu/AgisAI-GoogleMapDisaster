"""
AegisAI Simulation Module — Digital Twin Engine.

Production-grade singleton engine simulating the virtual city.
Implements a full agent-based simulation with:

  - Weather evolution (random walk with storm thresholds)
  - Traffic simulation (disaster + weather-aware congestion)
  - Citizen agent state machine (SAFE ? ENDANGERED ? EVACUATING/INJURED ? RESCUED)
  - Road network state (congestion + blockage tracking)
  - Building damage modeling
  - Bounded event log ring buffer
  - Optional autonomous random incident spawning
  - RabbitMQ state publishing (fire-and-forget, non-blocking)

The engine is a process-wide singleton accessed via the `engine` module-level
instance. All state mutation is synchronous (no async locks needed since
APScheduler runs ticks in a single thread).
"""

import asyncio
import json
import math
import random
from collections import deque
from datetime import datetime, timezone
from typing import Any

import structlog

from app.core.config.settings import settings
from app.modules.simulation.schemas import (
    BuildingState,
    CitizenState,
    CitizenStatus,
    DigitalTwinCityState,
    RoadSegment,
    SimulationConfig,
    SimulationEvent,
    SimulationEventType,
    TrafficCondition,
    WeatherCondition,
)

logger = structlog.get_logger("aegis_ai.simulation.engine")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two WGS84 points."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class DigitalTwinEngine:
    """
    Singleton Digital Twin City Simulator.

    Maintains complete city state and processes simulation ticks.
    Thread-safe for reading; write operations happen only inside
    the tick() method which is called from a single APScheduler thread.
    """

    _instance: "DigitalTwinEngine | None" = None
    _initialized: bool = False

    def __new__(cls) -> "DigitalTwinEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self.is_running: bool = False
        self.tick_count: int = 0
        self.last_tick_time: datetime | None = None

        # Engine configuration — mutable at runtime
        self.config: dict[str, Any] = {
            "weather_multiplier": 1.0,
            "traffic_multiplier": 1.0,
            "citizen_panic_factor": 1.0,
            "auto_spawn_incidents": False,
        }

        # Active disaster locations for citizen proximity calculations
        # List of (lat, lon, severity_value) tuples updated by force_spawn_incident
        self._active_disaster_locations: list[tuple[float, float, float]] = []

        # Environmental state
        self.weather: WeatherCondition = WeatherCondition()
        self.traffic: TrafficCondition = TrafficCondition()

        # Entity state
        self.buildings: list[BuildingState] = self._init_buildings()
        self.roads: list[RoadSegment] = self._init_roads()
        self.citizens: list[CitizenState] = self._init_citizens()
        self.active_disasters_count: int = 0

        # Bounded event log ring buffer
        max_events = settings.SIMULATION_MAX_EVENT_LOG_SIZE
        self._event_log: deque[SimulationEvent] = deque(maxlen=max_events)

        self._initialized = True
        logger.info("digital_twin_engine_initialized", citizens=len(self.citizens))

    # --- Initialization ------------------------------------------------------

    def _init_buildings(self) -> list[BuildingState]:
        """Initialize the city's building inventory around Chandigarh, India."""
        return [
            BuildingState(
                id=1, name="Government Multi-Specialty Hospital",
                building_type="HOSPITAL",
                latitude=30.7352, longitude=76.7756,
                capacity=500, occupancy=410,
            ),
            BuildingState(
                id=2, name="PGI Emergency Medical Center",
                building_type="HOSPITAL",
                latitude=30.7646, longitude=76.7754,
                capacity=900, occupancy=720,
            ),
            BuildingState(
                id=3, name="Sector 17 Community Shelter",
                building_type="SHELTER",
                latitude=30.7398, longitude=76.7821,
                capacity=1000, occupancy=250,
            ),
            BuildingState(
                id=4, name="Sector 22 Emergency Shelter",
                building_type="SHELTER",
                latitude=30.7339, longitude=76.7727,
                capacity=700, occupancy=180,
            ),
            BuildingState(
                id=5, name="Sector 17 Commercial Complex",
                building_type="COMMERCIAL",
                latitude=30.7399, longitude=76.7830,
                capacity=5000, occupancy=3500,
            ),
            BuildingState(
                id=6, name="Sector 22 Residential Block A",
                building_type="RESIDENTIAL",
                latitude=30.7340, longitude=76.7720,
                capacity=2000, occupancy=1800,
            ),
            BuildingState(
                id=7, name="Industrial Area Zone 1",
                building_type="INDUSTRIAL",
                latitude=30.7150, longitude=76.7600,
                capacity=500, occupancy=300,
            ),
        ]

    def _init_roads(self) -> list[RoadSegment]:
        """Initialize key road segments for the digital twin road network."""
        return [
            RoadSegment(
                id=1, name="NH-5 (Chandigarh-Ambala Highway)",
                start_latitude=30.7500, start_longitude=76.8100,
                end_latitude=30.7000, end_longitude=76.8000,
                length_km=6.5, congestion_factor=1.0,
            ),
            RoadSegment(
                id=2, name="Sector 17 - Sector 22 Link Road",
                start_latitude=30.7399, start_longitude=76.7830,
                end_latitude=30.7339, end_longitude=76.7727,
                length_km=1.2, congestion_factor=1.0,
            ),
            RoadSegment(
                id=3, name="PGI Access Road",
                start_latitude=30.7646, start_longitude=76.7754,
                end_latitude=30.7500, end_longitude=76.7750,
                length_km=1.6, congestion_factor=1.0,
            ),
            RoadSegment(
                id=4, name="Industrial Area Service Road",
                start_latitude=30.7150, start_longitude=76.7600,
                end_latitude=30.7200, end_longitude=76.7700,
                length_km=1.3, congestion_factor=1.0,
            ),
            RoadSegment(
                id=5, name="Mohali Bypass",
                start_latitude=30.7046, start_longitude=76.7179,
                end_latitude=30.7200, end_longitude=76.7400,
                length_km=3.8, congestion_factor=1.0,
            ),
        ]

    def _init_citizens(self) -> list[CitizenState]:
        """
        Initialize 150 citizen agents distributed across the city.

        Citizens are clustered around key city zones (commercial, residential,
        industrial) with realistic age distribution.
        """
        zones = [
            (30.7399, 76.7830, 60),  # Sector 17 commercial
            (30.7339, 76.7727, 40),  # Sector 22 residential
            (30.7150, 76.7600, 25),  # Industrial area
            (30.7046, 76.7179, 15),  # Mohali
            (30.6942, 76.8606, 10),  # Panchkula
        ]
        citizens: list[CitizenState] = []
        cid = 1
        for center_lat, center_lon, count in zones:
            for _ in range(count):
                age = random.choices(
                    [random.randint(5, 17), random.randint(18, 65), random.randint(66, 90)],
                    weights=[15, 65, 20],
                )[0]
                citizens.append(
                    CitizenState(
                        id=cid,
                        name=f"Citizen-{cid}",
                        latitude=center_lat + random.uniform(-0.01, 0.01),
                        longitude=center_lon + random.uniform(-0.01, 0.01),
                        status=CitizenStatus.SAFE,
                        age=age,
                        needs_medical=False,
                    )
                )
                cid += 1
        return citizens

    # --- Public Interface ----------------------------------------------------

    def reset(self) -> None:
        """Reset the simulation to its clean initial state."""
        self.is_running = False
        self.tick_count = 0
        self.last_tick_time = None
        self.weather = WeatherCondition()
        self.traffic = TrafficCondition()
        self.buildings = self._init_buildings()
        self.roads = self._init_roads()
        self.citizens = self._init_citizens()
        self.active_disasters_count = 0
        self._active_disaster_locations = []
        self._event_log.clear()
        logger.info("simulation_engine_reset")
        self._log_event(SimulationEventType.TICK_COMPLETED, "Simulation engine reset to initial state.")

    def get_event_log(self) -> list[SimulationEvent]:
        """Return the current event log as a list (newest first)."""
        return list(reversed(self._event_log))

    def update_config(self, config: SimulationConfig) -> None:
        """Apply new runtime configuration to the engine."""
        self.config["weather_multiplier"] = config.weather_multiplier
        self.config["traffic_multiplier"] = config.traffic_multiplier
        self.config["citizen_panic_factor"] = config.citizen_panic_factor
        self.config["auto_spawn_incidents"] = config.auto_spawn_incidents
        logger.info("simulation_config_updated", config=self.config)

    def force_add_disaster(
        self, lat: float, lon: float, severity: str
    ) -> None:
        """Register an external incident in the disaster proximity tracker."""
        _SEVERITY_VALUE = {"LOW": 0.5, "MEDIUM": 1.0, "HIGH": 2.0, "CRITICAL": 4.0}
        severity_val = _SEVERITY_VALUE.get(severity, 1.0)
        self._active_disaster_locations.append((lat, lon, severity_val))
        self.active_disasters_count += 1
        self._log_event(
            SimulationEventType.INCIDENT_SPAWNED,
            f"Incident registered at ({lat:.4f}, {lon:.4f}), severity: {severity}",
            {"latitude": lat, "longitude": lon, "severity": severity},
        )

    def get_snapshot(self) -> DigitalTwinCityState:
        """Construct and return current full city state snapshot."""
        state_counts = {s: 0 for s in CitizenStatus}
        for c in self.citizens:
            state_counts[c.status] = state_counts.get(c.status, 0) + 1

        return DigitalTwinCityState(
            tick_count=self.tick_count,
            active_disasters_count=self.active_disasters_count,
            total_citizens=len(self.citizens),
            safe_citizens=state_counts[CitizenStatus.SAFE],
            endangered_citizens=state_counts[CitizenStatus.ENDANGERED],
            evacuating_citizens=state_counts[CitizenStatus.EVACUATING],
            injured_citizens=state_counts[CitizenStatus.INJURED],
            rescued_citizens=state_counts[CitizenStatus.RESCUED],
            weather=self.weather,
            traffic=self.traffic,
            buildings=self.buildings,
            roads=self.roads,
            citizens=self.citizens,
            recent_events=self.get_event_log()[:10],
        )

    # --- Tick Processing -----------------------------------------------------

    async def tick(self) -> DigitalTwinCityState:
        """
        Process a single simulation tick.

        Order of operations:
          1. Increment tick counter, record timestamp
          2. Simulate weather evolution
          3. Simulate traffic based on weather + disasters
          4. Simulate road segment states
          5. Simulate citizen agent state transitions
          6. Simulate building damage
          7. Optionally spawn a random incident
          8. Build and publish the state snapshot

        Returns the complete city state snapshot for this tick.
        """
        self.tick_count += 1
        self.last_tick_time = datetime.now(timezone.utc)

        self._simulate_weather()
        self._simulate_traffic()
        self._simulate_roads()
        self._simulate_citizens()
        self._simulate_buildings()

        if self.config.get("auto_spawn_incidents") and self.tick_count % 20 == 0:
            self._spawn_random_incident()

        # Count citizen states
        state_counts = {s: 0 for s in CitizenStatus}
        for c in self.citizens:
            state_counts[c.status] = state_counts.get(c.status, 0) + 1

        self._log_event(
            SimulationEventType.TICK_COMPLETED,
            f"Tick {self.tick_count} processed. "
            f"Safe: {state_counts[CitizenStatus.SAFE]}, "
            f"Endangered: {state_counts[CitizenStatus.ENDANGERED]}",
            {"tick": self.tick_count},
        )

        state = DigitalTwinCityState(
            tick_count=self.tick_count,
            active_disasters_count=self.active_disasters_count,
            total_citizens=len(self.citizens),
            safe_citizens=state_counts[CitizenStatus.SAFE],
            endangered_citizens=state_counts[CitizenStatus.ENDANGERED],
            evacuating_citizens=state_counts[CitizenStatus.EVACUATING],
            injured_citizens=state_counts[CitizenStatus.INJURED],
            rescued_citizens=state_counts[CitizenStatus.RESCUED],
            weather=self.weather,
            traffic=self.traffic,
            buildings=self.buildings,
            roads=self.roads,
            citizens=self.citizens,
            recent_events=self.get_event_log()[:10],
        )

        logger.debug(
            "tick_processed",
            tick=self.tick_count,
            disasters=self.active_disasters_count,
            safe=state_counts[CitizenStatus.SAFE],
        )

        # 1. Record snapshot in Replay Manager
        try:
            from app.modules.simulation.replay import replay_manager  # noqa: PLC0415
            replay_manager.record_tick_snapshot(self.tick_count, state)
        except Exception as replay_err:
            logger.warning("replay_recording_failed", error=str(replay_err))

        # 2. Publish to RabbitMQ in background — non-blocking
        try:
            asyncio.create_task(self._publish_state(state))
        except Exception:
            pass

        # 3. Compute deltas and broadcast to WebSockets live stream
        try:
            from app.core.websocket.manager import ws_manager  # noqa: PLC0415
            
            # Compute Deltas (only sending what changed)
            if not hasattr(self, '_last_state_cache'):
                self._last_state_cache = {'citizens': {}, 'buildings': {}}

            changed_citizens = []
            for c in self.citizens:
                last_c = self._last_state_cache['citizens'].get(c.id)
                if not last_c or last_c.status != c.status or last_c.latitude != c.latitude:
                    changed_citizens.append(c.model_dump())
                    self._last_state_cache['citizens'][c.id] = c.model_copy()

            changed_buildings = []
            for b in self.buildings:
                last_b = self._last_state_cache['buildings'].get(b.id)
                if not last_b or last_b.damage_percent != b.damage_percent or last_b.occupancy != b.occupancy:
                    changed_buildings.append(b.model_dump())
                    self._last_state_cache['buildings'][b.id] = b.model_copy()

            delta_payload = {
                "tick": self.tick_count,
                "weather": self.weather.model_dump(),
                "traffic": self.traffic.model_dump(),
                "citizens": changed_citizens,
                "buildings": changed_buildings,
                "recent_events": [e.model_dump() for e in list(self._event_log)[-5:]],
            }
            asyncio.create_task(
                ws_manager.broadcast_to_channel("simulation", "SIMULATION_TICK_DELTA", delta_payload)
            )
        except Exception as ws_err:
            logger.warning("websocket_broadcast_failed", error=str(ws_err))

        return state

    # --- Subsystem Simulators ------------------------------------------------

    def _simulate_weather(self) -> None:
        """Evolve weather state using a bounded random walk model."""
        multiplier = self.config["weather_multiplier"]

        self.weather.temperature_celsius = max(
            -10.0,
            min(45.0, self.weather.temperature_celsius + random.uniform(-0.5, 0.5) * multiplier),
        )
        self.weather.wind_speed_kmh = max(
            0.0,
            min(120.0, self.weather.wind_speed_kmh + random.uniform(-2.0, 3.0) * multiplier),
        )
        self.weather.humidity_percent = max(
            0.0,
            min(100.0, self.weather.humidity_percent + random.uniform(-2.0, 2.0)),
        )
        self.weather.visibility_km = max(
            0.1,
            min(20.0, self.weather.visibility_km + random.uniform(-0.5, 0.5)),
        )

        # Storm threshold
        if self.weather.wind_speed_kmh > 60:
            self.weather.condition = "STORM"
            self.weather.visibility_km = min(self.weather.visibility_km, 2.0)
        elif self.weather.wind_speed_kmh > 30:
            self.weather.condition = "RAIN"
        elif random.random() < 0.05:  # 5% chance of fog
            self.weather.condition = "FOG"
            self.weather.visibility_km = min(self.weather.visibility_km, 1.5)
        else:
            self.weather.condition = "CLEAR"

        if self.weather.condition in ("STORM", "RAIN") and self.weather.condition != "STORM":
            pass  # only log significant changes
        elif self.weather.condition == "STORM":
            self._log_event(
                SimulationEventType.WEATHER_CHANGED,
                f"Storm conditions: wind {self.weather.wind_speed_kmh:.1f} km/h",
                {"condition": "STORM"},
            )

    def _simulate_traffic(self) -> None:
        """
        Model road traffic as a function of weather severity and active disasters.

        Disaster proximity increases congestion on nearby roads.
        Storm conditions impose a blanket congestion penalty.
        """
        multiplier = self.config["traffic_multiplier"]
        weather_penalty = 1.3 if self.weather.condition == "STORM" else (
            1.1 if self.weather.condition == "RAIN" else 1.0
        )
        disaster_penalty = 1.0 + (self.active_disasters_count * 0.15)

        base_congestion = weather_penalty * disaster_penalty * multiplier
        self.traffic.road_congestion_factor = round(
            max(1.0, min(5.0, base_congestion + random.uniform(-0.1, 0.1))), 2
        )
        self.traffic.average_speed_kmh = round(
            max(5.0, 50.0 / self.traffic.road_congestion_factor), 1
        )

    def _simulate_roads(self) -> None:
        """
        Update road segment states.

        Roads near active disasters may become blocked.
        Blocked roads have a 10% chance per tick of clearing.
        """
        for road in self.roads:
            # Recovery chance for blocked roads
            if road.is_blocked and random.random() < 0.10:
                road.is_blocked = False
                road.blocked_reason = None
                road.congestion_factor = 1.0
                self._log_event(
                    SimulationEventType.ROAD_CLEARED,
                    f"Road '{road.name}' has been cleared.",
                    {"road_id": road.id},
                )
                continue

            # Check proximity to active disasters
            road_mid_lat = (road.start_latitude + road.end_latitude) / 2
            road_mid_lon = (road.start_longitude + road.end_longitude) / 2

            for dis_lat, dis_lon, sev_val in self._active_disaster_locations:
                dist_km = _haversine_km(road_mid_lat, road_mid_lon, dis_lat, dis_lon)

                if dist_km < 0.5 and sev_val >= 3.0 and not road.is_blocked:
                    # High-severity disaster very close — may block the road
                    if random.random() < 0.20:
                        road.is_blocked = True
                        road.blocked_reason = "DISASTER_PROXIMITY"
                        self.traffic.blocked_roads_count += 1
                        self._log_event(
                            SimulationEventType.ROAD_BLOCKED,
                            f"Road '{road.name}' blocked due to nearby disaster.",
                            {"road_id": road.id, "distance_km": round(dist_km, 2)},
                        )
                elif dist_km < 2.0:
                    # Nearby disaster increases congestion
                    road.congestion_factor = round(
                        min(4.0, 1.0 + (2.0 - dist_km) * sev_val * 0.3), 2
                    )

    def _simulate_citizens(self) -> None:
        """
        Agent-based citizen simulation with full state machine transitions.

        State transitions driven by:
          - Proximity to active disaster locations (? ENDANGERED)
          - Time in ENDANGERED state (? EVACUATING or INJURED)
          - Rescue probability for INJURED citizens
          - Random movement for SAFE/EVACUATING citizens
        """
        panic_factor = self.config.get("citizen_panic_factor", 1.0)
        _ENDANGERMENT_RADIUS_KM = 0.5  # 500m from disaster = endangered

        for citizen in self.citizens:
            # Skip deceased citizens
            if citizen.status == CitizenStatus.DECEASED:
                continue

            # Check proximity to active disasters
            nearest_disaster_dist = float("inf")
            nearest_severity = 0.0
            for dis_lat, dis_lon, sev_val in self._active_disaster_locations:
                dist = _haversine_km(
                    citizen.latitude, citizen.longitude, dis_lat, dis_lon
                )
                if dist < nearest_disaster_dist:
                    nearest_disaster_dist = dist
                    nearest_severity = sev_val

            # State machine transitions
            if citizen.status == CitizenStatus.SAFE:
                if nearest_disaster_dist < _ENDANGERMENT_RADIUS_KM * panic_factor:
                    citizen.status = CitizenStatus.ENDANGERED
                    self._log_event(
                        SimulationEventType.CITIZEN_ENDANGERED,
                        f"Citizen {citizen.id} is endangered at ({citizen.latitude:.4f}, {citizen.longitude:.4f})",
                        {"citizen_id": citizen.id},
                    )
                else:
                    # Random movement within safe zone
                    citizen.latitude += random.uniform(-0.0002, 0.0002)
                    citizen.longitude += random.uniform(-0.0002, 0.0002)

            elif citizen.status == CitizenStatus.ENDANGERED:
                # Evacuate or get injured based on severity and chance
                injury_chance = min(0.4, 0.05 * nearest_severity * panic_factor)
                evacuate_chance = min(0.6, 0.15 * (1 / max(0.1, nearest_disaster_dist)))

                roll = random.random()
                if roll < injury_chance:
                    citizen.status = CitizenStatus.INJURED
                    citizen.needs_medical = True
                    self._log_event(
                        SimulationEventType.CITIZEN_INJURED,
                        f"Citizen {citizen.id} injured.",
                        {"citizen_id": citizen.id},
                    )
                elif roll < injury_chance + evacuate_chance:
                    citizen.status = CitizenStatus.EVACUATING
                    self._log_event(
                        SimulationEventType.CITIZEN_EVACUATING,
                        f"Citizen {citizen.id} evacuating.",
                        {"citizen_id": citizen.id},
                    )

            elif citizen.status == CitizenStatus.EVACUATING:
                # Move away from disaster each tick
                if self._active_disaster_locations:
                    nearest_dis_lat, nearest_dis_lon, _ = min(
                        self._active_disaster_locations,
                        key=lambda d: _haversine_km(
                            citizen.latitude, citizen.longitude, d[0], d[1]
                        ),
                    )
                    # Move in opposite direction
                    citizen.latitude += (citizen.latitude - nearest_dis_lat) * 0.01
                    citizen.longitude += (citizen.longitude - nearest_dis_lon) * 0.01

                if random.random() < 0.10:
                    citizen.status = CitizenStatus.SAFE
                    citizen.assigned_shelter_id = random.choice([1, 2, 3, 4])

            elif citizen.status == CitizenStatus.INJURED:
                # Chance of being rescued each tick
                if random.random() < 0.15:
                    citizen.status = CitizenStatus.RESCUED
                    citizen.needs_medical = False
                    self._log_event(
                        SimulationEventType.CITIZEN_RESCUED,
                        f"Citizen {citizen.id} rescued.",
                        {"citizen_id": citizen.id},
                    )

    def _simulate_buildings(self) -> None:
        """
        Simulate building damage from nearby active disasters.

        Buildings within 300m of a CRITICAL disaster receive damage.
        Damage compounds over time but caps at 100%.
        """
        for building in self.buildings:
            for dis_lat, dis_lon, sev_val in self._active_disaster_locations:
                dist_km = _haversine_km(
                    building.latitude, building.longitude, dis_lat, dis_lon
                )
                if dist_km < 0.3 and sev_val >= 3.0:
                    damage_increase = random.uniform(0, 1.5) * sev_val
                    building.damage_percent = min(100.0, building.damage_percent + damage_increase)
                    if building.damage_percent > 20 and not building.is_damaged:
                        building.is_damaged = True
                        self._log_event(
                            SimulationEventType.BUILDING_DAMAGED,
                            f"Building '{building.name}' is now damaged ({building.damage_percent:.0f}%)",
                            {"building_id": building.id, "damage_pct": building.damage_percent},
                        )
                    # Reduce occupancy as people flee damaged buildings
                    building.occupancy = max(0, int(building.occupancy * 0.99))

    def _spawn_random_incident(self) -> None:
        """
        Autonomously spawn a random incident for simulation stress-testing.

        Only called when `auto_spawn_incidents` config is enabled.
        Uses Chandigarh coordinates as the bounding box.
        """
        types = ["FIRE", "FLOOD", "BUILDING_COLLAPSE", "GAS_LEAK", "ACCIDENT"]
        severities = ["LOW", "MEDIUM", "HIGH"]
        weights = [60, 30, 10]

        lat = random.uniform(30.6900, 30.7700)
        lon = random.uniform(76.7100, 76.8700)
        incident_type = random.choice(types)
        severity = random.choices(severities, weights=weights)[0]

        _SEVERITY_VALUE = {"LOW": 0.5, "MEDIUM": 1.0, "HIGH": 2.0, "CRITICAL": 4.0}
        self._active_disaster_locations.append((lat, lon, _SEVERITY_VALUE[severity]))
        self.active_disasters_count += 1

        self._log_event(
            SimulationEventType.INCIDENT_SPAWNED,
            f"Auto-spawned {incident_type} ({severity}) at ({lat:.4f}, {lon:.4f})",
            {"type": incident_type, "severity": severity},
        )
        logger.info("auto_incident_spawned", type=incident_type, severity=severity)

    # --- Event Log -----------------------------------------------------------

    def _log_event(
        self,
        event_type: SimulationEventType,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append a simulation event to the bounded ring buffer."""
        event = SimulationEvent(
            tick=self.tick_count,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=description,
            metadata=metadata or {},
        )
        self._event_log.append(event)

    # --- RabbitMQ Publishing -------------------------------------------------

    _rmq_connection: Any = None
    _rmq_channel: Any = None
    _rmq_exchange: Any = None

    async def _get_rabbitmq_exchange(self) -> Any:
        """Get or initialize a persistent RabbitMQ channel and exchange."""
        import aio_pika  # noqa: PLC0415

        if self._rmq_connection is None or self._rmq_connection.is_closed:
            self._rmq_connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL,
                timeout=0.2,
            )
            self._rmq_channel = None
            self._rmq_exchange = None

        if self._rmq_channel is None or self._rmq_channel.is_closed:
            self._rmq_channel = await self._rmq_connection.channel()
            self._rmq_exchange = await self._rmq_channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

        return self._rmq_exchange

    async def _publish_state(self, state: DigitalTwinCityState) -> None:
        """
        Publish the tick state snapshot to RabbitMQ.

        Fire-and-forget: failures are logged but never propagate to the caller.
        Reuses persistent connection/channel to eliminate per-tick TCP+AMQP handshake overhead.
        """
        try:
            import aio_pika  # noqa: PLC0415

            exchange = await self._get_rabbitmq_exchange()
            message = aio_pika.Message(
                body=json.dumps(
                    state.model_dump(exclude={"citizens", "buildings", "roads"}),
                    default=str,
                ).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT,
            )
            await exchange.publish(message, routing_key="simulation.tick")
        except Exception as exc:
            # Reset cached connection so next tick attempts a fresh reconnect
            self._rmq_connection = None
            self._rmq_channel = None
            self._rmq_exchange = None
            logger.debug("rabbitmq_publish_failed", error=str(exc))


    @property
    def event_log(self) -> list[SimulationEvent]:
        """Return shallow copy of event log deque as a list."""
        return list(self._event_log)


# --- Module-level singleton ---------------------------------------------------
engine = DigitalTwinEngine()
