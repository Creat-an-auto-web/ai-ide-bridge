import {
  BridgeSidebarController,
  BridgeSidebarPanelState,
  emptyBridgeSidebarState,
} from './examples/sidebar-controller.js'
import { createPatchReviewModel, PatchReviewModel } from './patch-review.js'
import { TaskPolicy } from './protocol.js'
import { createWorkspaceEditModel, WorkspaceEditModel } from './workspace-edit.js'
import {
  CreateVoidBridgeRuntimeOptions,
  createVoidBridgeSidebarControllerFromServices,
} from './void-runtime.js'

export interface VoidHostNotification {
  level: 'info' | 'warning' | 'error'
  title: string
  message: string
}

export interface VoidHostBridgeCallbacks {
  onPanelStateChange?: (state: BridgeSidebarPanelState) => void
  onNotification?: (notification: VoidHostNotification) => void
  onApprovalStateChange?: (state: BridgeSidebarPanelState['approval']) => void
  onPatchReady?: (patch: NonNullable<BridgeSidebarPanelState['patch']>) => void
  onPatchReviewReady?: (review: PatchReviewModel) => void
  onWorkspaceEditReady?: (editModel: WorkspaceEditModel) => void
  onFinalSummary?: (summary: NonNullable<BridgeSidebarPanelState['finalSummary']>) => void
  onError?: (message: string) => void
}

const changed = (left: unknown, right: unknown): boolean => left !== right

export class VoidHostBridge {
  private readonly controller: BridgeSidebarController
  private readonly callbacks: VoidHostBridgeCallbacks
  private readonly unsubscribe: () => void
  private lastState = emptyBridgeSidebarState()

  constructor(controller: BridgeSidebarController, callbacks: VoidHostBridgeCallbacks = {}) {
    this.controller = controller
    this.callbacks = callbacks

    this.unsubscribe = this.controller.subscribe((state) => {
      this.handleStateChange(state)
    })
  }

  getState(): BridgeSidebarPanelState {
    return this.controller.getState()
  }

  dispose(): void {
    this.unsubscribe()
  }

  setPrompt(prompt: string): void {
    this.controller.setPrompt(prompt)
  }

  setMode(mode: BridgeSidebarPanelState['composer']['mode']): void {
    this.controller.setMode(mode)
  }

  async runCurrentPrompt(opts?: {
    sessionId?: string
    policy?: Partial<TaskPolicy>
  }): Promise<void> {
    await this.controller.runCurrentPrompt(opts)
  }

  async approvePendingCommand(reason?: string): Promise<void> {
    await this.controller.approvePendingCommand(reason)
  }

  async rejectPendingCommand(reason?: string): Promise<void> {
    await this.controller.rejectPendingCommand(reason)
  }

  async cancelTask(): Promise<void> {
    await this.controller.cancelTask()
  }

  reset(): void {
    this.controller.reset()
  }

  private handleStateChange(nextState: BridgeSidebarPanelState): void {
    const prevState = this.lastState
    this.lastState = nextState

    this.callbacks.onPanelStateChange?.(nextState)

    if (changed(prevState.approval.commandId, nextState.approval.commandId)) {
      this.callbacks.onApprovalStateChange?.(nextState.approval)

      if (nextState.approval.visible && nextState.approval.command) {
        this.callbacks.onNotification?.({
          level: 'info',
          title: '等待命令审批',
          message: nextState.approval.command,
        })
      }
    }

    if (changed(prevState.patch?.patchId, nextState.patch?.patchId) && nextState.patch) {
      this.callbacks.onPatchReady?.(nextState.patch)
      this.callbacks.onPatchReviewReady?.(createPatchReviewModel(nextState.patch))
      this.callbacks.onWorkspaceEditReady?.(createWorkspaceEditModel(nextState.patch))
      this.callbacks.onNotification?.({
        level: 'info',
        title: '补丁已就绪',
        message: nextState.patch.summary,
      })
    }

    if (changed(prevState.finalSummary, nextState.finalSummary) && nextState.finalSummary) {
      this.callbacks.onFinalSummary?.(nextState.finalSummary)
      this.callbacks.onNotification?.({
        level: 'info',
        title: '任务已结束',
        message: nextState.finalSummary,
      })
    }

    if (changed(prevState.errorMessage, nextState.errorMessage) && nextState.errorMessage) {
      this.callbacks.onError?.(nextState.errorMessage)
      this.callbacks.onNotification?.({
        level: 'error',
        title: 'Bridge 错误',
        message: nextState.errorMessage,
      })
    }
  }
}

export const createVoidHostBridgeFromServices = (
  options: CreateVoidBridgeRuntimeOptions & {
    callbacks?: VoidHostBridgeCallbacks
  },
): VoidHostBridge => {
  const controller = createVoidBridgeSidebarControllerFromServices(options)
  return new VoidHostBridge(controller, options.callbacks)
}
