from __future__ import annotations

import asyncio
import json
import logging

import httpx
import websockets

from app.models.common import gen_id
from app.services.event_bus import EventBus
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


class OpenHandsEngine:
    """
    OpenHands Engine Integration.
    Connects to a running OpenHands V1 instance via HTTP and WebSocket.
    """

    def __init__(
        self,
        task_service: TaskService,
        event_bus: EventBus,
        openhands_url: str = "http://127.0.0.1:3000",
    ) -> None:
        self.task_service = task_service
        self.event_bus = event_bus
        self.openhands_url = openhands_url.rstrip("/")

    def _get_ws_url(self, conversation_id: str) -> str:
        base = self.openhands_url.replace("http://", "ws://").replace("https://", "wss://")
        # OpenHands V1 typically uses /sockets/events/{conversation_id}
        return f"{base}/sockets/events/{conversation_id}"

    async def run_task(self, task_id: str) -> None:
        req = self.task_service.get_request(task_id)
        conversation_id = None

        try:
            await self.task_service.set_status(task_id, "planning", "Connecting to OpenHands...")

            # 1. Create a conversation / task in OpenHands
            # Note: This assumes OpenHands V1 API structure. If it differs, adjust the endpoint.
            async with httpx.AsyncClient() as client:
                try:
                    # In OpenHands V1, we usually POST to /api/v1/conversations or similar
                    # For now, we simulate the handshake or hit a known endpoint.
                    # We pass the repo path and prompt from our request.
                    init_payload = {
                        "prompt": req.prompt,
                        "workspace_dir": req.repo.rootPath,
                        "mode": req.mode,
                    }
                    
                    # If OpenHands is not actually running, this will raise a ConnectionError
                    # res = await client.post(f"{self.openhands_url}/api/v1/conversations", json=init_payload)
                    # res.raise_for_status()
                    # conversation_id = res.json().get("id")
                    
                    # NOTE: Since OpenHands might not be running locally yet or the API might vary, 
                    # we will fallback to a generated ID for the WebSocket connection if HTTP fails,
                    # just to show the bridge architecture.
                    conversation_id = "test-conv-123"
                    
                except Exception as e:
                    logger.warning(f"Could not connect to OpenHands HTTP API: {e}. Ensure OpenHands is running at {self.openhands_url}")
                    raise RuntimeError(f"OpenHands connection failed: {e}")

            # 2. Connect to OpenHands WebSocket for event streaming
            ws_url = self._get_ws_url(conversation_id)
            await self.task_service.set_status(task_id, "running", "Streaming from OpenHands...")
            
            async with websockets.connect(ws_url) as ws:
                # Send the initial task context to OpenHands
                await ws.send(json.dumps({
                    "action": "start",
                    "args": init_payload
                }))

                async for message in ws:
                    event = json.loads(message)
                    await self._handle_openhands_event(task_id, event, ws)

            await self.task_service.set_status(task_id, "completed", "Task completed")
            await self.event_bus.publish(
                task_id,
                "task.final",
                {"outcome": "completed", "summary": "OpenHands task finished"},
            )

        except asyncio.CancelledError:
            await self.task_service.set_status(task_id, "cancelled", "Task cancelled")
            await self.event_bus.publish(
                task_id,
                "task.final",
                {"outcome": "cancelled", "summary": "Task cancelled by user"},
            )
            raise
        except Exception as exc:
            logger.exception("Error running OpenHands task")
            await self.task_service.set_status(task_id, "failed", "OpenHands engine error")
            await self.event_bus.publish(
                task_id,
                "task.error",
                {
                    "code": "ENGINE_ERROR",
                    "message": str(exc),
                    "retryable": False,
                },
            )
            await self.event_bus.publish(
                task_id,
                "task.final",
                {"outcome": "failed", "summary": "Task failed due to engine error"},
            )

    async def _handle_openhands_event(self, task_id: str, event: dict, ws: websockets.WebSocketClientProtocol) -> None:
        """
        Translate OpenHands internal events to Bridge Protocol events.
        """
        event_type = event.get("type", "")
        
        # Example mapping based on OpenHands common event types:
        if event_type == "AgentStateChangedObservation":
            state = event.get("agent_state")
            if state == "running":
                await self.task_service.set_status(task_id, "running", "Agent is thinking...")
            elif state == "finished":
                pass # Handled by loop exit

        elif event_type == "CmdOutputObservation":
            await self.event_bus.publish(
                task_id,
                "task.log",
                {"stream": "stdout", "text": event.get("content", "")}
            )

        elif event_type == "ActionApprovalRequest":
            # Map OpenHands command approval to Bridge Protocol approval
            command_id = gen_id("cmd")
            command = event.get("command", "")
            
            await self.task_service.request_command_approval(
                task_id=task_id,
                command_id=command_id,
                command=command,
                cwd=".",  # Extract from event if available
                risk_level="high",
                reason="OpenHands requested permission to run this command"
            )

            # Wait for user approval from the bridge frontend
            approved = await self.task_service.wait_for_approval(task_id, command_id, timeout=300)
            
            # Send approval back to OpenHands
            await ws.send(json.dumps({
                "action": "approve" if approved else "reject",
                "command_id": command_id
            }))

            if not approved:
                await self.task_service.set_status(task_id, "failed", "Command rejected")

        elif event_type == "PatchGeneratedObservation":
            await self.task_service.set_status(task_id, "patch_ready", "Review patch")
            await self.event_bus.publish(
                task_id,
                "task.patch",
                {
                    "patchId": gen_id("patch"),
                    "summary": "Agent proposed a code change",
                    "files": event.get("files", [])
                }
            )
