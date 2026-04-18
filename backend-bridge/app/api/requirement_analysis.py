from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.common import ErrorBody, ResponseEnvelope
from app.models.requirement_analysis import RequirementAnalysisRunRequest


router = APIRouter(prefix="/v1/requirement-analysis", tags=["RequirementAnalysis"])


@router.post("/runs", response_model=ResponseEnvelope)
async def run_requirement_analysis(
    payload: RequirementAnalysisRunRequest,
    request: Request,
) -> ResponseEnvelope:
    service = request.app.state.requirement_analysis_service
    try:
        result = await service.run(payload)
    except Exception as exc:  # noqa: BLE001
        return ResponseEnvelope(
            success=False,
            error=ErrorBody(
                code="MODEL_ERROR",
                message=str(exc),
                retryable=False,
            ),
        )

    return ResponseEnvelope(
        success=True,
        data=result,
    )
