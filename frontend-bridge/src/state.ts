import {
  BridgeEvent,
  EventEnvelope,
  TaskCommandRequestPayload,
  TaskCommandResultPayload,
  TaskErrorPayload,
  TaskFinalPayload,
  TaskLogPayload,
  TaskPatchPayload,
  TaskPlanPayload,
  TaskRecord,
  TaskStatusPayload,
  TaskTestResultPayload,
} from './protocol.js'

export interface BridgeState {
  task: TaskRecord | null
  connectionState: 'idle' | 'connecting' | 'open' | 'closed' | 'error'
  events: BridgeEvent[]
  logs: Array<EventEnvelope<TaskLogPayload>>
  plan: TaskPlanPayload | null
  pendingCommand: TaskCommandRequestPayload | null
  patch: TaskPatchPayload | null
  testResult: TaskTestResultPayload | null
  finalResult: TaskFinalPayload | null
  error: TaskErrorPayload | null
  highestSeq: number
  protocolError: string | null
}

export const emptyBridgeState = (): BridgeState => ({
  task: null,
  connectionState: 'idle',
  events: [],
  logs: [],
  plan: null,
  pendingCommand: null,
  patch: null,
  testResult: null,
  finalResult: null,
  error: null,
  highestSeq: 0,
  protocolError: null,
})

export const applyBridgeEvent = (
  prev: BridgeState,
  event: BridgeEvent,
): BridgeState => {
  if (event.seq <= prev.highestSeq) return prev

  const next: BridgeState = {
    ...prev,
    events: [...prev.events, event],
    highestSeq: event.seq,
    protocolError: null,
  }

  switch (event.type) {
    case 'task.status': {
      const payload = event.payload as TaskStatusPayload
      next.task = next.task
        ? { ...next.task, status: payload.status, latestMessage: payload.message, updatedAt: event.timestamp }
        : next.task
      return next
    }
    case 'task.plan':
      next.plan = event.payload as TaskPlanPayload
      return next
    case 'task.log':
      next.logs = [...prev.logs, event as EventEnvelope<TaskLogPayload>]
      return next
    case 'task.command.request':
      next.pendingCommand = event.payload as TaskCommandRequestPayload
      return next
    case 'task.command.result': {
      const payload = event.payload as TaskCommandResultPayload
      if (prev.pendingCommand?.commandId === payload.commandId) {
        next.pendingCommand = null
      }
      return next
    }
    case 'task.patch':
      next.patch = event.payload as TaskPatchPayload
      return next
    case 'task.test.result':
      next.testResult = event.payload as TaskTestResultPayload
      return next
    case 'task.error':
      next.error = event.payload as TaskErrorPayload
      return next
    case 'task.final':
      next.finalResult = event.payload as TaskFinalPayload
      next.connectionState = 'closed'
      return next
  }
}
