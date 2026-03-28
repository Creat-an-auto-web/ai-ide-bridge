# Sidebar Controller Notes

This note explains how to use the UI-facing controller skeleton in:

- `src/examples/sidebar-controller.ts`

The point of this file is to save you from re-deriving UI state from raw bridge
events in every sidebar component.

## 1. What It Solves

Raw bridge state is protocol-oriented.

A sidebar usually wants UI-oriented state such as:

- current prompt
- selected task mode
- whether the Run button should be enabled
- current high-level task summary
- whether an approval card should be visible
- a flat log list for rendering
- a patch preview payload
- final summary text

`BridgeSidebarController` translates backend task state into that shape.

## 2. State Shape

The controller produces `BridgeSidebarPanelState`, which contains:

- `composer`
- `summary`
- `approval`
- `planSteps`
- `logs`
- `patch`
- `testSummary`
- `finalSummary`
- `errorMessage`

That shape is intentionally close to what a sidebar component wants to render.

## 3. Recommended Usage Pattern

1. Create a `VoidBridgeContextSource`
2. Create a `BridgeSidebarController`
3. Subscribe to controller state changes
4. Bind UI events to:
   - `setPrompt(...)`
   - `setMode(...)`
   - `runCurrentPrompt(...)`
   - `approvePendingCommand(...)`
   - `rejectPendingCommand(...)`
   - `cancelTask()`

## 4. Minimal Host-Side Sketch

```ts
import {
  BridgeSidebarController,
  BridgeClient,
  createVoidBridgeContextSource,
} from '@ai-ide-bridge/frontend-bridge'

const client = new BridgeClient({ baseUrl: 'http://127.0.0.1:27182' })
const contextSource = createVoidBridgeContextSource(voidHostServices)

const controller = new BridgeSidebarController({
  bridgeClient: client,
  contextSource,
})

const dispose = controller.subscribe((state) => {
  renderSidebar(state)
})

controller.setPrompt('Fix the current failing test')
controller.setMode('fix_test')
await controller.runCurrentPrompt()
```

## 5. Why This Layer Matters

Without this layer, your Void sidebar glue code tends to mix together:

- prompt input state
- backend connection state
- protocol event handling
- derived UI booleans
- approval action wiring

That becomes hard to maintain quickly.

This controller keeps:

- protocol logic in `BridgeClient`
- Void context collection in `VoidBridgeContextSource`
- sidebar rendering state in `BridgeSidebarController`

Those are the three layers you want to keep separate.
