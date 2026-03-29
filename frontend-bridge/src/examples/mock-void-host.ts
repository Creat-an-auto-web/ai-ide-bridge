import { BridgeClient } from '../client.js'
import { TaskMode } from '../protocol.js'
import { createVoidHostServicesFromServices } from '../void-services-adapter.js'
import { createVoidBridgeContextSource } from './void-source-skeleton.js'
import { BridgeSidebarController } from './sidebar-controller.js'
import {
  VoidHostBridge,
  VoidHostBridgeCallbacks,
} from '../void-host-bridge.js'

export interface MockVoidEditorState {
  repoRootPath: string
  activeFile: string
  selection?: {
    startLineNumber: number
    startColumn: number
    endLineNumber: number
    endColumn: number
  } | null
  openFiles: string[]
  diagnosticsByFile?: Record<string, Array<{ message: string; severity?: string | number }>>
  terminalTail?: string
  testLogs?: string
  gitDiff?: string
}

export interface MockVoidViewLogEntry {
  kind: 'render' | 'notification' | 'patch' | 'final' | 'error'
  message: string
}

export interface MockVoidView {
  logs: MockVoidViewLogEntry[]
  render(state: unknown): void
  showNotification(notification: { severity: string; title: string; message: string }): void
  focusApprovalCard(): void
  showPatchPreview(summary: string): void
  showWorkspaceEdit(summary: string): void
  setFinalSummary(summary: string): void
  setError(message: string): void
}

export const createMockVoidView = (): MockVoidView => {
  const logs: MockVoidViewLogEntry[] = []

  return {
    logs,
    render() {
      logs.push({ kind: 'render', message: '面板状态已刷新' })
    },
    showNotification(notification) {
      logs.push({
        kind: 'notification',
        message: `${notification.severity}:${notification.title}:${notification.message}`,
      })
    },
    focusApprovalCard() {
      logs.push({ kind: 'notification', message: '审批卡片已聚焦' })
    },
    showPatchPreview(summary) {
      logs.push({ kind: 'patch', message: summary })
    },
    showWorkspaceEdit(summary) {
      logs.push({ kind: 'patch', message: `workspace:${summary}` })
    },
    setFinalSummary(summary) {
      logs.push({ kind: 'final', message: summary })
    },
    setError(message) {
      logs.push({ kind: 'error', message })
    },
  }
}

export const createMockVoidHostBridge = (
  editorState: MockVoidEditorState,
  callbacks: VoidHostBridgeCallbacks = {},
): VoidHostBridge => {
  const client = new BridgeClient()
  const hostServices = createVoidHostServicesFromServices({
    workspaceContextService: {
      getWorkspace: () => ({
        folders: [{ uri: { fsPath: editorState.repoRootPath } }],
      }),
    },
    codeEditorService: {
      getActiveCodeEditor: () => ({
        getModel: () => ({ uri: { fsPath: editorState.activeFile } }),
        getSelection: () => editorState.selection ?? null,
      }),
    },
    modelService: {
      getModels: () =>
        editorState.openFiles.map((filePath) => ({
          uri: { fsPath: filePath },
        })),
    },
    markerService: {
      read: ({ resource }) => {
        const filePath =
          typeof resource === 'object' &&
          resource !== null &&
          'fsPath' in resource
            ? String((resource as { fsPath: unknown }).fsPath)
            : ''
        return editorState.diagnosticsByFile?.[filePath] ?? []
      },
    },
    terminalToolService: {
      listPersistentTerminalIds: () => ['main'],
      readTerminal: () => editorState.terminalTail ?? '',
    },
    gitDiffProvider: () => editorState.gitDiff ?? '',
    testLogsProvider: () => editorState.testLogs ?? '',
  })

  const contextSource = createVoidBridgeContextSource(hostServices)
  const controller = new BridgeSidebarController({
    bridgeClient: client,
    contextSource,
  })

  return new VoidHostBridge(controller, callbacks)
}

export const primeMockVoidPrompt = (
  bridge: VoidHostBridge,
  prompt: string,
  mode: TaskMode = 'fix_test',
): void => {
  bridge.setMode(mode)
  bridge.setPrompt(prompt)
}
