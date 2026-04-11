import { BridgeClient } from '../client.js'
import {
  TaskMode,
  TaskPatchPayload,
  TaskPolicy,
  TaskStatus,
} from '../protocol.js'
import { BridgeState } from '../state.js'
import { VoidBridgeContextSource } from '../void-adapter.js'
import {
  VoidBridgeController,
} from './void-source-skeleton.js'

export interface BridgeSidebarComposerState {
  prompt: string
  mode: TaskMode
  canRun: boolean
  isSubmitting: boolean
}

export interface BridgeSidebarApprovalState {
  visible: boolean
  commandId: string | null
  command: string | null
  cwd: string | null
  riskLevel: string | null
  reason: string | null
}

export interface BridgeSidebarSummaryState {
  taskId: string | null
  status: TaskStatus | 'idle'
  latestMessage: string | null
  connectionState: BridgeState['connectionState']
}

export interface BridgeSidebarPanelState {
  composer: BridgeSidebarComposerState
  summary: BridgeSidebarSummaryState
  approval: BridgeSidebarApprovalState
  planSteps: string[]
  logs: string[]
  patch: TaskPatchPayload | null
  testSummary: string | null
  finalSummary: string | null
  errorMessage: string | null
}

export const emptyBridgeSidebarState = (): BridgeSidebarPanelState => ({
  composer: {
    prompt: '',
    mode: 'fix_test',
    canRun: false,
    isSubmitting: false,
  },
  summary: {
    taskId: null,
    status: 'idle',
    latestMessage: null,
    connectionState: 'idle',
  },
  approval: {
    visible: false,
    commandId: null,
    command: null,
    cwd: null,
    riskLevel: null,
    reason: null,
  },
  planSteps: [],
  logs: [],
  patch: null,
  testSummary: null,
  finalSummary: null,
  errorMessage: null,
})

const toTestSummary = (state: BridgeState): string | null => {
  const result = state.testResult
  if (!result) return null
  return `${result.framework}: passed ${result.passed}, failed ${result.failed}, skipped ${result.skipped}`
}

const toSidebarState = (
  bridgeState: BridgeState,
  current: BridgeSidebarPanelState,
): BridgeSidebarPanelState => {
  const pending = bridgeState.pendingCommand

  return {
    ...current,
    summary: {
      taskId: bridgeState.task?.taskId ?? null,
      status: bridgeState.task?.status ?? 'idle',
      latestMessage: bridgeState.task?.latestMessage ?? null,
      connectionState: bridgeState.connectionState,
    },
    approval: {
      visible: !!pending,
      commandId: pending?.commandId ?? null,
      command: pending?.command ?? null,
      cwd: pending?.cwd ?? null,
      riskLevel: pending?.riskLevel ?? null,
      reason: pending?.reason ?? null,
    },
    planSteps: bridgeState.plan?.steps ?? [],
    logs: bridgeState.logs.map(item => item.payload.text),
    patch: bridgeState.patch,
    testSummary: toTestSummary(bridgeState),
    finalSummary: bridgeState.finalResult
      ? `${bridgeState.finalResult.outcome}: ${bridgeState.finalResult.summary}`
      : null,
    errorMessage: bridgeState.error?.message ?? bridgeState.protocolError,
  }
}

export type BridgeSidebarListener = (state: BridgeSidebarPanelState) => void

/**
 * 这是一个面向 UI 的 controller 骨架。
 *
 * 它保持为纯 TypeScript，实现上可以被 React sidebar、本地面板或其他宿主复用，
 * 不需要改动 bridge client。
 */
export class BridgeSidebarController {
  private readonly bridgeClient: BridgeClient
  private readonly bridgeController: VoidBridgeController
  private readonly listeners = new Set<BridgeSidebarListener>()
  private state = emptyBridgeSidebarState()

  constructor(opts: {
    bridgeClient?: BridgeClient
    contextSource: VoidBridgeContextSource
  }) {
    this.bridgeClient = opts.bridgeClient ?? new BridgeClient()
    this.bridgeController = new VoidBridgeController(this.bridgeClient, opts.contextSource)

    this.bridgeClient.subscribe({
      onStateChange: (bridgeState) => {
        this.state = toSidebarState(bridgeState, this.state)
        this.emit()
      },
    })
  }

  subscribe(listener: BridgeSidebarListener): () => void {
    this.listeners.add(listener)
    listener(this.state)
    return () => this.listeners.delete(listener)
  }

  getState(): BridgeSidebarPanelState {
    return this.state
  }

  private emit() {
    for (const listener of this.listeners) {
      listener(this.state)
    }
  }

  setPrompt(prompt: string) {
    this.state = {
      ...this.state,
      composer: {
        ...this.state.composer,
        prompt,
        canRun: prompt.trim().length > 0 && !this.state.composer.isSubmitting,
      },
    }
    this.emit()
  }

  setMode(mode: TaskMode) {
    this.state = {
      ...this.state,
      composer: {
        ...this.state.composer,
        mode,
      },
    }
    this.emit()
  }

  async runCurrentPrompt(opts?: {
    sessionId?: string
    policy?: Partial<TaskPolicy>
  }) {
    const prompt = this.state.composer.prompt.trim()
    if (!prompt || this.state.composer.isSubmitting) return

    this.state = {
      ...this.state,
      composer: {
        ...this.state.composer,
        isSubmitting: true,
        canRun: false,
      },
      errorMessage: null,
    }
    this.emit()

    try {
      await this.bridgeController.runTask({
        mode: this.state.composer.mode,
        userPrompt: prompt,
        sessionId: opts?.sessionId,
        policy: opts?.policy,
      })
    } catch (error) {
      this.state = {
        ...this.state,
        errorMessage: error instanceof Error ? error.message : String(error),
      }
      this.emit()
    } finally {
      this.state = {
        ...this.state,
        composer: {
          ...this.state.composer,
          isSubmitting: false,
          canRun: this.state.composer.prompt.trim().length > 0,
        },
      }
      this.emit()
    }
  }

  async approvePendingCommand(reason?: string) {
    const commandId = this.state.approval.commandId
    if (!commandId) return
    try {
      await this.bridgeController.approveCommand(commandId, reason)
    } catch (error) {
      this.state = {
        ...this.state,
        errorMessage: error instanceof Error ? error.message : String(error),
      }
      this.emit()
    }
  }

  async rejectPendingCommand(reason?: string) {
    const commandId = this.state.approval.commandId
    if (!commandId) return
    try {
      await this.bridgeController.rejectCommand(commandId, reason)
    } catch (error) {
      this.state = {
        ...this.state,
        errorMessage: error instanceof Error ? error.message : String(error),
      }
      this.emit()
    }
  }

  async cancelTask() {
    try {
      await this.bridgeController.cancelTask()
    } catch (error) {
      this.state = {
        ...this.state,
        errorMessage: error instanceof Error ? error.message : String(error),
      }
      this.emit()
    }
  }

  reset() {
    this.bridgeClient.reset()
    this.state = emptyBridgeSidebarState()
    this.emit()
  }
}
