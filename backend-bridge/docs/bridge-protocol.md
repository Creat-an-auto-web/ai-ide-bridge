# AI IDE Bridge Protocol

Version: `v1alpha1`  
Status: Draft  
Last Updated: `2026-03-28`

## 1. Purpose

This document defines the formal integration contract for this workspace:

- `void/` is the IDE shell and frontend client
- `ai-ide-bridge/backend-bridge/` is the protocol and orchestration layer
- `OpenHands/` is the agent execution backend and runtime provider

The protocol is the stable product boundary. Neither side should depend on the internal implementation details of Void or OpenHands.

## 2. Product Goal

The project aims to build a local AI IDE similar in user experience to Cursor, but with stronger control over backend agent workflows.

The product differs from a typical AI editor in one core way:

- agent execution must be observable
- agent execution must be controllable
- dangerous actions must be explicitly governed
- code changes should be reviewable before they are applied

This protocol exists to support those goals.

## 3. Architecture Boundary

### 3.1 Frontend Responsibility

The Void-based frontend is responsible for:

- launching tasks
- collecting editor and workspace context
- rendering task progress
- rendering logs and plan steps
- showing command approval UI
- previewing patches and diffs
- accepting or rejecting patches

The frontend must not depend on OpenHands internal objects, event classes, or runtime-specific APIs.

### 3.2 Backend Responsibility

The backend bridge is responsible for:

- receiving structured task requests
- validating input and policy
- managing task lifecycle
- managing workspace and runtime mode
- streaming events back to the frontend
- mediating command approval
- producing structured patch output
- adapting execution engines such as OpenHands

The backend must not expose Void internal component state or UI-specific structures.

### 3.3 OpenHands Responsibility

OpenHands is treated as an execution engine, not as the product protocol.

It is responsible for:

- planning and executing multi-step agent tasks
- interacting with tools and runtime environments
- reading files, running commands, and generating changes

The bridge protocol must not mirror OpenHands internal request or event types directly.

## 4. Design Principles

### 4.1 Protocol First

The protocol is the primary integration surface and must be defined before deep frontend or backend coupling.

### 4.2 HTTP for Control, WebSocket for Execution

Control-plane actions use HTTP and JSON:

- create task
- get task
- cancel task
- approve or reject command
- accept or reject patch

Execution-plane feedback uses WebSocket:

- status changes
- plans
- logs
- approval requests
- command results
- patches
- test results
- final outcomes

### 4.3 Patch Before Write

By default, the backend emits patch data for review. It should not force-write project files after patch emission unless the protocol or policy explicitly allows it.

This is the preferred product behavior because it preserves reviewability and supports agent workflow control.

### 4.4 Stable Bridge, Replaceable Engines

The bridge layer should remain stable even if:

- the frontend implementation changes
- the backend execution engine changes
- the runtime mode changes from local to docker or remote

### 4.5 No MCP as the Primary IDE Protocol

MCP may be used inside backend tooling or agent integrations, but it is not the primary protocol between the IDE frontend and the bridge backend.

The IDE-facing contract is this bridge protocol.

## 5. Transport

### 5.1 Control Plane

- Transport: HTTP/JSON over localhost
- Default base URL: `http://127.0.0.1:27182`

### 5.2 Event Plane

- Transport: WebSocket
- Endpoint: `/v1/tasks/{taskId}/events`
- Encoding: UTF-8 JSON text frames

### 5.3 Common Encoding Rules

- timestamps use RFC3339 UTC format
- IDs are opaque strings
- clients must ignore unknown additive fields
- clients must treat unknown enum values as unsupported

## 6. Versioning and Compatibility

### 6.1 Protocol Version

Current protocol version: `v1alpha1`

### 6.2 Compatibility Rules

- all endpoints are namespaced under `/v1`
- additive fields are allowed within the same major version
- existing fields must not change meaning within the same major version
- breaking changes require a version bump
- each response should include `protocolVersion`

### 6.3 Merge Checklist for Protocol Changes

Before merging a protocol change:

- frontend parser updated
- backend serializer updated
- event enum reviewed
- example payload updated
- breaking-change impact assessed
- version bump decision recorded

## 7. Protocol Scope

### 7.1 Goals

- stable task creation and control
- real-time event streaming
- command approval workflow
- structured patch delivery
- clear error handling
- support for local, docker, and remote workspace modes

### 7.2 Non-Goals

- exposing OpenHands internal SDK models
- exposing Void internal view state
- defining provider-specific LLM request payloads
- reproducing legacy OpenHands V0 websocket protocols

## 8. Task Model

### 8.1 Allowed Task Modes

- `repo_chat`
- `edit_selection`
- `fix_test`
- `refactor_scope`
- `explain_error`

### 8.2 Task Lifecycle States

- `queued`
- `planning`
- `awaiting_approval`
- `running`
- `patch_ready`
- `completed`
- `failed`
- `cancelled`

### 8.3 Task Semantics

A task is a backend-managed unit of work with:

- structured input context
- explicit execution policy
- a lifecycle state
- a stream of events
- a patch or completion outcome

### 8.4 Task Object

```json
{
  "taskId": "task_001",
  "mode": "fix_test",
  "status": "running",
  "workspaceMode": "docker",
  "createdAt": "2026-03-24T18:00:00Z",
  "updatedAt": "2026-03-24T18:00:10Z",
  "latestMessage": "Running tests"
}
```

## 9. Context Model

The frontend must send structured context, not arbitrary ad hoc payloads.

### 9.1 Current Editor Context

- active file
- selection
- open files

### 9.2 Repository Context

- repository root path
- branch
- git diff summary or raw diff

### 9.3 Diagnostics Context

- diagnostics
- terminal tail
- test logs

### 9.4 User Intent Context

- user prompt
- task mode
- workspace policy

### 9.5 Example

```json
{
  "activeFile": "src/foo.ts",
  "selection": {
    "startLine": 10,
    "startCol": 1,
    "endLine": 30,
    "endCol": 1
  },
  "openFiles": [
    "src/foo.ts",
    "tests/foo.test.ts"
  ],
  "diagnostics": [],
  "gitDiff": "",
  "terminalTail": "",
  "testLogs": ""
}
```

## 10. Policy Model

Policy is part of the task contract and must be explicit.

### 10.1 Core Fields

- `workspaceMode`: `local | docker | remote`
- `network`: `allow | deny`
- `requireApprovalFor`: `string[]`
- `maxDurationSec`: `integer`
- `maxOutputBytes`: `integer`
- `writablePaths`: `string[]`
- `envAllowlist`: `string[]`

### 10.2 Product Intention

The protocol should support two practical runtime modes:

- development mode: local workspace for fast iteration
- safety mode: docker or remote workspace for stronger isolation

## 11. HTTP API

### 11.1 Create Task

- Method: `POST`
- Path: `/v1/tasks`

Example request:

```json
{
  "requestId": "req_001",
  "sessionId": "sess_001",
  "protocolVersion": "v1alpha1",
  "mode": "fix_test",
  "userPrompt": "修复当前测试失败",
  "repo": {
    "rootPath": "/path/to/repo",
    "branch": "main"
  },
  "context": {
    "activeFile": "src/foo.ts",
    "selection": {
      "startLine": 10,
      "startCol": 1,
      "endLine": 30,
      "endCol": 1
    },
    "openFiles": [
      "src/foo.ts",
      "tests/foo.test.ts"
    ],
    "diagnostics": [],
    "gitDiff": "",
    "terminalTail": "",
    "testLogs": ""
  },
  "policy": {
    "workspaceMode": "local",
    "network": "deny",
    "requireApprovalFor": [
      "package_install",
      "destructive_command",
      "git_push"
    ],
    "maxDurationSec": 600,
    "maxOutputBytes": 262144,
    "writablePaths": [],
    "envAllowlist": []
  }
}
```

Example response:

```json
{
  "success": true,
  "requestId": "req_001",
  "data": {
    "task": {
      "taskId": "task_001",
      "mode": "fix_test",
      "status": "queued",
      "workspaceMode": "local",
      "createdAt": "2026-03-24T18:00:00Z",
      "updatedAt": "2026-03-24T18:00:00Z",
      "latestMessage": "Task queued"
    }
  },
  "error": null,
  "protocolVersion": "v1alpha1"
}
```

### 11.2 Get Task

- Method: `GET`
- Path: `/v1/tasks/{taskId}`

### 11.3 Cancel Task

- Method: `POST`
- Path: `/v1/tasks/{taskId}/cancel`

### 11.4 Command Approval

- Method: `POST`
- Path: `/v1/tasks/{taskId}/commands/{commandId}/approval`

Example request:

```json
{
  "approved": true,
  "reason": "User accepted package install"
}
```

### 11.5 Patch Acceptance

These endpoints are part of the intended protocol surface but may be implemented after the current task and approval flow is stable:

- `POST /v1/tasks/{taskId}/patches/{patchId}/accept`
- `POST /v1/tasks/{taskId}/patches/{patchId}/reject`

### 11.6 Retry Task

Retry is a valid future protocol operation but is not required for the initial minimum bridge:

- `POST /v1/tasks/{taskId}/retry`

## 12. Common Envelopes

### 12.1 Response Envelope

```json
{
  "success": true,
  "requestId": "req_123",
  "data": {},
  "error": null,
  "protocolVersion": "v1alpha1"
}
```

### 12.2 Error Envelope

```json
{
  "success": false,
  "requestId": "req_123",
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "repo.rootPath is required",
    "retryable": false,
    "details": {}
  },
  "protocolVersion": "v1alpha1"
}
```

## 13. Event Stream Model

All task events must use a unified envelope.

### 13.1 Event Envelope

```json
{
  "eventId": "evt_001",
  "taskId": "task_001",
  "seq": 12,
  "type": "task.log",
  "timestamp": "2026-03-24T18:00:12Z",
  "payload": {}
}
```

### 13.2 Event Rules

- events are ordered by `seq` per task
- duplicate delivery should be tolerated by clients
- each event belongs to exactly one task
- frontend parsing must not depend on event-specific outer shapes

### 13.3 Event Types

- `task.status`
- `task.plan`
- `task.log`
- `task.command.request`
- `task.command.result`
- `task.patch`
- `task.test.result`
- `task.error`
- `task.final`

### 13.4 Status Event

```json
{
  "type": "task.status",
  "payload": {
    "status": "running",
    "message": "Running pytest"
  }
}
```

### 13.5 Plan Event

```json
{
  "type": "task.plan",
  "payload": {
    "steps": [
      "Read failing test logs",
      "Locate related source file",
      "Patch implementation",
      "Re-run tests"
    ]
  }
}
```

### 13.6 Log Event

```json
{
  "type": "task.log",
  "payload": {
    "stream": "stdout",
    "text": "pytest -q\n"
  }
}
```

### 13.7 Command Request Event

```json
{
  "type": "task.command.request",
  "payload": {
    "commandId": "cmd_001",
    "command": "npm install",
    "cwd": "/workspace",
    "riskLevel": "high",
    "reason": "Install missing dependency"
  }
}
```

### 13.8 Command Result Event

```json
{
  "type": "task.command.result",
  "payload": {
    "commandId": "cmd_001",
    "exitCode": 0,
    "stdout": "...",
    "stderr": ""
  }
}
```

### 13.9 Patch Event

```json
{
  "type": "task.patch",
  "payload": {
    "patchId": "patch_001",
    "summary": "Fix parser boundary check",
    "files": [
      {
        "path": "src/parser.ts",
        "changeType": "modify",
        "unifiedDiff": "@@ ...",
        "ops": [
          {
            "op": "replace_range",
            "startLine": 42,
            "endLine": 49,
            "content": "..."
          }
        ]
      }
    ]
  }
}
```

### 13.10 Test Result Event

```json
{
  "type": "task.test.result",
  "payload": {
    "framework": "pytest",
    "passed": 12,
    "failed": 0,
    "skipped": 1
  }
}
```

### 13.11 Error Event

```json
{
  "type": "task.error",
  "payload": {
    "code": "TOOL_ERROR",
    "message": "pytest not found",
    "retryable": true
  }
}
```

### 13.12 Final Event

```json
{
  "type": "task.final",
  "payload": {
    "outcome": "completed",
    "summary": "Fixed failing test and verified with pytest",
    "artifacts": {
      "patchId": "patch_001"
    }
  }
}
```

## 14. Command Approval Protocol

Agent command execution must use an explicit frontend-backend handshake when approval is required.

### 14.1 Required Properties

- `commandId`
- approval endpoint
- approval response
- timeout policy
- rejection behavior

### 14.2 Risk Levels

- `low`
- `medium`
- `high`
- `critical`

### 14.3 Commands That Typically Require Approval

- destructive commands such as `rm -rf`
- privilege escalation such as `sudo`
- package installation
- network downloads
- remote git actions such as `git push`

### 14.4 Timeout and Rejection

The protocol must define what happens on timeout or explicit rejection. The recommended default is:

- timeout: mark approval as expired and fail the blocked action
- rejection: stop the blocked action and report the outcome clearly

## 15. Patch Protocol

### 15.1 Required Patch Shape

Patch payloads should support:

- multi-file changes
- structured file operations
- unified diff rendering
- patch summary text

Each changed file should include:

- `path`
- `changeType`
- `ops[]`
- `unifiedDiff`

### 15.2 Patch Principle

Transmission should favor structured patch data. Presentation may use unified diff text.

### 15.3 Acceptance Model

The intended default flow is:

1. backend generates patch
2. frontend previews patch
3. user accepts or rejects patch
4. file application occurs only after explicit acceptance, unless policy allows direct application

## 16. Error Model

### 16.1 Allowed Error Codes

- `VALIDATION_ERROR`
- `AUTH_ERROR`
- `WORKSPACE_ERROR`
- `MODEL_ERROR`
- `TOOL_ERROR`
- `PATCH_ERROR`
- `TIMEOUT_ERROR`
- `INTERNAL_ERROR`

### 16.2 Error Envelope Requirements

Each error should include:

- code
- message
- retryable
- details

## 17. Observability

Task-related logs should include, where available:

- `requestId`
- `sessionId`
- `taskId`
- `traceId`
- `workspaceMode`
- `model`
- `latencyMs`

These fields are primarily for debugging and production support and may be added incrementally.

## 18. Implementation Guidance

### 18.1 Current Direction

The current workspace already has a minimum bridge skeleton:

- task creation
- task retrieval
- task cancellation
- command approval
- event streaming
- mock patch output

This document should guide the next iterations of that bridge.

### 18.2 Recommended Execution Order

1. keep the protocol stable
2. let the Void frontend integrate against mock events first
3. keep patch review in the loop
4. replace the mock engine with a real OpenHands adapter only after the protocol boundary is stable

### 18.3 OpenHands Integration Direction

When integrating OpenHands, prefer the current application-server or SDK-oriented path rather than legacy V0 conversation and websocket flows.

## 19. Status of Optional Items

The following are part of the intended protocol but may be unimplemented in the current bridge code:

- task retry
- patch accept endpoint
- patch reject endpoint
- richer observability fields
- partial patch acceptance

They remain valid protocol targets, but they are not prerequisites for the minimum bridge.

## 20. Source Integration Summary

This document consolidates and formalizes the intent previously described across:

- project root `readme.md`
- `tips/backend_condition.md`
- `tips/instruction.md`
- `tips/structure.md`
- `tips/task_assignment.md`
- `tips/protocol.md`

Where those sources conflicted, this document resolves them with the following decisions:

- the bridge protocol is the primary stable integration surface
- MCP is not the primary IDE-to-bridge protocol
- patch review is preferred over direct file writes
- OpenHands is an execution engine behind the bridge, not the protocol itself
- legacy OpenHands V0 server flows should not define this protocol
