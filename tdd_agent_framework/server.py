from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from tdd_agent_framework.agents.requirement_analysis import (
    RequirementAnalysisAgentSettings,
    RequirementAnalysisInput,
    build_requirement_analysis_service,
)


def _json_response(
    handler: BaseHTTPRequestHandler,
    status_code: int,
    payload: dict[str, Any],
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


async def _run_requirement_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    settings = RequirementAnalysisAgentSettings.from_dict(payload.get("settings"))
    analysis_input = RequirementAnalysisInput.from_dict(payload.get("input"))
    service = build_requirement_analysis_service(settings)
    result = await service.analyze(analysis_input)
    return asdict(result)


class RequirementAnalysisHttpHandler(BaseHTTPRequestHandler):
    server_version = "RequirementAnalysisHTTP/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802
        _json_response(self, 200, {"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            _json_response(self, 200, {"ok": True})
            return
        _json_response(
            self,
            404,
            {"success": False, "error": {"message": "not found"}},
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/requirement-analysis/runs":
            _json_response(
                self,
                404,
                {"success": False, "error": {"message": "not found"}},
            )
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            result = asyncio.run(_run_requirement_analysis(payload))
        except Exception as exc:  # noqa: BLE001
            _json_response(
                self,
                400,
                {
                    "success": False,
                    "error": {
                        "message": str(exc),
                    },
                },
            )
            return

        _json_response(
            self,
            200,
            {
                "success": True,
                "data": result,
            },
        )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="RequirementAnalysis prototype HTTP service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=27184)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), RequirementAnalysisHttpHandler)
    print(
        f"RequirementAnalysis prototype server listening on http://{args.host}:{args.port}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
