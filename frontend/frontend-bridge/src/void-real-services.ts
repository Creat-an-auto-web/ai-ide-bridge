import { CreateVoidHostServicesOptions, createVoidHostServicesFromServices } from './void-services-adapter.js'

export interface VoidUriLike {
  fsPath: string
}

export interface VoidRealEditorLike {
  getModel(): { uri: VoidUriLike } | null
  getSelection(): {
    startLineNumber: number
    startColumn: number
    endLineNumber: number
    endColumn: number
  } | null
}

export interface VoidRealCodeEditorServiceLike {
  getActiveCodeEditor(): VoidRealEditorLike | null | Promise<VoidRealEditorLike | null>
}

export interface VoidRealModelServiceLike {
  getModels(): readonly { uri: VoidUriLike }[] | Promise<readonly { uri: VoidUriLike }[]>
}

export interface VoidRealMarkerServiceLike {
  read(filter?: {
    owner?: string
    resource?: unknown
    severities?: number
    take?: number
  }): readonly {
    message: string
    severity?: string | number
    source?: string
    code?: string | number | { value: string | number }
    startLineNumber?: number
    startColumn?: number
    endLineNumber?: number
    endColumn?: number
  }[] | Promise<readonly {
    message: string
    severity?: string | number
    source?: string
    code?: string | number | { value: string | number }
    startLineNumber?: number
    startColumn?: number
    endLineNumber?: number
    endColumn?: number
  }[]>
}

export interface VoidRealWorkspaceContextServiceLike {
  getWorkspace(): {
    folders?: readonly { uri: VoidUriLike }[]
  } | Promise<{
    folders?: readonly { uri: VoidUriLike }[]
  }>
}

export interface VoidRealTerminalToolServiceLike {
  listPersistentTerminalIds(): readonly string[] | Promise<readonly string[]>
  readTerminal(id: string): string | Promise<string>
}

export interface VoidRealServiceBag {
  ICodeEditorService: VoidRealCodeEditorServiceLike
  IModelService: VoidRealModelServiceLike
  IMarkerService: VoidRealMarkerServiceLike
  IWorkspaceContextService: VoidRealWorkspaceContextServiceLike
  ITerminalToolService?: VoidRealTerminalToolServiceLike
}

export interface CreateVoidRealHostServicesOptions {
  services: VoidRealServiceBag
  branchProvider?: () => Promise<string | undefined> | string | undefined
  gitDiffProvider?: () => Promise<string> | string
  testLogsProvider?: () => Promise<string> | string
  maxTerminalChars?: number
  resourceFactory?: (filePath: string) => unknown
}

export type VoidAccessorLike = {
  get(name: 'ICodeEditorService'): VoidRealCodeEditorServiceLike
  get(name: 'IModelService'): VoidRealModelServiceLike
  get(name: 'IMarkerService'): VoidRealMarkerServiceLike
  get(name: 'IWorkspaceContextService'): VoidRealWorkspaceContextServiceLike
  get(name: 'ITerminalToolService'): VoidRealTerminalToolServiceLike
}

const defaultResourceFactory = (filePath: string) => ({ fsPath: filePath })

const toCreateOptions = (
  options: CreateVoidRealHostServicesOptions,
): CreateVoidHostServicesOptions => ({
  workspaceContextService: options.services.IWorkspaceContextService,
  codeEditorService: options.services.ICodeEditorService,
  modelService: options.services.IModelService,
  markerService: {
    read: (filter) => options.services.IMarkerService.read(filter),
  },
  terminalToolService: options.services.ITerminalToolService,
  branchProvider: options.branchProvider,
  gitDiffProvider: options.gitDiffProvider,
  testLogsProvider: options.testLogsProvider,
  maxTerminalChars: options.maxTerminalChars,
  resourceFactory: options.resourceFactory ?? defaultResourceFactory,
})

export const createVoidRealHostServices = (
  options: CreateVoidRealHostServicesOptions,
) => createVoidHostServicesFromServices(toCreateOptions(options))

export const createVoidRealHostServicesFromAccessor = (options: {
  accessor: VoidAccessorLike
  branchProvider?: () => Promise<string | undefined> | string | undefined
  gitDiffProvider?: () => Promise<string> | string
  testLogsProvider?: () => Promise<string> | string
  maxTerminalChars?: number
  resourceFactory?: (filePath: string) => unknown
}) =>
  createVoidRealHostServices({
    services: {
      ICodeEditorService: options.accessor.get('ICodeEditorService'),
      IModelService: options.accessor.get('IModelService'),
      IMarkerService: options.accessor.get('IMarkerService'),
      IWorkspaceContextService: options.accessor.get('IWorkspaceContextService'),
      ITerminalToolService: options.accessor.get('ITerminalToolService'),
    },
    branchProvider: options.branchProvider,
    gitDiffProvider: options.gitDiffProvider,
    testLogsProvider: options.testLogsProvider,
    maxTerminalChars: options.maxTerminalChars,
    resourceFactory: options.resourceFactory,
  })
