import React, { useMemo, useState } from 'react'
import { useAiIdeBridge } from './useAiIdeBridge.js'

const statusTextOfConnection = (value: string) => {
  switch (value) {
    case 'open':
      return '已连接'
    case 'connecting':
      return '连接中'
    case 'closed':
      return '已关闭'
    case 'error':
      return '连接错误'
    default:
      return '空闲'
  }
}

export const AiIdeBridgePanel = () => {
  const bridge = useAiIdeBridge()
  const [prompt, setPrompt] = useState('')
  const { panel, latestNotification, finalSummary, errorMessage, latestPatchReview } = bridge.uiState

  const approvalVisible = panel.approval.visible && panel.approval.commandId

  const summaryLine = useMemo(() => {
    const taskId = panel.summary.taskId ?? '未创建'
    const status = panel.summary.status
    const connection = statusTextOfConnection(panel.summary.connectionState)
    return `${taskId} / ${status} / ${connection}`
  }, [panel.summary])

  return (
    <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ fontSize: 12, opacity: 0.8 }}>AI IDE Bridge</div>
        <textarea
          value={prompt}
          onChange={(event) => {
            const value = event.target.value
            setPrompt(value)
            bridge.setPrompt(value)
          }}
          placeholder='输入你的任务，例如：修复当前失败的测试'
          style={{ minHeight: 88, resize: 'vertical' }}
        />
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => { void bridge.run() }} disabled={!panel.composer.canRun}>
            运行
          </button>
          <button onClick={() => { void bridge.cancel() }}>
            取消
          </button>
          <button onClick={() => bridge.reset()}>
            重置
          </button>
        </div>
      </div>

      <div style={{ fontSize: 12, opacity: 0.85 }}>
        {summaryLine}
      </div>

      {panel.summary.latestMessage && (
        <div style={{ fontSize: 12 }}>
          {panel.summary.latestMessage}
        </div>
      )}

      {approvalVisible && (
        <div style={{ border: '1px solid var(--vscode-panel-border)', padding: 8 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>等待命令审批</div>
          <div style={{ fontSize: 12, marginBottom: 6 }}>{panel.approval.command}</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => { void bridge.approve('从 AI IDE Bridge 面板批准') }}>
              批准
            </button>
            <button onClick={() => { void bridge.reject('从 AI IDE Bridge 面板拒绝') }}>
              拒绝
            </button>
          </div>
        </div>
      )}

      {panel.planSteps.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>计划</div>
          <ol style={{ margin: 0, paddingLeft: 18 }}>
            {panel.planSteps.map((step, index) => (
              <li key={`${index}_${step}`}>{step}</li>
            ))}
          </ol>
        </div>
      )}

      {latestPatchReview && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>补丁预览</div>
          <div style={{ fontSize: 12, marginBottom: 6 }}>{latestPatchReview.summary}</div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {latestPatchReview.files.map((file) => (
              <li key={file.path}>{file.title}</li>
            ))}
          </ul>
        </div>
      )}

      {panel.logs.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>日志</div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
            {panel.logs.join('')}
          </pre>
        </div>
      )}

      {latestNotification && (
        <div style={{ fontSize: 12, opacity: 0.85 }}>
          {latestNotification.title}: {latestNotification.message}
        </div>
      )}

      {finalSummary && (
        <div style={{ fontSize: 12 }}>
          最终结果：{finalSummary}
        </div>
      )}

      {errorMessage && (
        <div style={{ color: 'var(--vscode-errorForeground)', fontSize: 12 }}>
          {errorMessage}
        </div>
      )}
    </div>
  )
}
