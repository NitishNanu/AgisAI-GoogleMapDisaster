"""AegisAI Hospital Module — Domain Service."""

import structlog
from sqlalchemy.orm import Session

from app.core.common.exceptions import EntityNotFoundException, ValidationException
from app.modules.hospital.models import Hospital
from app.modules.hospital.repository import HospitalRepository
from app.modules.hospital.schemas import HospitalCapacityUpdate, HospitalCreate, HospitalUpdate

logger = structlog.get_logger("aegis_ai.hospital")


class HospitalService:
    """
    Hospital Domain Service.

    Manages hospital CRUD and capacity tracking during emergencies.
    """

    @staticmethod
    def create_hospital(db: Session, payload: HospitalCreate) -> Hospital:
        """Register a new hospital in the response network."""
        if payload.icu_capacity > payload.total_beds:
            raise ValidationException(
                "ICU bed count cannot exceed total bed count.",
                details={"total_beds": payload.total_beds, "icu_capacity": payload.icu_capacity},
            )
        if payload.available_beds > payload.total_beds:
            raise ValidationException(
                "Available beds cannot exceed total bed count.",
                details={"total_beds": payload.total_beds, "available_beds": payload.available_beds},
            )

        repo = HospitalRepository(db)
        hospital = repo.create(
            name=payload.name,
            address=payload.address,
            emergency_contact=payload.emergency_contact,
            total_beds=payload.total_beds,
            available_beds=payload.available_beds,
            icu_capacity=payload.icu_capacity,
            available_icu=payload.available_icu,
            oxygen_available=payload.oxygen_available,
            blood_bank_available=payload.blood_bank_available,
            is_operational=payload.is_operational,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
        logger.info("hospital_created", hospital_id=hospital.id, name=hospital.name)
        return hospital

    @staticmethod
    def get_hospital(db: Session, hospital_id: int) -> Hospital:
        """Retrieve a hospital. Raises EntityNotFoundException if missing."""
        repo = HospitalRepository(db)
        hospital = repo.get_by_id(hospital_id)
        if hospital is None:
            raise EntityNotFoundException("Hospital", hospital_id)
        return hospital

    @staticmethod
    def list_hospitals(
        db: Session,
        page: int = 1,
        page_size: int = 50,
        operational_only: bool = False,
    ) -> tuple[list[Hospital], int]:
        """Return paginated hospitals."""
        repo = HospitalRepository(db)
        skip = (page - 1) * page_size
        return repo.get_all(skip=skip, limit=page_size, operational_only=operational_only)

    @staticmethod
    def update_hospital(db: Session, hospital_id: int, payload: HospitalUpdate) -> Hospital:
        """Apply partial updates to a hospital."""
        repo = HospitalRepository(db)
        existing = repo.get_by_id(hospital_id)
        if existing is None:
            raise EntityNotFoundException("Hospital", hospital_id)

        updates = payload.model_dump(exclude_none=True)

        # Validate bed counts if both are being updated
        final_beds = updates.get("total_beds", existing.total_beds)
        final_icu = updates.get("icu_capacity", existing.icu_capacity)
        final_avail = updates.get("available_beds", existing.available_beds)
        final_avail_icu = updates.get("available_icu", existing.available_icu)

        if final_icu > final_beds:
            raise ValidationException("icu_capacity cannot exceed total_beds.")
        if final_avail > final_beds:
            raise ValidationException("available_beds cannot exceed total_beds.")
        if final_avail_icu > final_icu:
            raise ValidationException("available_icu cannot exceed icu_capacity.")

        hospital = repo.update(hospital_id, updates)
        if hospital is None:
            raise EntityNotFoundException("Hospital", hospital_id)

        logger.info("hospital_updated", hospital_id=hospital_id, fields=list(updates.keys()))
        return hospital

    @staticmethod
    def update_capacity(
        db: Session, hospital_id: int, payload: HospitalCapacityUpdate
    ) -> Hospital:
        """Rapid capacity update for mass casualty events."""
        if payload.icu_capacity > payload.total_beds:
            raise ValidationException("icu_capacity cannot exceed total_beds.")

        repo = HospitalRepository(db)
        hospital = repo.update(
            hospital_id,
            {
                "total_beds": payload.total_beds,
                "available_beds": payload.available_beds,
                "icu_capacity": payload.icu_capacity,
                "available_icu": payload.available_icu,
                "oxygen_available": payload.oxygen_available,
            },
        )
        if hospital is None:
            raise EntityNotFoundException("Hospital", hospital_id)

        logger.info(
            "hospital_capacity_updated",
            hospital_id=hospital_id,
            total_beds=payload.total_beds,
            available_beds=payload.available_beds,
        )
        return hospital

    @staticmethod
    def delete_hospital(db: Session, hospital_id: int) -> None:
        """Delete a hospital from the response network."""
        repo = HospitalRepository(db)
        deleted = repo.delete(hospital_id)
        if not deleted:
            raise EntityNotFoundException("Hospital", hospital_id)
        logger.info("hospital_deleted", hospital_id=hospital_id)

