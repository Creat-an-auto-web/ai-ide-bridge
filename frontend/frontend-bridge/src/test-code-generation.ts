import {
  RequirementAnalysisAgentSettings,
  RequirementAnalysisResultPayload,
} from './agent-settings.js'
import {
  GeneratedTestCasePayload,
  TestCaseGenerationResultPayload,
} from './test-case-generation.js'

export interface TestCodeGenerationSettingsPayload {
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

export interface TestCodeGenerationExecutionConstraintsPayload {
  max_test_files: number
  prefer_existing_test_stack: boolean
  include_fixtures: boolean
  framework_hint: string | null
}

export interface GeneratedTestFilePayload {
  path: string
  language: string
  framework: string
  purpose: string
  related_test_case_ids: string[]
  content: string
}

export interface TestCodeGenerationRunInputPayload {
  task_id: string
  user_prompt: string
  plan: string | null
  story_units: RequirementAnalysisResultPayload['story_units']
  test_plan: string
  test_cases: GeneratedTestCasePayload[]
  execution_constraints: TestCodeGenerationExecutionConstraintsPayload
}

export interface TestCodeGenerationResultPayload {
  implementation_plan: string[]
  test_files: GeneratedTestFilePayload[]
  changed_files: string[]
  rationale: string
  warnings: string[]
  quality_checks: {
    has_test_file_content: boolean
    all_files_are_tests: boolean
    covers_all_input_test_cases: boolean
    changed_files_match_generated_files: boolean
  }
}

export const toTestCodeGenerationSettingsPayload = (
  settings: RequirementAnalysisAgentSettings,
): TestCodeGenerationSettingsPayload => ({
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

export const buildTestCodeGenerationWorkflowDraft = (
  requirementResult: RequirementAnalysisResultPayload,
  testCaseResult: TestCaseGenerationResultPayload,
): string => {
  const lines: string[] = []
  lines.push('Test Code Workflow Draft')
  lines.push(`目标：把 ${testCaseResult.test_cases.length} 条概念性测试用例转换成可执行测试代码草案。`)
  lines.push(`需求目标：${requirementResult.requirement_spec.product_goal}`)
  lines.push('转换原则：')
  lines.push('1. 只生成测试代码，不生成生产实现代码。')
  lines.push('2. 保留测试用例中的输入、步骤、预期结果，不要反向修改测试目标。')
  lines.push('3. 每个生成的测试文件都要明确覆盖哪些 test_case id。')
  lines.push('4. 优先使用当前仓库已有测试栈；如果无法判断，再明确说明选择原因。')
  lines.push('5. 对 string 类型字段补充空值、空白、非法格式、边界长度和重复值覆盖。')
  lines.push('推荐生成内容：')
  lines.push('- 测试文件')
  lines.push('- 必要 fixture')
  lines.push('- 参数化用例')
  lines.push('- 断言结构')
  lines.push('输入测试用例：')
  testCaseResult.test_cases.forEach((testCase, index) => {
    lines.push(
      `${index + 1}. ${testCase.id} | ${testCase.title} | ${testCase.level} | ${testCase.category} | 预期：${testCase.expected_result}`,
    )
  })
  return lines.join('\n')
}

export const toTestCodeGenerationInputPayload = (
  requirementResult: RequirementAnalysisResultPayload,
  testCaseResult: TestCaseGenerationResultPayload,
  planDraft: string,
  prompt: string,
): TestCodeGenerationRunInputPayload => ({
  task_id: requirementResult.task_id,
  user_prompt: prompt.trim() || requirementResult.requirement_spec.problem_statement,
  plan: planDraft.trim() || null,
  story_units: requirementResult.story_units,
  test_plan: testCaseResult.test_plan,
  test_cases: testCaseResult.test_cases,
  execution_constraints: {
    max_test_files: 4,
    prefer_existing_test_stack: true,
    include_fixtures: true,
    framework_hint: null,
  },
})
