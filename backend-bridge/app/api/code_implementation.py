from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.code_implementation import CodeImplementationRunRequest
from app.models.common import ErrorBody, ResponseEnvelope


router = APIRouter(prefix="/v1/code-implementation", tags=["CodeImplementation"])


@router.post("/runs", response_model=ResponseEnvelope)
async def run_code_implementation(
    payload: CodeImplementationRunRequest,
    request: Request,
) -> ResponseEnvelope:
    service = request.app.state.code_implementation_service
    try:
        result = await service.run(payload)
    except Exception as exc:  # noqa: BLE001
        return ResponseEnvelope(
            success=False,
            error=ErrorBody(code="MODEL_ERROR", message=str(exc), retryable=False),
        )
    return ResponseEnvelope(success=True, data=result)
