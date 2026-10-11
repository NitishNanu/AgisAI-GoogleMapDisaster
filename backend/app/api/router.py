"""
AegisAI API Router Aggregator.

Registers all module routers under the /api/v1 prefix.
Every new domain module must add its router import here.
"""

from fastapi import APIRouter

from app.api.routes.assignments import router as assignments_router
from app.api.routes.disasters import router as disasters_router
from app.api.routes.health import router as health_router
from app.api.routes.missions import router as missions_router
from app.modules.ai.agents.router import router as agents_router
from app.modules.ai.router import router as ai_router
from app.modules.analytics.router import router as analytics_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.auth.router import users_router
from app.modules.external_feeds.router import router as feeds_router
from app.modules.hospital.router import router as hospital_router
from app.modules.incident.router import router as incident_router
from app.modules.ml_intelligence.router import assistant_router
from app.modules.ml_intelligence.router import router as ml_router
from app.modules.notification.router import router as notification_router
from app.modules.prediction.router import router as prediction_router
from app.modules.resource.router import router as resource_router
from app.modules.scenario.router import router as scenario_router
from app.modules.simulation.router import router as simulation_router

api_router = APIRouter()

# ── Infrastructure ────────────────────────────────────────────────────────
api_router.include_router(health_router)

# ── Identity & Access Management ──────────────────────────────────────────
api_router.include_router(auth_router)
api_router.include_router(users_router)

# ── Emergency Domain & Mission Control ────────────────────────────────────
api_router.include_router(incident_router)
api_router.include_router(disasters_router)
api_router.include_router(hospital_router)
api_router.include_router(resource_router)
api_router.include_router(assignments_router)
api_router.include_router(missions_router)

# ── Digital Twin, Scenarios & AI ─────────────────────────────────────────
api_router.include_router(scenario_router)
api_router.include_router(simulation_router)
api_router.include_router(prediction_router)  # /api/v1/predictions
api_router.include_router(
    prediction_router, prefix="/prediction", tags=["AI & Prediction Engine (Legacy Alias)"]
)
api_router.include_router(ai_router)
api_router.include_router(agents_router)
api_router.include_router(ml_router)
api_router.include_router(assistant_router)

# ── Platform Intelligence & Feeds ────────────────────────────────────────
api_router.include_router(feeds_router)
api_router.include_router(analytics_router)
api_router.include_router(notification_router)
api_router.include_router(audit_router)

