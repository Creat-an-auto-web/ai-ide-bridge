import React, { useState } from 'react'
import { useIsDark } from '../util/services.js'
import '../styles.css'
import ErrorBoundary from './ErrorBoundary.js'
import { AiIdeBridgePanel } from '../bridge/AiIdeBridgePanel.js'
import { SidebarChat } from './SidebarChat.js'

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
      padding: '8px 12px',
      borderRadius: 10,
      opacity: props.active ? 1 : 0.72,
      fontWeight: props.active ? 600 : 400,
      background: props.active ? 'rgba(78, 161, 255, 0.18)' : 'rgba(255, 255, 255, 0.04)',
      color: 'var(--vscode-editor-foreground)',
    }}
  >
    {props.label}
  </button>
)

export const SidebarWithAiIdeBridge = () => {
  const isDark = useIsDark()
  const [tab, setTab] = useState<SidebarTab>('chat')

  return (
    <div
      className={`@@void-scope ${isDark ? 'dark' : ''}`}
      style={{
        width: '100%',
        height: '100%',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          width: '100%',
          height: '100%',
          background: 'var(--vscode-sideBar-background)',
          color: 'var(--vscode-editor-foreground)',
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: 8,
            padding: 12,
            borderBottom: '1px solid var(--vscode-panel-border)',
            background: 'rgba(255, 255, 255, 0.02)',
          }}
        >
          <TabButton active={tab === 'bridge'} label='AI IDE Bridge' onClick={() => setTab('bridge')} />
          <TabButton active={tab === 'chat'} label='原始 Chat' onClick={() => setTab('chat')} />
        </div>

        <div style={{ minHeight: 0, overflow: 'auto', flex: 1 }}>
          <ErrorBoundary>
            {tab === 'bridge'
              ? <AiIdeBridgePanel />
              : <SidebarChat />}
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}
