import {
  BridgeClient,
  BuildVoidTaskRequestArgs,
  CommandApprovalRequest,
  DiagnosticItem,
  Selection,
  TaskMode,
  TaskPolicy,
  VoidBridgeContextSource,
  buildVoidTaskRequest,
} from '../index.js'

/**
 * This file is a source skeleton only.
 *
 * It is intentionally placed in ai-ide-bridge/frontend-bridge instead of void/.
 * The goal is to define exactly what a Void-side adapter should provide without
 * modifying Void internals directly from this repository.
 */

export interface VoidModelLike {
  uri: { fsPath: string }
}

export interface VoidSelectionLike {
  startLineNumber: number
  startColumn: number
  endLineNumber: number
  endColumn: number
}

export interface VoidMarkerLike {
  message: string
  severity?: string | number
  source?: string
  code?: string | number | { value: string | number }
  startLineNumber?: number
  startColumn?: number
  endLineNumber?: number
  endColumn?: number
}

/**
 * This interface is the concrete contract your Void-side glue code should
 * satisfy by calling existing Void services.
 *
 * Recommended mappings to existing Void services:
 *
 * - repo root:
 *   IWorkspaceContextService.getWorkspace().folders[0]?.uri.fsPath
 *
 * - active editor / active file / selection:
 *   ICodeEditorService.getActiveCodeEditor()
 *
 * - open file models:
 *   IModelService.getModels()
 *
 * - diagnostics:
 *   IMarkerService.read({ resource })
 *
 * - terminal tail:
 *   ITerminalToolService.listPersistentTerminalIds()
 *   ITerminalToolService.readTerminal(id)
 *
 * - git diff:
 *   either a dedicated SCM wrapper you add later, or an empty string in stage 1
 *
 * - test logs:
 *   either terminal-derived output, or a dedicated test runner integration later
 */
export interface VoidHostServices {
  getRepoRootPath(): Promise<string> | string
  getBranch?(): Promise<string | undefined> | string | undefined

  getActiveModel(): Promise<VoidModelLike | null> | VoidModelLike | null
  getActiveSelection(): Promise<VoidSelectionLike | null> | VoidSelectionLike | null

  getOpenModels(): Promise<VoidModelLike[]> | VoidModelLike[]
  getDiagnosticsForFile(filePath: string): Promise<VoidMarkerLike[]> | VoidMarkerLike[]

  getGitDiff(): Promise<string> | string
  getTerminalTail(): Promise<string> | string
  getTestLogs(): Promise<string> | string
}

export const mapVoidSelection = (
  selection: VoidSelectionLike | null | undefined,
): Selection | null => {
  if (!selection) return null
  if (
    selection.startLineNumber === selection.endLineNumber &&
    selection.startColumn === selection.endColumn
  ) {
    return null
  }
  return {
    startLine: selection.startLineNumber,
    startCol: selection.startColumn,
    endLine: selection.endLineNumber,
    endCol: selection.endColumn,
  }
}

export const mapVoidMarker = (
  marker: VoidMarkerLike,
  filePath: string,
): DiagnosticItem => ({
  message: marker.message,
  severity: marker.severity,
  source: marker.source,
  code: typeof marker.code === 'object' && marker.code !== null ? marker.code.value : marker.code,
  file: filePath,
  startLine: marker.startLineNumber,
  startCol: marker.startColumn,
  endLine: marker.endLineNumber,
  endCol: marker.endColumn,
  raw: marker,
})

export const createVoidBridgeContextSource = (
  host: VoidHostServices,
): VoidBridgeContextSource => ({
  async getRepoRootPath() {
    return await host.getRepoRootPath()
  },

  async getBranch() {
    return await host.getBranch?.()
  },

  async getActiveFile() {
    const model = await host.getActiveModel()
    return model?.uri.fsPath
  },

  async getSelection() {
    return mapVoidSelection(await host.getActiveSelection())
  },

  async getOpenFiles() {
    const models = await host.getOpenModels()
    return models.map(model => model.uri.fsPath)
  },

  async getDiagnostics() {
    const model = await host.getActiveModel()
    const filePath = model?.uri.fsPath
    if (!filePath) return []
    const markers = await host.getDiagnosticsForFile(filePath)
    return markers.map(marker => mapVoidMarker(marker, filePath))
  },

  async getGitDiff() {
    return await host.getGitDiff()
  },

  async getTerminalTail() {
    return await host.getTerminalTail()
  },

  async getTestLogs() {
    return await host.getTestLogs()
  },
})

/**
 * Stage-1 orchestration skeleton:
 *
 * 1. create a context source from Void services
 * 2. build a bridge request
 * 3. create a task
 * 4. subscribe to task state
 * 5. explicitly approve or reject command requests
 */
export class VoidBridgeController {
  constructor(
    private readonly client: BridgeClient,
    private readonly contextSource: VoidBridgeContextSource,
  ) {}

  async runTask(args: {
    mode: TaskMode
    userPrompt: string
    sessionId?: string
    policy?: Partial<TaskPolicy>
    requestIdFactory?: () => string
  }) {
    const request = await buildVoidTaskRequest(
      this.contextSource,
      args satisfies BuildVoidTaskRequestArgs,
    )
    return await this.client.createTask(request)
  }

  async approveCommand(commandId: string, reason?: string) {
    const body: CommandApprovalRequest = { approved: true, reason }
    await this.client.approveCommand(commandId, body)
  }

  async rejectCommand(commandId: string, reason?: string) {
    const body: CommandApprovalRequest = { approved: false, reason }
    await this.client.approveCommand(commandId, body)
  }

  async cancelTask() {
    await this.client.cancelCurrentTask()
  }
}
