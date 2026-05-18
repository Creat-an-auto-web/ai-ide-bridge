from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.requirement_analysis import router as requirement_analysis_router
from app.api.test_case_generation import router as test_case_generation_router
from app.api.test_code_generation import router as test_code_generation_router
from app.api.test_code_execution import router as test_code_execution_router
from app.api.test_code_repair import router as test_code_repair_router
from app.api.tasks import router as task_router
from app.services.event_bus import EventBus
from app.services.mock_engine import MockEngine
from app.services.openhands_engine import OpenHandsEngine
from app.services.requirement_analysis_service import RequirementAnalysisBackendService
from app.services.test_case_generation_service import TestCaseGenerationBackendService
from app.services.test_code_execution_service import TestCodeExecutionBackendService
from app.services.test_code_generation_service import TestCodeGenerationBackendService
from app.services.test_code_repair_service import TestCodeRepairBackendService
from app.services.task_service import TaskService


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


_load_local_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    event_bus = EventBus()
    task_service = TaskService(event_bus)
    
    use_mock = os.getenv("USE_MOCK_ENGINE", "false").lower() in ("true", "1", "yes")
    if use_mock:
        engine = MockEngine(task_service, event_bus)
    else:
        openhands_url = os.getenv("OPENHANDS_URL", "http://127.0.0.1:3000")
        engine = OpenHandsEngine(task_service, event_bus, openhands_url)
        
    task_service.set_engine(engine)

    app.state.event_bus = event_bus
    app.state.task_service = task_service
    app.state.requirement_analysis_service = RequirementAnalysisBackendService()
    app.state.test_case_generation_service = TestCaseGenerationBackendService()
    app.state.test_code_generation_service = TestCodeGenerationBackendService()
    app.state.test_code_execution_service = TestCodeExecutionBackendService()
    app.state.test_code_repair_service = TestCodeRepairBackendService()
    yield


app = FastAPI(title="AI IDE Bridge API", version="v1alpha1", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"ok": True}


app.include_router(task_router)
app.include_router(requirement_analysis_router)
app.include_router(test_case_generation_router)
app.include_router(test_code_generation_router)
app.include_router(test_code_execution_router)
app.include_router(test_code_repair_router)
