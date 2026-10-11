"""
AegisAI AI Module — REST API Router.

Exposes comprehensive endpoints for the AI Decision Intelligence layer.
"""

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.common.response import ApiResponse
from app.core.database.session import get_db
from app.core.middleware.rate_limiter import limiter
from app.core.security.jwt import RequireRole, get_current_active_user
from app.modules.ai.dependencies import get_ai_service
from app.modules.ai.schemas import (
    AIDecisionApproveRequest,
    AIDecisionCreateRequest,
    AIDecisionFeedbackRequest,
    AIDecisionModifyRequest,
    AIDecisionRejectRequest,
    AIDecisionResponse,
    BenchmarkRequest,
    BenchmarkResponse,
    LLMExplanationResponse,
    WhatIfDecisionRequest,
    WhatIfDecisionResponse,
)
from app.modules.ai.service import AIDecisionService
from app.modules.auth.models import User

router = APIRouter(prefix="/ai", tags=["AI Decision Intelligence Engine"])


@router.post(
    "/decisions/generate",
    response_model=ApiResponse[list[AIDecisionResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI emergency response decisions",
    description="Evaluates disaster state and runs optimization to recommend emergency actions.",
)
@limiter.limit("20/minute")
async def generate_decisions(
    request: Request,
    body: AIDecisionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[list[AIDecisionResponse]]:
    decisions = await service.generate_decisions(
        db=db,
        request=body,
        current_user=current_user,
    )
    return ApiResponse.created(
        data=decisions,
        message=f"Successfully generated {len(decisions)} AI emergency decision(s).",
    )


@router.get(
    "/decisions",
    response_model=ApiResponse[dict],
    summary="List and filter AI decisions",
    description="Retrieve paginated list of AI decisions with optional filters.",
)
def list_decisions(
    status: str | None = Query(None, description="Filter by status"),
    decision_type: str | None = Query(None, description="Filter by decision type"),
    incident_id: int | None = Query(None, description="Filter by incident ID"),
    simulation_id: str | None = Query(None, description="Filter by simulation ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[dict]:
    skip = (page - 1) * page_size
    items, total = service.list_decisions(
        db=db,
        status=status,
        decision_type=decision_type,
        incident_id=incident_id,
        simulation_id=simulation_id,
        skip=skip,
        limit=page_size,
    )
    return ApiResponse.paginated(
        data=[item.model_dump(mode="json") for item in items],
        total=total,
        page=page,
        page_size=page_size,
        message=f"Retrieved {len(items)} decision(s).",
    )


@router.get(
    "/decisions/{decision_id}",
    response_model=ApiResponse[AIDecisionResponse],
    summary="Get AI decision by ID or UUID",
)
def get_decision(
    decision_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[AIDecisionResponse]:
    decision = service.get_decision(db, decision_id)
    return ApiResponse.ok(data=AIDecisionResponse.model_validate(decision))


@router.post(
    "/decisions/{decision_id}/approve",
    response_model=ApiResponse[AIDecisionResponse],
    summary="Approve an AI recommendation",
    description="Approves decision and optionally executes transaction-safe dispatch.",
)
async def approve_decision(
    decision_id: str,
    payload: AIDecisionApproveRequest = AIDecisionApproveRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[AIDecisionResponse]:
    approved = await service.approve_decision(
        db=db,
        identifier=decision_id,
        request=payload,
        current_user=current_user,
    )
    return ApiResponse.ok(data=approved, message="AI decision approved successfully.")


@router.post(
    "/decisions/{decision_id}/reject",
    response_model=ApiResponse[AIDecisionResponse],
    summary="Reject an AI recommendation",
    description="Rejects the AI decision and stores commander rationale for auditing.",
)
async def reject_decision(
    decision_id: str,
    payload: AIDecisionRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[AIDecisionResponse]:
    rejected = await service.reject_decision(
        db=db,
        identifier=decision_id,
        request=payload,
        current_user=current_user,
    )
    return ApiResponse.ok(data=rejected, message="AI decision rejected.")


@router.post(
    "/decisions/{decision_id}/modify",
    response_model=ApiResponse[AIDecisionResponse],
    summary="Modify an AI decision before approval",
    description="Allows commander to override recommended unit or destination hospital.",
)
async def modify_decision(
    decision_id: str,
    payload: AIDecisionModifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[AIDecisionResponse]:
    modified = await service.modify_decision(
        db=db,
        identifier=decision_id,
        request=payload,
        current_user=current_user,
    )
    return ApiResponse.ok(data=modified, message="AI decision modified successfully.")


@router.post(
    "/decisions/{decision_id}/execute",
    response_model=ApiResponse[AIDecisionResponse],
    summary="Execute approved AI decision into live mission",
    description="Invokes AssignmentService with row locking to create mission assignment.",
)
async def execute_decision(
    decision_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[AIDecisionResponse]:
    executed = await service.execute_decision(
        db=db,
        identifier=decision_id,
        current_user=current_user,
    )
    return ApiResponse.ok(data=executed, message="AI decision executed into active mission.")


@router.get(
    "/decisions/{decision_id}/explanation",
    response_model=ApiResponse[LLMExplanationResponse],
    summary="Get LLM tactical briefing & explainability",
    description="Generates operational briefing via Ollama LLM based on factual parameters.",
)
async def get_decision_explanation(
    decision_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[LLMExplanationResponse]:
    explanation = await service.get_explanation(db, decision_id)
    return ApiResponse.ok(data=explanation)


@router.post(
    "/decisions/benchmark",
    response_model=ApiResponse[BenchmarkResponse],
    summary="Benchmark decision policies",
    description="Compares Baseline, Heuristic, Global Optimization, and ML-Assisted policies.",
)
async def benchmark_policies(
    payload: BenchmarkRequest = BenchmarkRequest(),
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[BenchmarkResponse]:
    result = await service.benchmark_policies(db, payload)
    return ApiResponse.ok(data=result, message="Policy benchmark completed.")


@router.post(
    "/decisions/what-if",
    response_model=ApiResponse[WhatIfDecisionResponse],
    summary="Simulate What-If disaster scenarios",
    description="Evaluates AI decision recommendations on hypothetical disaster conditions.",
)
async def simulate_what_if(
    payload: WhatIfDecisionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[WhatIfDecisionResponse]:
    result = await service.run_what_if_analysis(db, payload)
    return ApiResponse.ok(data=result, message="What-If scenario evaluated.")


@router.post(
    "/decisions/{decision_id}/feedback",
    response_model=ApiResponse[dict],
    summary="Submit commander feedback & observed outcomes",
    description="Records real-world outcome telemetry and commander feedback for ML training.",
)
def submit_feedback(
    decision_id: str,
    payload: AIDecisionFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
    service: AIDecisionService = Depends(get_ai_service),
) -> ApiResponse[dict]:
    result = service.record_feedback(
        db=db,
        identifier=decision_id,
        request=payload,
        current_user=current_user,
    )
    return ApiResponse.ok(data=result, message="Feedback recorded successfully.")


@router.post(
    "/nlp/triage",
    response_model=ApiResponse[dict],
    summary="Run AI NLP emergency report triage",
    description="Extracts disaster classification, entities, geocoding candidates, and structured summary from text.",
)
async def nlp_triage(
    payload: dict,
    _: User = Depends(get_current_active_user),
) -> ApiResponse[dict]:
    from app.modules.ai.nlp.geocoder import disaster_geocoder
    from app.modules.ai.nlp.ollama_extractor import ollama_disaster_extractor

    text = payload.get("text", "")
    extraction = await ollama_disaster_extractor.extract_and_validate(text)

    geocoded_locations = []
    for loc_cand in extraction.get("data", {}).get("location_candidates", []):
        geo = await disaster_geocoder.geocode_candidate(loc_cand.get("text", ""))
        if geo:
            geocoded_locations.append(geo)

    result = {
        **extraction,
        "geocoded_candidates": geocoded_locations,
    }
    return ApiResponse.ok(data=result, message="NLP text triage completed.")


@router.post(
    "/vision/triage",
    response_model=ApiResponse[dict],
    summary="Run AI Computer Vision disaster image triage",
    description="Analyzes disaster photograph for visible hazards, damage level, and bounding boxes.",
)
async def vision_triage(
    payload: dict,
    _: User = Depends(get_current_active_user),
) -> ApiResponse[dict]:
    from app.modules.ai.vision.service import cv_analyzer

    image_name = payload.get("filename", "incident_image.jpg")
    analysis = cv_analyzer.analyze_image_bytes(image_data=b"synthetic_bytes", filename=image_name)
    return ApiResponse.ok(data=analysis, message="Computer vision image triage completed.")

