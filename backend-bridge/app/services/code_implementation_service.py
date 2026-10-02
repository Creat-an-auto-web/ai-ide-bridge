from __future__ import annotations

from dataclasses import asdict
from pathlib import Path, PurePosixPath
import sys

from app.models.code_implementation import CodeImplementationRunRequest


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tdd_agent_framework.agents.code_implementation import (  # noqa: E402
    CodeImplementationAgentSettings,
    CodeImplementationInput,
)
from tdd_agent_framework.orchestrators import CodeImplementationOrchestrator  # noqa: E402


class CodeImplementationBackendService:
    def __init__(self, orchestrator: CodeImplementationOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or CodeImplementationOrchestrator()

    async def run(self, payload: CodeImplementationRunRequest) -> dict:
        settings = CodeImplementationAgentSettings.from_dict(payload.settings.model_dump())
        input_data = payload.input.model_dump()
        repo_root = Path(input_data.pop("repo_root")).expanduser().resolve()
        if not repo_root.is_dir():
            raise ValueError(f"Workspace does not exist: {repo_root}")
        if not input_data["repository_context"]:
            input_data["repository_context"] = self._collect_repository_context(repo_root)
        implementation_input = CodeImplementationInput(**input_data)
        result = await self.orchestrator.run(settings, implementation_input)
        return asdict(result)

    @staticmethod
    def _collect_repository_context(repo_root: Path) -> dict[str, str]:
        """Return a bounded, non-secret source snapshot for the implementation prompt."""
        ignored = {".git", ".venv", "venv", "node_modules", "dist", "build", "coverage", "__pycache__"}
        manifests = {"package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml", "pom.xml", "README.md"}
        suffixes = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".toml", ".yaml", ".yml", ".md", ".go", ".java", ".rs"}
        result: dict[str, str] = {}
        remaining = 120_000
        for path in sorted(repo_root.rglob("*")):
            if len(result) >= 48 or remaining <= 0 or not path.is_file():
                continue
            try:
                relative = path.relative_to(repo_root)
            except ValueError:
                continue
            if any(part in ignored for part in relative.parts):
                continue
            if path.name.startswith(".env") or "secret" in path.name.lower() or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
                continue
            if path.name not in manifests and path.suffix.lower() not in suffixes:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            limit = min(12_000, remaining)
            result[PurePosixPath(relative).as_posix()] = content[:limit] + ("\n[truncated]" if len(content) > limit else "")
            remaining -= min(len(content), limit)
        return result
