import {
  CreateTaskRequest,
  DiagnosticItem,
  Selection,
  TaskContextPayload,
  TaskMode,
  TaskPolicy,
} from './protocol.js'

const defaultPolicy = (): TaskPolicy => ({
  workspaceMode: 'local',
  network: 'deny',
  requireApprovalFor: ['package_install', 'destructive_command', 'git_push'],
  maxDurationSec: 600,
  maxOutputBytes: 262144,
  writablePaths: [],
  envAllowlist: [],
})

export interface VoidBridgeContextSource {
  getRepoRootPath(): Promise<string> | string
  getBranch?(): Promise<string | undefined> | string | undefined
  getActiveFile(): Promise<string | undefined> | string | undefined
  getSelection(): Promise<Selection | null | undefined> | Selection | null | undefined
  getOpenFiles(): Promise<string[]> | string[]
  getDiagnostics(): Promise<DiagnosticItem[]> | DiagnosticItem[]
  getGitDiff(): Promise<string> | string
  getTerminalTail(): Promise<string> | string
  getTestLogs(): Promise<string> | string
}

export interface BuildVoidTaskRequestArgs {
  mode: TaskMode
  userPrompt: string
  sessionId?: string
  policy?: Partial<TaskPolicy>
  requestIdFactory?: () => string
}

const toRequestId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `req_${Math.random().toString(16).slice(2, 10)}`

export const collectVoidContext = async (
  source: VoidBridgeContextSource,
): Promise<TaskContextPayload> => ({
  activeFile: await source.getActiveFile(),
  selection: await source.getSelection(),
  openFiles: await source.getOpenFiles(),
  diagnostics: await source.getDiagnostics(),
  gitDiff: await source.getGitDiff(),
  terminalTail: await source.getTerminalTail(),
  testLogs: await source.getTestLogs(),
})

export const buildVoidTaskRequest = async (
  source: VoidBridgeContextSource,
  args: BuildVoidTaskRequestArgs,
): Promise<CreateTaskRequest> => {
  const policy: TaskPolicy = {
    ...defaultPolicy(),
    ...args.policy,
  }

  return {
    requestId: args.requestIdFactory?.() ?? toRequestId(),
    sessionId: args.sessionId,
    protocolVersion: 'v1alpha1',
    mode: args.mode,
    userPrompt: args.userPrompt,
    repo: {
      rootPath: await source.getRepoRootPath(),
      branch: await source.getBranch?.(),
    },
    context: await collectVoidContext(source),
    policy,
  }
}
