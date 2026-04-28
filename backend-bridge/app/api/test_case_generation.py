from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.common import ErrorBody, ResponseEnvelope
from app.models.test_case_generation import TestCaseGenerationRunRequest


router = APIRouter(prefix="/v1/test-case-generation", tags=["TestCaseGeneration"])


@router.post("/runs", response_model=ResponseEnvelope)
async def run_test_case_generation(
    payload: TestCaseGenerationRunRequest,
    request: Request,
) -> ResponseEnvelope:
    service = request.app.state.test_case_generation_service
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
