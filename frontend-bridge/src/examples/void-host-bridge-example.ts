import { TaskMode } from '../protocol.js'
import {
  CreateVoidBridgeRuntimeOptions,
} from '../void-runtime.js'
import {
  VoidHostBridge,
  VoidHostBridgeCallbacks,
  createVoidHostBridgeFromServices,
} from '../void-host-bridge.js'

export interface VoidSidebarView {
  render(state: unknown): void
  showNotification(notification: {
    severity: 'info' | 'warning' | 'error'
    title: string
    message: string
  }): void
  focusApprovalCard(): void
  showPatchPreview(summary: string): void
  showWorkspaceEdit(summary: string): void
  setFinalSummary(summary: string): void
  setError(message: string): void
}

const createCallbacks = (view: VoidSidebarView): VoidHostBridgeCallbacks => ({
  onPanelStateChange(state) {
    view.render(state)
  },
  onNotification(notification) {
    view.showNotification({
      severity: notification.level,
      title: notification.title,
      message: notification.message,
    })
  },
  onApprovalStateChange(approval) {
    if (approval.visible) {
      view.focusApprovalCard()
    }
  },
  onPatchReady(patch) {
    view.showPatchPreview(patch.summary)
  },
  onWorkspaceEditReady(editModel) {
    view.showWorkspaceEdit(editModel.summary)
  },
  onFinalSummary(summary) {
    view.setFinalSummary(summary)
  },
  onError(message) {
    view.setError(message)
  },
})

export const attachVoidSidebarBridge = (
  options: CreateVoidBridgeRuntimeOptions & {
    view: VoidSidebarView
  },
): VoidHostBridge =>
  createVoidHostBridgeFromServices({
    ...options,
    callbacks: createCallbacks(options.view),
  })

export const runVoidSidebarPrompt = async (
  bridge: VoidHostBridge,
  prompt: string,
  mode: TaskMode = 'fix_test',
): Promise<void> => {
  bridge.setMode(mode)
  bridge.setPrompt(prompt)
  await bridge.runCurrentPrompt()
}
