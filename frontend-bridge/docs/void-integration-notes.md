# Void Integration Notes

This document explains how the frontend bridge in this repository is expected to connect to existing Void interfaces without modifying `void/` directly from here.

## 1. Integration Boundary

`frontend-bridge` is not the UI.

It is a standalone adapter layer that:

- understands bridge protocol payloads
- knows how to build requests from Void-derived context
- knows how to talk to `backend-bridge`

The actual Void-side integration code should live in your own bridge glue on the product side and call into this module.

## 2. Recommended Void Service Mapping

### 2.1 Active File and Selection

Use:

- `ICodeEditorService.getActiveCodeEditor()`
- `editor.getModel()`
- `editor.getSelection()`

Map:

- `model.uri.fsPath` -> `context.activeFile`
- editor selection -> protocol `Selection`

### 2.2 Open Files

Use:

- `IModelService.getModels()`

Map:

- each `model.uri.fsPath` -> `context.openFiles[]`

### 2.3 Repository Root

Use:

- `IWorkspaceContextService.getWorkspace().folders[0]?.uri.fsPath`

Map:

- root folder path -> `repo.rootPath`

### 2.4 Diagnostics

Use:

- `IMarkerService.read({ resource })`

Map:

- markers -> `context.diagnostics[]`

### 2.5 Terminal Output

Use:

- `ITerminalToolService.listPersistentTerminalIds()`
- `ITerminalToolService.readTerminal(id)`

Map:

- recent terminal text -> `context.terminalTail`

### 2.6 Git Diff

Stage 1:

- allow empty string if you do not yet have a clean SCM integration

Later:

- add a dedicated SCM adapter and map the diff text into `context.gitDiff`

### 2.7 Test Logs

Stage 1:

- allow empty string or derive from terminal output

Later:

- add a dedicated test runner adapter and map structured output into `context.testLogs`

## 3. Stage-1 Integration Loop

1. Implement `VoidHostServices`
2. Create a `VoidBridgeContextSource` with `createVoidBridgeContextSource(...)`
3. Build a request with `buildVoidTaskRequest(...)`
4. Call `BridgeClient.createTask(...)`
5. Subscribe to client state and events
6. Render:
   - task status
   - plan
   - logs
   - command approval
   - patch preview
   - final result

## 4. Minimal Example

```ts
import {
  BridgeClient,
  VoidBridgeController,
  createVoidBridgeContextSource,
} from '@ai-ide-bridge/frontend-bridge'

const client = new BridgeClient({ baseUrl: 'http://127.0.0.1:27182' })

const contextSource = createVoidBridgeContextSource({
  getRepoRootPath: () => workspaceRoot,
  getActiveModel: () => activeModel,
  getActiveSelection: () => activeSelection,
  getOpenModels: () => openModels,
  getDiagnosticsForFile: (filePath) => readMarkers(filePath),
  getGitDiff: () => '',
  getTerminalTail: () => terminalTail,
  getTestLogs: () => '',
})

const controller = new VoidBridgeController(client, contextSource)

client.subscribe({
  onStateChange(state) {
    console.log(state)
  },
})

await controller.runTask({
  mode: 'fix_test',
  userPrompt: 'Fix the current failing test',
})
```
