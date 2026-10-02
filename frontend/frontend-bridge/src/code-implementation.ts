import {
  RequirementAnalysisAgentSettings,
  RequirementAnalysisResultPayload,
} from './agent-settings.js'
import { TestCaseGenerationResultPayload } from './test-case-generation.js'
import { GeneratedTestFilePayload } from './test-code-generation.js'

export interface CodeImplementationSettingsPayload {
  provider_name: string
  wire_api: RequirementAnalysisAgentSettings['wireApi']
  model: string
  api_base: string
  api_key: string
  temperature: number
  max_tokens: number
  timeout_seconds: number
  max_request_seconds: number
}

export interface GeneratedImplementationFilePayload {
  path: string
  language: string
  purpose: string
  content: string
}

export interface CodeImplementationResultPayload {
  implementation_plan: string[]
  files: GeneratedImplementationFilePayload[]
  changed_files: string[]
  rationale: string
  test_command: string[]
  warnings: string[]
  quality_checks: {
    has_complete_file_content: boolean
    keeps_test_baseline_immutable: boolean
    changed_files_match_generated_files: boolean
    paths_are_repository_relative: boolean
  }
}

export interface CodeImplementationRunInputPayload {
  task_id: string
  repo_root: string
  user_prompt: string
  requirement_spec: Record<string, unknown>
  story_units: RequirementAnalysisResultPayload['story_units']
  test_plan: string
  test_cases: TestCaseGenerationResultPayload['test_cases']
  test_files: GeneratedTestFilePayload[]
  repository_context: Record<string, string>
}

const safeArray = <T>(value: T[] | null | undefined): T[] => (
  Array.isArray(value) ? value : []
)

export const toCodeImplementationSettingsPayload = (
  settings: RequirementAnalysisAgentSettings,
): CodeImplementationSettingsPayload => ({
  provider_name: settings.providerName,
  wire_api: settings.wireApi,
  model: settings.model,
  api_base: settings.apiBase,
  api_key: settings.apiKey,
  temperature: Math.min(settings.temperature, 0.2),
  max_tokens: Math.max(settings.maxTokens, 8000),
  timeout_seconds: settings.timeoutSeconds,
  max_request_seconds: 900,
})

export const buildCodeImplementationWorkflowDraft = (
  requirementResult: RequirementAnalysisResultPayload,
  testCaseResult: TestCaseGenerationResultPayload,
  testFiles: GeneratedTestFilePayload[],
): string => [
  'Business Implementation Draft',
  `目标：${requirementResult.requirement_spec?.product_goal ?? ''}`,
  `固定测试基线：${testFiles.length} 个测试文件，${safeArray(testCaseResult.test_cases).length} 条测试用例。`,
  '约束：',
  '1. 仅生成业务/生产实现文件，不得修改测试文件。',
  '2. 每个文件必须输出可直接写入的完整内容。',
  '3. 复用仓库现有接口、依赖和公开 API；不新增外部依赖。',
  '4. 覆盖正常、边界和异常路径，并提供可执行测试命令。',
].join('\n')

export const toCodeImplementationInputPayload = (
  requirementResult: RequirementAnalysisResultPayload,
  testCaseResult: TestCaseGenerationResultPayload,
  testFiles: GeneratedTestFilePayload[],
  repoRoot: string,
  prompt: string,
): CodeImplementationRunInputPayload => ({
  task_id: requirementResult.task_id,
  repo_root: repoRoot,
  user_prompt: prompt.trim() || requirementResult.requirement_spec?.problem_statement || '',
  requirement_spec: requirementResult.requirement_spec ?? {},
  story_units: safeArray(requirementResult.story_units),
  test_plan: testCaseResult.test_plan,
  test_cases: safeArray(testCaseResult.test_cases),
  test_files: safeArray(testFiles),
  repository_context: {},
})
