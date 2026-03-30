import { BridgeClient, BridgeClientOptions } from './client.js'
import { attachVoidIdeSidebar, VoidIdeBridgeEntry, VoidIdeSidebarView } from './void-ide-entry.js'
import { createVoidBridgeContextSource } from './examples/void-source-skeleton.js'
import {
  VoidAccessorLike,
  CreateVoidRealHostServicesOptions,
  createVoidRealHostServicesFromAccessor,
} from './void-real-services.js'

export interface AttachVoidRealIdeSidebarOptions extends CreateVoidRealHostServicesOptions {
  view: VoidIdeSidebarView
  bridgeClient?: BridgeClient
  bridgeClientOptions?: BridgeClientOptions
}

export interface AttachVoidRealIdeSidebarFromAccessorOptions {
  accessor: VoidAccessorLike
  view: VoidIdeSidebarView
  bridgeClient?: BridgeClient
  bridgeClientOptions?: BridgeClientOptions
  branchProvider?: () => Promise<string | undefined> | string | undefined
  gitDiffProvider?: () => Promise<string> | string
  testLogsProvider?: () => Promise<string> | string
  maxTerminalChars?: number
}

const toBridgeClient = (
  bridgeClient?: BridgeClient,
  bridgeClientOptions?: BridgeClientOptions,
): BridgeClient => bridgeClient ?? new BridgeClient(bridgeClientOptions)

export const attachVoidRealIdeSidebar = (
  options: AttachVoidRealIdeSidebarOptions,
): VoidIdeBridgeEntry => {
  const client = toBridgeClient(options.bridgeClient, options.bridgeClientOptions)

  return attachVoidIdeSidebar({
    view: options.view,
    bridgeClient: client,
    workspaceContextService: options.services.IWorkspaceContextService,
    codeEditorService: options.services.ICodeEditorService,
    modelService: options.services.IModelService,
    markerService: options.services.IMarkerService,
    terminalToolService: options.services.ITerminalToolService,
    branchProvider: options.branchProvider,
    gitDiffProvider: options.gitDiffProvider,
    testLogsProvider: options.testLogsProvider,
    maxTerminalChars: options.maxTerminalChars,
    resourceFactory: options.resourceFactory,
  })
}

export const createVoidRealContextSourceFromAccessor = (
  options: Omit<AttachVoidRealIdeSidebarFromAccessorOptions, 'view' | 'bridgeClient' | 'bridgeClientOptions'>,
) => createVoidBridgeContextSource(createVoidRealHostServicesFromAccessor(options))

export const attachVoidRealIdeSidebarFromAccessor = (
  options: AttachVoidRealIdeSidebarFromAccessorOptions,
): VoidIdeBridgeEntry => {
  const client = toBridgeClient(options.bridgeClient, options.bridgeClientOptions)

  return attachVoidIdeSidebar({
    view: options.view,
    bridgeClient: client,
    workspaceContextService: options.accessor.get('IWorkspaceContextService'),
    codeEditorService: options.accessor.get('ICodeEditorService'),
    modelService: options.accessor.get('IModelService'),
    markerService: options.accessor.get('IMarkerService'),
    terminalToolService: options.accessor.get('ITerminalToolService'),
    branchProvider: options.branchProvider,
    gitDiffProvider: options.gitDiffProvider,
    testLogsProvider: options.testLogsProvider,
    maxTerminalChars: options.maxTerminalChars,
  })
}
