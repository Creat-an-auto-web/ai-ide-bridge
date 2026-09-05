from __future__ import annotations

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, status

from app.models.common import ErrorBody, ResponseEnvelope
from app.models.sandbox_execution import SandboxExecutionRunRequest


router = APIRouter(prefix="/v1/sandbox-execution", tags=["SandboxExecution"])


@router.get("/docker/status", response_model=ResponseEnvelope)
async def get_docker_runtime_status(request: Request) -> ResponseEnvelope:
    service = request.app.state.sandbox_execution_service
    return ResponseEnvelope(
        success=True,
        data=await service.check_docker_runtime(),
    )


@router.post("/runs", response_model=ResponseEnvelope)
async def run_sandbox_execution(
    payload: SandboxExecutionRunRequest,
    request: Request,
) -> ResponseEnvelope:
    service = request.app.state.sandbox_execution_service
    try:
        result = await service.run(payload)
    except ValueError as exc:
        return ResponseEnvelope(
            success=False,
            error=ErrorBody(
                code="VALIDATION_ERROR",
                message=str(exc),
                retryable=False,
            ),
        )
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


@router.websocket("/ws")
async def stream_sandbox_execution(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        raw_payload = await websocket.receive_json()
        payload = SandboxExecutionRunRequest.model_validate(raw_payload)
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json(
            {
                "type": "error",
                "stage": "invalid_request",
                "message": str(exc),
            },
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    service = websocket.app.state.sandbox_execution_service

    try:
        await service.stream_run(payload, websocket.send_json)
    except WebSocketDisconnect:
        return
    except ValueError as exc:
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "stage": "validation_failed",
                    "message": str(exc),
                },
            )
        except WebSocketDisconnect:
            return
    except Exception as exc:  # noqa: BLE001
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "stage": "failed",
                    "message": str(exc),
                },
            )
        except WebSocketDisconnect:
            return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
