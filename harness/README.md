# harness

Minimal verification harnesses for `ai-ide-bridge`.

## bridge_smoke_test.mjs

This script validates the end-to-end path:

1. create task over HTTP
2. connect to task events over WebSocket
3. print events
4. auto-approve command requests by default
5. wait for `task.final`

It uses only Node built-ins available in Node 22:

- `fetch`
- `WebSocket`

## Usage

Start `backend-bridge` first, then run:

```bash
node ai-ide-bridge/harness/bridge_smoke_test.mjs
```

Optional environment variables:

```bash
BRIDGE_BASE_URL=http://127.0.0.1:27182
BRIDGE_TASK_MODE=fix_test
BRIDGE_REPO_PATH=/path/to/repo
BRIDGE_PROMPT="Fix the current failing test"
BRIDGE_AUTO_APPROVE=1
BRIDGE_TIMEOUT_MS=30000
```

Example:

```bash
BRIDGE_REPO_PATH=/home/ricebean/ai-agent node ai-ide-bridge/harness/bridge_smoke_test.mjs
```
