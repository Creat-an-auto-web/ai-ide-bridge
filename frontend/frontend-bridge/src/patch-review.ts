import { PatchFile, PatchOpReplaceRange, TaskPatchPayload } from './protocol.js'

export interface PatchReviewRange {
  startLine: number
  endLine: number
  content: string
}

export interface PatchReviewFile {
  path: string
  changeType: PatchFile['changeType']
  title: string
  unifiedDiff: string
  ranges: PatchReviewRange[]
}

export interface PatchReviewModel {
  patchId: string
  summary: string
  fileCount: number
  files: PatchReviewFile[]
}

const toChangeTitle = (file: PatchFile): string => {
  switch (file.changeType) {
    case 'create':
      return `新增 ${file.path}`
    case 'delete':
      return `删除 ${file.path}`
    case 'rename':
      return `重命名 ${file.path}`
    case 'modify':
      return `修改 ${file.path}`
    default:
      return `${file.changeType} ${file.path}`
  }
}

const isReplaceRangeOp = (value: unknown): value is PatchOpReplaceRange =>
  typeof value === 'object' &&
  value !== null &&
  'op' in value &&
  (value as { op?: unknown }).op === 'replace_range' &&
  'startLine' in value &&
  'endLine' in value &&
  'content' in value

const toReviewFile = (file: PatchFile): PatchReviewFile => ({
  path: file.path,
  changeType: file.changeType,
  title: toChangeTitle(file),
  unifiedDiff: file.unifiedDiff,
  ranges: file.ops
    .filter(isReplaceRangeOp)
    .map((op) => ({
      startLine: op.startLine,
      endLine: op.endLine,
      content: op.content,
    })),
})

export const createPatchReviewModel = (
  patch: TaskPatchPayload,
): PatchReviewModel => ({
  patchId: patch.patchId,
  summary: patch.summary,
  fileCount: patch.files.length,
  files: patch.files.map(toReviewFile),
})
