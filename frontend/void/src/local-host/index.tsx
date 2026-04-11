import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { SidebarWithAiIdeBridge } from '../vs/workbench/contrib/void/browser/react/src/sidebar-tsx/SidebarWithAiIdeBridge.js'
import { _registerServices, VoidLocalAccessor } from '../vs/workbench/contrib/void/browser/react/src/util/services.js'
import './app.css'

interface SelectionState {
  startLineNumber: number
  startColumn: number
  endLineNumber: number
  endColumn: number
}

interface LocalHostState {
  repoRootPath: string
  activeFile: string
  openFilesText: string
  branch: string
  gitDiff: string
  testLogs: string
  terminalTail: string
  diagnosticsText: string
  selection: SelectionState
}

interface DesktopApi {
  getInitialState?: () => Promise<Partial<LocalHostState>>
  pickDirectory?: () => Promise<string | null>
  pickFile?: () => Promise<string | null>
  bridgeFetch?: (url: string, init?: RequestInit) => Promise<{
    ok: boolean
    status: number
    statusText: string
    headers: Array<[string, string]>
    bodyText: string
  }>
}

declare global {
  interface Window {
    aiIdeDesktop?: DesktopApi
  }
}

const defaultState = (): LocalHostState => ({
  repoRootPath: '',
  activeFile: '',
  openFilesText: '',
  branch: '',
  gitDiff: '',
  testLogs: '',
  terminalTail: '',
  diagnosticsText: '',
  selection: {
    startLineNumber: 1,
    startColumn: 1,
    endLineNumber: 1,
    endColumn: 1,
  },
})

const parseFileList = (value: string): string[] =>
  value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)

const parseDiagnostics = (value: string): Record<string, Array<{
  message: string
  severity?: string | number
  startLineNumber?: number
  startColumn?: number
  endLineNumber?: number
  endColumn?: number
}>> => {
  const lines = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  const result: Record<string, Array<{
    message: string
    severity?: string | number
    startLineNumber?: number
    startColumn?: number
    endLineNumber?: number
    endColumn?: number
  }>> = {}

  for (const line of lines) {
    const [filePath, message, severity, startLine, startColumn, endLine, endColumn] = line.split('|').map((part) => part?.trim())
    if (!filePath || !message) {
      continue
    }

    const item = {
      message,
      severity: severity || undefined,
      startLineNumber: startLine ? Number(startLine) : undefined,
      startColumn: startColumn ? Number(startColumn) : undefined,
      endLineNumber: endLine ? Number(endLine) : undefined,
      endColumn: endColumn ? Number(endColumn) : undefined,
    }

    result[filePath] ??= []
    result[filePath].push(item)
  }

  return result
}

const createAccessor = (
  stateRef: React.MutableRefObject<LocalHostState>,
): VoidLocalAccessor => {
  const readState = () => stateRef.current
  const bridgeHostBridgeOptions = {
    baseUrl: 'http://127.0.0.1:27182',
    branchProvider: () => readState().branch || undefined,
    gitDiffProvider: () => readState().gitDiff,
    testLogsProvider: () => readState().testLogs,
  }

  return {
    get(name) {

      switch (name) {
        case '__bridgeHostBridgeOptions':
          return bridgeHostBridgeOptions
        case 'IWorkspaceContextService':
          return {
            getWorkspace() {
              const state = readState()
              return {
                folders: state.repoRootPath
                  ? [{ uri: { fsPath: state.repoRootPath } }]
                  : [],
              }
            },
          }
        case 'ICodeEditorService':
          return {
            getActiveCodeEditor() {
              const state = readState()
              if (!state.activeFile.trim()) {
                return null
              }

              return {
                getModel() {
                  return { uri: { fsPath: state.activeFile.trim() } }
                },
                getSelection() {
                  return state.selection
                },
              }
            },
          }
        case 'IModelService':
          return {
            getModels() {
              const state = readState()
              return parseFileList(state.openFilesText).map((filePath) => ({
                uri: { fsPath: filePath },
              }))
            },
          }
        case 'IMarkerService':
          return {
            read(filter?: { resource?: unknown }) {
              const state = readState()
              const diagnosticsByFile = parseDiagnostics(state.diagnosticsText)
              const filePath =
                typeof filter?.resource === 'object' &&
                filter.resource !== null &&
                'fsPath' in filter.resource
                  ? String((filter.resource as { fsPath: unknown }).fsPath)
                  : ''
              return diagnosticsByFile[filePath] ?? []
            },
          }
        case 'ITerminalToolService':
          return {
            listPersistentTerminalIds() {
              return readState().terminalTail.trim() ? ['main'] : []
            },
            readTerminal() {
              return readState().terminalTail
            },
          }
        default:
          throw new Error(`未知的本地服务：${String(name)}`)
      }
    },
  }
}

const SidebarRuntime = (props: { accessor: VoidLocalAccessor }) => {
  const disposables = useMemo(() => _registerServices(props.accessor), [props.accessor])

  useEffect(() => {
    return () => {
      for (const disposable of disposables) {
        disposable.dispose()
      }
    }
  }, [disposables])

  return <SidebarWithAiIdeBridge />
}

const App = () => {
  const [state, setState] = useState<LocalHostState>(defaultState)
  const [backendOk, setBackendOk] = useState<'checking' | 'ok' | 'error'>('checking')
  const stateRef = useRef(state)

  useEffect(() => {
    stateRef.current = state
  }, [state])

  useEffect(() => {
    void window.aiIdeDesktop?.getInitialState?.().then((initialState) => {
      if (!initialState) return
      setState((prev) => ({
        ...prev,
        ...initialState,
        selection: {
          ...prev.selection,
          ...(initialState.selection ?? {}),
        },
      }))
    })
  }, [])

  useEffect(() => {
    let closed = false

    const check = async () => {
      try {
        const response = await fetch('http://127.0.0.1:27182/healthz')
        if (!closed) {
          setBackendOk(response.ok ? 'ok' : 'error')
        }
      } catch {
        if (!closed) {
          setBackendOk('error')
        }
      }
    }

    void check()
    const timer = window.setInterval(() => {
      void check()
    }, 5000)

    return () => {
      closed = true
      window.clearInterval(timer)
    }
  }, [])

  const accessor = useMemo(() => createAccessor(stateRef), [])

  const update = <K extends keyof LocalHostState>(key: K, value: LocalHostState[K]) => {
    setState((prev) => ({ ...prev, [key]: value }))
  }

  const pickDirectory = async () => {
    const value = await window.aiIdeDesktop?.pickDirectory?.()
    if (value) {
      update('repoRootPath', value)
    }
  }

  const pickFile = async () => {
    const value = await window.aiIdeDesktop?.pickFile?.()
    if (value) {
      update('activeFile', value)
      setState((prev) => ({
        ...prev,
        activeFile: value,
        openFilesText: prev.openFilesText.trim() ? prev.openFilesText : value,
      }))
    }
  }

  return (
    <div className='local-ide-shell'>
      <header className='local-ide-header'>
        <div>
          <h1>AI IDE Bridge 本地 IDE</h1>
          <p>左侧为 Void 风格桥接侧栏，右侧为本地宿主上下文与调试面板。</p>
        </div>
        <div className='header-badges'>
          <div className={`badge ${backendOk === 'ok' ? 'ok' : backendOk === 'error' ? 'error' : ''}`}>
            后端：{backendOk === 'ok' ? '已连接' : backendOk === 'error' ? '不可用' : '检查中'}
          </div>
          <div className='badge'>
            Repo：{state.repoRootPath || '未设置'}
          </div>
        </div>
      </header>

      <main className='local-ide-main'>
        <section className='sidebar-frame'>
          <SidebarRuntime accessor={accessor} />
        </section>

        <section className='workspace-frame'>
          <div className='workspace-toolbar'>
            <div>
              <h2>本地宿主上下文</h2>
              <span>这些字段会直接映射到 bridge 读取的 Void 风格服务。</span>
            </div>
            <div className='hint'>
              执行任务前请先填写仓库根目录，必要时再补充当前文件、终端输出或测试日志。
            </div>
          </div>

          <div className='workspace-content'>
            <div className='workspace-grid'>
              <section className='workspace-card'>
                <h3>工作区</h3>
                <p>映射 `IWorkspaceContextService` 与 `IModelService`。</p>
                <div className='field-list'>
                  <div className='field'>
                    <label>仓库根目录</label>
                    <input
                      value={state.repoRootPath}
                      onChange={(event) => update('repoRootPath', event.target.value)}
                      placeholder='/path/to/repo'
                    />
                  </div>
                  <div className='row-actions'>
                    <button className='primary-btn' onClick={() => { void pickDirectory() }}>选择目录</button>
                  </div>
                  <div className='field'>
                    <label>已打开文件</label>
                    <textarea
                      value={state.openFilesText}
                      onChange={(event) => update('openFilesText', event.target.value)}
                      placeholder={'src/main.tsx\nsrc/App.tsx'}
                    />
                  </div>
                </div>
              </section>

              <section className='workspace-card'>
                <h3>当前编辑器</h3>
                <p>映射 `ICodeEditorService`。</p>
                <div className='field-list'>
                  <div className='field'>
                    <label>当前文件</label>
                    <input
                      value={state.activeFile}
                      onChange={(event) => update('activeFile', event.target.value)}
                      placeholder='src/main.tsx'
                    />
                  </div>
                  <div className='row-actions'>
                    <button className='secondary-btn' onClick={() => { void pickFile() }}>选择文件</button>
                  </div>
                  <div className='selection-grid'>
                    <div className='field'>
                      <label>起始行</label>
                      <input
                        type='number'
                        value={state.selection.startLineNumber}
                        onChange={(event) => setState((prev) => ({
                          ...prev,
                          selection: { ...prev.selection, startLineNumber: Number(event.target.value) || 1 },
                        }))}
                      />
                    </div>
                    <div className='field'>
                      <label>起始列</label>
                      <input
                        type='number'
                        value={state.selection.startColumn}
                        onChange={(event) => setState((prev) => ({
                          ...prev,
                          selection: { ...prev.selection, startColumn: Number(event.target.value) || 1 },
                        }))}
                      />
                    </div>
                    <div className='field'>
                      <label>结束行</label>
                      <input
                        type='number'
                        value={state.selection.endLineNumber}
                        onChange={(event) => setState((prev) => ({
                          ...prev,
                          selection: { ...prev.selection, endLineNumber: Number(event.target.value) || 1 },
                        }))}
                      />
                    </div>
                    <div className='field'>
                      <label>结束列</label>
                      <input
                        type='number'
                        value={state.selection.endColumn}
                        onChange={(event) => setState((prev) => ({
                          ...prev,
                          selection: { ...prev.selection, endColumn: Number(event.target.value) || 1 },
                        }))}
                      />
                    </div>
                  </div>
                </div>
              </section>

              <section className='workspace-card full'>
                <h3>附加上下文</h3>
                <p>这些字段会被 bridge 作为终端、测试和差异上下文读取。</p>
                <div className='field-list two'>
                  <div className='field'>
                    <label>分支名</label>
                    <input
                      value={state.branch}
                      onChange={(event) => update('branch', event.target.value)}
                      placeholder='main'
                    />
                  </div>
                  <div className='field'>
                    <label>诊断信息</label>
                    <textarea
                      value={state.diagnosticsText}
                      onChange={(event) => update('diagnosticsText', event.target.value)}
                      placeholder={'src/main.tsx|类型错误|error|10|5|10|18'}
                    />
                  </div>
                  <div className='field'>
                    <label>终端尾部输出</label>
                    <textarea
                      value={state.terminalTail}
                      onChange={(event) => update('terminalTail', event.target.value)}
                      placeholder='pnpm test 的最新输出'
                    />
                  </div>
                  <div className='field'>
                    <label>测试日志</label>
                    <textarea
                      value={state.testLogs}
                      onChange={(event) => update('testLogs', event.target.value)}
                      placeholder='失败测试的详细日志'
                    />
                  </div>
                </div>
              </section>

              <section className='workspace-card full'>
                <h3>Git 差异</h3>
                <p>当前示例宿主还没有直连真实 git 服务，这里先提供手工输入入口。</p>
                <div className='field'>
                  <label>git diff</label>
                  <textarea
                    value={state.gitDiff}
                    onChange={(event) => update('gitDiff', event.target.value)}
                    placeholder='diff --git a/src/main.tsx b/src/main.tsx'
                  />
                </div>
              </section>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
