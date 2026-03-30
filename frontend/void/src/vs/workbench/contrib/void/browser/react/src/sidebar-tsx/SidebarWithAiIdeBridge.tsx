import React, { useState } from 'react'
import { useIsDark } from '../util/services.js'
import '../styles.css'
import ErrorBoundary from './ErrorBoundary.js'
import { AiIdeBridgePanel } from '../bridge/AiIdeBridgePanel.js'

type SidebarTab = 'chat' | 'bridge'

const TabButton = (props: {
  active: boolean
  label: string
  onClick: () => void
}) => (
  <button
    onClick={props.onClick}
    style={{
      border: '1px solid var(--vscode-panel-border)',
      padding: '6px 10px',
      borderRadius: 6,
      opacity: props.active ? 1 : 0.75,
      fontWeight: props.active ? 600 : 400,
    }}
  >
    {props.label}
  </button>
)

export const SidebarWithAiIdeBridge = () => {
  const isDark = useIsDark()
  const [tab, setTab] = useState<SidebarTab>('bridge')

  return (
    <div
      className={`@@void-scope ${isDark ? 'dark' : ''}`}
      style={{ width: '100%', height: '100%' }}
    >
      <div
        className='w-full h-full bg-void-bg-2 text-void-fg-1'
        style={{ display: 'flex', flexDirection: 'column' }}
      >
        <div
          style={{
            display: 'flex',
            gap: 8,
            padding: 10,
            borderBottom: '1px solid var(--vscode-panel-border)',
          }}
        >
          <TabButton active={tab === 'bridge'} label='AI IDE Bridge' onClick={() => setTab('bridge')} />
          <TabButton active={tab === 'chat'} label='原始 Chat' onClick={() => setTab('chat')} />
        </div>

        <div className='w-full h-full' style={{ minHeight: 0, overflow: 'auto' }}>
          <ErrorBoundary>
            {tab === 'bridge'
              ? <AiIdeBridgePanel />
              : (
                <div style={{ padding: 16, fontSize: 12, lineHeight: 1.6 }}>
                  这里预留给原始 Void Chat。
                  当前在 `ai-ide-bridge/frontend/void/` 这份副本里，我们只对 sidebar 接入位做联调改造，
                  不把整套聊天 UI 依赖树全部搬进来。
                </div>
              )}
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}
