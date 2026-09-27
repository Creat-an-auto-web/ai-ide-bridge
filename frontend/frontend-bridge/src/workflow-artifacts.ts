import { RequirementAnalysisResultPayload } from './agent-settings.js'
import { TestCaseGenerationResultPayload } from './test-case-generation.js'
import {
  GeneratedTestFilePayload,
  TestCodeGenerationResultPayload,
} from './test-code-generation.js'
import { TestCodeRepairResultPayload } from './test-code-repair.js'

export type WorkflowArtifactStage =
  | 'requirement_analysis'
  | 'test_case_generation'
  | 'test_code_generation'

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
    `- 03 Test code generation: ${hasStage('test_code_generation') ? 'complete' : 'not generated'}`,
    '',
    '## Generated test file drafts',
    '',
    ...(testFiles.length > 0
      ? testFiles.map((file) => `- \`03-test-code/files/${toSafeRelativePath(file.path, 'generated-test.txt')}\``)
      : ['- No test file draft has been generated.']),
    '',
    'These files are review snapshots. Generated test code stays under this artifact directory and does not overwrite workspace source files.',
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
  if (testCodeResult) {
    completedStages.push('test_code_generation')
  }

  files.push({
    relativePath: 'README.md',
    stage: 'summary',
    title: 'Artifact summary',
    content: buildSummary(taskId, completedStages, testFiles),
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
      relativePath: '03-test-code/manifest.json',
      stage: 'test_code_generation',
      title: 'Stage 3 test code manifest',
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
        relativePath: `03-test-code/files/${toSafeRelativePath(file.path, `generated-test-${index + 1}.txt`)}`,
        stage: 'test_code_generation',
        title: file.path || `Generated test ${index + 1}`,
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
