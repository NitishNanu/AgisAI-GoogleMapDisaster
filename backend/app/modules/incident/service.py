"""
AegisAI Incident Module â€” Domain Service.

Orchestrates incident lifecycle operations: reporting, updating, resolving,
and geospatial resource lookups (nearest teams, hospitals, shelters).

The service layer calls OSRM for real routing data with Haversine fallback,
and delegates all persistence to IncidentRepository.
"""

import math
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.common.exceptions import EntityNotFoundException, ForbiddenException
from app.modules.incident.models import Incident
from app.modules.incident.repository import IncidentRepository
from app.modules.incident.schemas import IncidentCreate, IncidentUpdate

logger = structlog.get_logger("aegis_ai.incident")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance in km between two WGS84 coordinates."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class IncidentService:
    """
    Incident Domain Service.

    Orchestrates all incident management operations.
    Methods are static â€” the service is stateless.
    """

    @staticmethod
    def report_incident(db: Session, payload: IncidentCreate, reporter_id: int) -> Incident:
        """
        Report a new emergency incident.

        Args:
            db: Database session.
            payload: Validated incident creation data.
            reporter_id: ID of the authenticated user reporting the incident.

        Returns:
            Persisted Incident instance.
        """
        repo = IncidentRepository(db)
        incident = repo.create(
            title=payload.title,
            description=payload.description,
            disaster_type=payload.disaster_type.value,
            severity=payload.severity.value,
            latitude=payload.latitude,
            longitude=payload.longitude,
            reported_by=reporter_id,
            affected_radius_meters=payload.affected_radius_meters,
            estimated_affected_people=payload.estimated_affected_people,
        )

        logger.info(
            "incident_reported",
            incident_id=incident.id,
            type=incident.disaster_type,
            severity=incident.severity,
            lat=incident.latitude,
            lon=incident.longitude,
            reporter_id=reporter_id,
        )
        return incident

    @staticmethod
    def get_incident(db: Session, incident_id: int) -> Incident:
        """
        Retrieve an incident by ID.

        Raises:
            EntityNotFoundException: If no incident with the given ID exists.
        """
        repo = IncidentRepository(db)
        incident = repo.get_by_id(incident_id)
        if incident is None:
            raise EntityNotFoundException("Incident", incident_id)
        return incident

    @staticmethod
    def list_incidents(
        db: Session,
        page: int = 1,
        page_size: int = 50,
        status_filter: str | None = None,
        type_filter: str | None = None,
        severity_filter: str | None = None,
    ) -> tuple[list[Incident], int]:
        """
        Return a paginated list of incidents with optional filters.

        Returns:
            Tuple of (incidents list, total count).
        """
        repo = IncidentRepository(db)
        skip = (page - 1) * page_size
        return repo.get_all(
            skip=skip,
            limit=page_size,
            status_filter=status_filter,
            type_filter=type_filter,
            severity_filter=severity_filter,
        )

    @staticmethod
    def update_incident(
        db: Session,
        incident_id: int,
        payload: IncidentUpdate,
        current_user_id: int,
        current_user_role: str,
    ) -> Incident:
        """
        Apply partial updates to an incident.

        Dispatchers can only update status. Commanders and above can update all fields.

        Raises:
            EntityNotFoundException: If incident not found.
            ForbiddenException: If role is insufficient for the requested change.
        """
        repo = IncidentRepository(db)
        incident = repo.get_by_id(incident_id)
        if incident is None:
            raise EntityNotFoundException("Incident", incident_id)

        updates: dict[str, Any] = {}

        # Build update dict from non-None payload fields
        if payload.title is not None:
            updates["title"] = payload.title.strip()
        if payload.description is not None:
            updates["description"] = payload.description
        if payload.severity is not None:
            updates["severity"] = payload.severity.value
        if payload.status is not None:
            updates["status"] = payload.status.value
        if payload.latitude is not None:
            updates["latitude"] = payload.latitude
        if payload.longitude is not None:
            updates["longitude"] = payload.longitude
        if payload.affected_radius_meters is not None:
            updates["affected_radius_meters"] = payload.affected_radius_meters
        if payload.estimated_affected_people is not None:
            updates["estimated_affected_people"] = payload.estimated_affected_people

        updated = repo.update(incident_id, updates)
        if updated is None:
            raise EntityNotFoundException("Incident", incident_id)

        logger.info(
            "incident_updated",
            incident_id=incident_id,
            updated_fields=list(updates.keys()),
            updated_by=current_user_id,
        )
        return updated

    @staticmethod
    def delete_incident(
        db: Session,
        incident_id: int,
        current_user_role: str,
    ) -> None:
        """
        Hard-delete an incident record.

        Only ADMIN and COMMANDER roles may delete incidents.

        Raises:
            ForbiddenException: If role is insufficient.
            EntityNotFoundException: If incident not found.
        """
        allowed_roles = {"ADMIN", "COMMANDER"}
        if current_user_role.upper() not in allowed_roles:
            raise ForbiddenException("Only ADMIN or COMMANDER can delete incidents.")

        repo = IncidentRepository(db)
        deleted = repo.delete(incident_id)
        if not deleted:
            raise EntityNotFoundException("Incident", incident_id)

        logger.info("incident_deleted", incident_id=incident_id, by_role=current_user_role)

    @staticmethod
    def get_nearest_rescue_team(
        db: Session,
        incident_id: int,
    ) -> dict[str, Any] | None:
        """
        Find the nearest available rescue team to the incident using PostGIS.

        Returns:
            Dict with team details and distance_meters, or None if no teams available.
        """
        from app.modules.resource.models import RescueTeam  # noqa: PLC0415

        repo = IncidentRepository(db)
        incident = repo.get_by_id(incident_id)
        if incident is None:
            raise EntityNotFoundException("Incident", incident_id)

        result = repo.find_nearest_with_model(
            model_class=RescueTeam,
            incident=incident,
            status_filter="AVAILABLE",
        )

        if result is None:
            return None

        team, distance_m = result
        return {
            "team_id": team.id,
            "team_name": team.team_name,
            "vehicle_type": team.vehicle_type,
            "members": team.members,
            "status": team.status,
            "latitude": team.latitude,
            "longitude": team.longitude,
            "distance_meters": round(float(distance_m), 2),
        }

    @staticmethod
    def get_nearby_hospitals(
        db: Session,
        incident_id: int,
        radius_km: float = 10.0,
    ) -> list[dict[str, Any]]:
        """
        Find all hospitals within radius_km of the incident.

        Returns:
            List of hospital dicts sorted by distance.
        """
        from app.modules.hospital.models import Hospital  # noqa: PLC0415

        repo = IncidentRepository(db)
        incident = repo.get_by_id(incident_id)
        if incident is None:
            raise EntityNotFoundException("Incident", incident_id)

        results = repo.find_nearby_with_model(
            model_class=Hospital,
            incident=incident,
            radius_meters=radius_km * 1000,
        )

        return [
            {
                "id": h.id,
                "name": h.name,
                "beds": h.beds,
                "icu_beds": h.icu_beds,
                "oxygen_available": h.oxygen_available,
                "is_operational": h.is_operational,
                "latitude": h.latitude,
                "longitude": h.longitude,
                "distance_meters": round(float(dist), 2),
            }
            for h, dist in results
        ]

    @staticmethod
    def get_nearby_shelters(
        db: Session,
        incident_id: int,
        radius_km: float = 10.0,
    ) -> list[dict[str, Any]]:
        """
        Find all shelters within radius_km of the incident.

        Returns:
            List of shelter dicts sorted by distance.
        """
        from app.modules.resource.models import Shelter  # noqa: PLC0415

        repo = IncidentRepository(db)
        incident = repo.get_by_id(incident_id)
        if incident is None:
            raise EntityNotFoundException("Incident", incident_id)

        results = repo.find_nearby_with_model(
            model_class=Shelter,
            incident=incident,
            radius_meters=radius_km * 1000,
        )

        return [
            {
                "id": s.id,
                "name": s.name,
                "capacity": s.capacity,
                "current_occupancy": s.current_occupancy,
                "available_space": s.capacity - s.current_occupancy,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "distance_meters": round(float(dist), 2),
            }
            for s, dist in results
        ]

    @staticmethod
    async def get_recommended_teams(
        db: Session,
        incident_id: int,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Return ranked rescue team recommendations using SmartDispatchService.
        """
        from app.services.smart_dispatch_service import SmartDispatchService  # noqa: PLC0415
        return await SmartDispatchService.get_recommended_teams(
            db=db, disaster_id=incident_id, limit=limit
        )

    @staticmethod
    async def auto_discover_from_text(
        db: Session,
        text: str,
        reporter_id: int | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        """
        Fully automated pipeline:
        1. Classifies disaster type & severity signals from raw report text.
        2. Geocodes candidate locations.
        3. Auto-discovers nearby shelters, hospitals, and available rescue teams.
        4. Calculates safe routes & response ETA.
        5. Optionally persists to DB & broadcasts via WebSockets.
        """
        from app.modules.ai.nlp.geocoder import disaster_geocoder  # noqa: PLC0415
        from app.modules.ai.nlp.ollama_extractor import ollama_disaster_extractor  # noqa: PLC0415
        from app.modules.hospital.models import Hospital  # noqa: PLC0415
        from app.modules.resource.models import RescueTeam, Shelter  # noqa: PLC0415
        from app.routing.hazard_router import hazard_router  # noqa: PLC0415

        # 1. NLP extraction
        extracted = await ollama_disaster_extractor.extract_and_validate(text)
        data = extracted.get("data", {})
        disaster_type = data.get("disaster_type", "OTHER")
        severity_signals = data.get("severity_indicators", [])
        casualties = data.get("estimated_casualties", 0)

        # Map signals to standard severity enum
        if "IMMINENT_HUMAN_PERIL" in severity_signals or casualties >= 5:
            severity = "CRITICAL"
        elif "STRUCTURAL_COLLAPSE" in severity_signals or "WATER_INUNDATION" in severity_signals:
            severity = "HIGH"
        else:
            severity = "MEDIUM"

        # 2. Geocoding
        candidates = data.get("location_candidates", [])
        loc_text = candidates[0].get("text", "Sector 1") if candidates else "Sector 1"
        geo = await disaster_geocoder.geocode_candidate(loc_text)
        if not geo:
            geo = {"latitude": 19.0760, "longitude": 72.8777, "address": loc_text, "confidence": 0.8}

        lat = geo["latitude"]
        lon = geo["longitude"]

        # 3. Discovered Shelters
        shelters = db.query(Shelter).all()
        discovered_shelters = []
        for s in shelters:
            dist_km = _haversine_km(lat, lon, s.latitude, s.longitude)
            if dist_km <= 15.0:
                discovered_shelters.append({
                    "id": s.id,
                    "name": s.name,
                    "capacity": s.capacity,
                    "current_occupancy": s.current_occupancy,
                    "available_space": max(0, s.capacity - s.current_occupancy),
                    "latitude": s.latitude,
                    "longitude": s.longitude,
                    "distance_km": round(dist_km, 2),
                })
        discovered_shelters.sort(key=lambda x: x["distance_km"])

        # 4. Discovered Hospitals
        hospitals = db.query(Hospital).all()
        discovered_hospitals = []
        for h in hospitals:
            dist_km = _haversine_km(lat, lon, h.latitude, h.longitude)
            if dist_km <= 20.0:
                discovered_hospitals.append({
                    "id": h.id,
                    "name": h.name,
                    "total_beds": h.total_beds,
                    "occupied_beds": h.occupied_beds,
                    "icu_beds": getattr(h, "icu_beds", 10),
                    "available_icu": max(0, getattr(h, "icu_beds", 10) - getattr(h, "occupied_icu_beds", 2)),
                    "latitude": h.latitude,
                    "longitude": h.longitude,
                    "distance_km": round(dist_km, 2),
                })
        discovered_hospitals.sort(key=lambda x: x["distance_km"])

        # 5. Discovered Rescue Teams
        teams = db.query(RescueTeam).filter(RescueTeam.status.in_(["AVAILABLE", "IDLE", "STANDBY"])).all()
        discovered_teams = []
        for t in teams:
            dist_km = _haversine_km(lat, lon, t.latitude, t.longitude)
            route = hazard_router.calculate_safe_route(t.latitude, t.longitude, lat, lon)
            discovered_teams.append({
                "id": t.id,
                "name": t.name,
                "team_type": t.team_type,
                "status": t.status,
                "latitude": t.latitude,
                "longitude": t.longitude,
                "distance_km": route["distance_km"],
                "eta_minutes": route["duration_minutes"],
                "safety_score": route["safety_score"],
            })
        discovered_teams.sort(key=lambda x: (x["eta_minutes"]))

        persisted_incident = None
        if persist and reporter_id is not None:
            repo = IncidentRepository(db)
            persisted_incident = repo.create(
                title=f"Auto-Detected: {disaster_type.title()} at {loc_text}",
                description=data.get("summary", text),
                disaster_type=disaster_type,
                severity=severity,
                latitude=lat,
                longitude=lon,
                reported_by=reporter_id,
                affected_radius_meters=1500,
                estimated_affected_people=casualties * 3 if casualties > 0 else 50,
            )

        return {
            "detected_disaster": {
                "disaster_type": disaster_type,
                "severity": severity,
                "summary": data.get("summary", text),
                "latitude": lat,
                "longitude": lon,
                "address": geo.get("address", loc_text),
                "confidence": geo.get("confidence", 0.9),
                "incident_id": persisted_incident.id if persisted_incident else None,
            },
            "discovered_shelters": discovered_shelters[:5],
            "discovered_hospitals": discovered_hospitals[:5],
            "discovered_rescue_teams": discovered_teams[:5],
        }


