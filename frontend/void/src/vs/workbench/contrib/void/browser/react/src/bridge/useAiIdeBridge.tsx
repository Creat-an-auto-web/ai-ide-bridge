import React, { useEffect, useMemo, useRef, useState } from 'react'
import { CancellationToken } from '../../../../../../../base/common/cancellation.js'
import { asText } from '../../../../../../../platform/request/common/request.js'
import { StorageScope, StorageTarget } from '../../../../../../../platform/storage/common/storage.js'
import {
  BridgeSidebarPanelState,
  PatchReviewModel,
  RequirementAnalysisAgentSettings,
  RequirementAnalysisAgentSettingsPayload,
  RequirementAnalysisAgentSettingsSummary,
  WorkspaceEditModel,
  attachVoidRealIdeSidebarFromAccessor,
  createDefaultRequirementAnalysisSettings,
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

  const [uiState, setUiState] = useState<AiIdeBridgeUiState>({
    panel: emptyBridgeSidebarState(),
    requirementAnalysisSettings: createDefaultRequirementAnalysisSettings(),
    requirementAnalysisSettingsSummary: summarizeRequirementAnalysisSettings(
      createDefaultRequirementAnalysisSettings(),
    ),
    requirementAnalysisSettingsPayload: toRequirementAnalysisAgentSettingsPayload(
      createDefaultRequirementAnalysisSettings(),
    ),
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
