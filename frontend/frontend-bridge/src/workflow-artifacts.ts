import { RequirementAnalysisResultPayload } from './agent-settings.js'
import { TestCaseGenerationResultPayload } from './test-case-generation.js'
import {
  GeneratedTestFilePayload,
  TestCodeGenerationResultPayload,
} from './test-code-generation.js'
import { TestCodeRepairResultPayload } from './test-code-repair.js'
import { CodeImplementationResultPayload, GeneratedImplementationFilePayload } from './code-implementation.js'

export type WorkflowArtifactStage =
  | 'requirement_analysis'
  | 'test_case_generation'
  | 'code_implementation'

export interface WorkflowArtifactFile {
  relativePath: string
  stage: WorkflowArtifactStage | 'summary'
  title: string
  content: string
}

export interface WorkflowArtifactBundle {
  taskId: string
  directoryName: string
  files: WorkflowArtifactFile[]
  completedStages: WorkflowArtifactStage[]
}

export interface BuildWorkflowArtifactBundleOptions {
  requirementAnalysisResult: RequirementAnalysisResultPayload | null
  testCaseGenerationResult: TestCaseGenerationResultPayload | null
  testCodeGenerationResult: TestCodeGenerationResultPayload | null
  testCodeRepairResult?: TestCodeRepairResultPayload | null
  codeImplementationResult?: CodeImplementationResultPayload | null
}

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
)

const isSafeRelativePath = (value: string): boolean => {
  const normalized = value.replace(/\\/g, '/')
  return (
    normalized.length > 0
    && !normalized.startsWith('/')
    && !/^[a-zA-Z]:/.test(normalized)
    && normalized.split('/').every((segment) => segment !== '' && segment !== '.' && segment !== '..')
  )
}

export const parseWorkflowArtifactBundle = (
  value: unknown,
): WorkflowArtifactBundle | null => {
  if (!isRecord(value)) return null
  const taskId = value.taskId
  const directoryName = value.directoryName
  const completedStages = value.completedStages
  const rawFiles = value.files
  if (
    typeof taskId !== 'string'
    || typeof directoryName !== 'string'
    || !Array.isArray(completedStages)
    || !Array.isArray(rawFiles)
  ) {
    return null
  }

  const validStages = new Set<WorkflowArtifactStage>([
    'requirement_analysis',
    'test_case_generation',
    'code_implementation',
  ])
  const files: WorkflowArtifactFile[] = []
  for (const rawFile of rawFiles) {
    if (!isRecord(rawFile)) return null
    const { relativePath, stage, title, content } = rawFile
    if (
      typeof relativePath !== 'string'
      || !isSafeRelativePath(relativePath)
      || typeof title !== 'string'
      || typeof content !== 'string'
      || (stage !== 'summary' && !validStages.has(stage as WorkflowArtifactStage))
    ) {
      return null
    }
    files.push({
      relativePath,
      stage: stage as WorkflowArtifactFile['stage'],
      title,
      content,
    })
  }

  return {
    taskId,
    directoryName: toSafePathSegment(directoryName, 'workflow-task'),
    files,
    completedStages: completedStages.filter(
      (stage): stage is WorkflowArtifactStage => (
        typeof stage === 'string' && validStages.has(stage as WorkflowArtifactStage)
      ),
    ),
  }
}

const toSafePathSegment = (value: string, fallback: string): string => {
  const normalized = value
    .trim()
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return normalized && normalized !== '.' && normalized !== '..'
    ? normalized
    : fallback
}

const toSafeRelativePath = (value: string, fallback: string): string => {
  const withoutDrive = value.trim().replace(/^[a-zA-Z]:/, '')
  const segments = withoutDrive
    .replace(/\\/g, '/')
    .split('/')
    .filter((segment) => segment && segment !== '.' && segment !== '..')
    .map((segment, index) => toSafePathSegment(segment, `segment-${index + 1}`))
  return segments.length > 0 ? segments.join('/') : fallback
}

const toJson = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`

const buildSummary = (
  taskId: string,
  completedStages: WorkflowArtifactStage[],
  testFiles: GeneratedTestFilePayload[],
  implementationFiles: GeneratedImplementationFilePayload[],
): string => {
  const hasStage = (stage: WorkflowArtifactStage) => completedStages.includes(stage)
  return [
    '# AI IDE workflow artifacts',
    '',
    `Task: ${taskId}`,
    '',
    '## Stage status',
    '',
    `- 01 Requirement analysis: ${hasStage('requirement_analysis') ? 'complete' : 'not generated'}`,
    `- 02 Test case generation: ${hasStage('test_case_generation') ? 'complete' : 'not generated'}`,
    `- 03 Business implementation: ${hasStage('code_implementation') ? 'complete' : 'not generated'}`,
    '',
    '## Test baseline',
    '',
    ...(testFiles.length > 0
      ? testFiles.map((file) => `- \`02-test-cases/test-code/${toSafeRelativePath(file.path, 'generated-test.txt')}\``)
      : ['- No test file draft has been generated.']),
    '',
    '## Generated business implementation',
    '',
    ...(implementationFiles.length > 0
      ? implementationFiles.map((file) => `- \`03-implementation/files/${toSafeRelativePath(file.path, 'generated-code.txt')}\``)
      : ['- No production implementation has been generated.']),
    '',
    'These files are review snapshots. They do not overwrite workspace source files.',
    '',
  ].join('\n')
}

export const buildWorkflowArtifactBundle = (
  options: BuildWorkflowArtifactBundleOptions,
): WorkflowArtifactBundle | null => {
  const requirementResult = options.requirementAnalysisResult
  if (!requirementResult) {
    return null
  }

  const testCaseResult = options.testCaseGenerationResult
  const testCodeResult = options.testCodeGenerationResult
  const implementationResult = options.codeImplementationResult ?? null
  const repairedTestFiles = options.testCodeRepairResult?.test_files ?? []
  const testFiles = repairedTestFiles.length > 0
    ? repairedTestFiles
    : testCodeResult?.test_files ?? []
  const taskId = requirementResult.task_id || 'workflow-task'
  const completedStages: WorkflowArtifactStage[] = ['requirement_analysis']
  const files: WorkflowArtifactFile[] = []

  if (testCaseResult) {
    completedStages.push('test_case_generation')
  }
  if (implementationResult) {
    completedStages.push('code_implementation')
  }

  files.push({
    relativePath: 'README.md',
    stage: 'summary',
    title: 'Artifact summary',
    content: buildSummary(taskId, completedStages, testFiles, implementationResult?.files ?? []),
  })
  files.push({
    relativePath: '01-requirement-analysis/requirement-analysis.json',
    stage: 'requirement_analysis',
    title: 'Stage 1 requirement analysis',
    content: toJson(requirementResult),
  })

  if (testCaseResult) {
    files.push({
      relativePath: '02-test-cases/test-cases.json',
      stage: 'test_case_generation',
      title: 'Stage 2 test cases',
      content: toJson(testCaseResult),
    })
    files.push({
      relativePath: '02-test-cases/test-plan.md',
      stage: 'test_case_generation',
      title: 'Stage 2 test plan',
      content: `${testCaseResult.test_plan.trim()}\n`,
    })
  }

  if (testCodeResult) {
    files.push({
        relativePath: '02-test-cases/test-code-manifest.json',
        stage: 'test_case_generation',
        title: 'Stage 2 test code baseline manifest',
      content: toJson({
        implementation_plan: testCodeResult.implementation_plan,
        changed_files: testCodeResult.changed_files,
        rationale: testCodeResult.rationale,
        warnings: testCodeResult.warnings,
        quality_checks: testCodeResult.quality_checks,
        source: repairedTestFiles.length > 0 ? 'repair' : 'generation',
        files: testFiles.map((file) => ({
          path: file.path,
          language: file.language,
          framework: file.framework,
          purpose: file.purpose,
          related_test_case_ids: file.related_test_case_ids,
        })),
      }),
    })
    testFiles.forEach((file, index) => {
      files.push({
          relativePath: `02-test-cases/test-code/${toSafeRelativePath(file.path, `generated-test-${index + 1}.txt`)}`,
          stage: 'test_case_generation',
        title: file.path || `Generated test ${index + 1}`,
        content: file.content.endsWith('\n') ? file.content : `${file.content}\n`,
      })
    })
  }

  if (implementationResult) {
    files.push({
      relativePath: '03-implementation/manifest.json',
      stage: 'code_implementation',
      title: 'Stage 3 business implementation manifest',
      content: toJson({
        implementation_plan: implementationResult.implementation_plan,
        changed_files: implementationResult.changed_files,
        rationale: implementationResult.rationale,
        test_command: implementationResult.test_command,
        warnings: implementationResult.warnings,
        quality_checks: implementationResult.quality_checks,
      }),
    })
    implementationResult.files.forEach((file, index) => {
      files.push({
        relativePath: `03-implementation/files/${toSafeRelativePath(file.path, `generated-code-${index + 1}.txt`)}`,
        stage: 'code_implementation',
        title: file.path || `Generated implementation ${index + 1}`,
        content: file.content.endsWith('\n') ? file.content : `${file.content}\n`,
      })
    })
  }

  return {
    taskId,
    directoryName: toSafePathSegment(taskId, 'workflow-task'),
    files,
    completedStages,
  }
}
