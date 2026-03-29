const state = {
  task: null,
  socket: null,
  highestSeq: 0,
  autoApprove: true,
}

const els = {
  mode: document.getElementById('mode'),
  repoRootPath: document.getElementById('repoRootPath'),
  userPrompt: document.getElementById('userPrompt'),
  activeFile: document.getElementById('activeFile'),
  openFiles: document.getElementById('openFiles'),
  terminalTail: document.getElementById('terminalTail'),
  testLogs: document.getElementById('testLogs'),
  createTaskBtn: document.getElementById('createTaskBtn'),
  cancelTaskBtn: document.getElementById('cancelTaskBtn'),
  autoApprove: document.getElementById('autoApprove'),
  connectionBadge: document.getElementById('connectionBadge'),
  taskId: document.getElementById('taskId'),
  taskStatus: document.getElementById('taskStatus'),
  latestMessage: document.getElementById('latestMessage'),
  approvalCard: document.getElementById('approvalCard'),
  planList: document.getElementById('planList'),
  testResult: document.getElementById('testResult'),
  patchContainer: document.getElementById('patchContainer'),
  logOutput: document.getElementById('logOutput'),
  eventOutput: document.getElementById('eventOutput'),
}

const pretty = (value) => JSON.stringify(value, null, 2)

const appendText = (element, text) => {
  element.textContent += text
  element.scrollTop = element.scrollHeight
}

const escapeHtml = (value) =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')

const resetUi = () => {
  state.highestSeq = 0
  els.taskId.textContent = '-'
  els.taskStatus.textContent = 'idle'
  els.latestMessage.textContent = '-'
  els.latestMessage.className = ''
  els.connectionBadge.textContent = 'idle'
  els.approvalCard.className = 'approval-card empty'
  els.approvalCard.textContent = 'No pending command request'
  els.planList.innerHTML = ''
  els.planList.className = 'list empty'
  els.testResult.textContent = 'No test result yet'
  els.testResult.className = 'empty'
  els.patchContainer.textContent = 'No patch yet'
  els.patchContainer.className = 'empty'
  els.logOutput.textContent = ''
  els.eventOutput.textContent = ''
}

const setConnectionState = (value) => {
  els.connectionBadge.textContent = value
}

const renderSummary = () => {
  els.taskId.textContent = state.task?.taskId ?? '-'
  els.taskStatus.textContent = state.task?.status ?? 'idle'
  els.latestMessage.textContent = state.task?.latestMessage ?? '-'
}

const renderApprovalCard = (payload) => {
  if (!payload) {
    els.approvalCard.className = 'approval-card empty'
    els.approvalCard.textContent = 'No pending command request'
    return
  }

  els.approvalCard.className = 'approval-card pending'
  els.approvalCard.innerHTML = `
    <div><strong>${payload.command}</strong></div>
    <div class="muted">${payload.cwd}</div>
    <div class="muted">${payload.riskLevel} · ${payload.reason}</div>
    <div class="approval-actions">
      <button id="approveBtn" class="primary">Approve</button>
      <button id="rejectBtn">Reject</button>
    </div>
  `

  document.getElementById('approveBtn')?.addEventListener('click', () => {
    void approveCommand(payload.commandId, true)
  })
  document.getElementById('rejectBtn')?.addEventListener('click', () => {
    void approveCommand(payload.commandId, false)
  })
}

const renderPlan = (steps) => {
  if (!steps?.length) {
    els.planList.innerHTML = ''
    els.planList.className = 'list empty'
    return
  }

  els.planList.className = 'list'
  els.planList.innerHTML = steps.map(step => `<li>${step}</li>`).join('')
}

const renderPatch = (payload) => {
  if (!payload) {
    els.patchContainer.textContent = 'No patch yet'
    els.patchContainer.className = 'empty'
    return
  }

  els.patchContainer.className = ''
  els.patchContainer.innerHTML = `
    <div class="muted" style="margin-bottom: 12px">${payload.summary}</div>
    ${payload.files.map(file => `
      <div class="patch-file">
        <h4>${file.path}</h4>
        <pre>${escapeHtml(file.unifiedDiff)}</pre>
      </div>
    `).join('')}
  `
}

const renderTestResult = (payload) => {
  if (!payload) {
    els.testResult.textContent = 'No test result yet'
    els.testResult.className = 'empty'
    return
  }
  els.testResult.className = ''
  els.testResult.textContent =
    `${payload.framework}: passed ${payload.passed}, failed ${payload.failed}, skipped ${payload.skipped}`
}

const postJson = async (path, body) => {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return await response.json()
}

const buildRequest = () => ({
  requestId: `req_${Math.random().toString(16).slice(2, 10)}`,
  protocolVersion: 'v1alpha1',
  mode: els.mode.value,
  userPrompt: els.userPrompt.value.trim(),
  repo: {
    rootPath: els.repoRootPath.value.trim(),
  },
  context: {
    activeFile: els.activeFile.value.trim() || undefined,
    selection: null,
    openFiles: els.openFiles.value.split(',').map(v => v.trim()).filter(Boolean),
    diagnostics: [],
    gitDiff: '',
    terminalTail: els.terminalTail.value,
    testLogs: els.testLogs.value,
  },
  policy: {
    workspaceMode: 'local',
    network: 'deny',
    requireApprovalFor: ['package_install', 'destructive_command', 'git_push'],
    maxDurationSec: 600,
    maxOutputBytes: 262144,
    writablePaths: [],
    envAllowlist: [],
  },
})

const approveCommand = async (commandId, approved) => {
  if (!state.task?.taskId) return
  const response = await postJson(`/v1/tasks/${state.task.taskId}/commands/${commandId}/approval`, {
    approved,
    reason: approved ? 'Approved from frontend-bridge demo' : 'Rejected from frontend-bridge demo',
  })
  appendText(els.eventOutput, `${pretty(response)}\n\n`)
}

const applyEvent = async (event) => {
  if (event.seq <= state.highestSeq) return
  state.highestSeq = event.seq
  appendText(els.eventOutput, `${pretty(event)}\n\n`)

  switch (event.type) {
    case 'task.status':
      state.task = state.task
        ? { ...state.task, status: event.payload.status, latestMessage: event.payload.message, updatedAt: event.timestamp }
        : state.task
      renderSummary()
      break
    case 'task.plan':
      renderPlan(event.payload.steps)
      break
    case 'task.log':
      appendText(els.logOutput, event.payload.text)
      break
    case 'task.command.request':
      renderApprovalCard(event.payload)
      if (state.autoApprove) {
        await approveCommand(event.payload.commandId, true)
      }
      break
    case 'task.command.result':
      renderApprovalCard(null)
      appendText(els.logOutput, `\n[command result] exit=${event.payload.exitCode}\n${event.payload.stdout}${event.payload.stderr}\n`)
      break
    case 'task.patch':
      renderPatch(event.payload)
      break
    case 'task.test.result':
      renderTestResult(event.payload)
      break
    case 'task.error':
      els.latestMessage.textContent = event.payload.message
      els.latestMessage.className = 'error'
      break
    case 'task.final':
      setConnectionState('completed')
      els.latestMessage.textContent = event.payload.summary
      break
  }
}

const connectEvents = (taskId) => {
  state.socket?.close()
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${location.host}/v1/tasks/${taskId}/events`)
  state.socket = ws

  setConnectionState('connecting')

  ws.onopen = () => setConnectionState('open')
  ws.onerror = () => setConnectionState('error')
  ws.onclose = () => {
    if (els.connectionBadge.textContent !== 'completed') {
      setConnectionState('closed')
    }
  }
  ws.onmessage = (message) => {
    const event = JSON.parse(String(message.data))
    void applyEvent(event)
  }
}

const createTask = async () => {
  const request = buildRequest()
  if (!request.repo.rootPath || !request.userPrompt) {
    window.alert('Repo Root Path and Prompt are required.')
    return
  }

  resetUi()

  const response = await postJson('/v1/tasks', request)
  appendText(els.eventOutput, `${pretty(response)}\n\n`)

  if (!response.success || !response.data?.task) {
    setConnectionState('error')
    els.latestMessage.textContent = response.error?.message ?? 'Failed to create task'
    els.latestMessage.className = 'error'
    return
  }

  state.task = response.data.task
  renderSummary()
  connectEvents(state.task.taskId)
}

const cancelTask = async () => {
  if (!state.task?.taskId) return
  await postJson(`/v1/tasks/${state.task.taskId}/cancel`, {})
}

els.autoApprove.addEventListener('change', () => {
  state.autoApprove = !!els.autoApprove.checked
})
els.createTaskBtn.addEventListener('click', () => { void createTask() })
els.cancelTaskBtn.addEventListener('click', () => { void cancelTask() })

els.repoRootPath.value = '/home/ricebean/ai-agent'
els.userPrompt.value = 'Fix the current failing test'
els.activeFile.value = 'readme.md'

resetUi()
