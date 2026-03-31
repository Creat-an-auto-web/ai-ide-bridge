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

  const buttonStyle = {
    border: '1px solid var(--vscode-panel-border)',
    borderRadius: 10,
    padding: '8px 12px',
    background: 'rgba(255, 255, 255, 0.04)',
    color: 'var(--vscode-editor-foreground)',
  } as const

  const sectionStyle = {
    border: '1px solid var(--vscode-panel-border)',
    borderRadius: 14,
    padding: 12,
    background: 'rgba(255, 255, 255, 0.03)',
  } as const

  return (
    <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12, color: 'var(--vscode-editor-foreground)' }}>
      <div style={sectionStyle}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 12, opacity: 0.8, color: 'var(--vscode-input-foreground)' }}>AI IDE Bridge</div>
          <textarea
            value={prompt}
            onChange={(event) => {
              const value = event.target.value
              setPrompt(value)
              bridge.setPrompt(value)
            }}
            placeholder='输入你的任务，例如：修复当前失败的测试'
            style={{
              minHeight: 104,
              resize: 'vertical',
              width: '100%',
              borderRadius: 10,
              border: '1px solid var(--vscode-panel-border)',
              padding: '10px 12px',
              background: 'var(--vscode-input-background)',
              color: 'var(--vscode-input-foreground)',
            }}
          />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={() => { void bridge.run() }}
              disabled={!panel.composer.canRun}
              style={{
                ...buttonStyle,
                background: panel.composer.canRun ? 'rgba(78, 161, 255, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                opacity: panel.composer.canRun ? 1 : 0.55,
              }}
            >
              运行
            </button>
            <button onClick={() => { void bridge.cancel() }} style={buttonStyle}>
              取消
            </button>
            <button onClick={() => bridge.reset()} style={buttonStyle}>
              重置
            </button>
          </div>
        </div>
      </div>

      <div style={{ ...sectionStyle, fontSize: 12, opacity: 0.92, color: 'var(--vscode-input-foreground)' }}>
        {summaryLine}
      </div>

      {panel.summary.latestMessage && (
        <div style={{ ...sectionStyle, fontSize: 12, color: 'var(--vscode-input-foreground)' }}>
          {panel.summary.latestMessage}
        </div>
      )}

      {approvalVisible && (
        <div style={sectionStyle}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--vscode-editor-foreground)' }}>等待命令审批</div>
          <div style={{ fontSize: 12, marginBottom: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{panel.approval.command}</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => { void bridge.approve('从 AI IDE Bridge 面板批准') }}
              style={{ ...buttonStyle, background: 'rgba(92, 196, 137, 0.18)' }}
            >
              批准
            </button>
            <button
              onClick={() => { void bridge.reject('从 AI IDE Bridge 面板拒绝') }}
              style={{ ...buttonStyle, background: 'rgba(255, 107, 107, 0.14)' }}
            >
              拒绝
            </button>
          </div>
        </div>
      )}

      {panel.planSteps.length > 0 && (
        <div style={sectionStyle}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--vscode-editor-foreground)' }}>计划</div>
          <ol style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
            {panel.planSteps.map((step, index) => (
              <li key={`${index}_${step}`}>{step}</li>
            ))}
          </ol>
        </div>
      )}

      {latestPatchReview && (
        <div style={sectionStyle}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--vscode-editor-foreground)' }}>补丁预览</div>
          <div style={{ fontSize: 12, marginBottom: 6 }}>{latestPatchReview.summary}</div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
            {latestPatchReview.files.map((file) => (
              <li key={file.path}>{file.title}</li>
            ))}
          </ul>
        </div>
      )}

      {panel.logs.length > 0 && (
        <div style={sectionStyle}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--vscode-editor-foreground)' }}>日志</div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.6, color: 'var(--vscode-input-foreground)' }}>
            {panel.logs.join('')}
          </pre>
        </div>
      )}

      {latestNotification && (
        <div style={{ ...sectionStyle, fontSize: 12, opacity: 0.92, color: 'var(--vscode-input-foreground)' }}>
          {latestNotification.title}: {latestNotification.message}
        </div>
      )}

      {finalSummary && (
        <div style={{ ...sectionStyle, fontSize: 12, color: 'var(--vscode-input-foreground)' }}>
          最终结果：{finalSummary}
        </div>
      )}

      {errorMessage && (
        <div style={{ ...sectionStyle, color: 'var(--vscode-errorForeground)', fontSize: 12 }}>
          {errorMessage}
        </div>
      )}
    </div>
  )
}
