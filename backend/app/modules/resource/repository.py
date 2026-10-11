"""AegisAI Resource Module â€” Repository Layer."""

from sqlalchemy.orm import Session

from app.modules.resource.models import RescueTeam, ResourceAssignment, Shelter


class ResourceRepository:
    """Data access layer for resource management."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # -----------------------------------------------------------------------
    # Rescue Teams
    # -----------------------------------------------------------------------
    def get_team(self, team_id: int) -> RescueTeam | None:
        return self._db.query(RescueTeam).filter(RescueTeam.id == team_id).first()

    def get_teams(self, skip: int = 0, limit: int = 100, status_filter: str | None = None) -> tuple[list[RescueTeam], int]:
        query = self._db.query(RescueTeam)
        if status_filter:
            query = query.filter(RescueTeam.status == status_filter.upper())
        total = query.count()
        teams = query.order_by(RescueTeam.team_name).offset(skip).limit(limit).all()
        return teams, total

    def create_team(self, **kwargs: object) -> RescueTeam:
        try:
            from geoalchemy2.elements import WKTElement  # noqa: PLC0415
            lat = kwargs.get("latitude")
            lon = kwargs.get("longitude")
            if lat is not None and lon is not None:
                kwargs["location"] = WKTElement(f"POINT({lon} {lat})", srid=4326)
        except ImportError:
            pass

        team = RescueTeam(**kwargs)
        self._db.add(team)
        self._db.commit()
        self._db.refresh(team)
        return team

    def update_team(self, team_id: int, updates: dict) -> RescueTeam | None:
        team = self.get_team(team_id)
        if not team:
            return None

        for k, v in updates.items():
            if hasattr(team, k) and v is not None:
                setattr(team, k, v)

        if "latitude" in updates or "longitude" in updates:
            try:
                from geoalchemy2.elements import WKTElement  # noqa: PLC0415
                team.location = WKTElement(f"POINT({team.longitude} {team.latitude})", srid=4326)
            except ImportError:
                pass

        self._db.commit()
        self._db.refresh(team)
        return team

    def delete_team(self, team_id: int) -> bool:
        team = self.get_team(team_id)
        if not team:
            return False
        self._db.delete(team)
        self._db.commit()
        return True

    # -----------------------------------------------------------------------
    # Shelters
    # -----------------------------------------------------------------------
    def get_shelter(self, shelter_id: int) -> Shelter | None:
        return self._db.query(Shelter).filter(Shelter.id == shelter_id).first()

    def get_shelters(self, skip: int = 0, limit: int = 100, available_only: bool = False) -> tuple[list[Shelter], int]:
        query = self._db.query(Shelter)
        if available_only:
            query = query.filter(Shelter.capacity > Shelter.current_occupancy)
        total = query.count()
        shelters = query.order_by(Shelter.name).offset(skip).limit(limit).all()
        return shelters, total

    def create_shelter(self, **kwargs: object) -> Shelter:
        try:
            from geoalchemy2.elements import WKTElement  # noqa: PLC0415
            lat = kwargs.get("latitude")
            lon = kwargs.get("longitude")
            if lat is not None and lon is not None:
                kwargs["location"] = WKTElement(f"POINT({lon} {lat})", srid=4326)
        except ImportError:
            pass

        shelter = Shelter(**kwargs)
        self._db.add(shelter)
        self._db.commit()
        self._db.refresh(shelter)
        return shelter

    def update_shelter(self, shelter_id: int, updates: dict) -> Shelter | None:
        shelter = self.get_shelter(shelter_id)
        if not shelter:
            return None

        for k, v in updates.items():
            if hasattr(shelter, k) and v is not None:
                setattr(shelter, k, v)

        if "latitude" in updates or "longitude" in updates:
            try:
                from geoalchemy2.elements import WKTElement  # noqa: PLC0415
                shelter.location = WKTElement(f"POINT({shelter.longitude} {shelter.latitude})", srid=4326)
            except ImportError:
                pass

        self._db.commit()
        self._db.refresh(shelter)
        return shelter

    def delete_shelter(self, shelter_id: int) -> bool:
        shelter = self.get_shelter(shelter_id)
        if not shelter:
            return False
        self._db.delete(shelter)
        self._db.commit()
        return True

    # -----------------------------------------------------------------------
    # Assignments
    # -----------------------------------------------------------------------
    def get_assignment(self, assignment_id: int) -> ResourceAssignment | None:
        return self._db.query(ResourceAssignment).filter(ResourceAssignment.id == assignment_id).first()

    def get_assignments_for_incident(self, incident_id: int) -> list[ResourceAssignment]:
        return self._db.query(ResourceAssignment).filter(ResourceAssignment.incident_id == incident_id).order_by(ResourceAssignment.created_at.desc()).all()

    def create_assignment(self, **kwargs: object) -> ResourceAssignment:
        assignment = ResourceAssignment(**kwargs)
        self._db.add(assignment)
        self._db.commit()
        self._db.refresh(assignment)
        return assignment

    def update_assignment(self, assignment_id: int, updates: dict) -> ResourceAssignment | None:
        assignment = self.get_assignment(assignment_id)
        if not assignment:
            return None

        for k, v in updates.items():
            if hasattr(assignment, k) and v is not None:
                setattr(assignment, k, v)

        self._db.commit()
        self._db.refresh(assignment)
        return assignment
