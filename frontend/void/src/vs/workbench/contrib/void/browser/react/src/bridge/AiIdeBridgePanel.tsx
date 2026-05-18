import React, { useMemo, useState } from 'react'
import {
  RequirementAnalysisAgentSettings,
  createDefaultRequirementAnalysisSettings,
  toRequirementAnalysisAgentSettingsDisplayPayload,
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

const statusTextOfRequirementPackage = (value: string) => {
  switch (value) {
    case 'paused_converged':
      return '已收敛，等待用户决定'
    case 'paused_content_verified':
      return '内容验证通过，等待用户审核'
    case 'paused_format_invalid':
      return '格式校验失败，等待重试或人工介入'
    case 'paused_stalled':
      return '已暂停，需继续优化或人工介入'
    case 'paused_blocked':
      return '已阻塞，需人工介入'
    case 'accepted':
      return '已接受，准备进入下一环'
    case 'cancelled':
      return '已取消'
    case 'blocked':
      return '阻塞'
    case 'verified':
      return '已验证'
    case 'draft':
      return '草稿'
    default:
      return value
  }
}

export const AiIdeBridgePanel = () => {
  const bridge = useAiIdeBridge()
  const [draftPrompt, setDraftPrompt] = useState('')
  const [feedbackText, setFeedbackText] = useState('')
  const [selectedStoryId, setSelectedStoryId] = useState('')
  const [draftRequirementSettings, setDraftRequirementSettings] = useState<RequirementAnalysisAgentSettings>(
    createDefaultRequirementAnalysisSettings(),
  )
  const [draftRequirementApiKey, setDraftRequirementApiKey] = useState('')
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
    requirementAnalysisResult,
    requirementAnalysisError,
    requirementAnalysisIsRunning,
    requirementAnalysisRunStage,
    requirementAnalysisLastPrompt,
    requirementAnalysisAutoRetryCount,
    requirementAnalysisPreviewText,
    requirementAnalysisEvents,
    testCaseGenerationPlanDraft,
    testCaseGenerationResult,
    testCaseGenerationError,
    testCaseGenerationIsRunning,
  } = bridge.uiState

  const promptValue = isEditing || isComposing ? draftPrompt : panel.composer.prompt

  React.useEffect(() => {
    if (!isEditing && !isComposing) {
      setDraftPrompt(panel.composer.prompt)
    }
  }, [isComposing, isEditing, panel.composer.prompt])

  React.useEffect(() => {
    setDraftRequirementSettings({
      ...requirementAnalysisSettings,
      apiKey: '',
    })
    setDraftRequirementApiKey('')
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
  const displayRequirementAnalysisSettingsPayload = useMemo(
    () => toRequirementAnalysisAgentSettingsDisplayPayload(requirementAnalysisSettings),
    [requirementAnalysisSettings],
  )
  const requirementCapabilityGroups = requirementAnalysisResult?.capability_groups ?? []
  const compositionVerification = requirementAnalysisResult?.composition_verification ?? null
  const requirementVerification = requirementAnalysisResult?.verification ?? {
    status: 'unknown',
    summary: '暂无验证结果',
    issues: [],
    revision_guidance: [],
    quality_score: {
      scope_clarity: 0,
      testability: 0,
      dependency_sanity: 0,
      story_granularity: 0,
    },
  }
  const requirementVerificationIssues = requirementVerification.issues ?? []
  const requirementHistory = requirementAnalysisResult?.history ?? []
  const verificationGateSummary = requirementAnalysisResult?.verification_gate_summary ?? null
  const userReviewGuidance = requirementAnalysisResult?.user_review_guidance ?? null
  const requirementPackageStatus = requirementAnalysisResult?.status ?? 'draft'
  const isRequirementResultAccepted = requirementPackageStatus === 'accepted'
  const hasPassedCompositionVerification = requirementAnalysisResult?.composition_verification?.status === 'pass'
  const hasFailedCompositionVerification = (
    requirementAnalysisResult?.composition_verification?.status === 'revise'
    || requirementAnalysisResult?.composition_verification?.status === 'blocked'
  )
  const canAcceptRequirementResult = (
    !isRequirementResultAccepted
    && !requirementAnalysisIsRunning
    &&
    requirementPackageStatus === 'paused_converged'
  )
  const canContinueRequirementResult = (
    !isRequirementResultAccepted
    && (
      requirementPackageStatus === 'paused_converged'
      || requirementPackageStatus === 'paused_content_verified'
      || requirementPackageStatus === 'paused_format_invalid'
      || requirementPackageStatus === 'paused_stalled'
      || requirementPackageStatus === 'paused_blocked'
    )
  )
  const canStartCompositionVerification = (
    !requirementAnalysisIsRunning
    && !isRequirementResultAccepted
    && !hasFailedCompositionVerification
    && (
      requirementPackageStatus === 'paused_content_verified'
      || requirementPackageStatus === 'paused_stalled'
    )
  )
  const canReturnToContentReview = (
    !requirementAnalysisIsRunning
    && !isRequirementResultAccepted
    && Boolean(requirementAnalysisResult)
    && hasFailedCompositionVerification
  )
  const canContinuePassedComposition = (
    !requirementAnalysisIsRunning
    && !isRequirementResultAccepted
    && Boolean(requirementAnalysisResult)
    && hasPassedCompositionVerification
  )
  const canRetryRequirementAnalysis = (
    !requirementAnalysisIsRunning
    && !isRequirementResultAccepted
    && Boolean(requirementAnalysisLastPrompt?.trim())
  )
  const canSubmitRequirementFeedback = (
    !requirementAnalysisIsRunning
    && !isRequirementResultAccepted
    && Boolean(requirementAnalysisResult)
    && Boolean(feedbackText.trim())
  )
  const canGenerateTestCases = (
    Boolean(requirementAnalysisResult)
    && !testCaseGenerationIsRunning
    && (
      isRequirementResultAccepted
      || hasPassedCompositionVerification
    )
  )
  const lastRequirementAnalysisEvent =
    requirementAnalysisEvents.length > 0
      ? requirementAnalysisEvents[requirementAnalysisEvents.length - 1]
      : null

  const updateRequirementSetting = <K extends keyof RequirementAnalysisAgentSettings>(
    key: K,
    value: RequirementAnalysisAgentSettings[K],
  ) => {
    setDraftRequirementSettings((prev) => ({ ...prev, [key]: value }))
  }

  const toNullablePositiveInteger = (rawValue: string) => {
    const trimmed = rawValue.trim()
    if (trimmed === '') {
      return null
    }
    const parsed = Number(trimmed)
    if (!Number.isFinite(parsed)) {
      return null
    }
    return Math.max(1, Math.round(parsed))
  }

  const resetFeedbackDraft = () => {
    setFeedbackText('')
    setSelectedStoryId('')
  }

  return (
    <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12, color: 'var(--vscode-editor-foreground)' }}>
      <details style={sectionStyle}>
        <summary style={{ cursor: 'pointer', fontWeight: 600, color: 'var(--vscode-editor-foreground)' }}>
          需求分析模型配置
        </summary>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', opacity: 0.86 }}>
            需求分析智能体状态：{settingsStatus}
          </div>
          <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', opacity: 0.78 }}>
            这部分配置会保存在本机 IDE，并用于调用独立的需求分析 RequirementAnalysis 原型服务。
          </div>
          <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', opacity: 0.78 }}>
            下方 JSON 已对齐需求分析 Python 服务工厂所需的 snake_case 配置格式。
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <input
              type='checkbox'
              checked={draftRequirementSettings.enabled}
              onChange={(event) => updateRequirementSetting('enabled', event.target.checked)}
            />
            启用需求分析智能体
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
                value={draftRequirementApiKey}
                onChange={(event) => setDraftRequirementApiKey(event.target.value)}
                placeholder={
                  requirementAnalysisSettingsSummary.hasApiKey
                    ? '已保存，留空则保持不变'
                    : '输入需求分析模型的 API Key'
                }
                style={inputStyle}
              />
              <span style={{ opacity: 0.72 }}>
                {requirementAnalysisSettingsSummary.hasApiKey
                  ? '当前已保存 API Key，界面不会回填明文。'
                  : '当前尚未保存 API Key。'}
              </span>
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
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
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                <span>Max Run(s)</span>
                <input
                  type='number'
                  min='1'
                  value={draftRequirementSettings.maxRequestSeconds}
                  onChange={(event) => {
                    const nextValue = Number(event.target.value)
                    if (Number.isFinite(nextValue)) {
                      updateRequirementSetting('maxRequestSeconds', nextValue)
                    }
                  }}
                  style={inputStyle}
                />
              </label>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 12, opacity: 0.82 }}>
                Story / Group 上限策略：留空表示该轮次“不设上限”。
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                  <span>首轮最多组数</span>
                  <input
                    type='number'
                    min='1'
                    value={draftRequirementSettings.firstRoundMaxCapabilityGroups ?? ''}
                    onChange={(event) => {
                      updateRequirementSetting(
                        'firstRoundMaxCapabilityGroups',
                        toNullablePositiveInteger(event.target.value),
                      )
                    }}
                    style={inputStyle}
                    placeholder='4'
                  />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                  <span>首轮最多 Story</span>
                  <input
                    type='number'
                    min='1'
                    value={draftRequirementSettings.firstRoundMaxStoryUnits ?? ''}
                    onChange={(event) => {
                      updateRequirementSetting(
                        'firstRoundMaxStoryUnits',
                        toNullablePositiveInteger(event.target.value),
                      )
                    }}
                    style={inputStyle}
                    placeholder='12'
                  />
                </label>
                <div />
                <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                  <span>第二轮最多组数</span>
                  <input
                    type='number'
                    min='1'
                    value={draftRequirementSettings.secondRoundMaxCapabilityGroups ?? ''}
                    onChange={(event) => {
                      updateRequirementSetting(
                        'secondRoundMaxCapabilityGroups',
                        toNullablePositiveInteger(event.target.value),
                      )
                    }}
                    style={inputStyle}
                    placeholder='6'
                  />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                  <span>第二轮最多 Story</span>
                  <input
                    type='number'
                    min='1'
                    value={draftRequirementSettings.secondRoundMaxStoryUnits ?? ''}
                    onChange={(event) => {
                      updateRequirementSetting(
                        'secondRoundMaxStoryUnits',
                        toNullablePositiveInteger(event.target.value),
                      )
                    }}
                    style={inputStyle}
                    placeholder='24'
                  />
                </label>
                <div />
                <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                  <span>第三轮起最多组数</span>
                  <input
                    type='number'
                    min='1'
                    value={draftRequirementSettings.laterRoundMaxCapabilityGroups ?? ''}
                    onChange={(event) => {
                      updateRequirementSetting(
                        'laterRoundMaxCapabilityGroups',
                        toNullablePositiveInteger(event.target.value),
                      )
                    }}
                    style={inputStyle}
                    placeholder='留空=不限'
                  />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                  <span>第三轮起最多 Story</span>
                  <input
                    type='number'
                    min='1'
                    value={draftRequirementSettings.laterRoundMaxStoryUnits ?? ''}
                    onChange={(event) => {
                      updateRequirementSetting(
                        'laterRoundMaxStoryUnits',
                        toNullablePositiveInteger(event.target.value),
                      )
                    }}
                    style={inputStyle}
                    placeholder='留空=不限'
                  />
                </label>
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={() => bridge.saveRequirementAnalysisSettings({
                ...draftRequirementSettings,
                apiKey:
                  draftRequirementApiKey.trim().length > 0
                    ? draftRequirementApiKey
                    : requirementAnalysisSettings.apiKey,
              })}
              style={{ ...buttonStyle, background: 'rgba(78, 161, 255, 0.18)' }}
            >
              保存需求分析配置
            </button>
            <button
              onClick={() => {
                setDraftRequirementSettings(createDefaultRequirementAnalysisSettings())
                setDraftRequirementApiKey('')
                bridge.resetRequirementAnalysisSettings()
              }}
              style={buttonStyle}
            >
              恢复默认
            </button>
            <button
              onClick={async () => {
                const payloadText = JSON.stringify(displayRequirementAnalysisSettingsPayload, null, 2)
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
            <button
              onClick={() => { void bridge.runRequirementAnalysis(promptValue) }}
              disabled={requirementAnalysisIsRunning || !requirementAnalysisSettingsSummary.isConfigured}
              style={{
                ...buttonStyle,
                background:
                  requirementAnalysisIsRunning || !requirementAnalysisSettingsSummary.isConfigured
                    ? 'rgba(255, 255, 255, 0.03)'
                    : 'rgba(92, 196, 137, 0.18)',
                opacity:
                  requirementAnalysisIsRunning || !requirementAnalysisSettingsSummary.isConfigured
                    ? 0.55
                    : 1,
              }}
            >
              {requirementAnalysisIsRunning ? '需求分析运行中' : '运行需求分析'}
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', opacity: 0.86 }}>
              需求分析运行配置预览
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
              {JSON.stringify(displayRequirementAnalysisSettingsPayload, null, 2)}
            </pre>
          </div>
        </div>
      </details>

      {(requirementAnalysisIsRunning || requirementAnalysisEvents.length > 0 || requirementAnalysisPreviewText) && (
        <div style={sectionStyle}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--vscode-editor-foreground)' }}>
            需求分析运行状态
          </div>
          <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--vscode-input-foreground)' }}>
            当前阶段：{requirementAnalysisRunStage ?? 'unknown'}
          </div>
          {requirementAnalysisAutoRetryCount > 0 && (
            <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--vscode-input-foreground)' }}>
              连接失败后已自动重试 {requirementAnalysisAutoRetryCount} 次。
            </div>
          )}
          {lastRequirementAnalysisEvent && (
            <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--vscode-input-foreground)' }}>
              最新事件：{lastRequirementAnalysisEvent.message}
              {typeof lastRequirementAnalysisEvent.elapsed_ms === 'number'
                ? ` (${Math.round(lastRequirementAnalysisEvent.elapsed_ms / 1000)}s)`
                : ''}
            </div>
          )}
          {requirementAnalysisPreviewText && (
            <pre
              style={{
                margin: '0 0 10px',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontSize: 12,
                lineHeight: 1.5,
                color: 'var(--vscode-input-foreground)',
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid var(--vscode-panel-border)',
                borderRadius: 8,
                padding: '10px 12px',
                maxHeight: 180,
                overflow: 'auto',
              }}
            >
              {requirementAnalysisPreviewText}
            </pre>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {requirementAnalysisEvents.slice(-6).map((event, index) => (
              <div
                key={`${event.stage}-${index}-${event.elapsed_ms ?? index}`}
                style={{
                  fontSize: 12,
                  color: 'var(--vscode-input-foreground)',
                  opacity: event.type === 'heartbeat' ? 0.72 : 0.92,
                }}
              >
                [{event.stage}] {event.message}
                {typeof event.elapsed_ms === 'number'
                  ? ` · ${Math.round(event.elapsed_ms / 1000)}s`
                  : ''}
              </div>
            ))}
          </div>
          {requirementAnalysisIsRunning && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
              <button onClick={() => bridge.stopRequirementAnalysis()} style={buttonStyle}>
                停止任务
              </button>
            </div>
          )}
        </div>
      )}

      {requirementAnalysisResult && (
        <div style={sectionStyle}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--vscode-editor-foreground)' }}>
            需求分析结果
          </div>
          <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--vscode-input-foreground)' }}>
            包状态：{statusTextOfRequirementPackage(requirementAnalysisResult.status)} · 迭代轮次：{requirementAnalysisResult.iteration_count}
          </div>
          <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--vscode-input-foreground)' }}>
            {requirementAnalysisResult.requirement_spec.problem_statement}
          </div>
          <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--vscode-input-foreground)' }}>
            验证结论：{requirementVerification.status} · {requirementVerification.summary}
          </div>
          {verificationGateSummary && (
            <div style={{ marginBottom: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--vscode-editor-foreground)' }}>
                验证门禁摘要
              </div>
              <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)' }}>
                阻塞问题 {verificationGateSummary.blocking_issue_count} · 非阻塞建议 {verificationGateSummary.nonblocking_suggestion_count} · 显式能力覆盖 {verificationGateSummary.explicit_capability_coverage.covered_count}/{verificationGateSummary.explicit_capability_coverage.required_count}
              </div>
              {verificationGateSummary.explicit_capability_coverage.missing.length > 0 && (
                <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)' }}>
                  缺失能力：{verificationGateSummary.explicit_capability_coverage.missing.join('、')}
                </div>
              )}
              <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)' }}>
                放行/暂停原因：{verificationGateSummary.decision_reason}
              </div>
            </div>
          )}
          {userReviewGuidance && (
            <div style={{ marginBottom: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {userReviewGuidance.summary_points.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, marginBottom: 6, fontWeight: 600, color: 'var(--vscode-editor-foreground)' }}>
                    快速概要
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                    {userReviewGuidance.summary_points.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {userReviewGuidance.suggestions.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, marginBottom: 6, fontWeight: 600, color: 'var(--vscode-editor-foreground)' }}>
                    审核建议
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                    {userReviewGuidance.suggestions.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {userReviewGuidance.clarification_questions.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, marginBottom: 6, fontWeight: 600, color: 'var(--vscode-editor-foreground)' }}>
                    建议你直接回答的问题
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                    {userReviewGuidance.clarification_questions.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          {compositionVerification && (
            <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--vscode-input-foreground)' }}>
              组合验证：{compositionVerification.status} · {compositionVerification.summary}
            </div>
          )}
          <div style={{ fontSize: 12, marginBottom: 6, color: 'var(--vscode-input-foreground)' }}>
            Capability 组数量：{requirementAnalysisResult.analysis_summary.capability_group_count ?? requirementCapabilityGroups.length} · 用户故事数量：{requirementAnalysisResult.analysis_summary.story_unit_count}
          </div>
          {requirementCapabilityGroups.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 12, marginBottom: 6, color: 'var(--vscode-input-foreground)' }}>
                Capability 分组
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                {requirementCapabilityGroups.map((group) => (
                  <li key={group.id}>
                    {group.title} · {(group.story_ids ?? []).length} 个用户故事
                  </li>
                ))}
              </ul>
            </div>
          )}
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
            {requirementAnalysisResult.story_units.map((storyUnit) => (
              <li key={storyUnit.id}>
                <div style={{ fontWeight: 600 }}>{storyUnit.title}</div>
                <div>
                  {storyUnit.narrative || `As a ${storyUnit.as_a}, I want ${storyUnit.i_want}${storyUnit.so_that ? `, so that ${storyUnit.so_that}` : ''}.`}
                </div>
              </li>
            ))}
          </ul>
          {requirementVerificationIssues.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 12, marginBottom: 6, color: 'var(--vscode-input-foreground)' }}>
                验证问题
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                {requirementVerificationIssues.map((issue) => (
                  <li key={issue.id}>
                    [{issue.severity}] {issue.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {compositionVerification && (
            <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)' }}>
                组合覆盖：主目标 {compositionVerification.coverage_assessment.covers_primary_user_goal ? '已覆盖' : '未覆盖'} · 权限 {compositionVerification.coverage_assessment.covers_permission_constraints ? '已覆盖' : '未覆盖'} · 失败处理 {compositionVerification.coverage_assessment.covers_failure_handling ? '已覆盖' : '未覆盖'} · 端到端 {compositionVerification.coverage_assessment.covers_end_to_end_flow ? '已覆盖' : '未覆盖'}
              </div>
              {compositionVerification.missing_story_topics.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, marginBottom: 6, color: 'var(--vscode-input-foreground)' }}>
                    缺失主题
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                    {compositionVerification.missing_story_topics.map((topic) => (
                      <li key={topic}>{topic}</li>
                    ))}
                  </ul>
                </div>
              )}
              {compositionVerification.composition_issues.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, marginBottom: 6, color: 'var(--vscode-input-foreground)' }}>
                    组合问题
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                    {compositionVerification.composition_issues.map((issue) => (
                      <li key={issue.id}>
                        [{issue.severity}] {issue.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          {requirementHistory.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 12, marginBottom: 6, color: 'var(--vscode-input-foreground)' }}>
                迭代历史
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                {requirementHistory.map((item) => (
                  <li key={`iteration_${item.iteration}`}>
                    第 {item.iteration} 轮 · 验证 {item.verification_status} · 问题数 {item.issue_count}
                    {item.composition_verification_status ? ` · 组合 ${item.composition_verification_status} / ${item.composition_issue_count}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {isRequirementResultAccepted && (
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--vscode-input-foreground)', background: 'rgba(92, 196, 137, 0.10)', border: '1px solid rgba(92, 196, 137, 0.28)', borderRadius: 8, padding: '10px 12px', lineHeight: 1.6 }}>
              当前需求分析结果已被接受，需求分析阶段已锁定。你现在可以基于当前 story 集合继续生成测试用例草案，并让后端检查是否完成 workflow draft。
            </div>
          )}
          {!requirementAnalysisIsRunning && !isRequirementResultAccepted && (
            <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--vscode-editor-foreground)' }}>
                继续完善需求分析
              </div>
              <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', opacity: 0.82 }}>
                可以追加全局需求说明，或选择一条 story 给出定向反馈。未选择 story 时会作为全局反馈处理。
              </div>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                <span>选择要反馈的 Story（可选）</span>
                <select
                  value={selectedStoryId}
                  onChange={(event) => setSelectedStoryId(event.target.value)}
                  style={inputStyle}
                >
                  <option value=''>不指定，作为全局反馈</option>
                  {requirementAnalysisResult.story_units.map((storyUnit) => (
                    <option key={storyUnit.id} value={storyUnit.id}>
                      {storyUnit.id} · {storyUnit.title}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                <span>追加说明或反馈意见</span>
                <textarea
                  value={feedbackText}
                  onChange={(event) => setFeedbackText(event.target.value)}
                  placeholder='例如：第一期只允许仓库管理员导出；或者：这条 story 太大了，应拆分权限限制与成功导出路径。'
                  style={{
                    ...inputStyle,
                    minHeight: 88,
                    resize: 'vertical',
                  }}
                />
              </label>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button
                  onClick={() => {
                    if (!requirementAnalysisResult || !feedbackText.trim()) {
                      return
                    }
                    const globalFeedback = selectedStoryId
                      ? null
                      : {
                        feedback_id: `gfb_${Date.now()}`,
                        package_id: requirementAnalysisResult.package_id,
                        task_id: requirementAnalysisResult.task_id,
                        kind: 'global_feedback' as const,
                        author_role: 'user',
                        feedback_type: 'scope_adjustment' as const,
                        feedback_text: feedbackText.trim(),
                        applies_to: {
                          capability_group_ids: [],
                          story_ids: [],
                        },
                        expected_action: 'refine_existing_stories' as const,
                        created_at: new Date().toISOString(),
                      }
                    const storyFeedback = selectedStoryId
                      ? {
                        feedback_id: `sfb_${Date.now()}`,
                        package_id: requirementAnalysisResult.package_id,
                        task_id: requirementAnalysisResult.task_id,
                        kind: 'story_feedback' as const,
                        author_role: 'user',
                        story_id: selectedStoryId,
                        feedback_type: 'wording_issue' as const,
                        feedback_text: feedbackText.trim(),
                        expected_action: 'refine_existing_stories' as const,
                        created_at: new Date().toISOString(),
                      }
                      : null

                    void bridge.continueRequirementAnalysisWithFeedback({
                      appendedPrompt: selectedStoryId ? null : feedbackText.trim(),
                      globalFeedback,
                      storyFeedback,
                    })
                    resetFeedbackDraft()
                  }}
                  disabled={!canSubmitRequirementFeedback}
                  style={{
                    ...buttonStyle,
                    opacity: canSubmitRequirementFeedback ? 1 : 0.55,
                    background: canSubmitRequirementFeedback ? 'rgba(78, 161, 255, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                  }}
                >
                  带反馈继续分析
                </button>
                <button
                  onClick={() => resetFeedbackDraft()}
                  style={buttonStyle}
                >
                  清空反馈
                </button>
              </div>
            </div>
          )}
          {!requirementAnalysisIsRunning && !isRequirementResultAccepted && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
              <button
                onClick={() => bridge.acceptRequirementAnalysisResult()}
                disabled={!canAcceptRequirementResult}
                style={{
                  ...buttonStyle,
                  opacity: canAcceptRequirementResult ? 1 : 0.55,
                  background: canAcceptRequirementResult ? 'rgba(92, 196, 137, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                }}
              >
                接受当前结果
              </button>
              {!hasPassedCompositionVerification && (
                <button
                  onClick={() => { void bridge.continueRequirementAnalysis() }}
                  disabled={!canContinueRequirementResult}
                  style={{
                    ...buttonStyle,
                    opacity: canContinueRequirementResult ? 1 : 0.55,
                    background: canContinueRequirementResult ? 'rgba(78, 161, 255, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                  }}
                >
                  {hasFailedCompositionVerification ? '按组合问题继续优化' : '继续优化'}
                </button>
              )}
              {hasPassedCompositionVerification && (
                <button
                  onClick={() => { void bridge.continueRequirementAnalysisWithFeedback({ analysisGoal: 'content_review' }) }}
                  disabled={!canContinuePassedComposition}
                  style={{
                    ...buttonStyle,
                    opacity: canContinuePassedComposition ? 1 : 0.55,
                    background: canContinuePassedComposition ? 'rgba(78, 161, 255, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                  }}
                >
                  继续单条 story 优化
                </button>
              )}
              {hasPassedCompositionVerification && (
                <button
                  onClick={() => { void bridge.continueRequirementAnalysisWithFeedback({ analysisGoal: 'composition_revision' }) }}
                  disabled={!canContinuePassedComposition}
                  style={{
                    ...buttonStyle,
                    opacity: canContinuePassedComposition ? 1 : 0.55,
                    background: canContinuePassedComposition ? 'rgba(92, 196, 137, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                  }}
                >
                  继续组合优化
                </button>
              )}
              {hasFailedCompositionVerification && (
                <button
                  onClick={() => { void bridge.continueRequirementAnalysisWithFeedback({ analysisGoal: 'content_review' }) }}
                  disabled={!canReturnToContentReview}
                  style={{
                    ...buttonStyle,
                    opacity: canReturnToContentReview ? 1 : 0.55,
                    background: canReturnToContentReview ? 'rgba(255, 255, 255, 0.07)' : 'rgba(255, 255, 255, 0.03)',
                  }}
                >
                  返回单条 story 优化
                </button>
              )}
              <button
                onClick={() => { void bridge.continueRequirementAnalysisToCompositionReview() }}
                disabled={!canStartCompositionVerification}
                style={{
                  ...buttonStyle,
                  opacity: canStartCompositionVerification ? 1 : 0.55,
                  background: canStartCompositionVerification ? 'rgba(92, 196, 137, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                }}
              >
                进入组合验证
              </button>
              <button
                onClick={() => { void bridge.retryRequirementAnalysis() }}
                disabled={!canRetryRequirementAnalysis}
                style={{
                  ...buttonStyle,
                  opacity: canRetryRequirementAnalysis ? 1 : 0.55,
                  background: canRetryRequirementAnalysis ? 'rgba(255, 196, 92, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                }}
              >
                重试需求分析
              </button>
            </div>
          )}
        </div>
      )}

      {requirementAnalysisResult && (
        <div style={sectionStyle}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--vscode-editor-foreground)' }}>
            下一阶段：测试用例生成
          </div>
          <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--vscode-input-foreground)' }}>
            这一步会把已收敛的需求分析结果、story 集合和下方 workflow draft 一起发给后端 `/v1/test-case-generation/runs`。
          </div>
          <div style={{ fontSize: 12, marginBottom: 8, color: 'var(--vscode-input-foreground)' }}>
            draft 会提醒后端关注概念性测试用例和可执行测试之间的 gap，例如 string 字段、边界值、非法格式、重复值和端到端组合覆盖。
          </div>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
            <span>Workflow Draft / Plan</span>
            <textarea
              value={testCaseGenerationPlanDraft}
              onChange={(event) => bridge.setTestCaseGenerationPlanDraft(event.target.value)}
              placeholder='接受需求分析结果后，这里会自动生成 workflow draft。你也可以手动补充注册、登录、参数组合、边界值和端到端覆盖要求。'
              style={{
                ...inputStyle,
                minHeight: 180,
                resize: 'vertical',
              }}
            />
          </label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
            <button
              onClick={() => { void bridge.generateTestCasesFromRequirementAnalysis() }}
              disabled={!canGenerateTestCases}
              style={{
                ...buttonStyle,
                opacity: canGenerateTestCases ? 1 : 0.55,
                background: canGenerateTestCases ? 'rgba(92, 196, 137, 0.18)' : 'rgba(255, 255, 255, 0.03)',
              }}
            >
              {testCaseGenerationIsRunning ? '测试用例生成中' : '生成测试用例草案'}
            </button>
            <button
              onClick={() => bridge.resetTestCaseGenerationPlanDraft()}
              disabled={!requirementAnalysisResult}
              style={{
                ...buttonStyle,
                opacity: requirementAnalysisResult ? 1 : 0.55,
              }}
            >
              重置 workflow draft
            </button>
          </div>

          {testCaseGenerationError && (
            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--vscode-errorForeground)' }}>
              测试用例生成错误：{testCaseGenerationError}
            </div>
          )}

          {testCaseGenerationResult && (
            <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)' }}>
                覆盖摘要：已覆盖 {testCaseGenerationResult.coverage_summary.covered_story_count}/{testCaseGenerationResult.coverage_summary.total_story_count} 个 story，共 {testCaseGenerationResult.coverage_summary.total_test_case_count} 条测试用例。
              </div>
              <pre
                style={{
                  margin: 0,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontSize: 12,
                  lineHeight: 1.6,
                  color: 'var(--vscode-input-foreground)',
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--vscode-panel-border)',
                  borderRadius: 8,
                  padding: '10px 12px',
                }}
              >
                {testCaseGenerationResult.test_plan}
              </pre>
              {testCaseGenerationResult.completion_check && (
                <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)', background: 'rgba(78, 161, 255, 0.10)', border: '1px solid rgba(78, 161, 255, 0.24)', borderRadius: 8, padding: '10px 12px', lineHeight: 1.6 }}>
                  完成度检查：{testCaseGenerationResult.completion_check.status} · {testCaseGenerationResult.completion_check.summary}
                  {testCaseGenerationResult.completion_check.missing_items.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                      缺失项：{testCaseGenerationResult.completion_check.missing_items.join('、')}
                    </div>
                  )}
                </div>
              )}
              <div style={{ fontSize: 12, color: 'var(--vscode-input-foreground)' }}>
                质量检查：输入/预期 {testCaseGenerationResult.quality_checks.has_inputs_and_expected_results ? '通过' : '缺失'} · 覆盖全部 story {testCaseGenerationResult.quality_checks.covers_all_stories ? '通过' : '未通过'} · 边界 {testCaseGenerationResult.quality_checks.has_boundary_cases ? '通过' : '缺失'} · 负向 {testCaseGenerationResult.quality_checks.has_negative_cases ? '通过' : '缺失'}
              </div>
              {testCaseGenerationResult.warnings.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, marginBottom: 6, color: 'var(--vscode-input-foreground)' }}>
                    警告
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                    {testCaseGenerationResult.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div>
                <div style={{ fontSize: 12, marginBottom: 6, color: 'var(--vscode-input-foreground)' }}>
                  测试用例列表
                </div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                  {testCaseGenerationResult.test_cases.map((testCase) => (
                    <li key={testCase.id}>
                      <div style={{ fontWeight: 600 }}>{testCase.title}</div>
                      <div>{testCase.story_id} · {testCase.level} · {testCase.category} · 预期：{testCase.expected_result}</div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      {requirementAnalysisError && (
        <div style={{ ...sectionStyle, color: 'var(--vscode-errorForeground)', fontSize: 12 }}>
          需求分析错误：{requirementAnalysisError}
          {canRetryRequirementAnalysis && (
            <div style={{ marginTop: 10 }}>
              <button
                onClick={() => { void bridge.retryRequirementAnalysis() }}
                style={{ ...buttonStyle, background: 'rgba(255, 196, 92, 0.18)' }}
              >
                重试需求分析
              </button>
            </div>
          )}
        </div>
      )}

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
