import React, { useMemo, useState } from 'react'
import {
  RequirementAnalysisAgentSettings,
  createDefaultRequirementAnalysisSettings,
} from '../../../../../../../../ai-ide-bridge/frontend-bridge/src/index.js'
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
  const [draftPrompt, setDraftPrompt] = useState('')
  const [draftRequirementSettings, setDraftRequirementSettings] = useState<RequirementAnalysisAgentSettings>(
    createDefaultRequirementAnalysisSettings(),
  )
  const [isComposing, setIsComposing] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const {
    panel,
    latestNotification,
    finalSummary,
    errorMessage,
    latestPatchReview,
    requirementAnalysisSettings,
    requirementAnalysisSettingsSummary,
    requirementAnalysisSettingsPayload,
  } = bridge.uiState

  const promptValue = isEditing || isComposing ? draftPrompt : panel.composer.prompt

  React.useEffect(() => {
    if (!isEditing && !isComposing) {
      setDraftPrompt(panel.composer.prompt)
    }
  }, [isComposing, isEditing, panel.composer.prompt])

  React.useEffect(() => {
    setDraftRequirementSettings(requirementAnalysisSettings)
  }, [requirementAnalysisSettings])

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

  const inputStyle = {
    width: '100%',
    borderRadius: 8,
    border: '1px solid var(--vscode-panel-border)',
    padding: '8px 10px',
    background: 'var(--vscode-input-background)',
    color: 'var(--vscode-input-foreground)',
  } as const

  const settingsStatus = requirementAnalysisSettingsSummary.isConfigured
    ? '已配置'
    : '未完成'

  const updateRequirementSetting = <K extends keyof RequirementAnalysisAgentSettings>(
    key: K,
    value: RequirementAnalysisAgentSettings[K],
  ) => {
    setDraftRequirementSettings((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12, color: 'var(--vscode-editor-foreground)' }}>
      <details style={sectionStyle}>
        <summary style={{ cursor: 'pointer', fontWeight: 600, color: 'var(--vscode-editor-foreground)' }}>
          第一环模型配置
        </summary>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', opacity: 0.86 }}>
            需求分析智能体状态：{settingsStatus}
          </div>
          <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', opacity: 0.78 }}>
            这部分配置目前仅保存在本机 IDE，用于第一环 RequirementAnalysis 智能体，尚未接入当前 bridge 后端请求。
          </div>
          <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', opacity: 0.78 }}>
            下方 JSON 已对齐第一环 Python 服务工厂所需的 snake_case 配置格式。
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <input
              type='checkbox'
              checked={draftRequirementSettings.enabled}
              onChange={(event) => updateRequirementSetting('enabled', event.target.checked)}
            />
            启用第一环需求分析智能体
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 10 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <span>Provider 名称</span>
              <input
                value={draftRequirementSettings.providerName}
                onChange={(event) => updateRequirementSetting('providerName', event.target.value)}
                placeholder='例如：openai / openrouter / my-gateway'
                style={inputStyle}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <span>模型名称</span>
              <input
                value={draftRequirementSettings.model}
                onChange={(event) => updateRequirementSetting('model', event.target.value)}
                placeholder='例如：gpt-5.4 / qwen/qwen3-32b'
                style={inputStyle}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <span>Base URL</span>
              <input
                value={draftRequirementSettings.apiBase}
                onChange={(event) => updateRequirementSetting('apiBase', event.target.value)}
                placeholder='例如：https://api.openai.com/v1'
                style={inputStyle}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <span>API Key</span>
              <input
                type='password'
                value={draftRequirementSettings.apiKey}
                onChange={(event) => updateRequirementSetting('apiKey', event.target.value)}
                placeholder='输入第一环模型的 API Key'
                style={inputStyle}
              />
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                <span>Temperature</span>
                <input
                  type='number'
                  step='0.1'
                  value={draftRequirementSettings.temperature}
                  onChange={(event) => {
                    const nextValue = Number(event.target.value)
                    if (Number.isFinite(nextValue)) {
                      updateRequirementSetting('temperature', nextValue)
                    }
                  }}
                  style={inputStyle}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                <span>Max Tokens</span>
                <input
                  type='number'
                  min='1'
                  value={draftRequirementSettings.maxTokens}
                  onChange={(event) => {
                    const nextValue = Number(event.target.value)
                    if (Number.isFinite(nextValue)) {
                      updateRequirementSetting('maxTokens', nextValue)
                    }
                  }}
                  style={inputStyle}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                <span>Timeout(s)</span>
                <input
                  type='number'
                  min='1'
                  value={draftRequirementSettings.timeoutSeconds}
                  onChange={(event) => {
                    const nextValue = Number(event.target.value)
                    if (Number.isFinite(nextValue)) {
                      updateRequirementSetting('timeoutSeconds', nextValue)
                    }
                  }}
                  style={inputStyle}
                />
              </label>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={() => bridge.saveRequirementAnalysisSettings(draftRequirementSettings)}
              style={{ ...buttonStyle, background: 'rgba(78, 161, 255, 0.18)' }}
            >
              保存第一环配置
            </button>
            <button
              onClick={() => {
                setDraftRequirementSettings(createDefaultRequirementAnalysisSettings())
                bridge.resetRequirementAnalysisSettings()
              }}
              style={buttonStyle}
            >
              恢复默认
            </button>
            <button
              onClick={async () => {
                const payloadText = JSON.stringify(requirementAnalysisSettingsPayload, null, 2)
                try {
                  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
                    await navigator.clipboard.writeText(payloadText)
                  }
                } catch {
                  // ignore clipboard errors
                }
              }}
              style={buttonStyle}
            >
              复制配置 JSON
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', opacity: 0.86 }}>
              第一环运行配置预览
            </div>
            <pre
              style={{
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontSize: 12,
                lineHeight: 1.5,
                color: 'var(--vscode-input-foreground)',
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid var(--vscode-panel-border)',
                borderRadius: 8,
                padding: '10px 12px',
              }}
            >
              {JSON.stringify(requirementAnalysisSettingsPayload, null, 2)}
            </pre>
          </div>
        </div>
      </details>

      <div style={sectionStyle}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 12, opacity: 0.8, color: 'var(--vscode-input-foreground)' }}>AI IDE Bridge</div>
          <textarea
            value={promptValue}
            onFocus={() => {
              setIsEditing(true)
              setDraftPrompt(panel.composer.prompt)
            }}
            onBlur={(event) => {
              const nextValue = event.currentTarget.value
              setIsEditing(false)
              setDraftPrompt(nextValue)
              bridge.setPrompt(nextValue)
            }}
            onChange={(event) => {
              const nextValue = event.target.value
              setDraftPrompt(nextValue)
              if (!isComposing) {
                bridge.setPrompt(nextValue)
              }
            }}
            onCompositionStart={() => {
              setIsComposing(true)
            }}
            onCompositionEnd={(event) => {
              const nextValue = event.currentTarget.value
              setIsComposing(false)
              setDraftPrompt(nextValue)
              bridge.setPrompt(nextValue)
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
