"""
AegisAI Simulation Module — Pydantic v2 Schemas.

Defines the complete Digital Twin state representation including:
  - WeatherCondition: Environmental parameters
  - TrafficCondition: Road network congestion
  - BuildingState: Fixed infrastructure (hospitals, shelters, residential)
  - RoadSegment: Road network elements with congestion tracking
  - CitizenState: Individual citizen agents with full state machine
  - SimulationEvent: Timestamped event log entries
  - DigitalTwinCityState: Complete tick snapshot
  - SimulationStateResponse: Engine metadata response
  - SimulationConfig: Runtime configuration
  - SimulationActionRequest: Control commands
  - SpawnIncidentRequest: Manual incident injection
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# --- Enums -------------------------------------------------------------------

class CitizenStatus(str, Enum):
    """Agent-based citizen status state machine."""

    SAFE = "SAFE"
    ENDANGERED = "ENDANGERED"
    EVACUATING = "EVACUATING"
    INJURED = "INJURED"
    RESCUED = "RESCUED"
    DECEASED = "DECEASED"


class BuildingType(str, Enum):
    """Building classification for the digital twin."""

    HOSPITAL = "HOSPITAL"
    SHELTER = "SHELTER"
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    INDUSTRIAL = "INDUSTRIAL"
    GOVERNMENT = "GOVERNMENT"


class SimulationEventType(str, Enum):
    """Types of events that can occur during simulation."""

    INCIDENT_SPAWNED = "INCIDENT_SPAWNED"
    CITIZEN_ENDANGERED = "CITIZEN_ENDANGERED"
    CITIZEN_EVACUATING = "CITIZEN_EVACUATING"
    CITIZEN_RESCUED = "CITIZEN_RESCUED"
    CITIZEN_INJURED = "CITIZEN_INJURED"
    WEATHER_CHANGED = "WEATHER_CHANGED"
    ROAD_BLOCKED = "ROAD_BLOCKED"
    ROAD_CLEARED = "ROAD_CLEARED"
    BUILDING_DAMAGED = "BUILDING_DAMAGED"
    TEAM_DISPATCHED = "TEAM_DISPATCHED"
    SHELTER_OPENED = "SHELTER_OPENED"
    TICK_COMPLETED = "TICK_COMPLETED"


# --- Environmental State -----------------------------------------------------

class WeatherCondition(BaseModel):
    """Current weather state in the simulation."""

    condition: str = Field(default="CLEAR", description="CLEAR | RAIN | STORM | FOG")
    temperature_celsius: float = Field(default=22.0, description="Ambient temperature")
    wind_speed_kmh: float = Field(default=10.0, ge=0, description="Wind speed in km/h")
    wind_direction_degrees: float = Field(default=180.0, ge=0, le=360)
    visibility_km: float = Field(default=10.0, ge=0)
    humidity_percent: float = Field(default=60.0, ge=0, le=100)


class TrafficCondition(BaseModel):
    """Current road traffic state in the digital twin."""

    road_congestion_factor: float = Field(
        default=1.0,
        description="Multiplier on travel time: 1.0 = normal, 2.0 = severe congestion",
    )
    average_speed_kmh: float = Field(default=45.0, ge=0)
    blocked_roads_count: int = Field(default=0, ge=0)


# --- Entity State -------------------------------------------------------------

class BuildingState(BaseModel):
    """Snapshot of a building entity in the digital twin."""

    id: int
    name: str
    building_type: str
    latitude: float
    longitude: float
    capacity: int = Field(default=0, ge=0)
    occupancy: int = Field(default=0, ge=0)
    is_damaged: bool = Field(default=False)
    damage_percent: float = Field(default=0.0, ge=0.0, le=100.0)


class RoadSegment(BaseModel):
    """A road segment entity in the digital twin road network."""

    id: int
    name: str
    start_latitude: float
    start_longitude: float
    end_latitude: float
    end_longitude: float
    length_km: float = Field(default=1.0, ge=0)
    congestion_factor: float = Field(
        default=1.0,
        description="1.0 = free flow; >2.0 = severe congestion",
    )
    is_blocked: bool = Field(default=False, description="True if road is impassable")
    blocked_reason: str | None = Field(
        default=None, description="Reason for blockage (e.g., FLOOD, DEBRIS)"
    )


class CitizenState(BaseModel):
    """
    Individual citizen agent state in the simulation.

    Citizens follow a state machine:
      SAFE ? ENDANGERED ? EVACUATING ? SAFE (successful evacuation)
                        ? INJURED    ? RESCUED
                                     ? DECEASED
    """

    id: int
    name: str
    latitude: float
    longitude: float
    status: CitizenStatus = Field(default=CitizenStatus.SAFE)
    age: int = Field(default=30, ge=0, le=120)
    needs_medical: bool = Field(default=False)
    assigned_shelter_id: int | None = Field(default=None)
    nearest_incident_id: int | None = Field(default=None)


# --- Event Log ---------------------------------------------------------------

class SimulationEvent(BaseModel):
    """A timestamped event entry in the simulation event log."""

    tick: int
    event_type: SimulationEventType
    timestamp: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- City State Snapshot -----------------------------------------------------

class DigitalTwinCityState(BaseModel):
    """
    Complete snapshot of the digital twin city state at a given tick.

    Represents the full state of the simulated city including all
    environmental conditions, infrastructure states, and citizen agents.
    This is the primary payload published to RabbitMQ on each tick.
    """

    tick_count: int
    active_disasters_count: int
    total_citizens: int
    safe_citizens: int
    endangered_citizens: int
    evacuating_citizens: int = Field(default=0)
    injured_citizens: int = Field(default=0)
    rescued_citizens: int = Field(default=0)
    weather: WeatherCondition
    traffic: TrafficCondition
    buildings: list[BuildingState]
    roads: list[RoadSegment] = Field(default_factory=list)
    citizens: list[CitizenState]
    recent_events: list[SimulationEvent] = Field(default_factory=list)


# --- Engine Control -----------------------------------------------------------

class SimulationConfig(BaseModel):
    """Runtime configuration for the simulation engine."""

    weather_multiplier: float = Field(
        default=1.0, ge=0.1, le=10.0,
        description="Amplifies weather severity effects on spread and traffic",
    )
    traffic_multiplier: float = Field(
        default=1.0, ge=0.1, le=10.0,
        description="Amplifies traffic congestion effects on response times",
    )
    citizen_panic_factor: float = Field(
        default=1.0, ge=0.0, le=5.0,
        description="Modulates how quickly citizens transition to ENDANGERED state",
    )
    auto_spawn_incidents: bool = Field(
        default=False,
        description="If true, the engine automatically spawns random incidents",
    )


class SimulationStateResponse(BaseModel):
    """Current simulation engine operational state — returned by the control API."""

    is_running: bool
    current_tick: int
    active_incidents: int
    available_resources: int
    config: dict[str, Any]
    last_tick_time: datetime | None = None


# --- Control Requests ---------------------------------------------------------

class SimulationActionRequest(BaseModel):
    """
    Simulation engine control command.

    Supported actions:
      - start: Begin automatic tick processing
      - stop: Halt automatic tick processing
      - tick: Manually process one tick regardless of running state
      - reset: Reset entire engine to initial state (destroys all state!)
    """

    action: str = Field(
        ...,
        pattern="^(start|stop|pause|resume|tick|reset)$",
        description="Control action: start | stop | pause | resume | tick | reset",
    )


class SpawnIncidentRequest(BaseModel):
    """Request to inject a simulated incident into the digital twin."""

    incident_type: str = Field(
        ...,
        description="Disaster type: FIRE | FLOOD | EARTHQUAKE | GAS_LEAK | BUILDING_COLLAPSE",
    )
    severity: str = Field(
        default="MEDIUM",
        pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$",
        description="Incident severity level",
    )
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    affected_radius_meters: float = Field(
        default=500.0, ge=50.0, le=50000.0,
        description="Initial affected radius in meters",
    )
