import {
  BridgeEvent,
  CommandApprovalRequest,
  CreateTaskRequest,
  ResponseEnvelope,
  TaskRecord,
} from './protocol.js'
import { applyBridgeEvent, BridgeState, emptyBridgeState } from './state.js'

export interface BridgeClientOptions {
  baseUrl?: string
  webSocketFactory?: (url: string) => WebSocket
  fetchImpl?: typeof fetch
}

export interface BridgeClientListener {
  onStateChange?: (state: BridgeState) => void
  onEvent?: (event: BridgeEvent) => void
}

export class BridgeClient {
  private readonly baseUrl: string
  private readonly fetchImpl: typeof fetch
  private readonly webSocketFactory: (url: string) => WebSocket

  private socket: WebSocket | null = null
  private state: BridgeState = emptyBridgeState()
  private listeners = new Set<BridgeClientListener>()

  constructor(options: BridgeClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? 'http://127.0.0.1:27182'
    this.fetchImpl = options.fetchImpl ?? fetch
    this.webSocketFactory = options.webSocketFactory ?? ((url) => new WebSocket(url))
  }

  getState(): BridgeState {
    return this.state
  }

  subscribe(listener: BridgeClientListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private emitState() {
    for (const listener of this.listeners) {
      listener.onStateChange?.(this.state)
    }
  }

  private emitEvent(event: BridgeEvent) {
    for (const listener of this.listeners) {
      listener.onEvent?.(event)
    }
  }

  private setState(next: BridgeState) {
    this.state = next
    this.emitState()
  }

  private wsBaseUrl() {
    const url = new URL(this.baseUrl)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    return url.toString().replace(/\/$/, '')
  }

  private async postJson<T>(path: string, body: unknown): Promise<ResponseEnvelope<T>> {
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return await response.json() as ResponseEnvelope<T>
  }

  private connectTaskEvents(taskId: string) {
    this.socket?.close()
    this.setState({ ...this.state, connectionState: 'connecting' })

    const socket = this.webSocketFactory(`${this.wsBaseUrl()}/v1/tasks/${taskId}/events`)
    this.socket = socket

    socket.onopen = () => {
      this.setState({ ...this.state, connectionState: 'open' })
    }

    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(String(message.data)) as BridgeEvent
        this.setState(applyBridgeEvent(this.state, event))
        this.emitEvent(event)
      } catch (error) {
        this.setState({
          ...this.state,
          connectionState: 'error',
          protocolError: error instanceof Error ? error.message : String(error),
        })
      }
    }

    socket.onerror = () => {
      this.setState({ ...this.state, connectionState: 'error' })
    }

    socket.onclose = () => {
      this.setState({ ...this.state, connectionState: 'closed' })
      if (this.socket === socket) {
        this.socket = null
      }
    }
  }

  async createTask(request: CreateTaskRequest): Promise<ResponseEnvelope<{ task: TaskRecord }>> {
    this.setState(emptyBridgeState())
    const response = await this.postJson<{ task: TaskRecord }>('/v1/tasks', request)
    if (!response.success || !response.data?.task) {
      this.setState({
        ...this.state,
        connectionState: 'error',
        protocolError: response.error?.message ?? 'Failed to create task',
      })
      return response
    }

    this.setState({
      ...this.state,
      task: response.data.task,
      connectionState: 'connecting',
    })
    this.connectTaskEvents(response.data.task.taskId)
    return response
  }

  async getTask(taskId: string): Promise<ResponseEnvelope<{ task: TaskRecord }>> {
    const response = await this.fetchImpl(`${this.baseUrl}/v1/tasks/${taskId}`)
    return await response.json() as ResponseEnvelope<{ task: TaskRecord }>
  }

  async cancelCurrentTask(): Promise<void> {
    const taskId = this.state.task?.taskId
    if (!taskId) return
    await this.postJson(`/v1/tasks/${taskId}/cancel`, {})
  }

  async approveCommand(commandId: string, body: CommandApprovalRequest): Promise<void> {
    const taskId = this.state.task?.taskId
    if (!taskId) return
    await this.postJson(`/v1/tasks/${taskId}/commands/${commandId}/approval`, body)
  }

  reset(): void {
    this.socket?.close()
    this.socket = null
    this.setState(emptyBridgeState())
  }
}
