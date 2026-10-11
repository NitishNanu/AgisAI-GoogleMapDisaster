"""
AegisAI AI Agents Module — API Router.

Exposes specialized Autonomous Domain Agents:
- Incident Intelligence & Triage Agent
- Mission Operations & In-Flight Tracking Agent
- Scenario Architect & Simulation Director Agent
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.common.response import ApiResponse
from app.core.database.session import get_db
from app.core.security.jwt import get_current_active_user
from app.modules.ai.agents.incident_agent import IncidentIntelligenceAgent
from app.modules.ai.agents.mission_agent import MissionOperationsAgent
from app.modules.ai.agents.scenario_agent import ScenarioArchitectAgent
from app.modules.ai.agents.schemas import (
    HazardEnvelopeResponse,
    IncidentActionPlan,
    MissionMedevacRecommendation,
    MissionMonitorReport,
    MissionSITREP,
    ScenarioPromptGenerateRequest,
    ScenarioStressTestResult,
)
from app.modules.auth.models import User
from app.modules.incident.models import Incident

router = APIRouter(prefix="/agents", tags=["AI Domain Agents"])

incident_agent = IncidentIntelligenceAgent()
mission_agent = MissionOperationsAgent()
scenario_agent = ScenarioArchitectAgent()


# ============================================================================
# INCIDENT INTELLIGENCE AGENT ENDPOINTS
# ============================================================================

@router.post(
    "/incident/{incident_id}/iap",
    response_model=ApiResponse[IncidentActionPlan],
    summary="Generate AI Incident Action Plan (IAP) & Tactical Directive",
)
async def generate_incident_iap(
    incident_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[IncidentActionPlan]:
    try:
        iap = await incident_agent.generate_incident_action_plan(db=db, incident_id=incident_id)
        return ApiResponse.ok(data=iap, message="Incident Action Plan formulated successfully.")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Agent IAP generation error: {str(err)}")


@router.post(
    "/incident/{incident_id}/hazard-envelope",
    response_model=ApiResponse[HazardEnvelopeResponse],
    summary="Calculate dynamic multi-horizon hazard spread envelopes (+15m, +30m, +60m)",
)
async def calculate_hazard_envelope(
    incident_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[HazardEnvelopeResponse]:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident #{incident_id} not found.")
    res = incident_agent.calculate_hazard_envelopes(incident=incident)
    return ApiResponse.ok(data=res, message="Hazard propagation envelopes generated.")


# ============================================================================
# MISSION OPERATIONS AGENT ENDPOINTS
# ============================================================================

@router.post(
    "/mission/{assignment_id}/sitrep",
    response_model=ApiResponse[MissionSITREP],
    summary="Generate tactical Mission Situation Report (SITREP) with anomaly audit",
)
async def generate_mission_sitrep(
    assignment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[MissionSITREP]:
    try:
        sitrep = await mission_agent.generate_mission_sitrep(db=db, assignment_id=assignment_id)
        return ApiResponse.ok(data=sitrep, message="Mission SITREP synthesized successfully.")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Agent SITREP generation error: {str(err)}")


@router.post(
    "/mission/{assignment_id}/medevac",
    response_model=ApiResponse[MissionMedevacRecommendation],
    summary="Generate dynamic Hospital Medevac recommendation & optimal route",
)
async def generate_mission_medevac(
    assignment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[MissionMedevacRecommendation]:
    try:
        medevac = await mission_agent.generate_medevac_recommendation(db=db, assignment_id=assignment_id)
        return ApiResponse.ok(data=medevac, message="Medevac hospital transfer plan generated.")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Agent Medevac allocation error: {str(err)}")


@router.get(
    "/mission/monitor-all",
    response_model=ApiResponse[MissionMonitorReport],
    summary="Batch surveillance & anomaly audit across all active missions",
)
async def monitor_all_missions(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[MissionMonitorReport]:
    try:
        report = await mission_agent.monitor_all_missions(db=db)
        return ApiResponse.ok(data=report, message="Mission monitoring report synthesized.")
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Agent Mission monitoring error: {str(err)}")


# ============================================================================
# SCENARIO ARCHITECT AGENT ENDPOINTS
# ============================================================================

@router.post(
    "/scenario/generate",
    response_model=ApiResponse[dict[str, Any]],
    summary="Generate complete crisis blueprint from natural language prompt",
)
async def generate_scenario_from_prompt(
    payload: ScenarioPromptGenerateRequest,
    _: User = Depends(get_current_active_user),
) -> ApiResponse[dict[str, Any]]:
    try:
        blueprint = await scenario_agent.generate_blueprint_from_prompt(request=payload)
        return ApiResponse.ok(data=blueprint, message="Scenario blueprint synthesized successfully.")
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Agent blueprint generation error: {str(err)}")


@router.post(
    "/scenario/stress-test",
    response_model=ApiResponse[ScenarioStressTestResult],
    summary="Run AI Stress-Test simulation curve and casualty forecast on scenario blueprint",
)
async def stress_test_scenario_config(
    payload: dict[str, Any],
    _: User = Depends(get_current_active_user),
) -> ApiResponse[ScenarioStressTestResult]:
    try:
        result = await scenario_agent.stress_test_scenario(scenario_config=payload)
        return ApiResponse.ok(data=result, message="Scenario stress-test evaluation complete.")
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Agent stress-test error: {str(err)}")
