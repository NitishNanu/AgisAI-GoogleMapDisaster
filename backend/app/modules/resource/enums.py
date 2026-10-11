"""AegisAI Resource Module â€” Domain Enums."""

from enum import Enum


class VehicleType(str, Enum):
    """Rescue vehicle classifications."""

    AMBULANCE = "AMBULANCE"
    FIRE_TRUCK = "FIRE_TRUCK"
    RESCUE_VAN = "RESCUE_VAN"
    HELICOPTER = "HELICOPTER"
    BOAT = "BOAT"
    CRANE_TRUCK = "CRANE_TRUCK"
    HAZMAT_UNIT = "HAZMAT_UNIT"
    COMMAND_VEHICLE = "COMMAND_VEHICLE"


class TeamStatus(str, Enum):
    """Operational status of a rescue team."""

    AVAILABLE = "AVAILABLE"      # Ready for dispatch
    DISPATCHED = "DISPATCHED"    # Assigned and en route
    ON_SCENE = "ON_SCENE"        # Arrived at incident
    RETURNING = "RETURNING"      # Returning to base
    MAINTENANCE = "MAINTENANCE"  # Unavailable for operational reasons
    STANDBY = "STANDBY"          # On standby, reduced availability


class AssignmentStatus(str, Enum):
    """Lifecycle status of a resource assignment."""

    ASSIGNED = "ASSIGNED"
    DISPATCHED = "DISPATCHED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    ON_SCENE = "ON_SCENE"
    OPERATIONAL = "OPERATIONAL"
    MEDEVAC = "MEDEVAC"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
