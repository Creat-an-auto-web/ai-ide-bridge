from __future__ import annotations

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, status

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


@router.websocket("/ws")
async def stream_requirement_analysis(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        raw_payload = await websocket.receive_json()
        payload = RequirementAnalysisRunRequest.model_validate(raw_payload)
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json(
            {
                "type": "error",
                "stage": "invalid_request",
                "message": str(exc),
            }
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    service = websocket.app.state.requirement_analysis_service

    try:
        await websocket.send_json(
            {
                "type": "status",
                "stage": "accepted",
                "message": "已收到第一环运行请求",
            }
        )
        await service.stream_run(payload, websocket.send_json)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "stage": "failed",
                    "message": str(exc),
                }
            )
        except WebSocketDisconnect:
            return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
