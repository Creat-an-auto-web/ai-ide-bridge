import { PatchFile, PatchOpReplaceRange, TaskPatchPayload } from './protocol.js'

export interface WorkspaceEditRange {
  startLineNumber: number
  startColumn: number
  endLineNumber: number
  endColumn: number
}

export interface WorkspaceTextEdit {
  resourcePath: string
  range: WorkspaceEditRange
  text: string
}

export interface WorkspaceFileEdit {
  resourcePath: string
  changeType: PatchFile['changeType']
  textEdits: WorkspaceTextEdit[]
  unifiedDiff: string
}

export interface WorkspaceEditModel {
  patchId: string
  summary: string
  files: WorkspaceFileEdit[]
}

const isReplaceRangeOp = (value: unknown): value is PatchOpReplaceRange =>
  typeof value === 'object' &&
  value !== null &&
  'op' in value &&
  (value as { op?: unknown }).op === 'replace_range' &&
  'startLine' in value &&
  'endLine' in value &&
  'content' in value

const toWorkspaceTextEdit = (
  resourcePath: string,
  op: PatchOpReplaceRange,
): WorkspaceTextEdit => ({
  resourcePath,
  range: {
    startLineNumber: op.startLine,
    startColumn: 1,
    endLineNumber: op.endLine,
    endColumn: 1,
  },
  text: op.content,
})

const toWorkspaceFileEdit = (file: PatchFile): WorkspaceFileEdit => ({
  resourcePath: file.path,
  changeType: file.changeType,
  unifiedDiff: file.unifiedDiff,
  textEdits: file.ops
    .filter(isReplaceRangeOp)
    .map((op) => toWorkspaceTextEdit(file.path, op)),
})

export const createWorkspaceEditModel = (
  patch: TaskPatchPayload,
): WorkspaceEditModel => ({
  patchId: patch.patchId,
  summary: patch.summary,
  files: patch.files.map(toWorkspaceFileEdit),
})
