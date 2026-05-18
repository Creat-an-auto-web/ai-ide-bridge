import {
  RequirementAnalysisAgentSettings,
  RequirementAnalysisResultPayload,
} from './agent-settings.js'
import { TestCaseGenerationResultPayload } from './test-case-generation.js'
import {
  GeneratedTestFilePayload,
} from './test-code-generation.js'
import { TestCodeExecutionResultPayload } from './test-code-execution.js'

export interface TestCodeRepairSettingsPayload {
  enabled: boolean
  provider_kind: 'openai_compatible'
  provider_name: string
  model: string
  api_base: string
  api_key: string
  temperature: number
  max_tokens: number
  timeout_seconds: number
}

export interface TestCodeRepairRunInputPayload {
  task_id: string
  user_prompt: string
  plan: string | null
  story_units: RequirementAnalysisResultPayload['story_units']
  test_plan: string
  test_cases: TestCaseGenerationResultPayload['test_cases']
  test_files: GeneratedTestFilePayload[]
  execution_result: {
    command: string
    exit_code: number
    stdout: string
    stderr: string
    failed_tests: string[]
    workspace_diff: string | null
  }
}

export interface TestCodeRepairResultPayload {
  repair_plan: string[]
  test_files: GeneratedTestFilePayload[]
  changed_files: string[]
  reasoning_summary: string
  warnings: string[]
  quality_checks: {
    has_test_file_content: boolean
    covers_all_original_files: boolean
    keeps_test_scope: boolean
  }
}

export const toTestCodeRepairSettingsPayload = (
  settings: RequirementAnalysisAgentSettings,
): TestCodeRepairSettingsPayload => ({
  enabled: settings.enabled,
  provider_kind: 'openai_compatible',
  provider_name: settings.providerName,
  model: settings.model,
  api_base: settings.apiBase,
  api_key: settings.apiKey,
  temperature: settings.temperature,
  max_tokens: settings.maxTokens,
  timeout_seconds: settings.timeoutSeconds,
})

export const toTestCodeRepairInputPayload = (
  requirementResult: RequirementAnalysisResultPayload,
  testCaseResult: TestCaseGenerationResultPayload,
  testFiles: GeneratedTestFilePayload[],
  executionResult: TestCodeExecutionResultPayload,
  prompt: string,
  planDraft?: string | null,
): TestCodeRepairRunInputPayload => ({
  task_id: requirementResult.task_id,
  user_prompt: prompt.trim() || requirementResult.requirement_spec.problem_statement,
  plan: planDraft?.trim() || null,
  story_units: requirementResult.story_units,
  test_plan: testCaseResult.test_plan,
  test_cases: testCaseResult.test_cases,
  test_files: testFiles,
  execution_result: {
    command: executionResult.command,
    exit_code: executionResult.exit_code,
    stdout: executionResult.stdout,
    stderr: executionResult.stderr,
    failed_tests: executionResult.failed_tests,
    workspace_diff: executionResult.workspace_diff || null,
  },
})
