import {
  RequirementAnalysisAgentSettings,
  RequirementAnalysisResultPayload,
} from './agent-settings.js'

export interface TestCaseGenerationSettingsPayload {
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

export interface TestCaseGenerationExecutionConstraintsPayload {
  max_test_cases_per_story: number
  require_boundary_cases: boolean
  require_negative_cases: boolean
}

export interface TestCaseGenerationStoryUnitPayload {
  id: string
  story_kind: string
  title: string
  as_a: string
  when_context: string
  i_want: string
  so_that: string | null
  narrative: string
  actor: string
  context: string
  goal: string
  business_value: string | null
  business_outcome: string
  scope: string[]
  out_of_scope: string[]
  acceptance_criteria: string[]
  dependencies: string[]
  priority: string
  risk: string
  test_focus: string[]
  implementation_hints: string[]
}

export interface TestCaseGenerationRunInputPayload {
  task_id: string
  user_prompt: string
  plan: string | null
  story_units: TestCaseGenerationStoryUnitPayload[]
  story_dependency_graph?: RequirementAnalysisResultPayload['story_dependency_graph']
  story_relationships?: RequirementAnalysisResultPayload['story_relationships']
  execution_constraints: TestCaseGenerationExecutionConstraintsPayload
}

export interface GeneratedTestCasePayload {
  id: string
  story_id: string
  title: string
  level: string
  category: string
  purpose: string
  preconditions: string[]
  test_input: Record<string, unknown>
  steps: string[]
  expected_result: string
  acceptance_criteria_refs: string[]
  priority: string
  automatable: boolean
}

export interface TestCaseGenerationResultPayload {
  test_plan: string
  test_cases: GeneratedTestCasePayload[]
  coverage_summary: {
    total_story_count: number
    covered_story_count: number
    uncovered_story_ids: string[]
    total_test_case_count: number
    per_story_case_count: Record<string, number>
  }
  warnings: string[]
  quality_checks: {
    has_inputs_and_expected_results: boolean
    covers_all_stories: boolean
    has_boundary_cases: boolean
    has_negative_cases: boolean
    case_count_within_limit: boolean
  }
  completion_check?: {
    status: string
    is_complete: boolean
    summary: string
    missing_items: string[]
    notes: string[]
  } | null
}

const uniqueNonEmptyStrings = (values: Array<string | null | undefined>) => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const value of values) {
    const normalized = value?.trim()
    if (!normalized || seen.has(normalized)) {
      continue
    }
    seen.add(normalized)
    result.push(normalized)
  }
  return result
}

const safeArray = <T>(value: T[] | null | undefined): T[] => (
  Array.isArray(value) ? value : []
)

export const toTestCaseGenerationSettingsPayload = (
  settings: RequirementAnalysisAgentSettings,
): TestCaseGenerationSettingsPayload => ({
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

export const buildTestCaseGenerationWorkflowDraft = (
  result: RequirementAnalysisResultPayload,
): string => {
  const lines: string[] = []
  const requirementSpec = result.requirement_spec ?? {
    acceptance_criteria: [],
    product_goal: '',
    problem_statement: '',
  }
  const storyUnits = safeArray(result.story_units)
  const capabilityTitles = safeArray(result.capability_groups).map((group) => group.title)
  const integrationScenarios = safeArray(result.composition_verification?.integration_test_scenarios)
  const dependencyEdges = safeArray(result.story_dependency_graph?.edges)
  const storyRelationships = safeArray(result.story_relationships)
  const requiredBehaviors = uniqueNonEmptyStrings([
    ...safeArray(requirementSpec.acceptance_criteria),
    ...storyUnits.flatMap((story) => safeArray(story.acceptance_criteria)),
  ])

  lines.push('Workflow Draft')
  lines.push(`目标：${requirementSpec.product_goal}`)
  if (capabilityTitles.length > 0) {
    lines.push(`能力范围：${capabilityTitles.join('、')}`)
  }
  lines.push('前后联合流程：')
  lines.push('1. 前端提交已接受的 requirement analysis 结果中的 story_units。')
  lines.push('2. 后端输出与当前实现挂钩的概念性测试计划与测试用例描述。')
  lines.push('3. 后端对照本 draft 做 completion_check，判断覆盖是否完成。')
  lines.push('4. 当前阶段先保证测试设计可审核、可落地，再进入测试代码或实现代码阶段。')
  lines.push('可执行性补齐项：')
  lines.push('- 每个输入字段都要明确参数类型、是否必填、合法格式、边界值和冲突规则。')
  lines.push('- 如果字段是 string，至少覆盖 empty、whitespace、invalid_format、over_max_length、duplicate 五类组合。')
  lines.push('- 需要区分正常路径、边界路径、负向路径，以及跨 story 的端到端联动路径。')
  lines.push('- 测试用例先输出概念性描述，但标题、输入、步骤、预期结果必须能映射到后续测试代码。')

  if (requiredBehaviors.length > 0) {
    lines.push('必须覆盖的需求行为：')
    requiredBehaviors.forEach((item, index) => {
      lines.push(`${index + 1}. ${item}`)
    })
  }

  if (integrationScenarios.length > 0) {
    lines.push('建议保留的端到端场景：')
    integrationScenarios.forEach((scenario, index) => {
      lines.push(`${index + 1}. ${scenario.title} -> ${scenario.expected_outcome}`)
    })
  }

  if (dependencyEdges.length > 0) {
    lines.push('Story 依赖顺序：')
    dependencyEdges.forEach((edge, index) => {
      const from = edge.from ?? edge.from_story_id ?? ''
      const to = edge.to ?? edge.to_story_id ?? ''
      lines.push(`${index + 1}. ${from} -> ${to}：${edge.reason}`)
    })
  }

  if (storyRelationships.length > 0) {
    lines.push('Story 组合关系：')
    storyRelationships.forEach((relationship, index) => {
      const source = relationship.source ?? relationship.source_story_id ?? ''
      const target = relationship.target ?? relationship.target_story_id ?? ''
      lines.push(`${index + 1}. ${source} -> ${target}：${relationship.type}，${relationship.reason}`)
    })
  }

  lines.push('Story 级测试焦点：')
  storyUnits.forEach((story, index) => {
    const testFocus = safeArray(story.test_focus)
    const scope = safeArray(story.scope)
    const focus = testFocus.length > 0 ? testFocus.join('、') : scope.join('、')
    lines.push(`${index + 1}. ${story.title}：${focus}`)
  })

  return lines.join('\n')
}

export const toTestCaseGenerationInputPayload = (
  result: RequirementAnalysisResultPayload,
  planDraft: string,
  prompt: string,
): TestCaseGenerationRunInputPayload => ({
  task_id: result.task_id,
  user_prompt: prompt.trim() || result.requirement_spec?.problem_statement || '',
  plan: planDraft.trim() || null,
  story_units: safeArray(result.story_units).map((story) => ({
    id: story.id,
    story_kind: story.story_kind,
    title: story.title,
    as_a: story.as_a,
    when_context: story.when_context,
    i_want: story.i_want,
    so_that: story.so_that,
    narrative: story.narrative,
    actor: story.actor,
    context: story.when_context,
    goal: story.goal,
    business_value: story.business_value,
    business_outcome: story.business_outcome,
    scope: safeArray(story.scope),
    out_of_scope: safeArray(story.out_of_scope),
    acceptance_criteria: safeArray(story.acceptance_criteria),
    dependencies: safeArray(story.dependencies),
    priority: story.priority,
    risk: story.risk,
    test_focus: safeArray(story.test_focus),
    implementation_hints: safeArray(story.implementation_hints),
  })),
  story_dependency_graph: result.story_dependency_graph,
  story_relationships: safeArray(result.story_relationships),
  execution_constraints: {
    max_test_cases_per_story: 6,
    require_boundary_cases: true,
    require_negative_cases: true,
  },
})
