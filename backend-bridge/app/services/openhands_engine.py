from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import urlencode, urlparse

import httpx
import websockets

from app.models.common import gen_id
from app.services.event_bus import EventBus
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


class OpenHandsEngine:
    def __init__(
        self,
        task_service: TaskService,
        event_bus: EventBus,
        openhands_url: str = "http://127.0.0.1:3000",
        request_timeout_sec: float = 180.0,
    ) -> None:
        self.task_service = task_service
        self.event_bus = event_bus
        self.openhands_url = openhands_url.rstrip("/")
        self.request_timeout_sec = request_timeout_sec

    @staticmethod
    def _extract_prompt(req: object) -> str:
        prompt = getattr(req, "userPrompt", None)
        if isinstance(prompt, str) and prompt.strip():
            return prompt
        legacy_prompt = getattr(req, "prompt", None)
        if isinstance(legacy_prompt, str):
            return legacy_prompt
        raise RuntimeError("Task request does not contain a valid user prompt")

    @staticmethod
    def _extract_selected_repository(repo_root_path: str) -> str | None:
        value = repo_root_path.strip().strip("/")
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
            return value
        return None

    @staticmethod
    def _to_ws_base(http_url: str) -> str:
        parsed = urlparse(http_url)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError(f"Invalid URL for websocket conversion: {http_url}")
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        return f"{ws_scheme}://{parsed.netloc}"

    def _build_ws_url(
        self,
        conversation_id: str,
        conversation_url: str | None,
        agent_server_url: str | None,
        session_api_key: str | None,
    ) -> str:
        if conversation_url:
            parsed = urlparse(conversation_url)
            ws_scheme = "wss" if parsed.scheme == "https" else "ws"
            path_prefix = parsed.path.split("/api/conversations")[0].rstrip("/")
            base = f"{ws_scheme}://{parsed.netloc}{path_prefix}"
        elif agent_server_url:
            base = self._to_ws_base(agent_server_url)
        else:
            base = self._to_ws_base(self.openhands_url)

        params: dict[str, str] = {"resend_all": "true"}
        if session_api_key:
            params["session_api_key"] = session_api_key
        return f"{base}/sockets/events/{conversation_id}?{urlencode(params)}"

    @staticmethod
    def _extract_task_status(start_task: dict) -> str:
        return str(start_task.get("status", "WORKING")).upper()

    async def _start_conversation(self, client: httpx.AsyncClient, req) -> dict:
        selected_repository = self._extract_selected_repository(req.repo.rootPath)
        payload = {
            "initial_message": {
                "role": "user",
                "content": [{"type": "text", "text": self._extract_prompt(req)}],
            },
            "agent_type": "default",
        }
        if selected_repository:
            payload["selected_repository"] = selected_repository
            if req.repo.branch:
                payload["selected_branch"] = req.repo.branch
        response = await client.post(
            f"{self.openhands_url}/api/v1/app-conversations",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not data.get("id"):
            raise RuntimeError("OpenHands did not return a valid start task")
        return data

    async def _poll_start_task(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        start_task_id: str,
        timeout_sec: int = 300,
        interval_sec: float = 2.0,
    ) -> dict:
        deadline = asyncio.get_running_loop().time() + timeout_sec
        last_status = ""
        while True:
            response = await client.get(
                f"{self.openhands_url}/api/v1/app-conversations/start-tasks",
                params={"ids": start_task_id},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or not payload or payload[0] is None:
                raise RuntimeError("OpenHands start-task polling returned empty data")
            start_task = payload[0]
            if not isinstance(start_task, dict):
                raise RuntimeError("OpenHands start-task payload is invalid")

            status = self._extract_task_status(start_task)
            detail = start_task.get("detail") or f"OpenHands start task: {status}"
            if status != last_status:
                await self.task_service.set_status(task_id, "planning", str(detail))
                last_status = status

            if status == "READY":
                return start_task
            if status == "ERROR":
                raise RuntimeError(f"OpenHands start task failed: {detail}")
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError("Timeout waiting for OpenHands start task to become READY")
            await asyncio.sleep(interval_sec)

    async def _get_app_conversation(
        self, client: httpx.AsyncClient, conversation_id: str
    ) -> dict | None:
        response = await client.get(
            f"{self.openhands_url}/api/v1/app-conversations",
            params={"ids": conversation_id},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
        return None

    async def _get_execution_status(
        self, client: httpx.AsyncClient, conversation_id: str
    ) -> str | None:
        conversation = await self._get_app_conversation(client, conversation_id)
        if not conversation:
            return None
        value = conversation.get("execution_status")
        return str(value).upper() if value else None

    async def run_task(self, task_id: str) -> None:
        req = self.task_service.get_request(task_id)
        conversation_id: str | None = None

        try:
            await self.task_service.set_status(task_id, "planning", "Connecting to OpenHands...")
            timeout = httpx.Timeout(
                connect=10.0,
                read=self.request_timeout_sec,
                write=30.0,
                pool=30.0,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                start_task = await self._start_conversation(client, req)
                start_task_id = str(start_task["id"])
                await self.event_bus.publish(
                    task_id,
                    "task.log",
                    {
                        "stream": "stdout",
                        "text": f"OpenHands start task created: {start_task_id}\n",
                    },
                )
                ready_task = await self._poll_start_task(client, task_id, start_task_id)
                conversation_id_value = ready_task.get("app_conversation_id")
                if not isinstance(conversation_id_value, str) or not conversation_id_value:
                    raise RuntimeError("OpenHands returned READY but without app_conversation_id")
                conversation_id = conversation_id_value

                conversation = await self._get_app_conversation(client, conversation_id)
                conversation_url = (
                    str(conversation.get("conversation_url"))
                    if isinstance(conversation, dict) and conversation.get("conversation_url")
                    else None
                )
                session_api_key = (
                    str(conversation.get("session_api_key"))
                    if isinstance(conversation, dict) and conversation.get("session_api_key")
                    else None
                )
                agent_server_url = (
                    str(ready_task.get("agent_server_url"))
                    if ready_task.get("agent_server_url")
                    else None
                )
                ws_url = self._build_ws_url(
                    conversation_id=conversation_id,
                    conversation_url=conversation_url,
                    agent_server_url=agent_server_url,
                    session_api_key=session_api_key,
                )
                await self.task_service.set_status(task_id, "running", "Streaming from OpenHands...")

                async with websockets.connect(
                    ws_url,
                    ping_interval=None,
                    ping_timeout=None,
                    close_timeout=30,
                    max_size=None,
                ) as ws:
                    while True:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=20.0)
                        except asyncio.TimeoutError:
                            execution_status = await self._get_execution_status(
                                client, conversation_id
                            )
                            if execution_status in {"FINISHED", "STOPPED", "PAUSED"}:
                                break
                            continue
                        except websockets.exceptions.ConnectionClosed as exc:
                            execution_status = await self._get_execution_status(
                                client, conversation_id
                            )
                            if execution_status in {"FINISHED", "STOPPED", "PAUSED"}:
                                break
                            raise RuntimeError(
                                f"OpenHands websocket closed before completion: {exc}"
                            ) from exc
                        event = json.loads(message)
                        await self._handle_openhands_event(task_id, event, ws)
                        event_type = event.get("type") if isinstance(event, dict) else None
                        if event_type == "AgentStateChangedObservation":
                            state = str(event.get("agent_state", "")).upper()
                            if state in {"FINISHED", "STOPPED"}:
                                break

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
                    "message": str(exc) or repr(exc),
                    "retryable": False,
                },
            )
            await self.event_bus.publish(
                task_id,
                "task.final",
                {"outcome": "failed", "summary": "Task failed due to engine error"},
            )

    async def _handle_openhands_event(self, task_id: str, event: dict, ws) -> None:
        event_type = event.get("type", "")

        await self.event_bus.publish(
            task_id,
            "task.log",
            {"stream": "stdout", "text": json.dumps(event, ensure_ascii=False) + "\n"},
        )

        if event_type == "AgentStateChangedObservation":
            state = event.get("agent_state")
            if state == "running":
                await self.task_service.set_status(task_id, "running", "Agent is thinking...")

        elif event_type == "CmdOutputObservation":
            await self.event_bus.publish(
                task_id,
                "task.log",
                {"stream": "stdout", "text": event.get("content", "")}
            )

        elif event_type == "ActionApprovalRequest":
            command_id = gen_id("cmd")
            command = event.get("command", "")

            await self.task_service.request_command_approval(
                task_id=task_id,
                command_id=command_id,
                command=command,
                cwd=".",
                risk_level="high",
                reason="OpenHands requested permission to run this command"
            )

            approved = await self.task_service.wait_for_approval(task_id, command_id, timeout=300)

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
