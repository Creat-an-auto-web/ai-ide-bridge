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
 * 这个文件只提供接入骨架。
 *
 * 它被有意放在 ai-ide-bridge/frontend-bridge，而不是 void/ 里。
 * 目标是在不直接修改 Void 内部实现的前提下，明确 Void 侧适配层需要提供什么能力。
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
 * 这个接口就是你们 Void 侧胶水代码应当满足的具体契约。
 *
 * 推荐与现有 Void 服务的映射关系：
 *
 * - 仓库根目录：
 *   IWorkspaceContextService.getWorkspace().folders[0]?.uri.fsPath
 *
 * - 当前编辑器 / 当前文件 / 选区：
 *   ICodeEditorService.getActiveCodeEditor()
 *
 * - 已打开文件模型：
 *   IModelService.getModels()
 *
 * - 诊断信息：
 *   IMarkerService.read({ resource })
 *
 * - 终端尾部输出：
 *   ITerminalToolService.listPersistentTerminalIds()
 *   ITerminalToolService.readTerminal(id)
 *
 * - git diff：
 *   第一阶段可以先返回空字符串，后续再接专门的 SCM 包装层
 *
 * - 测试日志：
 *   第一阶段可以先从终端输出中提取，后续再接专门的测试运行器集成
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

const uniqueFilePaths = (filePaths: Array<string | undefined>): string[] => {
  const seen = new Set<string>()
  const result: string[] = []

  for (const filePath of filePaths) {
    if (!filePath || seen.has(filePath)) {
      continue
    }
    seen.add(filePath)
    result.push(filePath)
  }

  return result
}

const collectDiagnosticsForFiles = async (
  host: VoidHostServices,
  filePaths: string[],
): Promise<DiagnosticItem[]> => {
  const markerLists = await Promise.all(
    filePaths.map(async (filePath) => ({
      filePath,
      markers: await host.getDiagnosticsForFile(filePath),
    })),
  )

  return markerLists.flatMap(({ filePath, markers }) =>
    markers.map((marker) => mapVoidMarker(marker, filePath)),
  )
}

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
    return uniqueFilePaths(models.map((model) => model.uri.fsPath))
  },

  async getDiagnostics() {
    const [activeModel, openModels] = await Promise.all([
      host.getActiveModel(),
      host.getOpenModels(),
    ])

    const filePaths = uniqueFilePaths([
      activeModel?.uri.fsPath,
      ...openModels.map((model) => model.uri.fsPath),
    ])

    if (filePaths.length === 0) {
      return []
    }

    return await collectDiagnosticsForFiles(host, filePaths)
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
 * 第一阶段编排骨架：
 *
 * 1. 基于 Void 服务创建 context source
 * 2. 构造 bridge 请求
 * 3. 创建任务
 * 4. 订阅任务状态
 * 5. 显式批准或拒绝命令请求
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
