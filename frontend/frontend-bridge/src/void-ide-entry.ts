import { BridgeSidebarPanelState } from './examples/sidebar-controller.js'
import { PatchReviewModel } from './patch-review.js'
import { TaskMode, TaskPolicy } from './protocol.js'
import { CreateVoidBridgeRuntimeOptions } from './void-runtime.js'
import {
  VoidHostBridge,
  VoidHostNotification,
  createVoidHostBridgeFromServices,
} from './void-host-bridge.js'
import { WorkspaceEditModel } from './workspace-edit.js'

export interface VoidIdeSidebarView {
  renderPanel(state: BridgeSidebarPanelState): void
  showNotification?(notification: VoidHostNotification): void
  focusApprovalCard?(): void
  showPatchReview?(review: PatchReviewModel): void
  showWorkspaceEdit?(editModel: WorkspaceEditModel): void
  showFinalSummary?(summary: string): void
  showError?(message: string): void
}

export interface VoidIdeBridgeEntry {
  getState(): BridgeSidebarPanelState
  setPrompt(prompt: string): void
  setMode(mode: TaskMode): void
  run(prompt?: string, opts?: { sessionId?: string; policy?: Partial<TaskPolicy> }): Promise<void>
  approve(reason?: string): Promise<void>
  reject(reason?: string): Promise<void>
  cancel(): Promise<void>
  reset(): void
  dispose(): void
}

class MountedVoidIdeBridgeEntry implements VoidIdeBridgeEntry {
  constructor(
    private readonly bridge: VoidHostBridge,
  ) {}

  getState(): BridgeSidebarPanelState {
    return this.bridge.getState()
  }

  setPrompt(prompt: string): void {
    this.bridge.setPrompt(prompt)
  }

  setMode(mode: TaskMode): void {
    this.bridge.setMode(mode)
  }

  async run(
    prompt?: string,
    opts?: { sessionId?: string; policy?: Partial<TaskPolicy> },
  ): Promise<void> {
    if (typeof prompt === 'string') {
      this.bridge.setPrompt(prompt)
    }
    await this.bridge.runCurrentPrompt(opts)
  }

  async approve(reason?: string): Promise<void> {
    await this.bridge.approvePendingCommand(reason)
  }

  async reject(reason?: string): Promise<void> {
    await this.bridge.rejectPendingCommand(reason)
  }

  async cancel(): Promise<void> {
    await this.bridge.cancelTask()
  }

  reset(): void {
    this.bridge.reset()
  }

  dispose(): void {
    this.bridge.dispose()
  }
}

export const attachVoidIdeSidebar = (
  options: CreateVoidBridgeRuntimeOptions & {
    view: VoidIdeSidebarView
  },
): VoidIdeBridgeEntry => {
  const bridge = createVoidHostBridgeFromServices({
    ...options,
    callbacks: {
      onPanelStateChange(state) {
        options.view.renderPanel(state)
      },
      onNotification(notification) {
        options.view.showNotification?.(notification)
      },
      onApprovalStateChange(approval) {
        if (approval.visible) {
          options.view.focusApprovalCard?.()
        }
      },
      onPatchReviewReady(review) {
        options.view.showPatchReview?.(review)
      },
      onWorkspaceEditReady(editModel) {
        options.view.showWorkspaceEdit?.(editModel)
      },
      onFinalSummary(summary) {
        options.view.showFinalSummary?.(summary)
      },
      onError(message) {
        options.view.showError?.(message)
      },
    },
  })

  return new MountedVoidIdeBridgeEntry(bridge)
}
