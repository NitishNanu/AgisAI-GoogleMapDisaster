"""
RescueNet AI — Database Initialization and Auto-Bootstrap.
"""

import structlog
from sqlalchemy import text

from app.core.database.base import Base
from app.core.database.session import SessionLocal, engine
from app.modules.analytics.models import AnalyticsReport, SystemMetricSnapshot  # noqa: F401
from app.modules.auth.models import User
from app.modules.incident.models import Incident

logger = structlog.get_logger("aegis_ai.database")


def init_db():
    from app.core.config.settings import settings

    if settings.ENVIRONMENT == "testing":
        return

    try:
        # PostGIS extension must be installed by a DB superuser.
        # We attempt creation here as a convenience for fresh dev databases;
        # in production the DBA pre-installs it, so a failure here is non-fatal.
        with engine.begin() as connection:
            try:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                logger.info("postgis_extension_verified")
            except Exception as ext_err:
                logger.warning(
                    "postgis_extension_unavailable",
                    reason=str(ext_err),
                    hint="Ensure PostGIS is installed and the DB user has SUPERUSER or extension privileges.",
                )

        Base.metadata.create_all(bind=engine)
        logger.info("database_tables_verified")

        # Ensure requested admin and demo users exist
        db = SessionLocal()
        try:
            from app.core.security.jwt import hash_password

            users_to_ensure = [
                {
                    "email": "nitrexo19@gmail.com",
                    "name": "Nitish Kumar",
                    "password": "kumar19##Nitish",
                    "role": "ADMIN",
                },
                {
                    "email": "admin@aegis.local",
                    "name": "Admin Root",
                    "password": "Password123!",
                    "role": "ADMIN",
                },
                {
                    "email": "commander@aegis.local",
                    "name": "Commander Alpha",
                    "password": "Password123!",
                    "role": "COMMANDER",
                },
                {
                    "email": "dispatcher@aegis.local",
                    "name": "Dispatcher Dave",
                    "password": "Password123!",
                    "role": "DISPATCHER",
                },
                {
                    "email": "medic@aegis.local",
                    "name": "Medic Mary",
                    "password": "Password123!",
                    "role": "MEDIC",
                },
                {
                    "email": "citizen@aegis.local",
                    "name": "Citizen John",
                    "password": "Password123!",
                    "role": "CITIZEN",
                },
            ]

            for u_data in users_to_ensure:
                existing_user = db.query(User).filter(User.email == u_data["email"]).first()
                if existing_user:
                    existing_user.password_hash = hash_password(u_data["password"])
                    existing_user.role = u_data["role"]
                    existing_user.is_active = True
                else:
                    new_user = User(
                        name=u_data["name"],
                        email=u_data["email"],
                        password_hash=hash_password(u_data["password"]),
                        role=u_data["role"],
                        is_active=True,
                    )
                    db.add(new_user)
            db.commit()
            logger.info("bootstrap_users_verified")
        except Exception as user_err:
            db.rollback()
            logger.error("bootstrap_users_failed", error=str(user_err))
        finally:
            db.close()

        # Auto-seed if database is empty
        db = SessionLocal()
        try:
            incident_count = db.query(Incident).count()
            if incident_count == 0:
                logger.info("database_empty_auto_seeding")
                try:
                    from app.database.seeder import seed_database
                    seed_database()
                except Exception as seed_err:
                    logger.warning("seeder_failed", error=str(seed_err))
        finally:
            db.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("database_initialization_failed", error=str(e))
