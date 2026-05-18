import { GeneratedTestFilePayload } from './test-code-generation.js'

export interface TestCodeExecutionRunInputPayload {
  task_id: string
  repo_root: string
  test_files: GeneratedTestFilePayload[]
  test_command: string | null
  timeout_seconds: number
}

export interface TestCodeExecutionEvaluationPayload {
  decision: 'success' | 'repair'
  failure_summary: string | null
  repair_targets: string[]
  stop_reason: string | null
}

export interface TestCodeExecutionResultPayload {
  task_id: string
  repo_root: string
  written_files: string[]
  command: string
  exit_code: number
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
}

export const toTestCodeExecutionInputPayload = (
  taskId: string,
  repoRoot: string,
  testFiles: GeneratedTestFilePayload[],
  testCommand: string,
  timeoutSeconds = 120,
): TestCodeExecutionRunInputPayload => ({
  task_id: taskId,
  repo_root: repoRoot,
  test_files: testFiles,
  test_command: testCommand.trim() || null,
  timeout_seconds: timeoutSeconds,
})
