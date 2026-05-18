from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.common import ErrorBody, ResponseEnvelope
from app.models.test_code_execution import TestCodeExecutionRunRequest


router = APIRouter(prefix="/v1/test-code-execution", tags=["TestCodeExecution"])


@router.post("/runs", response_model=ResponseEnvelope)
async def run_test_code_execution(
    payload: TestCodeExecutionRunRequest,
    request: Request,
) -> ResponseEnvelope:
    service = request.app.state.test_code_execution_service
    try:
        result = await service.run(payload)
    except Exception as exc:  # noqa: BLE001
        return ResponseEnvelope(
            success=False,
            error=ErrorBody(
                code="TOOL_ERROR",
                message=str(exc),
                retryable=False,
            ),
        )

    return ResponseEnvelope(
        success=True,
        data=result,
    )
