import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  BridgeSidebarPanelState,
  PatchReviewModel,
  WorkspaceEditModel,
  attachVoidRealIdeSidebarFromAccessor,
  emptyBridgeSidebarState,
} from '../../../../../../../../../../frontend-bridge/src/index.js'
import { useAccessor } from '../util/services.js'

export interface AiIdeBridgeUiState {
  panel: BridgeSidebarPanelState
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

export const useAiIdeBridge = (options: UseAiIdeBridgeOptions = {}) => {
  const accessor = useAccessor()
  const entryRef = useRef<ReturnType<typeof attachVoidRealIdeSidebarFromAccessor> | null>(null)

  const [uiState, setUiState] = useState<AiIdeBridgeUiState>({
    panel: emptyBridgeSidebarState(),
    latestNotification: null,
    latestPatchReview: null,
    latestWorkspaceEdit: null,
    finalSummary: null,
    errorMessage: null,
  })

  useEffect(() => {
    const entry = attachVoidRealIdeSidebarFromAccessor({
      accessor,
      bridgeClientOptions: {
        baseUrl: options.baseUrl,
      },
      branchProvider: options.branchProvider,
      gitDiffProvider: options.gitDiffProvider,
      testLogsProvider: options.testLogsProvider,
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
  }, [accessor, options.baseUrl, options.branchProvider, options.gitDiffProvider, options.testLogsProvider])

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
  }), [uiState])
}
