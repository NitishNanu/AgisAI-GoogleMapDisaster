"""
AegisAI Database Seeder — Production-Grade Idempotent Seed Script.

Creates a complete, realistic dataset for the Chandigarh/Mohali/Panchkula
tri-city area using only the new modular ORM models.

Safe to run repeatedly (idempotent) — uses skip-if-exists logic on
unique identifiers (email for users, name for facilities).

Usage:
    # From the backend/ directory:
    python -m app.database.seeder

Seed data:
    - 2 Users (1 ADMIN, 1 COMMANDER)
    - 6 Rescue Teams (geospatially distributed)
    - 5 Hospitals (with realistic bed counts)
    - 6 Shelters (with capacity and occupancy)
    - 6 Incidents (variety of types and severities)
"""

import sys

import structlog
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.database.session import SessionLocal
from app.core.security.jwt import hash_password
from app.modules.auth.models import User
from app.modules.hospital.models import Hospital
from app.modules.incident.models import Incident
from app.modules.resource.models import RescueTeam, Shelter

logger = structlog.get_logger("aegis_ai.seeder")


def _wkt(lon: float, lat: float) -> WKTElement:
    """Create a PostGIS WKTElement for a WGS84 point (lon, lat order)."""
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def _upsert_user(db: Session, email: str, data: dict) -> tuple[User, bool]:
    """Return existing user or create new one. Returns (user, created)."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return existing, False
    user = User(**data)
    db.add(user)
    db.flush()
    return user, True


def _upsert_hospital(db: Session, name: str, data: dict) -> tuple[Hospital, bool]:
    existing = db.query(Hospital).filter(Hospital.name == name).first()
    if existing:
        return existing, False
    hospital = Hospital(**data)
    db.add(hospital)
    db.flush()
    return hospital, True


def _upsert_team(db: Session, team_name: str, data: dict) -> tuple[RescueTeam, bool]:
    existing = db.query(RescueTeam).filter(RescueTeam.team_name == team_name).first()
    if existing:
        return existing, False
    team = RescueTeam(**data)
    db.add(team)
    db.flush()
    return team, True


def _upsert_shelter(db: Session, name: str, data: dict) -> tuple[Shelter, bool]:
    existing = db.query(Shelter).filter(Shelter.name == name).first()
    if existing:
        return existing, False
    shelter = Shelter(**data)
    db.add(shelter)
    db.flush()
    return shelter, True


def seed_database() -> None:
    """
    Seed the AegisAI database with realistic demo data.

    All operations are wrapped in a single transaction. Rolls back on
    any failure to leave the DB in a clean state.
    """
    db: Session = SessionLocal()
    stats = {
        "users": 0,
        "hospitals": 0,
        "teams": 0,
        "shelters": 0,
        "incidents": 0,
    }

    try:
        logger.info("seeder_started")

        # -- Users --------------------------------------------------------------
        admin, created = _upsert_user(db, "nitrexo19@gmail.com", {
            "name": "Nitish Kumar",
            "email": "nitrexo19@gmail.com",
            "password_hash": hash_password("kumar19##Nitish"),
            "role": "ADMIN",
            "is_active": True,
        })
        if created:
            stats["users"] += 1
            logger.info("user_created", email=admin.email, role="ADMIN")

        commander, created = _upsert_user(db, "commander@aegisai.io", {
            "name": "Field Commander Singh",
            "email": "commander@aegisai.io",
            "password_hash": hash_password("Commander@AegisAI2026!"),
            "role": "COMMANDER",
            "is_active": True,
        })
        if created:
            stats["users"] += 1
            logger.info("user_created", email=commander.email, role="COMMANDER")

        db.commit()
        reporter_id = admin.id

        # -- Hospitals ----------------------------------------------------------
        hospitals_data = [
            {
                "name": "Government Multi-Specialty Hospital",
                "latitude": 30.7352, "longitude": 76.7756,
                "beds": 500, "icu_beds": 80,
                "oxygen_available": True, "is_operational": True,
                "location": _wkt(76.7756, 30.7352),
            },
            {
                "name": "PGI Emergency Medical Center",
                "latitude": 30.7646, "longitude": 76.7754,
                "beds": 900, "icu_beds": 150,
                "oxygen_available": True, "is_operational": True,
                "location": _wkt(76.7754, 30.7646),
            },
            {
                "name": "Sector 32 Emergency Hospital",
                "latitude": 30.7057, "longitude": 76.7947,
                "beds": 400, "icu_beds": 60,
                "oxygen_available": True, "is_operational": True,
                "location": _wkt(76.7947, 30.7057),
            },
            {
                "name": "Fortis Mohali Emergency Center",
                "latitude": 30.6942, "longitude": 76.7160,
                "beds": 350, "icu_beds": 55,
                "oxygen_available": True, "is_operational": True,
                "location": _wkt(76.7160, 30.6942),
            },
            {
                "name": "Civil Hospital Panchkula",
                "latitude": 30.6946, "longitude": 76.8500,
                "beds": 300, "icu_beds": 40,
                "oxygen_available": True, "is_operational": True,
                "location": _wkt(76.8500, 30.6946),
            },
        ]

        for h_data in hospitals_data:
            _, created = _upsert_hospital(db, str(h_data["name"]), h_data)
            if created:
                stats["hospitals"] += 1

        db.commit()
        logger.info("hospitals_seeded", count=stats["hospitals"])

        # -- Rescue Teams -------------------------------------------------------
        teams_data = [
            {
                "team_name": "Chandigarh Rescue Team Alpha",
                "vehicle_type": "AMBULANCE", "members": 6,
                "status": "AVAILABLE", "specialization": "MEDICAL",
                "latitude": 30.7335, "longitude": 76.7794,
                "location": _wkt(76.7794, 30.7335),
            },
            {
                "team_name": "Chandigarh Fire & Rescue Bravo",
                "vehicle_type": "FIRE_TRUCK", "members": 8,
                "status": "AVAILABLE", "specialization": "FIRE",
                "latitude": 30.7410, "longitude": 76.7680,
                "location": _wkt(76.7680, 30.7410),
            },
            {
                "team_name": "Sector 17 Emergency Unit Charlie",
                "vehicle_type": "RESCUE_VAN", "members": 5,
                "status": "AVAILABLE", "specialization": "SEARCH_AND_RESCUE",
                "latitude": 30.7400, "longitude": 76.7930,
                "location": _wkt(76.7930, 30.7400),
            },
            {
                "team_name": "Mohali Disaster Response Team Delta",
                "vehicle_type": "AMBULANCE", "members": 5,
                "status": "AVAILABLE", "specialization": "MEDICAL",
                "latitude": 30.7046, "longitude": 76.7179,
                "location": _wkt(76.7179, 30.7046),
            },
            {
                "team_name": "Panchkula Emergency Response Echo",
                "vehicle_type": "RESCUE_VAN", "members": 7,
                "status": "AVAILABLE", "specialization": "SEARCH_AND_RESCUE",
                "latitude": 30.6942, "longitude": 76.8606,
                "location": _wkt(76.8606, 30.6942),
            },
            {
                "team_name": "Rapid Response Unit Foxtrot",
                "vehicle_type": "FIRE_TRUCK", "members": 9,
                "status": "AVAILABLE", "specialization": "FIRE",
                "latitude": 30.7500, "longitude": 76.8100,
                "location": _wkt(76.8100, 30.7500),
            },
        ]

        for t_data in teams_data:
            _, created = _upsert_team(db, str(t_data["team_name"]), t_data)
            if created:
                stats["teams"] += 1

        db.commit()
        logger.info("teams_seeded", count=stats["teams"])

        # -- Shelters -----------------------------------------------------------
        shelters_data = [
            {
                "name": "Sector 17 Community Shelter",
                "capacity": 1000, "current_occupancy": 250,
                "latitude": 30.7398, "longitude": 76.7821, "is_active": True,
                "location": _wkt(76.7821, 30.7398),
            },
            {
                "name": "Sector 22 Emergency Shelter",
                "capacity": 700, "current_occupancy": 180,
                "latitude": 30.7339, "longitude": 76.7727, "is_active": True,
                "location": _wkt(76.7727, 30.7339),
            },
            {
                "name": "Manimajra Relief Center",
                "capacity": 800, "current_occupancy": 320,
                "latitude": 30.7232, "longitude": 76.8320, "is_active": True,
                "location": _wkt(76.8320, 30.7232),
            },
            {
                "name": "Mohali Community Relief Center",
                "capacity": 600, "current_occupancy": 150,
                "latitude": 30.7045, "longitude": 76.7178, "is_active": True,
                "location": _wkt(76.7178, 30.7045),
            },
            {
                "name": "Panchkula Disaster Shelter",
                "capacity": 900, "current_occupancy": 210,
                "latitude": 30.6970, "longitude": 76.8600, "is_active": True,
                "location": _wkt(76.8600, 30.6970),
            },
            {
                "name": "Sector 35 Relief Camp",
                "capacity": 500, "current_occupancy": 80,
                "latitude": 30.7120, "longitude": 76.7650, "is_active": True,
                "location": _wkt(76.7650, 30.7120),
            },
        ]

        for s_data in shelters_data:
            _, created = _upsert_shelter(db, str(s_data["name"]), s_data)
            if created:
                stats["shelters"] += 1

        db.commit()
        logger.info("shelters_seeded", count=stats["shelters"])

        # -- Incidents ----------------------------------------------------------
        incidents_data = [
            {
                "title": "Industrial Fire — Phase 1",
                "description": "Large industrial fire requiring immediate fire and medical response.",
                "disaster_type": "FIRE", "severity": "CRITICAL", "status": "RESPONDING",
                "latitude": 30.7415, "longitude": 76.7785,
                "affected_radius_meters": 800.0, "estimated_casualties": 12,
                "reporter_id": reporter_id,
                "location": _wkt(76.7785, 30.7415),
            },
            {
                "title": "Building Collapse — Sector 22",
                "description": "Partial building collapse with possible trapped civilians.",
                "disaster_type": "BUILDING_COLLAPSE", "severity": "CRITICAL", "status": "INVESTIGATING",
                "latitude": 30.7330, "longitude": 76.7850,
                "affected_radius_meters": 300.0, "estimated_casualties": 8,
                "reporter_id": reporter_id,
                "location": _wkt(76.7850, 30.7330),
            },
            {
                "title": "Major Flood — Sector 17",
                "description": "Severe flooding reported around roads near Sector 17.",
                "disaster_type": "FLOOD", "severity": "HIGH", "status": "ACTIVE",
                "latitude": 30.7355, "longitude": 76.7900,
                "affected_radius_meters": 1200.0, "estimated_casualties": 0,
                "reporter_id": reporter_id,
                "location": _wkt(76.7900, 30.7355),
            },
            {
                "title": "Road Accident — NH-5",
                "description": "Major multi-vehicle road accident requiring ambulance and rescue response.",
                "disaster_type": "ACCIDENT", "severity": "HIGH", "status": "RESPONDING",
                "latitude": 30.7505, "longitude": 76.8105,
                "affected_radius_meters": 200.0, "estimated_casualties": 5,
                "reporter_id": reporter_id,
                "location": _wkt(76.8105, 30.7505),
            },
            {
                "title": "Gas Leak — Industrial Zone",
                "description": "Potential hazardous gas leak requiring immediate emergency response and evacuation.",
                "disaster_type": "GAS_LEAK", "severity": "CRITICAL", "status": "REPORTED",
                "latitude": 30.7150, "longitude": 76.7600,
                "affected_radius_meters": 500.0, "estimated_casualties": 3,
                "reporter_id": reporter_id,
                "location": _wkt(76.7600, 30.7150),
            },
            {
                "title": "Flash Flood — Mohali",
                "description": "Flash flooding reported in the Mohali residential area.",
                "disaster_type": "FLOOD", "severity": "MEDIUM", "status": "MONITORING",
                "latitude": 30.7040, "longitude": 76.7200,
                "affected_radius_meters": 600.0, "estimated_casualties": 0,
                "reporter_id": reporter_id,
                "location": _wkt(76.7200, 30.7040),
            },
        ]

        for i_data in incidents_data:
            existing = (
                db.query(Incident)
                .filter(Incident.title == i_data["title"])
                .first()
            )
            if not existing:
                incident = Incident(**i_data)
                db.add(incident)
                stats["incidents"] += 1

        db.commit()
        logger.info("incidents_seeded", count=stats["incidents"])

        # -- Summary ------------------------------------------------------------
        print()
        print("=" * 65)
        print("          AegisAI Database Seed Complete")
        print("=" * 65)
        print()
        print(f"  Users created     : {stats['users']}")
        print(f"  Hospitals created : {stats['hospitals']}")
        print(f"  Rescue Teams      : {stats['teams']}")
        print(f"  Shelters          : {stats['shelters']}")
        print(f"  Incidents         : {stats['incidents']}")
        print()
        print("  Demo Credentials:")
        print("    Admin     : admin@aegisai.io / Admin@AegisAI2026!")
        print("    Commander : commander@aegisai.io / Commander@AegisAI2026!")
        print()
        print("  Coverage: Chandigarh / Mohali / Panchkula tri-city area")
        print("=" * 65)
        print()

    except Exception as error:
        db.rollback()
        logger.error("seeder_failed", error=str(error), exc_info=True)
        print(f"\n[SEED ERROR] {error}\n")
        raise
    finally:
        db.close()


seed_data = seed_database


if __name__ == "__main__":
    # Allow running as: python -m app.database.seeder
    seed_database()
    sys.exit(0)

