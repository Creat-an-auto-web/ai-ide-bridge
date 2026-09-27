import React, { useEffect, useMemo, useRef, useState } from 'react'
import { VSBuffer } from '../../../../../../../base/common/buffer.js'
import { CancellationToken } from '../../../../../../../base/common/cancellation.js'
import { URI } from '../../../../../../../base/common/uri.js'
import { asText } from '../../../../../../../platform/request/common/request.js'
import { StorageScope, StorageTarget } from '../../../../../../../platform/storage/common/storage.js'
import {
  BridgeSidebarPanelState,
  buildTestCaseGenerationWorkflowDraft,
  buildTestCodeGenerationWorkflowDraft,
  GlobalFeedbackPayload,
  PatchReviewModel,
  RequirementAnalysisAgentSettings,
  RequirementAnalysisResultPayload,
  RequirementAnalysisAgentSettingsPayload,
  RequirementAnalysisAgentSettingsSummary,
  StoryFeedbackPayload,
  TestCaseGenerationResultPayload,
  TestCodeExecutionResultPayload,
  TestCodeGenerationResultPayload,
  TestCodeRepairResultPayload,
  RequirementAnalysisStreamEvent,
  DockerRuntimeStatusPayload,
  SandboxExecutionDebugDraft,
  SandboxExecutionResultPayload,
  SandboxExecutionStreamEvent,
  WorkspaceEditModel,
  attachVoidRealIdeSidebarFromAccessor,
  buildWorkflowArtifactBundle,
  collectVoidContext,
  createDefaultRequirementAnalysisSettings,
  createVoidRealContextSourceFromAccessor,
  emptyBridgeSidebarState,
  normalizeRequirementAnalysisSettings,
  summarizeRequirementAnalysisSettings,
  createSandboxExecutionDebugDraft,
  splitCommandDraft,
  toTestCaseGenerationInputPayload,
  toTestCaseGenerationSettingsPayload,
  toTestCodeExecutionInputPayload,
  toTestCodeGenerationInputPayload,
  toTestCodeGenerationSettingsPayload,
  toTestCodeRepairInputPayload,
  toTestCodeRepairSettingsPayload,
  toRequirementAnalysisAgentSettingsPayload,
  toSandboxExecutionInputPayload,
} from '../../../../../../../../ai-ide-bridge/frontend-bridge/src/index.js'
import { useAccessor } from '../util/services.js'

interface DesktopBridgeFetchResult {
  ok: boolean
  status: number
  statusText: string
  headers: Array<[string, string]>
  bodyText: string
}

interface DesktopApi {
  bridgeFetch?: (url: string, init?: RequestInit) => Promise<DesktopBridgeFetchResult>
}

interface NativeRequestServiceLike {
  request(
    options: {
      type?: string
      url?: string
      headers?: Record<string, string>
      data?: string
    },
    token: typeof CancellationToken.None,
  ): Promise<unknown>
}

interface StorageServiceLike {
  get(key: string, scope: StorageScope, fallbackValue?: string): string
  store(key: string, value: string, scope: StorageScope, target: StorageTarget): void
}

declare global {
  interface Window {
    aiIdeDesktop?: DesktopApi
  }
}

export interface AiIdeBridgeUiState {
  panel: BridgeSidebarPanelState
  requirementAnalysisSettings: RequirementAnalysisAgentSettings
  requirementAnalysisSettingsSummary: RequirementAnalysisAgentSettingsSummary
  requirementAnalysisSettingsPayload: RequirementAnalysisAgentSettingsPayload
  requirementAnalysisResult: RequirementAnalysisResultPayload | null
  requirementAnalysisError: string | null
  requirementAnalysisIsRunning: boolean
  requirementAnalysisRunStage: string | null
  requirementAnalysisLastPrompt: string | null
  requirementAnalysisAutoRetryCount: number
  requirementAnalysisPreviewText: string
  requirementAnalysisEvents: RequirementAnalysisStreamEvent[]
  testCaseGenerationPlanDraft: string
  testCaseGenerationResult: TestCaseGenerationResultPayload | null
  testCaseGenerationError: string | null
  testCaseGenerationIsRunning: boolean
  testCodeGenerationPlanDraft: string
  testCodeGenerationResult: TestCodeGenerationResultPayload | null
  testCodeGenerationError: string | null
  testCodeGenerationIsRunning: boolean
  testCodeExecutionCommandDraft: string
  testCodeExecutionResult: TestCodeExecutionResultPayload | null
  testCodeExecutionError: string | null
  testCodeExecutionIsRunning: boolean
  testCodeRepairResult: TestCodeRepairResultPayload | null
  testCodeRepairError: string | null
  testCodeRepairIsRunning: boolean
  workflowArtifactsStatus: 'idle' | 'preview' | 'retained'
  workflowArtifactsDirectoryPath: string | null
  workflowArtifactsWrittenFiles: string[]
  workflowArtifactsError: string | null
  workflowArtifactsIsWorking: boolean
  sandboxDebugDraft: SandboxExecutionDebugDraft
  sandboxDebugEvents: SandboxExecutionStreamEvent[]
  sandboxDebugResult: SandboxExecutionResultPayload | null
  sandboxDebugError: string | null
  sandboxDebugIsRunning: boolean
  sandboxDockerStatus: DockerRuntimeStatusPayload | null
  sandboxDockerCheckIsRunning: boolean
  sandboxDockerChoiceRequired: boolean
  latestNotification: { level: 'info' | 'warning' | 'error'; title: string; message: string } | null
  latestPatchReview: PatchReviewModel | null
  latestWorkspaceEdit: WorkspaceEditModel | null
  finalSummary: string | null
  errorMessage: string | null
}

export interface UseAiIdeBridgeOptions {
  baseUrl?: string
  gitDiffProvider?: () => Promise<string> | string
  testLogsProvider?: () => Promise<string> | string
  branchProvider?: () => Promise<string | undefined> | string | undefined
}

interface RequirementAnalysisContinuationOptions {
  previousResult?: RequirementAnalysisResultPayload | null
  appendedPrompt?: string | null
  globalFeedback?: GlobalFeedbackPayload | null
  storyFeedback?: StoryFeedbackPayload | null
  storyFeedbacks?: StoryFeedbackPayload[] | null
  analysisGoal?: 'content_review' | 'composition_review' | 'composition_revision'
}

const cloneContinuationOptions = (
  options: RequirementAnalysisContinuationOptions,
): RequirementAnalysisContinuationOptions => ({
  previousResult: options.previousResult ?? null,
  appendedPrompt: options.appendedPrompt ?? null,
  globalFeedback: options.globalFeedback ?? null,
  storyFeedback: options.storyFeedback ?? null,
  storyFeedbacks: options.storyFeedbacks ? [...options.storyFeedbacks] : null,
  analysisGoal: options.analysisGoal ?? 'content_review',
})

const uniqueNonEmptyStrings = (values: Array<string | null | undefined>): string[] => {
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

const safeArray = <T,>(value: T[] | null | undefined): T[] => (
  Array.isArray(value) ? value : []
)

const normalizeCapabilityGroupsForSnapshot = (
  previousResult: RequirementAnalysisResultPayload,
): RequirementAnalysisResultPayload['capability_groups'] => {
  const alternateCapabilityGroups = (previousResult as { capabilityGroups?: RequirementAnalysisResultPayload['capability_groups'] }).capabilityGroups
  if (Array.isArray(previousResult.capability_groups) && previousResult.capability_groups.length > 0) {
    return previousResult.capability_groups
  }
  if (Array.isArray(alternateCapabilityGroups) && alternateCapabilityGroups.length > 0) {
    return alternateCapabilityGroups
  }

  const stories = safeArray(previousResult.story_units)
  if (stories.length === 0) {
    return []
  }
  const storyScope = uniqueNonEmptyStrings(stories.flatMap((story) => safeArray(story.scope)))
  const specScope = uniqueNonEmptyStrings(safeArray(previousResult.requirement_spec?.scope))
  const storyIds = uniqueNonEmptyStrings(stories.map((story) => story.id))
  return [
    {
      id: 'capability_group_1',
      title: '整体需求分组',
      goal: '基于当前已通过的 user story 组合进入组合验证',
      scope: storyScope.length > 0 ? storyScope : specScope.length > 0 ? specScope : ['当前需求范围'],
      story_ids: storyIds,
      priority: stories.some((story) => story.priority === 'high') ? 'high' : 'medium',
    },
  ]
}

const toPreviousAnalysisResultSnapshot = (
  previousResult: RequirementAnalysisResultPayload | null | undefined,
) => {
  if (!previousResult) {
    return null
  }
  return {
    requirement_spec: previousResult.requirement_spec,
    story_units: previousResult.story_units,
    capability_groups: normalizeCapabilityGroupsForSnapshot(previousResult),
    warnings: previousResult.warnings,
    quality_checks: previousResult.quality_checks,
    story_dependency_graph: previousResult.story_dependency_graph,
    story_relationships: previousResult.story_relationships,
    verification: previousResult.verification,
    composition_verification: previousResult.composition_verification ?? null,
  }
}

const shouldContinueWithCompositionRevision = (
  previousResult: RequirementAnalysisResultPayload | null | undefined,
) => {
  const compositionStatus = previousResult?.composition_verification?.status
  return compositionStatus === 'revise' || compositionStatus === 'blocked'
}

const isNativeVoidHost = () =>
  typeof window !== 'undefined' && window.location.protocol === 'vscode-file:'

const defaultNativeBaseUrl = () =>
  isNativeVoidHost() ? 'https://localhost:27183' : undefined

const defaultNativeWebSocketFactory = (() => {
  if (!isNativeVoidHost()) {
    return undefined
  }

  return (url: string) => {
    const wsUrl = new URL(url)
    wsUrl.protocol = 'ws:'
    wsUrl.hostname = '127.0.0.1'
    wsUrl.port = '27182'
    return new WebSocket(wsUrl.toString())
  }
})()

const toWebSocketUrl = (baseUrl: string, path: string) => {
  const url = new URL(baseUrl)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = path
  url.search = ''
  url.hash = ''
  return url.toString()
}

const appendRequirementAnalysisEvent = (
  events: RequirementAnalysisStreamEvent[],
  nextEvent: RequirementAnalysisStreamEvent,
) => [...events, nextEvent].slice(-50)

const createDesktopFetch = (): typeof fetch | undefined => {
  const bridgeFetch = window.aiIdeDesktop?.bridgeFetch
  if (!bridgeFetch) {
    return undefined
  }

  return async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    const method =
      init?.method
      ?? (typeof Request !== 'undefined' && input instanceof Request ? input.method : undefined)
    const headers =
      init?.headers
      ?? (typeof Request !== 'undefined' && input instanceof Request ? input.headers : undefined)
    const body =
      init?.body
      ?? (typeof Request !== 'undefined' && input instanceof Request ? input.body : undefined)

    const response = await bridgeFetch(url, {
      ...init,
      method,
      headers: headers instanceof Headers ? Object.fromEntries(headers.entries()) : headers,
      body: typeof body === 'string' ? body : undefined,
    })

    return new Response(response.bodyText, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    })
  }
}

const toRequestUrl = (input: RequestInfo | URL): string =>
  typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url

const toRequestMethod = (input: RequestInfo | URL, init?: RequestInit): string =>
  init?.method
  ?? (typeof Request !== 'undefined' && input instanceof Request ? input.method : undefined)
  ?? 'GET'

const toRequestHeaders = (
  input: RequestInfo | URL,
  init?: RequestInit,
): Record<string, string> => {
  const source =
    init?.headers
    ?? (typeof Request !== 'undefined' && input instanceof Request ? input.headers : undefined)

  if (!source) {
    return {}
  }

  if (source instanceof Headers) {
    return Object.fromEntries(source.entries())
  }

  if (Array.isArray(source)) {
    return Object.fromEntries(source)
  }

  return Object.fromEntries(
    Object.entries(source).map(([key, value]) => [key, String(value)]),
  )
}

const toRequestBody = async (
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<string | undefined> => {
  const body =
    init?.body
    ?? (typeof Request !== 'undefined' && input instanceof Request ? await input.clone().text() : undefined)

  if (typeof body === 'string') {
    return body
  }

  if (body instanceof URLSearchParams) {
    return body.toString()
  }

  return undefined
}

const toResponseHeaders = (headers: Record<string, string | string[] | undefined>) =>
  Object.entries(headers).flatMap(([key, value]) => {
    if (typeof value === 'undefined') {
      return []
    }

    if (Array.isArray(value)) {
      return value.map((item) => [key, item] satisfies [string, string])
    }

    return [[key, value] satisfies [string, string]]
  })

const createNativeRequestFetch = (
  requestService: NativeRequestServiceLike | undefined,
): typeof fetch | undefined => {
  if (!requestService) {
    return undefined
  }

  return async (input, init) => {
    const context = await requestService.request(
      {
        type: toRequestMethod(input, init),
        url: toRequestUrl(input),
        headers: toRequestHeaders(input, init),
        data: await toRequestBody(input, init),
      },
      CancellationToken.None,
    ) as Awaited<ReturnType<NativeRequestServiceLike['request']>>

    const bodyText = await asText(context as never) ?? ''
    const responseContext = context as {
      res: {
        statusCode?: number
        headers: Record<string, string | string[] | undefined>
      }
    }

    return new Response(bodyText, {
      status: responseContext.res.statusCode ?? 200,
      headers: toResponseHeaders(responseContext.res.headers),
    })
  }
}

const REQUIREMENT_ANALYSIS_SETTINGS_STORAGE_KEY = 'aiIdeBridge.requirementAnalysis.settings'
const REQUIREMENT_ANALYSIS_SETTINGS_LOCAL_STORAGE_KEY = 'ai-ide-bridge.requirement-analysis.settings'
const loadRequirementAnalysisSettingsFromStorage = (
  storageService: StorageServiceLike | undefined,
): RequirementAnalysisAgentSettings => {
  try {
    const storedValue = storageService?.get(
      REQUIREMENT_ANALYSIS_SETTINGS_STORAGE_KEY,
      StorageScope.APPLICATION,
      '',
    )
    if (storedValue) {
      return normalizeRequirementAnalysisSettings(JSON.parse(storedValue))
    }
  } catch {
    // ignore storage parse errors and fall back to localStorage/defaults
  }

  try {
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
      const storedValue = window.localStorage.getItem(REQUIREMENT_ANALYSIS_SETTINGS_LOCAL_STORAGE_KEY)
      if (storedValue) {
        return normalizeRequirementAnalysisSettings(JSON.parse(storedValue))
      }
    }
  } catch {
    // ignore localStorage errors and fall back to defaults
  }

  return createDefaultRequirementAnalysisSettings()
}

const persistRequirementAnalysisSettings = (
  settings: RequirementAnalysisAgentSettings,
  storageService: StorageServiceLike | undefined,
) => {
  const serialized = JSON.stringify(settings)

  try {
    storageService?.store(
      REQUIREMENT_ANALYSIS_SETTINGS_STORAGE_KEY,
      serialized,
      StorageScope.APPLICATION,
      StorageTarget.MACHINE,
    )
  } catch {
    // ignore storage errors and still attempt browser fallback
  }

  try {
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
      window.localStorage.setItem(REQUIREMENT_ANALYSIS_SETTINGS_LOCAL_STORAGE_KEY, serialized)
    }
  } catch {
    // ignore localStorage write failures
  }
}

const toSelectionText = (selection: BridgeSidebarPanelState['summary'] | { startLine?: number; startCol?: number; endLine?: number; endCol?: number } | null | undefined) => {
  if (!selection || typeof selection !== 'object') {
    return null
  }
  const range = selection as { startLine?: number; startCol?: number; endLine?: number; endCol?: number }
  if (
    typeof range.startLine !== 'number'
    || typeof range.startCol !== 'number'
    || typeof range.endLine !== 'number'
    || typeof range.endCol !== 'number'
  ) {
    return null
  }
  return `${range.startLine}:${range.startCol}-${range.endLine}:${range.endCol}`
}

const toDiagnosticText = (diagnostic: unknown) => {
  if (!diagnostic || typeof diagnostic !== 'object') {
    return String(diagnostic)
  }
  const record = diagnostic as { message?: unknown; file?: unknown; source?: unknown; severity?: unknown }
  const message = typeof record.message === 'string' ? record.message : String(record.message ?? '')
  const file = typeof record.file === 'string' ? record.file : ''
  const source = typeof record.source === 'string' ? record.source : ''
  const severity = typeof record.severity === 'string' || typeof record.severity === 'number'
    ? String(record.severity)
    : ''
  return [severity, source, file, message].filter(Boolean).join(' | ')
}

const toRecentTestFailures = (testLogs: string): string[] =>
  testLogs
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .slice(-10)

const trimTextHead = (text: string, maxChars: number): string =>
  text.length <= maxChars ? text : text.slice(0, maxChars)

const trimTextTail = (text: string, maxChars: number): string =>
  text.length <= maxChars ? text : text.slice(-maxChars)

const REQUIREMENT_ANALYSIS_MAX_OPEN_FILES = 8
const REQUIREMENT_ANALYSIS_MAX_DIAGNOSTICS = 8
const REQUIREMENT_ANALYSIS_MAX_TEST_FAILURES = 8
const REQUIREMENT_ANALYSIS_MAX_GIT_DIFF_CHARS = 4000
const REQUIREMENT_ANALYSIS_MAX_PREVIOUS_SUMMARY_CHARS = 1200

const resolveIterationExecutionConstraints = (
  settings: RequirementAnalysisAgentSettings,
  iteration: number,
) => {
  if (iteration <= 1) {
    return {
      max_capability_groups: settings.firstRoundMaxCapabilityGroups,
      max_story_units: settings.firstRoundMaxStoryUnits,
    }
  }
  if (iteration === 2) {
    return {
      max_capability_groups: settings.secondRoundMaxCapabilityGroups,
      max_story_units: settings.secondRoundMaxStoryUnits,
    }
  }
  return {
    max_capability_groups: settings.laterRoundMaxCapabilityGroups,
    max_story_units: settings.laterRoundMaxStoryUnits,
  }
}

const toContinuationRevisionFocus = (
  previousResult: RequirementAnalysisResultPayload | null | undefined,
  globalFeedback?: GlobalFeedbackPayload | null,
  storyFeedback?: StoryFeedbackPayload | null,
  storyFeedbacks?: StoryFeedbackPayload[] | null,
): string[] => {
  const focus: string[] = []
  const seen = new Set<string>()
  const pushUnique = (value: string | null | undefined) => {
    const normalized = value?.trim()
    if (!normalized || seen.has(normalized)) {
      return
    }
    seen.add(normalized)
    focus.push(normalized)
  }
  const compositionVerification = previousResult?.composition_verification
  const revisionGuidance = safeArray(compositionVerification?.revision_guidance)
  const missingStoryTopics = safeArray(compositionVerification?.missing_story_topics)
  const compositionIssues = safeArray(compositionVerification?.composition_issues)
  if (revisionGuidance.length) {
    revisionGuidance.forEach(pushUnique)
  }
  if (missingStoryTopics.length) {
    missingStoryTopics.forEach((topic) => pushUnique(`补充缺失的组合能力：${topic}`))
  }
  if (compositionIssues.length) {
    compositionIssues.forEach((issue) => pushUnique(issue.suggested_action || issue.message))
  }
  if (compositionVerification?.status === 'pass' && focus.length === 0) {
    pushUnique('在不破坏当前已通过组合闭环的前提下，继续增强端到端流程覆盖、边界场景、跨 story 依赖一致性和集成测试可验证性。')
  }
  if (globalFeedback?.feedback_text?.trim()) {
    pushUnique(globalFeedback.feedback_text.trim())
  }
  const effectiveStoryFeedbacks = (
    storyFeedbacks?.length
      ? storyFeedbacks
      : storyFeedback
        ? [storyFeedback]
        : []
  )
  effectiveStoryFeedbacks.forEach((feedback) => {
    if (feedback.feedback_text?.trim() && feedback.story_id?.trim()) {
      pushUnique(`针对 ${feedback.story_id.trim()}：${feedback.feedback_text.trim()}`)
    }
  })
  if (focus.length > 0) {
    return focus
  }
  if (!previousResult) {
    return []
  }
  const verificationRevisionGuidance = safeArray(previousResult.verification?.revision_guidance)
  const verificationIssues = safeArray(previousResult.verification?.issues)
  if (verificationRevisionGuidance.length) {
    return verificationRevisionGuidance
  }
  if (verificationIssues.length) {
    return verificationIssues.map((issue) => issue.message)
  }
  return ['在保持当前质量的前提下继续提升需求拆解的一致性、边界清晰度和 user story 粒度。']
}

const toRequirementAnalysisInputPayload = async (
  accessor: unknown,
  settings: RequirementAnalysisAgentSettings,
  prompt: string,
  options: RequirementAnalysisContinuationOptions = {},
) => {
  const previousResult = options.previousResult ?? null
  const appendedPrompt = options.appendedPrompt?.trim() ?? ''
  const analysisGoal = options.analysisGoal ?? 'content_review'
  const iteration = previousResult
    ? analysisGoal === 'composition_review'
      ? Math.max(1, previousResult.iteration_count)
      : Math.max(1, previousResult.iteration_count + 1)
    : 1
  const executionConstraints = resolveIterationExecutionConstraints(settings, iteration)
  const contextSource = createVoidRealContextSourceFromAccessor({
    accessor: accessor as never,
  })
  const [repoRootPath, context] = await Promise.all([
    contextSource.getRepoRootPath(),
    collectVoidContext(contextSource),
  ])

  return {
    task_id:
      previousResult?.task_id
      ?? (typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `ra_${Math.random().toString(16).slice(2, 10)}`),
    mode: 'repo_chat',
    user_prompt: appendedPrompt
      ? `${prompt}\n\n[用户追加说明]\n${appendedPrompt}`
      : prompt,
    repo_root: repoRootPath,
    workspace_summary: {
      languages: [],
      frameworks: [],
      key_modules: [],
    },
    active_file: context.activeFile ?? null,
    selection: toSelectionText(context.selection),
    open_files: context.openFiles.slice(0, REQUIREMENT_ANALYSIS_MAX_OPEN_FILES),
    diagnostics: context.diagnostics
      .map((diagnostic) => toDiagnosticText(diagnostic))
      .slice(0, REQUIREMENT_ANALYSIS_MAX_DIAGNOSTICS),
    recent_test_failures: toRecentTestFailures(context.testLogs).slice(0, REQUIREMENT_ANALYSIS_MAX_TEST_FAILURES),
    git_diff_summary: trimTextTail(context.gitDiff, REQUIREMENT_ANALYSIS_MAX_GIT_DIFF_CHARS),
    global_feedback: options.globalFeedback ?? null,
    story_feedback: options.storyFeedback ?? null,
    story_feedbacks: (
      options.storyFeedbacks?.length
        ? options.storyFeedbacks
        : options.storyFeedback
          ? [options.storyFeedback]
          : []
    ),
    revision_focus: toContinuationRevisionFocus(
      previousResult,
      options.globalFeedback,
      options.storyFeedback,
      options.storyFeedbacks,
    ),
    previous_verification_summary:
      trimTextHead(
        previousResult?.composition_verification?.summary
          ?? previousResult?.verification?.summary
          ?? '',
        REQUIREMENT_ANALYSIS_MAX_PREVIOUS_SUMMARY_CHARS,
      ) || null,
    iteration,
    analysis_goal: analysisGoal,
    previous_analysis_result:
      analysisGoal === 'composition_review' || analysisGoal === 'composition_revision'
        ? toPreviousAnalysisResultSnapshot(previousResult)
        : null,
    execution_constraints: {
      disallow_new_dependencies: true,
      preserve_public_api: true,
      max_capability_groups: executionConstraints.max_capability_groups,
      max_story_units: executionConstraints.max_story_units,
    },
  }
}

export const useAiIdeBridge = (options: UseAiIdeBridgeOptions = {}) => {
  const accessor = useAccessor()
  const accessorRef = useRef(accessor)
  accessorRef.current = accessor
  const nativeRequestService =
    ('get' in accessor
      ? accessor.get('IRequestService' as never)
      : undefined) as NativeRequestServiceLike | undefined
  const storageService =
    ('get' in accessor
      ? accessor.get('IStorageService' as never)
      : undefined) as StorageServiceLike | undefined
  const hostOptions =
    ('get' in accessor
      ? accessor.get('__bridgeHostBridgeOptions' as never) as {
        baseUrl?: string
        branchProvider?: () => Promise<string | undefined> | string | undefined
        gitDiffProvider?: () => Promise<string> | string
        testLogsProvider?: () => Promise<string> | string
        fetchImpl?: typeof fetch
        webSocketFactory?: (url: string) => WebSocket
      }
      : {}) ?? {}
  const bridgeBaseUrl = useMemo(
    () => (
      options.baseUrl
      ?? hostOptions.baseUrl
      ?? defaultNativeBaseUrl()
      ?? 'http://127.0.0.1:27182'
    ),
    [hostOptions.baseUrl, options.baseUrl],
  )
  const bridgeFetchImpl = useMemo(
    () => (
      hostOptions.fetchImpl
      ?? createNativeRequestFetch(nativeRequestService)
      ?? createDesktopFetch()
      ?? fetch
    ),
    [hostOptions.fetchImpl, nativeRequestService],
  )
  const entryRef = useRef<ReturnType<typeof attachVoidRealIdeSidebarFromAccessor> | null>(null)
  const requirementAnalysisSocketRef = useRef<WebSocket | null>(null)
  const sandboxDebugSocketRef = useRef<WebSocket | null>(null)
  const sandboxDebugOperationRef = useRef(0)
  const requirementAnalysisStopRequestedRef = useRef(false)
  const requirementAnalysisLastRunOptionsRef = useRef<RequirementAnalysisContinuationOptions>({})

  const [uiState, setUiState] = useState<AiIdeBridgeUiState>({
    panel: emptyBridgeSidebarState(),
    requirementAnalysisSettings: createDefaultRequirementAnalysisSettings(),
    requirementAnalysisSettingsSummary: summarizeRequirementAnalysisSettings(
      createDefaultRequirementAnalysisSettings(),
    ),
    requirementAnalysisSettingsPayload: toRequirementAnalysisAgentSettingsPayload(
      createDefaultRequirementAnalysisSettings(),
    ),
    requirementAnalysisResult: null,
    requirementAnalysisError: null,
    requirementAnalysisIsRunning: false,
    requirementAnalysisRunStage: null,
    requirementAnalysisLastPrompt: null,
    requirementAnalysisAutoRetryCount: 0,
    requirementAnalysisPreviewText: '',
    requirementAnalysisEvents: [],
    testCaseGenerationPlanDraft: '',
    testCaseGenerationResult: null,
    testCaseGenerationError: null,
    testCaseGenerationIsRunning: false,
    testCodeGenerationPlanDraft: '',
    testCodeGenerationResult: null,
    testCodeGenerationError: null,
    testCodeGenerationIsRunning: false,
    testCodeExecutionCommandDraft: '',
    testCodeExecutionResult: null,
    testCodeExecutionError: null,
    testCodeExecutionIsRunning: false,
    testCodeRepairResult: null,
    testCodeRepairError: null,
    testCodeRepairIsRunning: false,
    workflowArtifactsStatus: 'idle',
    workflowArtifactsDirectoryPath: null,
    workflowArtifactsWrittenFiles: [],
    workflowArtifactsError: null,
    workflowArtifactsIsWorking: false,
    sandboxDebugDraft: createSandboxExecutionDebugDraft(),
    sandboxDebugEvents: [],
    sandboxDebugResult: null,
    sandboxDebugError: null,
    sandboxDebugIsRunning: false,
    sandboxDockerStatus: null,
    sandboxDockerCheckIsRunning: false,
    sandboxDockerChoiceRequired: false,
    latestNotification: null,
    latestPatchReview: null,
    latestWorkspaceEdit: null,
    finalSummary: null,
    errorMessage: null,
  })

  useEffect(() => {
    const loadedSettings = loadRequirementAnalysisSettingsFromStorage(storageService)
    setUiState((prev) => ({
      ...prev,
      requirementAnalysisSettings: loadedSettings,
      requirementAnalysisSettingsSummary: summarizeRequirementAnalysisSettings(loadedSettings),
      requirementAnalysisSettingsPayload: toRequirementAnalysisAgentSettingsPayload(loadedSettings),
    }))
  }, [storageService])

  useEffect(() => {
    const entry = attachVoidRealIdeSidebarFromAccessor({
      accessor: accessorRef.current,
      bridgeClientOptions: {
        baseUrl: bridgeBaseUrl,
        fetchImpl: bridgeFetchImpl,
        webSocketFactory: hostOptions.webSocketFactory ?? defaultNativeWebSocketFactory,
      },
      branchProvider: options.branchProvider ?? hostOptions.branchProvider,
      gitDiffProvider: options.gitDiffProvider ?? hostOptions.gitDiffProvider,
      testLogsProvider: options.testLogsProvider ?? hostOptions.testLogsProvider,
      view: {
        renderPanel(panel) {
          setUiState((prev) => ({ ...prev, panel }))
        },
        showNotification(notification) {
          setUiState((prev) => ({ ...prev, latestNotification: notification }))
        },
        focusApprovalCard() {
          return
        },
        showPatchReview(review) {
          setUiState((prev) => ({ ...prev, latestPatchReview: review }))
        },
        showWorkspaceEdit(editModel) {
          setUiState((prev) => ({ ...prev, latestWorkspaceEdit: editModel }))
        },
        showFinalSummary(summary) {
          setUiState((prev) => ({ ...prev, finalSummary: summary }))
        },
        showError(message) {
          setUiState((prev) => ({ ...prev, errorMessage: message }))
        },
      },
    })

    entryRef.current = entry

    return () => {
      sandboxDebugOperationRef.current += 1
      sandboxDebugSocketRef.current?.close()
      sandboxDebugSocketRef.current = null
      entry.dispose()
      entryRef.current = null
    }
  }, [
    hostOptions.baseUrl,
    hostOptions.branchProvider,
    hostOptions.gitDiffProvider,
    hostOptions.testLogsProvider,
    bridgeBaseUrl,
    bridgeFetchImpl,
    options.branchProvider,
    options.gitDiffProvider,
    options.testLogsProvider,
  ])

  const workflowArtifactBundle = buildWorkflowArtifactBundle({
    requirementAnalysisResult: uiState.requirementAnalysisResult,
    testCaseGenerationResult: uiState.testCaseGenerationResult,
    testCodeGenerationResult: uiState.testCodeGenerationResult,
    testCodeRepairResult: uiState.testCodeRepairResult,
  })

  const getWorkflowArtifactDirectory = (preview: boolean) => {
    if (!workflowArtifactBundle) {
      throw new Error('当前没有可写入的阶段产物。')
    }
    const workspace = accessorRef.current.get('IWorkspaceContextService').getWorkspace()
    const workspaceRoot = workspace.folders?.[0]?.uri
    if (!workspaceRoot) {
      throw new Error('当前未打开工作区，无法保存阶段产物。')
    }
    return URI.joinPath(
      workspaceRoot,
      'ai-ide-artifacts',
      preview
        ? `.preview-${workflowArtifactBundle.directoryName}`
        : workflowArtifactBundle.directoryName,
    )
  }

  const materializeWorkflowArtifacts = async (retain: boolean) => {
    if (!workflowArtifactBundle) {
      setUiState((prev) => ({
        ...prev,
        workflowArtifactsError: '当前没有可查看的阶段产物。',
      }))
      return
    }

    setUiState((prev) => ({
      ...prev,
      workflowArtifactsIsWorking: true,
      workflowArtifactsError: null,
    }))
    try {
      const fileService = accessorRef.current.get('IFileService')
      const commandService = accessorRef.current.get('ICommandService')
      const artifactDirectory = getWorkflowArtifactDirectory(!retain)
      if (await fileService.exists(artifactDirectory)) {
        await fileService.del(artifactDirectory, { recursive: true })
      }
      await fileService.createFolder(artifactDirectory)

      const writtenFiles: string[] = []
      for (const file of workflowArtifactBundle.files) {
        const pathSegments = file.relativePath.split('/').filter(Boolean)
        const fileUri = URI.joinPath(artifactDirectory, ...pathSegments)
        if (pathSegments.length > 1) {
          await fileService.createFolder(
            URI.joinPath(artifactDirectory, ...pathSegments.slice(0, -1)),
          )
        }
        await fileService.writeFile(fileUri, VSBuffer.fromString(file.content))
        writtenFiles.push(file.relativePath)
      }

      const summaryUri = URI.joinPath(artifactDirectory, 'README.md')
      await commandService.executeCommand('vscode.open', summaryUri)
      if (retain) {
        const previewDirectory = getWorkflowArtifactDirectory(true)
        if (await fileService.exists(previewDirectory)) {
          await fileService.del(previewDirectory, { recursive: true })
        }
      }
      setUiState((prev) => ({
        ...prev,
        workflowArtifactsStatus: retain ? 'retained' : 'preview',
        workflowArtifactsDirectoryPath: artifactDirectory.fsPath,
        workflowArtifactsWrittenFiles: writtenFiles,
        workflowArtifactsError: null,
        latestNotification: {
          level: 'info',
          title: 'WorkflowArtifacts',
          message: retain
            ? `已保留 ${writtenFiles.length} 个阶段产物文件。`
            : `已在 IDE 中打开 ${writtenFiles.length} 个阶段产物文件。`,
        },
      }))
    } catch (error) {
      setUiState((prev) => ({
        ...prev,
        workflowArtifactsError: error instanceof Error ? error.message : String(error),
      }))
    } finally {
      setUiState((prev) => ({
        ...prev,
        workflowArtifactsIsWorking: false,
      }))
    }
  }

  return useMemo(() => ({
    uiState,
    workflowArtifactBundle,
    async previewWorkflowArtifacts() {
      if (uiState.workflowArtifactsStatus === 'retained') {
        try {
          const artifactDirectory = getWorkflowArtifactDirectory(false)
          const fileService = accessorRef.current.get('IFileService')
          if (await fileService.exists(artifactDirectory)) {
            await accessorRef.current.get('ICommandService').executeCommand(
              'vscode.open',
              URI.joinPath(artifactDirectory, 'README.md'),
            )
            return
          }
        } catch (error) {
          setUiState((prev) => ({
            ...prev,
            workflowArtifactsError: error instanceof Error ? error.message : String(error),
          }))
          return
        }
      }
      await materializeWorkflowArtifacts(uiState.workflowArtifactsStatus === 'retained')
    },
    async retainWorkflowArtifacts() {
      await materializeWorkflowArtifacts(true)
    },
    async discardWorkflowArtifactPreview() {
      if (uiState.workflowArtifactsStatus !== 'preview') {
        return
      }
      setUiState((prev) => ({
        ...prev,
        workflowArtifactsIsWorking: true,
        workflowArtifactsError: null,
      }))
      try {
        const artifactDirectory = getWorkflowArtifactDirectory(true)
        const fileService = accessorRef.current.get('IFileService')
        if (await fileService.exists(artifactDirectory)) {
          await fileService.del(artifactDirectory, { recursive: true })
        }
        setUiState((prev) => ({
          ...prev,
          workflowArtifactsStatus: 'idle',
          workflowArtifactsDirectoryPath: null,
          workflowArtifactsWrittenFiles: [],
          latestNotification: {
            level: 'info',
            title: 'WorkflowArtifacts',
            message: '阶段产物预览文件已清理。',
          },
        }))
      } catch (error) {
        setUiState((prev) => ({
          ...prev,
          workflowArtifactsError: error instanceof Error ? error.message : String(error),
        }))
      } finally {
        setUiState((prev) => ({
          ...prev,
          workflowArtifactsIsWorking: false,
        }))
      }
    },
    setPrompt(prompt: string) {
      entryRef.current?.setPrompt(prompt)
    },
    setMode(mode: BridgeSidebarPanelState['composer']['mode']) {
      entryRef.current?.setMode(mode)
    },
    async run(prompt?: string) {
      await entryRef.current?.run(prompt)
    },
    async runRequirementAnalysis(
      prompt?: string,
      continuationOptions: RequirementAnalysisContinuationOptions = {},
    ) {
      const nextPrompt = (prompt ?? uiState.panel.composer.prompt).trim()
      if (!nextPrompt) {
        setUiState((prev) => ({
          ...prev,
          requirementAnalysisError: '请先输入需求，再运行需求分析。',
        }))
        return
      }

      requirementAnalysisLastRunOptionsRef.current = cloneContinuationOptions(continuationOptions)
      requirementAnalysisStopRequestedRef.current = false

      setUiState((prev) => ({
        ...prev,
        requirementAnalysisError: null,
        requirementAnalysisIsRunning: true,
        requirementAnalysisRunStage: 'starting',
        requirementAnalysisLastPrompt: nextPrompt,
        requirementAnalysisAutoRetryCount: 0,
        requirementAnalysisPreviewText: '',
        requirementAnalysisEvents: [],
        requirementAnalysisResult: continuationOptions.previousResult ?? null,
        testCaseGenerationResult: null,
        testCaseGenerationError: null,
        testCodeGenerationResult: null,
        testCodeGenerationError: null,
        testCodeExecutionCommandDraft: '',
        testCodeExecutionResult: null,
        testCodeExecutionError: null,
        testCodeRepairResult: null,
        testCodeRepairError: null,
        workflowArtifactsStatus: 'idle',
        workflowArtifactsDirectoryPath: null,
        workflowArtifactsWrittenFiles: [],
        workflowArtifactsError: null,
      }))

      try {
        const inputPayload = await toRequirementAnalysisInputPayload(
          accessorRef.current,
          uiState.requirementAnalysisSettings,
          nextPrompt,
          continuationOptions,
        )
        const payload = {
          settings: uiState.requirementAnalysisSettingsPayload,
          input: inputPayload,
        }
        const webSocketFactory =
          hostOptions.webSocketFactory
          ?? defaultNativeWebSocketFactory
          ?? ((url: string) => new WebSocket(url))

        await new Promise<void>((resolve, reject) => {
          let settled = false
          const socket = webSocketFactory(
            toWebSocketUrl(bridgeBaseUrl, '/v1/requirement-analysis/ws'),
          )
          requirementAnalysisSocketRef.current = socket

          const finishWithError = (error: Error) => {
            if (requirementAnalysisStopRequestedRef.current) {
              if (!settled) {
                settled = true
                resolve()
              }
              return
            }
            if (settled) {
              return
            }
            settled = true
            try {
              socket.close()
            } catch {
              // ignore close errors
            }
            if (requirementAnalysisSocketRef.current === socket) {
              requirementAnalysisSocketRef.current = null
            }
            reject(error)
          }

          socket.onopen = () => {
            socket.send(JSON.stringify(payload))
          }

          socket.onmessage = (message) => {
            try {
              const event = JSON.parse(String(message.data)) as RequirementAnalysisStreamEvent
              setUiState((prev) => ({
                ...prev,
                requirementAnalysisRunStage: event.stage ?? prev.requirementAnalysisRunStage,
                requirementAnalysisAutoRetryCount:
                  event.stage === 'provider_request_retrying'
                    ? Math.max(
                      prev.requirementAnalysisAutoRetryCount,
                      Number(event.metadata?.attempt ?? 0),
                    )
                    : prev.requirementAnalysisAutoRetryCount,
                requirementAnalysisPreviewText:
                  typeof event.raw_text_preview === 'string'
                    ? event.raw_text_preview
                    : typeof event.raw_text_delta === 'string' && event.raw_text_delta.length > 0
                      ? `${prev.requirementAnalysisPreviewText}${event.raw_text_delta}`.slice(-2000)
                      : prev.requirementAnalysisPreviewText,
                requirementAnalysisEvents: appendRequirementAnalysisEvent(
                  prev.requirementAnalysisEvents,
                  event,
                ),
                requirementAnalysisResult:
                  event.type === 'result' && event.data
                    ? event.data
                    : prev.requirementAnalysisResult,
                testCaseGenerationPlanDraft:
                  event.type === 'result' && event.data
                    ? buildTestCaseGenerationWorkflowDraft(event.data)
                    : prev.testCaseGenerationPlanDraft,
                testCaseGenerationResult:
                  event.type === 'result'
                    ? null
                    : prev.testCaseGenerationResult,
                testCodeGenerationPlanDraft:
                  event.type === 'result' && event.data
                    ? ''
                    : prev.testCodeGenerationPlanDraft,
                testCodeGenerationResult:
                  event.type === 'result'
                    ? null
                    : prev.testCodeGenerationResult,
                testCodeExecutionCommandDraft:
                  event.type === 'result'
                    ? ''
                    : prev.testCodeExecutionCommandDraft,
                testCodeExecutionResult:
                  event.type === 'result'
                    ? null
                    : prev.testCodeExecutionResult,
                testCodeRepairResult:
                  event.type === 'result'
                    ? null
                    : prev.testCodeRepairResult,
                workflowArtifactsStatus:
                  event.type === 'result' ? 'idle' : prev.workflowArtifactsStatus,
                workflowArtifactsDirectoryPath:
                  event.type === 'result' ? null : prev.workflowArtifactsDirectoryPath,
                workflowArtifactsWrittenFiles:
                  event.type === 'result' ? [] : prev.workflowArtifactsWrittenFiles,
                workflowArtifactsError:
                  event.type === 'result' ? null : prev.workflowArtifactsError,
                requirementAnalysisError:
                  event.type === 'error'
                    ? event.message
                    : prev.requirementAnalysisError,
                latestNotification:
                  event.type === 'result' && event.data
                    ? {
                      level: 'info',
                      title: 'RequirementAnalysis',
                      message: `已生成 ${event.data.analysis_summary.story_unit_count} 个用户故事`,
                    }
                    : prev.latestNotification,
              }))

              if (event.type === 'result') {
                if (!settled) {
                  settled = true
                  resolve()
                }
                if (requirementAnalysisSocketRef.current === socket) {
                  requirementAnalysisSocketRef.current = null
                }
                socket.close()
                return
              }

              if (event.type === 'error') {
                finishWithError(new Error(event.message || '需求分析服务调用失败'))
              }
            } catch (error) {
              finishWithError(
                error instanceof Error ? error : new Error(String(error)),
              )
            }
          }

          socket.onerror = () => {
            if (requirementAnalysisStopRequestedRef.current) {
              if (!settled) {
                settled = true
                resolve()
              }
              return
            }
            finishWithError(new Error('需求分析流式连接失败'))
          }

          socket.onclose = () => {
            if (requirementAnalysisSocketRef.current === socket) {
              requirementAnalysisSocketRef.current = null
            }
            if (requirementAnalysisStopRequestedRef.current) {
              if (!settled) {
                settled = true
                resolve()
              }
              return
            }
            if (!settled) {
              finishWithError(new Error('需求分析流式连接已关闭'))
            }
          }
        })
      } catch (error) {
        setUiState((prev) => ({
          ...prev,
          requirementAnalysisRunStage: 'failed',
          requirementAnalysisError: error instanceof Error ? error.message : String(error),
        }))
      } finally {
        requirementAnalysisStopRequestedRef.current = false
        setUiState((prev) => ({
          ...prev,
          requirementAnalysisIsRunning: false,
        }))
      }
    },
    async continueRequirementAnalysis() {
      const previousResult = uiState.requirementAnalysisResult
      await this.runRequirementAnalysis(uiState.panel.composer.prompt, {
        previousResult,
        analysisGoal: shouldContinueWithCompositionRevision(previousResult)
          ? 'composition_revision'
          : 'content_review',
      })
    },
    async continueRequirementAnalysisToCompositionReview() {
      await this.runRequirementAnalysis(uiState.panel.composer.prompt, {
        previousResult: uiState.requirementAnalysisResult,
        analysisGoal: 'composition_review',
      })
    },
    async continueRequirementAnalysisWithFeedback(
      continuationOptions: RequirementAnalysisContinuationOptions = {},
    ) {
      const previousResult = uiState.requirementAnalysisResult
      await this.runRequirementAnalysis(uiState.panel.composer.prompt, {
        previousResult,
        analysisGoal: shouldContinueWithCompositionRevision(previousResult)
          ? 'composition_revision'
          : 'content_review',
        ...continuationOptions,
      })
    },
    async retryRequirementAnalysis() {
      await this.runRequirementAnalysis(
        uiState.requirementAnalysisLastPrompt ?? uiState.panel.composer.prompt,
        requirementAnalysisLastRunOptionsRef.current,
      )
    },
    acceptRequirementAnalysisResult() {
      if (!uiState.requirementAnalysisResult) {
        return
      }
      const acceptedResult = {
        ...uiState.requirementAnalysisResult,
        status: 'accepted' as const,
      }
      setUiState((prev) => ({
        ...prev,
        requirementAnalysisResult: acceptedResult,
        testCaseGenerationPlanDraft: buildTestCaseGenerationWorkflowDraft(acceptedResult),
        testCodeGenerationPlanDraft: '',
        workflowArtifactsStatus: 'idle',
        workflowArtifactsDirectoryPath: null,
        workflowArtifactsWrittenFiles: [],
        workflowArtifactsError: null,
        latestNotification: {
          level: 'info',
          title: 'RequirementAnalysis',
          message: '已接受当前需求分析结果，可以继续生成测试用例草案。',
        },
        finalSummary: '需求分析结果已接受，下一阶段可直接生成测试用例草案并校验覆盖完成度。',
      }))
    },
    setTestCaseGenerationPlanDraft(planDraft: string) {
      setUiState((prev) => ({
        ...prev,
        testCaseGenerationPlanDraft: planDraft,
      }))
    },
    resetTestCaseGenerationPlanDraft() {
      if (!uiState.requirementAnalysisResult) {
        return
      }
      setUiState((prev) => ({
        ...prev,
        testCaseGenerationPlanDraft: buildTestCaseGenerationWorkflowDraft(
          uiState.requirementAnalysisResult!,
        ),
      }))
    },
    async generateTestCasesFromRequirementAnalysis(planDraft?: string) {
      if (!uiState.requirementAnalysisResult) {
        setUiState((prev) => ({
          ...prev,
          testCaseGenerationError: '请先完成需求分析，再生成测试用例。',
        }))
        return
      }

      setUiState((prev) => ({
        ...prev,
        testCaseGenerationIsRunning: true,
        testCaseGenerationError: null,
      }))

      try {
        const payload = {
          settings: toTestCaseGenerationSettingsPayload(uiState.requirementAnalysisSettings),
          input: toTestCaseGenerationInputPayload(
            uiState.requirementAnalysisResult,
            planDraft ?? uiState.testCaseGenerationPlanDraft,
            uiState.panel.composer.prompt,
          ),
        }
        const response = await bridgeFetchImpl(
          new URL('/v1/test-case-generation/runs', bridgeBaseUrl).toString(),
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          },
        )
        const bodyText = await response.text()
        const envelope = bodyText ? JSON.parse(bodyText) as {
          success?: boolean
          data?: TestCaseGenerationResultPayload
          error?: { message?: string }
        } : {}

        if (!response.ok || !envelope.success || !envelope.data) {
          throw new Error(
            envelope.error?.message
              || `测试用例生成失败（HTTP ${response.status}）`,
          )
        }

        const completionSummary = envelope.data.completion_check?.summary
        const nextTestCodePlanDraft =
          uiState.requirementAnalysisResult
            ? buildTestCodeGenerationWorkflowDraft(uiState.requirementAnalysisResult, envelope.data)
            : ''
        setUiState((prev) => ({
          ...prev,
          testCaseGenerationResult: envelope.data ?? null,
          testCodeGenerationPlanDraft: nextTestCodePlanDraft,
          testCodeGenerationResult: null,
          testCodeGenerationError: null,
          testCodeExecutionCommandDraft: '',
          testCodeExecutionResult: null,
          testCodeExecutionError: null,
          testCodeRepairResult: null,
          testCodeRepairError: null,
          workflowArtifactsStatus: 'idle',
          workflowArtifactsDirectoryPath: null,
          workflowArtifactsWrittenFiles: [],
          workflowArtifactsError: null,
          latestNotification: {
            level: 'info',
            title: 'TestCaseGeneration',
            message: `已生成 ${envelope.data.test_cases.length} 条测试用例`,
          },
          finalSummary:
            completionSummary
            ?? `测试用例生成完成，共 ${envelope.data.test_cases.length} 条。`,
        }))
      } catch (error) {
        setUiState((prev) => ({
          ...prev,
          testCaseGenerationError: error instanceof Error ? error.message : String(error),
        }))
      } finally {
        setUiState((prev) => ({
          ...prev,
          testCaseGenerationIsRunning: false,
        }))
      }
    },
    setTestCodeGenerationPlanDraft(planDraft: string) {
      setUiState((prev) => ({
        ...prev,
        testCodeGenerationPlanDraft: planDraft,
      }))
    },
    resetTestCodeGenerationPlanDraft() {
      if (!uiState.requirementAnalysisResult || !uiState.testCaseGenerationResult) {
        return
      }
      setUiState((prev) => ({
        ...prev,
        testCodeGenerationPlanDraft: buildTestCodeGenerationWorkflowDraft(
          uiState.requirementAnalysisResult!,
          uiState.testCaseGenerationResult!,
        ),
      }))
    },
    async generateTestCodeFromTestCases(planDraft?: string) {
      if (!uiState.requirementAnalysisResult || !uiState.testCaseGenerationResult) {
        setUiState((prev) => ({
          ...prev,
          testCodeGenerationError: '请先完成测试用例生成，再生成测试代码。',
        }))
        return
      }

      setUiState((prev) => ({
        ...prev,
        testCodeGenerationIsRunning: true,
        testCodeGenerationError: null,
      }))

      try {
        const payload = {
          settings: toTestCodeGenerationSettingsPayload(uiState.requirementAnalysisSettings),
          input: toTestCodeGenerationInputPayload(
            uiState.requirementAnalysisResult,
            uiState.testCaseGenerationResult,
            planDraft ?? uiState.testCodeGenerationPlanDraft,
            uiState.panel.composer.prompt,
          ),
        }
        const response = await bridgeFetchImpl(
          new URL('/v1/test-code-generation/runs', bridgeBaseUrl).toString(),
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          },
        )
        const bodyText = await response.text()
        const envelope = bodyText ? JSON.parse(bodyText) as {
          success?: boolean
          data?: TestCodeGenerationResultPayload
          error?: { message?: string }
        } : {}

        if (!response.ok || !envelope.success || !envelope.data) {
          throw new Error(
            envelope.error?.message
              || `测试代码生成失败（HTTP ${response.status}）`,
          )
        }

        setUiState((prev) => ({
          ...prev,
          testCodeGenerationResult: envelope.data ?? null,
          testCodeExecutionCommandDraft: '',
          testCodeExecutionResult: null,
          testCodeExecutionError: null,
          testCodeRepairResult: null,
          testCodeRepairError: null,
          workflowArtifactsStatus: 'idle',
          workflowArtifactsDirectoryPath: null,
          workflowArtifactsWrittenFiles: [],
          workflowArtifactsError: null,
          latestNotification: {
            level: 'info',
            title: 'TestCodeGeneration',
            message: `已生成 ${envelope.data.test_files.length} 个测试文件草案`,
          },
          finalSummary: `测试代码生成完成，共 ${envelope.data.test_files.length} 个文件草案。`,
        }))
      } catch (error) {
        setUiState((prev) => ({
          ...prev,
          testCodeGenerationError: error instanceof Error ? error.message : String(error),
        }))
      } finally {
        setUiState((prev) => ({
          ...prev,
          testCodeGenerationIsRunning: false,
        }))
      }
    },
    setSandboxDebugDraft(draft: SandboxExecutionDebugDraft) {
      setUiState((prev) => ({
        ...prev,
        sandboxDebugDraft: draft,
      }))
    },
    loadSandboxDebugFixture() {
      sandboxDebugOperationRef.current += 1
      sandboxDebugSocketRef.current?.close()
      sandboxDebugSocketRef.current = null
      setUiState((prev) => ({
        ...prev,
        sandboxDebugDraft: createSandboxExecutionDebugDraft(),
        sandboxDebugEvents: [],
        sandboxDebugResult: null,
        sandboxDebugError: null,
        sandboxDockerStatus: null,
        sandboxDockerCheckIsRunning: false,
        sandboxDockerChoiceRequired: false,
      }))
    },
    async runSandboxDebug(runtime: 'docker' | 'local_copy' = 'docker') {
      const draft = uiState.sandboxDebugDraft
      const testFilePath = draft.test_file_path.trim()
      const testFileContent = draft.test_file_content
      if (!testFilePath) {
        setUiState((prev) => ({
          ...prev,
          sandboxDebugError: '请填写联调测试文件路径。',
        }))
        return
      }
      if (!testFileContent.trim()) {
        setUiState((prev) => ({
          ...prev,
          sandboxDebugError: '请填写联调测试文件内容。',
        }))
        return
      }

      const operationId = sandboxDebugOperationRef.current + 1
      sandboxDebugOperationRef.current = operationId
      const isCurrentOperation = () =>
        sandboxDebugOperationRef.current === operationId

      if (runtime === 'docker') {
        setUiState((prev) => ({
          ...prev,
          sandboxDockerCheckIsRunning: true,
          sandboxDockerChoiceRequired: false,
          sandboxDockerStatus: null,
          sandboxDebugEvents: [],
          sandboxDebugResult: null,
          sandboxDebugError: null,
        }))
        try {
          const response = await bridgeFetchImpl(
            new URL('/v1/sandbox-execution/docker/status', bridgeBaseUrl).toString(),
            { method: 'GET' },
          )
          const bodyText = await response.text()
          const envelope = bodyText ? JSON.parse(bodyText) as {
            success?: boolean
            data?: DockerRuntimeStatusPayload
            error?: { message?: string }
          } : {}
          if (!response.ok || !envelope.success || !envelope.data) {
            throw new Error(
              envelope.error?.message
                || `Docker 状态检测失败（HTTP ${response.status}）`,
            )
          }
          if (!isCurrentOperation()) {
            return
          }
          setUiState((prev) => ({
            ...prev,
            sandboxDockerStatus: envelope.data ?? null,
          }))
          if (!envelope.data.available) {
            setUiState((prev) => ({
              ...prev,
              sandboxDockerChoiceRequired: true,
              sandboxDebugError: null,
            }))
            return
          }
        } catch (error) {
          if (isCurrentOperation()) {
            setUiState((prev) => ({
              ...prev,
              sandboxDebugError: error instanceof Error ? error.message : String(error),
            }))
          }
          return
        } finally {
          if (isCurrentOperation()) {
            setUiState((prev) => ({
              ...prev,
              sandboxDockerCheckIsRunning: false,
            }))
          }
        }
      }

      if (!isCurrentOperation()) {
        return
      }
      setUiState((prev) => ({
        ...prev,
        sandboxDebugIsRunning: true,
        sandboxDockerChoiceRequired: false,
        sandboxDebugEvents: [],
        sandboxDebugResult: null,
        sandboxDebugError: null,
      }))

      try {
        const contextSource = createVoidRealContextSourceFromAccessor({
          accessor: accessorRef.current as never,
        })
        const repoRoot = await contextSource.getRepoRootPath()
        if (!repoRoot) {
          throw new Error('当前未检测到仓库根目录，无法创建独立沙箱联调工作区。')
        }

        const commandDraft = draft.command.trim()
        const command = commandDraft
          ? {
            argv: splitCommandDraft(commandDraft),
            cwd: '.',
            environment: {},
          }
          : null
        const payload = toSandboxExecutionInputPayload(
          uiState.requirementAnalysisResult?.task_id ?? 'sandbox_debug',
          repoRoot,
          [{
            path: testFilePath,
            language: 'python',
            framework: 'pytest',
            purpose: '沙箱运行测试',
            related_test_case_ids: ['sandbox_debug_smoke'],
            content: testFileContent,
          }],
          command,
          120,
          runtime,
        )
        if (!isCurrentOperation()) {
          return
        }
        const webSocketFactory =
          hostOptions.webSocketFactory
          ?? defaultNativeWebSocketFactory
          ?? ((url: string) => new WebSocket(url))

        await new Promise<void>((resolve, reject) => {
          let settled = false
          const socket = webSocketFactory(
            toWebSocketUrl(bridgeBaseUrl, '/v1/sandbox-execution/ws'),
          )
          sandboxDebugSocketRef.current = socket

          const finishWithError = (error: Error) => {
            if (settled) {
              return
            }
            settled = true
            if (sandboxDebugSocketRef.current === socket) {
              sandboxDebugSocketRef.current = null
            }
            try {
              socket.close()
            } catch {
              // ignore close errors
            }
            if (isCurrentOperation()) {
              reject(error)
            } else {
              resolve()
            }
          }

          socket.onopen = () => {
            socket.send(JSON.stringify(payload))
          }

          socket.onmessage = (message) => {
            if (!isCurrentOperation()) {
              try {
                socket.close()
              } catch {
                // ignore close errors
              }
              return
            }
            let event: SandboxExecutionStreamEvent
            try {
              event = JSON.parse(String(message.data)) as SandboxExecutionStreamEvent
            } catch (error) {
              finishWithError(
                new Error(`沙箱运行测试事件格式无效：${error instanceof Error ? error.message : String(error)}`),
              )
              return
            }

            setUiState((prev) => {
              const nextState: AiIdeBridgeUiState = {
                ...prev,
                sandboxDebugEvents: [...prev.sandboxDebugEvents, event].slice(-80),
              }
              if (event.type === 'result' && event.data) {
                nextState.sandboxDebugResult = event.data
                if (
                  runtime === 'docker'
                  && (
                    event.data.failure?.kind === 'docker_runtime_unavailable'
                    || event.data.failure?.kind === 'docker_execution_failed'
                  )
                ) {
                  nextState.sandboxDockerChoiceRequired = true
                  nextState.sandboxDockerStatus = {
                    available: false,
                    command: nextState.sandboxDockerStatus?.command ?? 'docker',
                    server_version: null,
                    detail: event.data.failure.summary,
                  }
                }
                nextState.latestNotification = {
                  level: event.data.status === 'passed' ? 'info' : 'warning',
                  title: 'SandboxExecution',
                  message: event.data.status === 'passed'
                    ? '沙箱运行测试通过。'
                    : `沙箱运行测试结束：${event.data.status}。`,
                }
                nextState.finalSummary = event.data.failure?.summary
                  ?? `沙箱运行测试结束，状态：${event.data.status}。`
              }
              if (event.type === 'error') {
                nextState.sandboxDebugError = event.message
              }
              return nextState
            })

            if (event.type === 'result' && event.data) {
              settled = true
              if (sandboxDebugSocketRef.current === socket) {
                sandboxDebugSocketRef.current = null
              }
              resolve()
              socket.close()
            } else if (event.type === 'error') {
              finishWithError(new Error(event.message || '沙箱运行测试失败。'))
            }
          }

          socket.onerror = () => {
            finishWithError(new Error('沙箱运行测试 WebSocket 连接失败。'))
          }

          socket.onclose = () => {
            if (!settled) {
              finishWithError(new Error('沙箱运行测试连接在收到最终结果前关闭。'))
            }
          }
        })
      } catch (error) {
        if (isCurrentOperation()) {
          setUiState((prev) => ({
            ...prev,
            sandboxDebugError: error instanceof Error ? error.message : String(error),
          }))
        }
      } finally {
        if (isCurrentOperation()) {
          setUiState((prev) => ({
            ...prev,
            sandboxDebugIsRunning: false,
            sandboxDockerCheckIsRunning: false,
          }))
        }
      }
    },
    cancelSandboxDebug() {
      sandboxDebugOperationRef.current += 1
      sandboxDebugSocketRef.current?.close()
      sandboxDebugSocketRef.current = null
      setUiState((prev) => ({
        ...prev,
        sandboxDebugIsRunning: false,
        sandboxDockerCheckIsRunning: false,
        sandboxDockerChoiceRequired: false,
        sandboxDebugError: null,
        sandboxDebugEvents: [],
        sandboxDebugResult: null,
        sandboxDockerStatus: null,
        latestNotification: {
          level: 'warning',
          title: 'SandboxExecution',
          message: '已取消本次沙箱测试。',
        },
      }))
    },
    setTestCodeExecutionCommandDraft(commandDraft: string) {
      setUiState((prev) => ({
        ...prev,
        testCodeExecutionCommandDraft: commandDraft,
      }))
    },
    async runGeneratedTestCode(commandDraft?: string) {
      const requirementResult = uiState.requirementAnalysisResult
      const testCaseResult = uiState.testCaseGenerationResult
      const currentTestFiles =
        uiState.testCodeRepairResult?.test_files
        ?? uiState.testCodeGenerationResult?.test_files
        ?? null

      if (!requirementResult || !testCaseResult || !currentTestFiles?.length) {
        setUiState((prev) => ({
          ...prev,
          testCodeExecutionError: '请先生成测试代码草案，再在隔离环境中运行测试。',
        }))
        return
      }

      setUiState((prev) => ({
        ...prev,
        testCodeExecutionIsRunning: true,
        testCodeExecutionError: null,
      }))

      try {
        const contextSource = createVoidRealContextSourceFromAccessor({
          accessor: accessorRef.current as never,
        })
        const repoRoot = await contextSource.getRepoRootPath()
        if (!repoRoot) {
          throw new Error('当前未检测到仓库根目录，无法创建隔离工作区并执行测试。')
        }

        const payload = {
          input: toTestCodeExecutionInputPayload(
            requirementResult.task_id,
            repoRoot,
            currentTestFiles,
            commandDraft ?? uiState.testCodeExecutionCommandDraft,
          ),
        }
        const response = await bridgeFetchImpl(
          new URL('/v1/test-code-execution/runs', bridgeBaseUrl).toString(),
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          },
        )
        const bodyText = await response.text()
        const envelope = bodyText ? JSON.parse(bodyText) as {
          success?: boolean
          data?: TestCodeExecutionResultPayload
          error?: { message?: string }
        } : {}

        if (!response.ok || !envelope.success || !envelope.data) {
          throw new Error(
            envelope.error?.message
              || `测试代码执行失败（HTTP ${response.status}）`,
          )
        }

        setUiState((prev) => ({
          ...prev,
          testCodeExecutionResult: envelope.data ?? null,
          latestNotification: {
            level: envelope.data.passed ? 'info' : 'warning',
            title: 'TestCodeExecution',
            message: envelope.data.passed
              ? `隔离测试执行通过，覆盖 ${envelope.data.artifacts.written_files.length} 个测试文件`
              : envelope.data.evaluation.decision === 'repair'
                ? `测试断言失败，可进入 repair，失败用例 ${envelope.data.failed_tests.length} 条`
                : `测试未能执行完成：${envelope.data.evaluation.failure_summary ?? envelope.data.evaluation.stop_reason ?? '运行环境不可用'}`,
          },
          finalSummary: envelope.data.passed
            ? `隔离测试执行通过，命令：${envelope.data.command}`
            : envelope.data.evaluation.decision === 'repair'
              ? `隔离测试执行完成，命令退出码 ${envelope.data.exit_code}，建议进入 repair。`
              : `隔离测试未能执行完成：${envelope.data.evaluation.failure_summary ?? envelope.data.evaluation.stop_reason ?? '运行环境不可用'}。`,
        }))
      } catch (error) {
        setUiState((prev) => ({
          ...prev,
          testCodeExecutionError: error instanceof Error ? error.message : String(error),
        }))
      } finally {
        setUiState((prev) => ({
          ...prev,
          testCodeExecutionIsRunning: false,
        }))
      }
    },
    async repairGeneratedTestCode() {
      const requirementResult = uiState.requirementAnalysisResult
      const testCaseResult = uiState.testCaseGenerationResult
      const executionResult = uiState.testCodeExecutionResult
      const currentTestFiles =
        uiState.testCodeRepairResult?.test_files
        ?? uiState.testCodeGenerationResult?.test_files
        ?? null

      if (!requirementResult || !testCaseResult || !executionResult || !currentTestFiles?.length) {
        setUiState((prev) => ({
          ...prev,
          testCodeRepairError: '请先完成测试代码执行，再根据失败结果进行 repair。',
        }))
        return
      }

      setUiState((prev) => ({
        ...prev,
        testCodeRepairIsRunning: true,
        testCodeRepairError: null,
      }))

      try {
        const payload = {
          settings: toTestCodeRepairSettingsPayload(uiState.requirementAnalysisSettings),
          input: toTestCodeRepairInputPayload(
            requirementResult,
            testCaseResult,
            currentTestFiles,
            executionResult,
            uiState.panel.composer.prompt,
            uiState.testCodeGenerationPlanDraft,
          ),
        }
        const response = await bridgeFetchImpl(
          new URL('/v1/test-code-repair/runs', bridgeBaseUrl).toString(),
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          },
        )
        const bodyText = await response.text()
        const envelope = bodyText ? JSON.parse(bodyText) as {
          success?: boolean
          data?: TestCodeRepairResultPayload
          error?: { message?: string }
        } : {}

        if (!response.ok || !envelope.success || !envelope.data) {
          throw new Error(
            envelope.error?.message
              || `测试代码 repair 失败（HTTP ${response.status}）`,
          )
        }

        setUiState((prev) => ({
          ...prev,
          testCodeRepairResult: envelope.data ?? null,
          workflowArtifactsStatus: 'idle',
          workflowArtifactsDirectoryPath: null,
          workflowArtifactsWrittenFiles: [],
          workflowArtifactsError: null,
          latestNotification: {
            level: 'info',
            title: 'TestCodeRepair',
            message: `已生成 ${envelope.data.changed_files.length} 个测试文件修复结果`,
          },
          finalSummary: `测试代码 repair 完成，可再次执行测试验证修复结果。`,
        }))
      } catch (error) {
        setUiState((prev) => ({
          ...prev,
          testCodeRepairError: error instanceof Error ? error.message : String(error),
        }))
      } finally {
        setUiState((prev) => ({
          ...prev,
          testCodeRepairIsRunning: false,
        }))
      }
    },
    stopRequirementAnalysis() {
      requirementAnalysisStopRequestedRef.current = true
      requirementAnalysisSocketRef.current?.close()
      requirementAnalysisSocketRef.current = null
      setUiState((prev) => ({
        ...prev,
        requirementAnalysisIsRunning: false,
        requirementAnalysisRunStage: 'cancelled',
        latestNotification: {
          level: 'warning',
          title: 'RequirementAnalysis',
          message: '已手动停止需求分析任务。',
        },
      }))
    },
    async approve(reason?: string) {
      await entryRef.current?.approve(reason)
    },
    async reject(reason?: string) {
      await entryRef.current?.reject(reason)
    },
    async cancel() {
      await entryRef.current?.cancel()
    },
    reset() {
      entryRef.current?.reset()
    },
    saveRequirementAnalysisSettings(settings: RequirementAnalysisAgentSettings) {
      const normalized = normalizeRequirementAnalysisSettings(settings)
      persistRequirementAnalysisSettings(normalized, storageService)
      setUiState((prev) => ({
        ...prev,
        requirementAnalysisSettings: normalized,
        requirementAnalysisSettingsSummary: summarizeRequirementAnalysisSettings(normalized),
        requirementAnalysisSettingsPayload: toRequirementAnalysisAgentSettingsPayload(normalized),
      }))
    },
    resetRequirementAnalysisSettings() {
      const defaults = createDefaultRequirementAnalysisSettings()
      persistRequirementAnalysisSettings(defaults, storageService)
      setUiState((prev) => ({
        ...prev,
        requirementAnalysisSettings: defaults,
        requirementAnalysisSettingsSummary: summarizeRequirementAnalysisSettings(defaults),
        requirementAnalysisSettingsPayload: toRequirementAnalysisAgentSettingsPayload(defaults),
      }))
    },
  }), [bridgeBaseUrl, bridgeFetchImpl, uiState])
}
