export type TaskMode =
  | 'repo_chat'
  | 'edit_selection'
  | 'fix_test'
  | 'refactor_scope'
  | 'explain_error'

export type TaskStatus =
  | 'queued'
  | 'planning'
  | 'awaiting_approval'
  | 'running'
  | 'patch_ready'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type WorkspaceMode = 'local' | 'docker' | 'remote'
export type NetworkPolicy = 'allow' | 'deny'
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export type EventType =
  | 'task.status'
  | 'task.plan'
  | 'task.log'
  | 'task.command.request'
  | 'task.command.result'
  | 'task.patch'
  | 'task.test.result'
  | 'task.error'
  | 'task.final'

export type ErrorCode =
  | 'VALIDATION_ERROR'
  | 'AUTH_ERROR'
  | 'WORKSPACE_ERROR'
  | 'MODEL_ERROR'
  | 'TOOL_ERROR'
  | 'PATCH_ERROR'
  | 'TIMEOUT_ERROR'
  | 'INTERNAL_ERROR'

export interface Selection {
  startLine: number
  startCol: number
  endLine: number
  endCol: number
}

export interface DiagnosticItem {
  message: string
  severity?: string | number
  source?: string
  code?: string | number
  file?: string
  startLine?: number
  startCol?: number
  endLine?: number
  endCol?: number
  raw?: unknown
}

export interface TaskContextPayload {
  activeFile?: string
  selection?: Selection | null
  openFiles: string[]
  diagnostics: DiagnosticItem[]
  gitDiff: string
  terminalTail: string
  testLogs: string
}

export interface TaskPolicy {
  workspaceMode: WorkspaceMode
  network: NetworkPolicy
  requireApprovalFor: string[]
  maxDurationSec?: number
  maxOutputBytes?: number
  writablePaths?: string[]
  envAllowlist?: string[]
}

export interface RepoRef {
  rootPath: string
  branch?: string
}

export interface CreateTaskRequest {
  requestId?: string
  sessionId?: string
  protocolVersion?: 'v1alpha1'
  mode: TaskMode
  userPrompt: string
  repo: RepoRef
  context: TaskContextPayload
  policy: TaskPolicy
}

export interface TaskRecord {
  taskId: string
  mode: TaskMode
  status: TaskStatus
  workspaceMode: WorkspaceMode
  createdAt: string
  updatedAt: string
  latestMessage?: string | null
}

export interface ErrorBody {
  code: ErrorCode
  message: string
  retryable: boolean
  details?: Record<string, unknown>
}

export interface ResponseEnvelope<T> {
  success: boolean
  requestId?: string
  data: T | null
  error?: ErrorBody | null
  protocolVersion: string
}

export interface EventEnvelope<TPayload = unknown> {
  eventId: string
  taskId: string
  seq: number
  type: EventType
  timestamp: string
  payload: TPayload
}

export interface TaskStatusPayload {
  status: TaskStatus
  message: string
}

export interface TaskPlanPayload {
  steps: string[]
}

export interface TaskLogPayload {
  stream: 'stdout' | 'stderr' | string
  text: string
}

export interface TaskCommandRequestPayload {
  commandId: string
  command: string
  cwd: string
  riskLevel: RiskLevel
  reason: string
}

export interface TaskCommandResultPayload {
  commandId: string
  exitCode: number
  stdout: string
  stderr: string
}

export interface PatchOpReplaceRange {
  op: 'replace_range'
  startLine: number
  endLine: number
  content: string
}

export type PatchOp = PatchOpReplaceRange | Record<string, unknown>

export interface PatchFile {
  path: string
  changeType: 'create' | 'modify' | 'delete' | 'rename' | string
  unifiedDiff: string
  ops: PatchOp[]
}

export interface TaskPatchPayload {
  patchId: string
  summary: string
  files: PatchFile[]
}

export interface TaskTestResultPayload {
  framework: string
  passed: number
  failed: number
  skipped: number
}

export interface TaskErrorPayload {
  code: ErrorCode
  message: string
  retryable: boolean
}

export interface TaskFinalPayload {
  outcome: 'completed' | 'failed' | 'cancelled'
  summary: string
  artifacts?: Record<string, unknown>
}

export interface EventMap {
  'task.status': TaskStatusPayload
  'task.plan': TaskPlanPayload
  'task.log': TaskLogPayload
  'task.command.request': TaskCommandRequestPayload
  'task.command.result': TaskCommandResultPayload
  'task.patch': TaskPatchPayload
  'task.test.result': TaskTestResultPayload
  'task.error': TaskErrorPayload
  'task.final': TaskFinalPayload
}

export type BridgeEvent<K extends keyof EventMap = keyof EventMap> =
  EventEnvelope<EventMap[K]> & { type: K }

export interface CommandApprovalRequest {
  approved: boolean
  reason?: string
}
