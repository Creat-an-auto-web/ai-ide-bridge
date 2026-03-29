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
): Promise<TaskContextPayload> => {
  const [
    activeFile,
    selection,
    openFiles,
    diagnostics,
    gitDiff,
    terminalTail,
    testLogs,
  ] = await Promise.all([
    source.getActiveFile(),
    source.getSelection(),
    source.getOpenFiles(),
    source.getDiagnostics(),
    source.getGitDiff(),
    source.getTerminalTail(),
    source.getTestLogs(),
  ])

  return {
    activeFile,
    selection,
    openFiles,
    diagnostics,
    gitDiff,
    terminalTail,
    testLogs,
  }
}

export const buildVoidTaskRequest = async (
  source: VoidBridgeContextSource,
  args: BuildVoidTaskRequestArgs,
): Promise<CreateTaskRequest> => {
  const policy: TaskPolicy = {
    ...defaultPolicy(),
    ...args.policy,
  }

  const [repoRootPath, branch, context] = await Promise.all([
    source.getRepoRootPath(),
    source.getBranch?.(),
    collectVoidContext(source),
  ])

  return {
    requestId: args.requestIdFactory?.() ?? toRequestId(),
    sessionId: args.sessionId,
    protocolVersion: 'v1alpha1',
    mode: args.mode,
    userPrompt: args.userPrompt,
    repo: {
      rootPath: repoRootPath,
      branch,
    },
    context,
    policy,
  }
}
