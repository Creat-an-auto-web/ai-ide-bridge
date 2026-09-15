# AI IDE Bridge TDD Execution Guide

This document describes the complete local execution path from a feature request to a reviewed code patch.

## 1. What the System Does

The default `tdd` engine runs this sequence:

1. Receive a feature request and bounded editor/workspace context.
2. Analyze the requirement and derive user stories and acceptance criteria.
3. Generate normal, boundary, and negative test cases.
4. Convert test cases into executable test files.
5. Generate production implementation files.
6. Run the generated files and tests in an isolated Docker workspace.
7. Repair the implementation when tests fail, up to the configured retry limit.
8. Stream a patch with production and regression-test diffs back to the IDE.

The source workspace is never written during the TDD test loop. The final patch is emitted for review.

## 2. Prerequisites

Install the following locally:

- Python 3.11 or later
- Node.js 20.18.2 for the native Void shell
- Docker Desktop, with the Docker daemon running
- A funded OpenAI-compatible model provider account

Verify Docker before starting the bridge:

```bash
docker info --format '{{.ServerVersion}}'
```

## 3. Backend Setup

From the repository root:

```bash
python -m venv .venv
.venv/bin/pip install -r backend-bridge/requirements.txt
```

Create `backend-bridge/.env`. This file is ignored by Git and must never be committed:

```dotenv
BRIDGE_ENGINE=tdd
GLM_API_KEY=<provider-api-key>
GLM_MODEL=Qwen/Qwen3-8B
GLM_API_BASE=https://api.siliconflow.cn/v1
GLM_WIRE_API=chat_completions
```

`GLM_*` names are generic bridge configuration names. The engine uses them for any OpenAI-compatible provider; they do not require a GLM model.

### Environment Precedence

The bridge loads `backend-bridge/.env` only for variables not already present in the process environment. Existing shell variables therefore take precedence. Before starting the bridge, remove stale provider values when necessary:

```bash
unset GLM_API_KEY GLM_MODEL GLM_API_BASE GLM_WIRE_API
```

For a fully isolated manual launch on macOS/Linux:

```bash
cd backend-bridge
env -i PATH="$PATH" HOME="$HOME" ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 27182
```

Check the service:

```bash
curl http://127.0.0.1:27182/healthz
curl http://127.0.0.1:27182/v1/sandbox-execution/docker/status
```

The second request must report `"available": true` before a Docker-isolated TDD task can complete.

## 4. Frontend Setup

Native Void requires Node 20.18.2:

```bash
npm run install:native-deps --prefix frontend/void
npm run start:native --prefix frontend/void
```

For the browser demo:

```bash
npm run demo --prefix frontend/frontend-bridge
```

Open `http://127.0.0.1:4310`.

In the AI IDE Bridge panel:

1. Enter a feature request and keep the relevant file open.
2. Use **Run** for the complete TDD pipeline.
3. Use **Run requirement analysis** only when reviewing/refining the requirement; it does not generate production code.
4. Watch task status, logs, test results, and the patch preview.
5. Expand each patch file to inspect the generated unified diff before applying it through the host IDE workflow.

## 5. Task API Flow

The frontend submits `POST /v1/tasks` with:

- `userPrompt`: the requested feature or fix
- `repo.rootPath`: absolute workspace path
- `context`: active file, open files, diagnostics, diff, and test logs
- `policy`: workspace, network, duration, and output limits

Example request shape:

```json
{
  "mode": "repo_chat",
  "userPrompt": "Implement calculator.add for two integers and reject other types.",
  "repo": {"rootPath": "/absolute/path/to/project"},
  "context": {"activeFile": "calculator.py", "openFiles": ["calculator.py"]},
  "policy": {
    "workspaceMode": "local",
    "network": "deny",
    "maxDurationSec": 300,
    "maxOutputBytes": 262144
  }
}
```

Subscribe to `ws://127.0.0.1:27182/v1/tasks/{taskId}/events` immediately after task creation. Important events are:

| Event | Meaning |
| --- | --- |
| `task.status` | Queued, planning, running, patch-ready, completed, or failed state |
| `task.plan` | Six-stage TDD plan |
| `task.log` | Model and test process progress |
| `task.test.result` | Per-iteration test counts |
| `task.patch` | Reviewable production and test diffs |
| `task.error` | Structured failure reason |
| `task.final` | Final outcome and artifacts |

## 6. Docker Test Policy

When `policy.network` is `deny`, the TDD engine selects the Docker runtime. It copies the repository to a temporary workspace, overlays generated implementation and immutable test files, then runs the detected test command in the container.

The runtime selects a framework in this order:

1. `unittest`
2. `pytest`
3. `vitest`
4. `jest`
5. A safe model-provided test command

Docker failure does not modify the original repository. The service returns an infrastructure error with diagnostics.

## 7. Model Requirements

The pipeline makes several structured JSON requests. Use a general reasoning or code model that reliably follows JSON instructions. Translation-only models can authenticate successfully but may produce incomplete test-case records, preventing code generation.

The test-case prompt explicitly requires:

- a non-empty object `test_input`
- at least one non-empty `steps` entry
- a non-empty, assertable `expected_result`
- normal, boundary, and negative coverage when requested

## 8. Troubleshooting

| Symptom | Cause | Resolution |
| --- | --- | --- |
| `401 token expired or incorrect` | Invalid API key or wrong provider endpoint | Replace the key and verify `GLM_API_BASE` for the selected provider |
| `402 balance is insufficient` | Provider account has no usable balance | Recharge or use a funded key/model |
| Requests go to an unexpected provider | Stale shell `GLM_*` variables override `.env` | Unset stale variables or use the clean launch command |
| Docker status is unavailable | Docker Desktop is not running | Start Docker Desktop and wait for `docker info` to succeed |
| `expected_result must be a non-empty string` | Selected model returned incomplete structured output | Use a stronger code/reasoning model; inspect task logs |
| WebSocket returns `404` | Uvicorn lacks a WebSocket backend | Reinstall `uvicorn[standard]` or `websockets` |
| `Workspace does not exist` | `repo.rootPath` is wrong | Submit an absolute path to an existing project directory |

## 9. Verification Commands

Run the backend suite:

```bash
cd backend-bridge
../.venv/bin/python -m pytest tests -q
```

Run frontend bridge type checking:

```bash
npm run typecheck --prefix frontend/frontend-bridge
```

Before committing, ensure no local credentials are staged:

```bash
git status --short
git check-ignore -v backend-bridge/.env
git diff --check
```
