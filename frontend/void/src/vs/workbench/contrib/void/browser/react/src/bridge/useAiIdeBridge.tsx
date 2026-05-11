import React, { useEffect, useMemo, useRef, useState } from 'react'
import { CancellationToken } from '../../../../../../../base/common/cancellation.js'
import { asText } from '../../../../../../../platform/request/common/request.js'
import { StorageScope, StorageTarget } from '../../../../../../../platform/storage/common/storage.js'
import {
  BridgeSidebarPanelState,
  GlobalFeedbackPayload,
  PatchReviewModel,
  RequirementAnalysisAgentSettings,
  RequirementAnalysisResultPayload,
  RequirementAnalysisAgentSettingsPayload,
  RequirementAnalysisAgentSettingsSummary,
  StoryFeedbackPayload,
  RequirementAnalysisStreamEvent,
  WorkspaceEditModel,
  attachVoidRealIdeSidebarFromAccessor,
  collectVoidContext,
  createDefaultRequirementAnalysisSettings,
  createVoidRealContextSourceFromAccessor,
  emptyBridgeSidebarState,
  normalizeRequirementAnalysisSettings,
  summarizeRequirementAnalysisSettings,
  toRequirementAnalysisAgentSettingsPayload,
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

const toContinuationRevisionFocus = (
  previousResult: RequirementAnalysisResultPayload | null | undefined,
  globalFeedback?: GlobalFeedbackPayload | null,
  storyFeedback?: StoryFeedbackPayload | null,
): string[] => {
  const focus: string[] = []
  const compositionGuidance = previousResult?.composition_verification?.revision_guidance ?? []
  if (compositionGuidance.length > 0) {
    focus.push(...compositionGuidance)
  }
  if (globalFeedback?.feedback_text?.trim()) {
    focus.push(globalFeedback.feedback_text.trim())
  }
  if (storyFeedback?.feedback_text?.trim() && storyFeedback.story_id?.trim()) {
    focus.push(`针对 ${storyFeedback.story_id.trim()}：${storyFeedback.feedback_text.trim()}`)
  }
  if (focus.length > 0) {
    return focus
  }
  if (!previousResult) {
    return []
  }
  if (previousResult.verification?.revision_guidance?.length) {
    return previousResult.verification.revision_guidance
  }
  if (previousResult.verification?.issues?.length) {
    return previousResult.verification.issues.map((issue) => issue.message)
  }
  return ['在保持当前质量的前提下继续提升需求拆解的一致性、边界清晰度和 user story 粒度。']
}

const toRequirementAnalysisInputPayload = async (
  accessor: unknown,
  prompt: string,
  options: RequirementAnalysisContinuationOptions = {},
) => {
  const previousResult = options.previousResult ?? null
  const appendedPrompt = options.appendedPrompt?.trim() ?? ''
  const contextSource = createVoidRealContextSourceFromAccessor({
    accessor: accessor as never,
  })
  const [repoRootPath, context] = await Promise.all([
    contextSource.getRepoRootPath(),
    collectVoidContext(contextSource),
  ])

  return {
    task_id: typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `ra_${Math.random().toString(16).slice(2, 10)}`,
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
    revision_focus: toContinuationRevisionFocus(
      previousResult,
      options.globalFeedback,
      options.storyFeedback,
    ),
    previous_verification_summary:
      trimTextHead(
        previousResult?.composition_verification?.summary
          ?? previousResult?.verification?.summary
          ?? '',
        REQUIREMENT_ANALYSIS_MAX_PREVIOUS_SUMMARY_CHARS,
      ) || null,
    iteration: previousResult ? Math.max(1, previousResult.iteration_count + 1) : 1,
    execution_constraints: {
      disallow_new_dependencies: true,
      preserve_public_api: true,
      max_capability_groups: 6,
      max_story_units: 24,
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
  const entryRef = useRef<ReturnType<typeof attachVoidRealIdeSidebarFromAccessor> | null>(null)
  const requirementAnalysisSocketRef = useRef<WebSocket | null>(null)

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
        baseUrl: options.baseUrl ?? hostOptions.baseUrl ?? defaultNativeBaseUrl(),
        fetchImpl:
          hostOptions.fetchImpl
          ?? createNativeRequestFetch(nativeRequestService)
          ?? createDesktopFetch(),
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
      entry.dispose()
      entryRef.current = null
    }
  }, [
    hostOptions.baseUrl,
    hostOptions.branchProvider,
    hostOptions.gitDiffProvider,
    hostOptions.testLogsProvider,
    options.baseUrl,
    options.branchProvider,
    options.gitDiffProvider,
    options.testLogsProvider,
    nativeRequestService,
  ])

  return useMemo(() => ({
    uiState,
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
      }))

      try {
        const inputPayload = await toRequirementAnalysisInputPayload(
          accessorRef.current,
          nextPrompt,
          continuationOptions,
        )
        const requirementAnalysisBaseUrl =
          options.baseUrl
          ?? hostOptions.baseUrl
          ?? defaultNativeBaseUrl()
          ?? 'http://127.0.0.1:27182'
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
            toWebSocketUrl(requirementAnalysisBaseUrl, '/v1/requirement-analysis/ws'),
          )
          requirementAnalysisSocketRef.current = socket

          const finishWithError = (error: Error) => {
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
            finishWithError(new Error('需求分析流式连接失败'))
          }

          socket.onclose = () => {
            if (requirementAnalysisSocketRef.current === socket) {
              requirementAnalysisSocketRef.current = null
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
        setUiState((prev) => ({
          ...prev,
          requirementAnalysisIsRunning: false,
        }))
      }
    },
    async continueRequirementAnalysis() {
      await this.runRequirementAnalysis(uiState.panel.composer.prompt, {
        previousResult: uiState.requirementAnalysisResult,
      })
    },
    async continueRequirementAnalysisWithFeedback(
      continuationOptions: RequirementAnalysisContinuationOptions = {},
    ) {
      await this.runRequirementAnalysis(uiState.panel.composer.prompt, {
        previousResult: uiState.requirementAnalysisResult,
        ...continuationOptions,
      })
    },
    async retryRequirementAnalysis() {
      await this.runRequirementAnalysis(
        uiState.requirementAnalysisLastPrompt ?? uiState.panel.composer.prompt,
        {
          previousResult: uiState.requirementAnalysisResult,
        },
      )
    },
    acceptRequirementAnalysisResult() {
      if (!uiState.requirementAnalysisResult) {
        return
      }
      setUiState((prev) => ({
        ...prev,
        requirementAnalysisResult: {
          ...prev.requirementAnalysisResult!,
          status: 'accepted',
        },
        latestNotification: {
          level: 'info',
          title: 'RequirementAnalysis',
          message: '已接受当前需求分析结果。',
        },
      }))
    },
    stopRequirementAnalysis() {
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
  }), [uiState])
}
