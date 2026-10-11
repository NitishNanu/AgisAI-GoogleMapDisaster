"""
AegisAI ML Intelligence Module — REST API Router.

Endpoints:
  POST /api/v1/ml/severity/predict — XGBoost severity classification & Kuhn-Munkres multipliers
  POST /api/v1/ml/forecast/series   — PyTorch LSTM multi-horizon trajectory forecasting
  POST /api/v1/assistant/query      — Tactical Commander RAG Assistant (FEMA/ICS SOPs + Ollama)
"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.common.response import ApiResponse
from app.core.common.sanitizer import sanitize_text
from app.core.middleware.rate_limiter import limiter
from app.core.security.jwt import RequireRole, get_current_active_user
from app.modules.auth.models import User
from app.modules.ml_intelligence.commander_rag import CommanderRAGAssistant
from app.modules.ml_intelligence.lstm_forecaster import LSTMDisasterForecaster
from app.modules.ml_intelligence.severity_model import DisasterSeverityModel

router = APIRouter(prefix="/ml", tags=["ML / DL / RL & Predictive Intelligence"])
assistant_router = APIRouter(prefix="/assistant", tags=["Tactical Commander RAG Assistant"])


class SeverityPredictRequest(BaseModel):
    estimated_casualties: float = Field(default=0, ge=0)
    critical_patients: float = Field(default=0, ge=0)
    affected_radius_meters: float = Field(default=100.0, ge=0)
    disaster_type: str = Field(default="FIRE")
    wind_speed_kmh: float = Field(default=15.0)
    rainfall_mm: float = Field(default=0.0)
    priority: float = Field(default=3.0, ge=1.0, le=5.0)


class TimeSeriesForecastRequest(BaseModel):
    history: list[dict[str, float]] = Field(
        default_factory=list,
        description="List of consecutive timestep dictionaries with casualties, critical, radius_meters",
    )
    baseline_casualties: float = Field(default=10.0, ge=0)
    baseline_radius_meters: float = Field(default=250.0, ge=0)


class AssistantQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    incident_context: dict[str, Any] | None = None


@router.post("/severity/predict", response_model=ApiResponse[dict[str, Any]])
def predict_disaster_severity(
    payload: SeverityPredictRequest,
    _: User = Depends(get_current_active_user),
) -> ApiResponse[dict[str, Any]]:
    """Classify incident severity using trained XGBoost gradient boosted model."""
    model = DisasterSeverityModel.get_instance()
    result = model.predict_severity(payload.model_dump())
    return ApiResponse.ok(data=result, message="XGBoost severity prediction generated successfully.")


@router.post("/forecast/series", response_model=ApiResponse[dict[str, Any]])
def forecast_time_series(
    payload: TimeSeriesForecastRequest,
    _: User = Depends(get_current_active_user),
) -> ApiResponse[dict[str, Any]]:
    """Produce deep recurrent multi-horizon casualty & spread projections using PyTorch LSTM."""
    forecaster = LSTMDisasterForecaster.get_instance()
    result = forecaster.forecast_trajectory(
        history=payload.history,
        baseline_casualties=payload.baseline_casualties,
        baseline_radius=payload.baseline_radius_meters,
    )
    return ApiResponse.ok(data=result, message="PyTorch LSTM time-series forecast generated successfully.")


@assistant_router.post("/query", response_model=ApiResponse[dict[str, Any]])
@limiter.limit("20/minute")
async def query_commander_assistant(
    request: Request,
    payload: AssistantQueryRequest,
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[dict[str, Any]]:
    """Tactical RAG Commander Assistant querying indexed SOPs and synthesising actionable doctrine."""
    clean_query = sanitize_text(payload.query, max_length=1000)
    assistant = CommanderRAGAssistant.get_instance()
    result = await assistant.answer_query(
        query=clean_query,
        incident_context=payload.incident_context,
    )
    return ApiResponse.ok(data=result, message="Tactical briefing generated successfully.")
