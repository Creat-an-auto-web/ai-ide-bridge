import {
  VoidHostServices,
  VoidMarkerLike,
  VoidModelLike,
  VoidSelectionLike,
} from './examples/void-source-skeleton.js'

export interface VoidWorkspaceFolderLike {
  uri: { fsPath: string }
}

export interface VoidWorkspaceLike {
  folders?: readonly VoidWorkspaceFolderLike[]
}

export interface VoidWorkspaceContextServiceLike {
  getWorkspace(): Promise<VoidWorkspaceLike> | VoidWorkspaceLike
}

export interface VoidCodeEditorLike {
  getModel(): VoidModelLike | null
  getSelection(): VoidSelectionLike | null
}

export interface VoidCodeEditorServiceLike {
  getActiveCodeEditor(): Promise<VoidCodeEditorLike | null> | VoidCodeEditorLike | null
}

export interface VoidModelServiceLike {
  getModels(): Promise<readonly VoidModelLike[]> | readonly VoidModelLike[]
}

export interface VoidMarkerServiceLike {
  read(filter: { resource: unknown }): Promise<readonly VoidMarkerLike[]> | readonly VoidMarkerLike[]
}

export type VoidTerminalId = string | number

export type VoidTerminalReadResult =
  | string
  | {
      text?: string
      content?: string
      lines?: string[]
      buffer?: string[]
    }

export interface VoidTerminalToolServiceLike {
  listPersistentTerminalIds(): Promise<readonly VoidTerminalId[]> | readonly VoidTerminalId[]
  readTerminal(id: VoidTerminalId): Promise<VoidTerminalReadResult> | VoidTerminalReadResult
}

export interface CreateVoidHostServicesOptions {
  workspaceContextService: VoidWorkspaceContextServiceLike
  codeEditorService: VoidCodeEditorServiceLike
  modelService: VoidModelServiceLike
  markerService: VoidMarkerServiceLike
  terminalToolService?: VoidTerminalToolServiceLike
  branchProvider?: () => Promise<string | undefined> | string | undefined
  gitDiffProvider?: () => Promise<string> | string
  testLogsProvider?: () => Promise<string> | string
  resourceFactory?: (filePath: string) => unknown
  maxTerminalChars?: number
}

const defaultResourceFactory = (filePath: string) => ({ fsPath: filePath })

const trimTail = (text: string, maxChars: number): string =>
  text.length <= maxChars ? text : text.slice(-maxChars)

const readTerminalText = (value: VoidTerminalReadResult): string => {
  if (typeof value === 'string') {
    return value
  }

  if (typeof value.text === 'string') {
    return value.text
  }

  if (typeof value.content === 'string') {
    return value.content
  }

  if (Array.isArray(value.lines)) {
    return value.lines.join('\n')
  }

  if (Array.isArray(value.buffer)) {
    return value.buffer.join('\n')
  }

  return ''
}

export const createVoidHostServicesFromServices = (
  options: CreateVoidHostServicesOptions,
): VoidHostServices => {
  const resourceFactory = options.resourceFactory ?? defaultResourceFactory
  const maxTerminalChars = options.maxTerminalChars ?? 12000

  return {
    async getRepoRootPath() {
      const workspace = await options.workspaceContextService.getWorkspace()
      return workspace.folders?.[0]?.uri.fsPath ?? ''
    },

    async getBranch() {
      return await options.branchProvider?.()
    },

    async getActiveModel() {
      const editor = await options.codeEditorService.getActiveCodeEditor()
      return editor?.getModel() ?? null
    },

    async getActiveSelection() {
      const editor = await options.codeEditorService.getActiveCodeEditor()
      return editor?.getSelection() ?? null
    },

    async getOpenModels() {
      return [...await options.modelService.getModels()]
    },

    async getDiagnosticsForFile(filePath: string) {
      const markers = await options.markerService.read({
        resource: resourceFactory(filePath),
      })
      return [...markers]
    },

    async getGitDiff() {
      return await options.gitDiffProvider?.() ?? ''
    },

    async getTerminalTail() {
      if (!options.terminalToolService) {
        return ''
      }

      const terminalIds = await options.terminalToolService.listPersistentTerminalIds()
      if (terminalIds.length === 0) {
        return ''
      }

      const terminalTexts = await Promise.all(
        [...terminalIds].map(async (terminalId) =>
          readTerminalText(await options.terminalToolService!.readTerminal(terminalId)),
        ),
      )

      return trimTail(
        terminalTexts
          .filter((text) => text.trim().length > 0)
          .join('\n\n'),
        maxTerminalChars,
      )
    },

    async getTestLogs() {
      return await options.testLogsProvider?.() ?? ''
    },
  }
}
