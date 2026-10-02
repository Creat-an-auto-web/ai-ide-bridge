import { GeneratedTestFilePayload } from './test-code-generation.js'
import { GeneratedImplementationFilePayload } from './code-implementation.js'

export type SandboxExecutionStatus =
  | 'passed'
  | 'failed'
  | 'timed_out'
  | 'cancelled'
  | 'blocked'
  | 'infrastructure_error'

export interface SandboxCommandPayload {
  argv: string[]
  cwd: string
  environment: Record<string, string>
}

export interface SandboxExecutionPolicyPayload {
  runtime: 'local_copy' | 'docker'
  network: 'allow' | 'deny'
  timeout_seconds: number
  max_output_bytes: number
  retain_artifacts: boolean
  allow_workspace_changes: boolean
}

export interface DockerRuntimeStatusPayload {
  available: boolean
  command: string
  server_version: string | null
  detail: string
}

export interface SandboxExecutionRunInputPayload {
  protocol_version: 'sandbox-execution.v1'
  task_id: string
  run_id?: string
  workspace: {
    repo_root: string
    base_revision?: string | null
  }
  test_files: GeneratedTestFilePayload[]
  command: SandboxCommandPayload | null
  execution_policy: SandboxExecutionPolicyPayload
  provenance: {
    requirement_package_id?: string | null
    test_case_result_id?: string | null
    test_code_result_id?: string | null
  }
}

export interface SandboxExecutionResultPayload {
  protocol_version: string
  task_id: string
  run_id: string
  status: SandboxExecutionStatus
  execution: {
    command: {
      argv: string[]
      cwd: string
    }
    runtime: 'local_copy' | 'docker'
    sandbox_id: string
    workspace_isolated: boolean
    network_isolated: boolean
    duration_ms: number
    exit_code: number | null
    signal: number | null
    termination_reason: string
  }
  test_summary: {
    framework: string | null
    total: number
    passed: number
    failed: number
    skipped: number
    errors: number
    failed_tests: string[]
    passed_tests: string[]
  }
  outputs: {
    stdout: string
    stderr: string
    output_truncated: boolean
    workspace_diff: string
    artifacts: string[]
  }
  failure: {
    kind: string
    summary: string
    repair_targets: string[]
    related_test_case_ids: string[]
  } | null
  warnings: string[]
  provenance: {
    requirement_package_id?: string | null
    test_case_result_id?: string | null
    test_code_result_id?: string | null
  }
}

export interface SandboxExecutionStreamEvent {
  type: 'status' | 'heartbeat' | 'output' | 'result' | 'error'
  stage: string
  message: string
  elapsed_ms?: number
  stream?: 'stdout' | 'stderr'
  text?: string
  metadata?: Record<string, unknown>
  data?: SandboxExecutionResultPayload
}

export interface TestCodeExecutionRunInputPayload {
  task_id: string
  repo_root: string
  test_files: GeneratedTestFilePayload[]
  workspace_files: GeneratedImplementationFilePayload[]
  test_command: string | null
  timeout_seconds: number
}

export interface TestCodeExecutionEvaluationPayload {
  decision: 'success' | 'repair' | 'blocked'
  failure_summary: string | null
  repair_targets: string[]
  stop_reason: string | null
}

export interface TestCodeExecutionResultPayload {
  task_id: string
  repo_root: string
  written_files: string[]
  command: string
  exit_code: number | null
  passed: boolean
  failed_tests: string[]
  passed_tests: string[]
  stdout: string
  stderr: string
  duration_ms: number
  artifacts: {
    written_files: string[]
  }
  workspace_diff: string
  evaluation: TestCodeExecutionEvaluationPayload
  sandbox?: SandboxExecutionResultPayload
}

export interface SandboxExecutionDebugDraft {
  test_file_path: string
  test_file_content: string
  command: string
}

export const createSandboxExecutionDebugDraft = (): SandboxExecutionDebugDraft => ({
  test_file_path: 'tests/test_sandbox_smoke.py',
  test_file_content: [
    'from pathlib import Path',
    '',
    'assert Path("tests/test_sandbox_smoke.py").exists()',
    'print("sandbox smoke passed")',
    '',
  ].join('\n'),
  command: 'python tests/test_sandbox_smoke.py',
})

export const splitCommandDraft = (value: string): string[] => {
  const tokens: string[] = []
  let token = ''
  let quote: '"' | "'" | null = null
  let escaped = false

  for (const character of value.trim()) {
    if (escaped) {
      token += character
      escaped = false
      continue
    }
    if (character === '\\' && quote !== "'") {
      escaped = true
      continue
    }
    if (quote) {
      if (character === quote) {
        quote = null
      } else {
        token += character
      }
      continue
    }
    if (character === '"' || character === "'") {
      quote = character
    } else if (/\s/.test(character)) {
      if (token) {
        tokens.push(token)
        token = ''
      }
    } else {
      token += character
    }
  }

  if (escaped) {
    token += '\\'
  }
  if (quote) {
    throw new Error('测试命令包含未闭合的引号。')
  }
  if (token) {
    tokens.push(token)
  }
  if (tokens.length === 0) {
    throw new Error('请填写测试命令，或留空让后端根据测试文件自动推断。')
  }
  return tokens
}

export const toSandboxExecutionInputPayload = (
  taskId: string,
  repoRoot: string,
  testFiles: GeneratedTestFilePayload[],
  command: SandboxCommandPayload | null,
  timeoutSeconds = 120,
  runtime: SandboxExecutionPolicyPayload['runtime'] = 'docker',
): SandboxExecutionRunInputPayload => ({
  protocol_version: 'sandbox-execution.v1',
  task_id: taskId,
  workspace: {
    repo_root: repoRoot,
  },
  test_files: testFiles,
  command,
  execution_policy: {
    runtime,
    network: runtime === 'docker' ? 'deny' : 'allow',
    timeout_seconds: timeoutSeconds,
    max_output_bytes: 262144,
    retain_artifacts: true,
    allow_workspace_changes: false,
  },
  provenance: {},
})

export const toTestCodeExecutionInputPayload = (
  taskId: string,
  repoRoot: string,
  testFiles: GeneratedTestFilePayload[],
  testCommand: string,
  workspaceFiles: GeneratedImplementationFilePayload[] = [],
  timeoutSeconds = 120,
): TestCodeExecutionRunInputPayload => ({
  task_id: taskId,
  repo_root: repoRoot,
  test_files: testFiles,
  workspace_files: workspaceFiles,
  test_command: testCommand.trim() || null,
  timeout_seconds: timeoutSeconds,
})
