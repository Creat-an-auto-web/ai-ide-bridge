export type RequirementAnalysisProviderKind = 'openai_compatible'

export interface RequirementAnalysisAgentSettings {
  enabled: boolean
  providerKind: RequirementAnalysisProviderKind
  providerName: string
  model: string
  apiBase: string
  apiKey: string
  temperature: number
  maxTokens: number
  timeoutSeconds: number
}

export interface RequirementAnalysisAgentSettingsSummary {
  enabled: boolean
  providerKind: RequirementAnalysisProviderKind
  providerName: string
  model: string
  apiBase: string
  hasApiKey: boolean
  isConfigured: boolean
}

export interface RequirementAnalysisAgentSettingsPayload {
  enabled: boolean
  provider_kind: RequirementAnalysisProviderKind
  provider_name: string
  model: string
  api_base: string
  api_key: string
  temperature: number
  max_tokens: number
  timeout_seconds: number
}

export interface RequirementAnalysisAgentSettingsDisplayPayload
  extends Omit<RequirementAnalysisAgentSettingsPayload, 'api_key'> {
  api_key: string
}

export interface RequirementAnalysisRunInputPayload {
  task_id: string
  mode: string
  user_prompt: string
  repo_root: string
  workspace_summary: {
    languages: string[]
    frameworks: string[]
    key_modules: string[]
  }
  active_file: string | null
  selection: string | null
  open_files: string[]
  diagnostics: string[]
  recent_test_failures: string[]
  git_diff_summary: string
  execution_constraints: {
    disallow_new_dependencies: boolean
    preserve_public_api: boolean
    max_story_units: number
  }
}

export interface RequirementAnalysisResultPayload {
  requirement_spec: {
    task_id: string
    version: number
    problem_statement: string
    product_goal: string
    scope: string[]
    out_of_scope: string[]
    constraints: string[]
    assumptions: string[]
    interfaces_or_contracts: string[]
    acceptance_criteria: string[]
    decomposition_strategy: string
  }
  story_units: Array<{
    id: string
    title: string
    actor: string
    goal: string
    business_value: string | null
    scope: string[]
    out_of_scope: string[]
    acceptance_criteria: string[]
    dependencies: string[]
    priority: string
    risk: string
    test_focus: string[]
    implementation_hints: string[]
  }>
  analysis_summary: {
    story_unit_count: number
    high_priority_count: number
    high_risk_count: number
  }
  warnings: string[]
  quality_checks: {
    has_clear_scope: boolean
    has_testable_ac: boolean
    dependency_graph_valid: boolean
    story_count_within_limit: boolean
  }
}

export interface RequirementAnalysisStreamEvent {
  type: 'status' | 'heartbeat' | 'model_output' | 'result' | 'error'
  stage: string
  message: string
  raw_text_delta?: string | null
  raw_text_preview?: string | null
  metadata?: Record<string, unknown>
  elapsed_ms?: number
  data?: RequirementAnalysisResultPayload
}

export const createDefaultRequirementAnalysisSettings = (): RequirementAnalysisAgentSettings => ({
  enabled: true,
  providerKind: 'openai_compatible',
  providerName: 'openai',
  model: '',
  apiBase: 'https://api.openai.com/v1',
  apiKey: '',
  temperature: 0.2,
  maxTokens: 4000,
  timeoutSeconds: 60,
})

const toFiniteNumber = (value: unknown, fallback: number) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallback
  }
  return value
}

const toNonEmptyString = (value: unknown, fallback: string) => {
  if (typeof value !== 'string') {
    return fallback
  }
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : fallback
}

export const normalizeRequirementAnalysisSettings = (
  value: unknown,
): RequirementAnalysisAgentSettings => {
  const defaults = createDefaultRequirementAnalysisSettings()
  if (!value || typeof value !== 'object') {
    return defaults
  }

  const record = value as Partial<RequirementAnalysisAgentSettings>
  return {
    enabled: typeof record.enabled === 'boolean' ? record.enabled : defaults.enabled,
    providerKind: 'openai_compatible',
    providerName: toNonEmptyString(record.providerName, defaults.providerName),
    model: typeof record.model === 'string' ? record.model.trim() : defaults.model,
    apiBase: toNonEmptyString(record.apiBase, defaults.apiBase),
    apiKey: typeof record.apiKey === 'string' ? record.apiKey : defaults.apiKey,
    temperature: toFiniteNumber(record.temperature, defaults.temperature),
    maxTokens: Math.max(1, Math.round(toFiniteNumber(record.maxTokens, defaults.maxTokens))),
    timeoutSeconds: Math.max(1, toFiniteNumber(record.timeoutSeconds, defaults.timeoutSeconds)),
  }
}

export const summarizeRequirementAnalysisSettings = (
  settings: RequirementAnalysisAgentSettings,
): RequirementAnalysisAgentSettingsSummary => ({
  enabled: settings.enabled,
  providerKind: settings.providerKind,
  providerName: settings.providerName,
  model: settings.model,
  apiBase: settings.apiBase,
  hasApiKey: settings.apiKey.trim().length > 0,
  isConfigured:
    settings.enabled
    && settings.providerName.trim().length > 0
    && settings.model.trim().length > 0
    && settings.apiBase.trim().length > 0
    && settings.apiKey.trim().length > 0,
})

export const toRequirementAnalysisAgentSettingsPayload = (
  settings: RequirementAnalysisAgentSettings,
): RequirementAnalysisAgentSettingsPayload => ({
  enabled: settings.enabled,
  provider_kind: settings.providerKind,
  provider_name: settings.providerName,
  model: settings.model,
  api_base: settings.apiBase,
  api_key: settings.apiKey,
  temperature: settings.temperature,
  max_tokens: settings.maxTokens,
  timeout_seconds: settings.timeoutSeconds,
})

export const toRequirementAnalysisAgentSettingsDisplayPayload = (
  settings: RequirementAnalysisAgentSettings,
): RequirementAnalysisAgentSettingsDisplayPayload => ({
  ...toRequirementAnalysisAgentSettingsPayload(settings),
  api_key: settings.apiKey.trim().length > 0 ? '<stored>' : '',
})
