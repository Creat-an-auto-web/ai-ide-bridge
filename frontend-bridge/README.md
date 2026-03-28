# frontend-bridge

Frontend-side bridge module for integrating Void with `backend-bridge`.

## Scope

This package is intentionally kept outside `void/`.

It provides:

- protocol-facing TypeScript types
- a bridge HTTP/WebSocket client
- a state reducer for task events
- a Void-facing context adapter interface

It does not modify Void internals directly.

## Main Entry Points

- `src/protocol.ts`
- `src/client.ts`
- `src/state.ts`
- `src/void-adapter.ts`

## Intended Usage

1. Implement `VoidBridgeContextSource` by calling existing Void services.
2. Build a `CreateTaskRequest` with `buildVoidTaskRequest(...)`.
3. Use `BridgeClient` to:
   - create tasks
   - subscribe to task state
   - listen to task events
   - approve commands
   - cancel tasks

## Minimal Sketch

```ts
import { BridgeClient, buildVoidTaskRequest } from '@ai-ide-bridge/frontend-bridge'

const client = new BridgeClient({ baseUrl: 'http://127.0.0.1:27182' })

client.subscribe({
  onStateChange(state) {
    console.log(state)
  },
})

const request = await buildVoidTaskRequest(voidContextSource, {
  mode: 'fix_test',
  userPrompt: 'Fix the current failing test',
})

await client.createTask(request)
```
