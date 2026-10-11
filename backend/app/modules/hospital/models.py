"""
AegisAI Hospital Module â€” ORM Model.

Extends the legacy Hospital schema with operational fields, contact info,
blood bank availability, and soft-deactivation support.
"""

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, TimestampMixin


class Hospital(Base, TimestampMixin):
    """
    Hospital entity representing a medical facility in the response network.

    Used for:
    - Geospatial proximity queries (nearest hospitals to incidents)
    - Capacity tracking during mass casualty events
    - Resource allocation in the AI decision engine
    """

    __tablename__ = "hospitals"

    __table_args__ = (
        CheckConstraint("total_beds >= 0", name="ck_hospitals_beds_positive"),
        CheckConstraint("icu_capacity >= 0", name="ck_hospitals_icu_positive"),
        CheckConstraint("icu_capacity <= total_beds", name="ck_hospitals_icu_lte_beds"),
        CheckConstraint("available_beds >= 0", name="ck_hospitals_avail_beds_nn"),
        CheckConstraint("available_icu >= 0", name="ck_hospitals_avail_icu_nn"),
        CheckConstraint("available_beds <= total_beds", name="ck_hospitals_avail_lte_total"),
        CheckConstraint("available_icu <= icu_capacity", name="ck_hospitals_avail_icu_lte_cap"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_hospitals_lat"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_hospitals_lon"),
        Index("ix_hospitals_operational", "is_operational"),
        Index("ix_hospitals_lat_lon", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    emergency_contact: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ---- Capacity columns (aligned with forecaster & migration 001) ----
    total_beds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Total physical bed count",
    )

    available_beds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Unoccupied beds — decremented on patient admission",
    )

    icu_capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Total ICU bed count",
    )

    available_icu: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Currently unoccupied ICU beds",
    )

    oxygen_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    blood_bank_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    is_operational: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    latitude: Mapped[float] = mapped_column(nullable=False)

    longitude: Mapped[float] = mapped_column(nullable=False)

    location = mapped_column(
        __import__("geoalchemy2", fromlist=["Geography"]).Geography(
            geometry_type="POINT",
            srid=4326,
            spatial_index=True,
        ),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Backward-compatibility properties for legacy service/schema code
    # that still references `beds` and `icu_beds` (old names).
    # ------------------------------------------------------------------
    @property
    def beds(self) -> int:
        """Alias → total_beds (backward compat)."""
        return self.total_beds

    @beds.setter
    def beds(self, value: int) -> None:
        self.total_beds = value
        if not self.available_beds:
            self.available_beds = value

    @property
    def icu_beds(self) -> int:
        """Alias → icu_capacity (backward compat)."""
        return self.icu_capacity

    @icu_beds.setter
    def icu_beds(self, value: int) -> None:
        self.icu_capacity = value
        if not self.available_icu:
            self.available_icu = value

    @property
    def occupied_beds(self) -> int:
        """Currently occupied beds calculated from total and available beds."""
        return max(0, self.total_beds - self.available_beds)
