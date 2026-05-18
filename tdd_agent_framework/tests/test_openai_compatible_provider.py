from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch
import httpx

from tdd_agent_framework.core import (
    AgentRunContext,
    GenerationConfig,
    ModelTarget,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
)
from tdd_agent_framework.agents.requirement_composition_verification.prompt_builder import (
    RequirementCompositionVerificationPromptBuilder,
)
from tdd_agent_framework.agents.requirement_verification.prompt_builder import (
    RequirementVerificationPromptBuilder,
)
from tdd_agent_framework.agents.requirement_verification.agent import RequirementVerificationAgent
from tdd_agent_framework.agents.requirement_verification.parser import RequirementVerificationParser
from tdd_agent_framework.agents.requirement_verification.models import RequirementVerificationInput
from tdd_agent_framework.agents.requirement_analysis.models import RequirementVerificationResult
from tdd_agent_framework.core import parse_json_object_from_text
from tdd_agent_framework.providers import OpenAICompatibleProvider, ProviderConfig, ProviderError


class OpenAICompatibleProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = OpenAICompatibleProvider(
            ProviderConfig(
                provider_name="openrouter",
                api_base="https://openrouter.ai/api/v1",
                api_key="test-key",
            ),
        )

    def test_build_payload_uses_request_model_and_messages(self) -> None:
        provider_request = ProviderRequest(
            agent_name="requirement_analysis",
            task_id="task_001",
            model_target=ModelTarget(provider="openrouter", model="qwen/qwen3"),
            system_prompt="system prompt with json output requirement",
            messages=(ProviderMessage(role="user", content="return json please"),),
            generation_config=GenerationConfig(temperature=0.1, max_tokens=1200),
        )

        payload = self.provider._build_payload(provider_request)

        self.assertEqual(payload["model"], "qwen/qwen3")
        self.assertEqual(payload["temperature"], 0.1)
        self.assertEqual(payload["max_tokens"], 1200)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")
        joined_content = " ".join(message["content"] for message in payload["messages"])
        self.assertIn("json", joined_content)

    def test_build_payload_keeps_streaming_for_non_json_object_requests(self) -> None:
        provider_request = ProviderRequest(
            agent_name="generic_agent",
            task_id="task_002",
            model_target=ModelTarget(provider="openrouter", model="qwen/qwen3"),
            system_prompt="plain text output is acceptable",
            messages=(ProviderMessage(role="user", content="answer normally"),),
            generation_config=GenerationConfig(
                temperature=0.1,
                max_tokens=1200,
                response_format="text",
            ),
        )

        payload = self.provider._build_payload(provider_request)

        self.assertTrue(payload["stream"])
        self.assertNotIn("response_format", payload)

    def test_extract_content_supports_string_message(self) -> None:
        raw_json = {
            "choices": [
                {
                    "message": {
                        "content": "{\"ok\": true}"
                    }
                }
            ]
        }

        content = self.provider._extract_content(raw_json)

        self.assertEqual(json.loads(content), {"ok": True})

    def test_extract_content_supports_output_text_shape(self) -> None:
        raw_json = {
            "id": "resp_123",
            "output_text": "{\"ok\": true, \"source\": \"output_text\"}",
        }

        content = self.provider._extract_content(raw_json)

        self.assertEqual(json.loads(content), {"ok": True, "source": "output_text"})

    def test_extract_content_supports_output_content_text_shape(self) -> None:
        raw_json = {
            "id": "resp_456",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "{\"ok\": true, \"source\": \"output.content\"}",
                        }
                    ],
                }
            ],
        }

        content = self.provider._extract_content(raw_json)

        self.assertEqual(json.loads(content), {"ok": True, "source": "output.content"})

    def test_parse_json_object_from_text_extracts_wrapped_json_object(self) -> None:
        wrapped = '```json\\n{"status":"pass","summary":"ok"}\\n```'

        parsed = parse_json_object_from_text(wrapped)

        self.assertEqual(parsed, {"status": "pass", "summary": "ok"})

    def test_format_timeout_error_keeps_useful_details_when_exception_message_is_empty(self) -> None:
        provider_request = ProviderRequest(
            agent_name="requirement_analysis",
            task_id="task_001",
            model_target=ModelTarget(provider="openrouter", model="qwen/qwen3"),
            system_prompt="system prompt",
            messages=(ProviderMessage(role="user", content="user prompt"),),
            generation_config=GenerationConfig(temperature=0.1, max_tokens=1200),
        )

        message = self.provider._format_timeout_error(
            httpx.ReadTimeout(""),
            url="https://openrouter.ai/api/v1/chat/completions",
            provider_request=provider_request,
        )

        self.assertIn("ReadTimeout", message)
        self.assertIn("requirement_analysis", message)
        self.assertIn("qwen/qwen3", message)
        self.assertIn("openrouter.ai/api/v1/chat/completions", message)
        self.assertIn("no additional detail", message)
        self.assertIn("read_timeout=180.0s", message)

    def test_build_timeout_uses_bounded_read_timeout_for_json_object(self) -> None:
        provider_request = ProviderRequest(
            agent_name="requirement_analysis",
            task_id="task_001",
            model_target=ModelTarget(provider="openrouter", model="qwen/qwen3"),
            system_prompt="system prompt with json output requirement",
            messages=(ProviderMessage(role="user", content="return json please"),),
            generation_config=GenerationConfig(temperature=0.1, max_tokens=1200),
        )

        timeout = self.provider._build_timeout(provider_request)

        self.assertEqual(timeout.read, 180.0)

    def test_summarize_error_body_prefers_html_title(self) -> None:
        body = "<html><head><title>xxsxx.fun | 524: A timeout occurred</title></head><body>...</body></html>"

        summary = self.provider._summarize_error_body(body)

        self.assertEqual(summary, "html_title=xxsxx.fun | 524: A timeout occurred")

    def test_retries_retryable_http_status_before_failing(self) -> None:
        provider_request = ProviderRequest(
            agent_name="requirement_analysis",
            task_id="task_001",
            model_target=ModelTarget(provider="openrouter", model="qwen/qwen3"),
            system_prompt="system prompt with json output requirement",
            messages=(ProviderMessage(role="user", content="return json please"),),
            generation_config=GenerationConfig(temperature=0.1, max_tokens=1200),
        )

        class StubResponse:
            status_code = 524
            text = (
                "<html><head><title>xxsxx.fun | 524: A timeout occurred</title></head>"
                "<body>timeout</body></html>"
            )

        attempts: list[int] = []

        async def fake_read_response(response, agent_name):
            attempts.append(1)
            raise httpx.HTTPStatusError(
                "timeout",
                request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
                response=httpx.Response(
                    524,
                    request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
                    text=StubResponse.text,
                ),
            )

        class StubStreamContext:
            def __init__(self, response):
                self.response = response

            async def __aenter__(self):
                return self.response

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class StubClient:
            def __init__(self, response):
                self.response = response

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def stream(self, method, url, json, headers):
                return StubStreamContext(self.response)

        with (
            patch.object(self.provider, "_read_response", side_effect=fake_read_response),
            patch("tdd_agent_framework.providers.openai_compatible.httpx.AsyncClient", return_value=StubClient(StubResponse())),
            patch("tdd_agent_framework.providers.openai_compatible.asyncio.sleep", new=self._noop_sleep),
        ):
            with self.assertRaisesRegex(ProviderError, "HTTP 524"):
                asyncio.run(self.provider.generate(provider_request))

        self.assertEqual(len(attempts), self.provider.request_retry_attempts)

    def test_total_request_timeout_bounds_streaming_generation(self) -> None:
        provider = OpenAICompatibleProvider(
            ProviderConfig(
                provider_name="openrouter",
                api_base="https://openrouter.ai/api/v1",
                api_key="test-key",
                max_request_seconds=0.01,
            ),
        )
        provider_request = ProviderRequest(
            agent_name="requirement_analysis",
            task_id="task_001",
            model_target=ModelTarget(provider="openrouter", model="qwen/qwen3"),
            system_prompt="system prompt with json output requirement",
            messages=(ProviderMessage(role="user", content="return json please"),),
            generation_config=GenerationConfig(temperature=0.1, max_tokens=1200),
        )

        class StubResponse:
            pass

        class StubStreamContext:
            async def __aenter__(self):
                return StubResponse()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class StubClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def stream(self, method, url, json, headers):
                return StubStreamContext()

        async def never_finishes(response, agent_name):
            await asyncio.sleep(60)
            return {}, ""

        with (
            patch.object(provider, "_read_response", side_effect=never_finishes),
            patch("tdd_agent_framework.providers.openai_compatible.httpx.AsyncClient", return_value=StubClient()),
        ):
            with self.assertRaisesRegex(ProviderError, "total request timeout"):
                asyncio.run(provider.generate(provider_request))

    async def _noop_sleep(self, _seconds: float) -> None:
        return None

    def test_requirement_verification_prompt_mentions_json_in_user_prompt(self) -> None:
        prompt = RequirementVerificationPromptBuilder().build_user_prompt(
            RequirementVerificationInput(
                analysis_input=self._make_verification_analysis_input(),
                analysis_result=self._make_verification_analysis_result(),
                iteration=1,
            )
        )

        self.assertIn("json 对象", prompt)

    def test_requirement_composition_prompt_mentions_json_in_user_prompt(self) -> None:
        from tdd_agent_framework.agents.requirement_composition_verification.models import (
            RequirementCompositionVerificationInput,
        )

        prompt = RequirementCompositionVerificationPromptBuilder().build_user_prompt(
            RequirementCompositionVerificationInput(
                analysis_input=self._make_verification_analysis_input(),
                analysis_result=self._make_verification_analysis_result(),
                iteration=1,
                session_id="session_001",
            )
        )

        self.assertIn("json 对象", prompt)

    def test_requirement_verification_result_accepts_issue_type_alias_and_missing_summary(self) -> None:
        result = RequirementVerificationResult.from_dict(
            {
                "verdict": "revise",
                "issues": [
                    {
                        "id": "issue_1",
                        "severity": "medium",
                        "issue_type": "untestable_ac",
                        "message": "验收标准不够单义。",
                    }
                ],
                "revision_guidance": ["补充唯一预期结果"],
                "quality_score": {
                    "scope_clarity": 70,
                    "testability": 60,
                    "dependency_sanity": 80,
                    "story_granularity": 65,
                },
            }
        )

        self.assertEqual(result.status, "revise")
        self.assertEqual(result.issues[0].issue_type, "untestable_ac")
        self.assertTrue(result.summary)

    def test_requirement_verification_parser_treats_non_blocking_revise_as_pass(self) -> None:
        result = RequirementVerificationParser().parse(
            ProviderResponse(
                raw_text="{}",
                parsed_json={
                    "status": "revise",
                    "summary": "建议进一步打磨 story 文案。",
                    "issues": [
                        {
                            "id": "issue_1",
                            "severity": "medium",
                            "type": "wording_issue",
                            "message": "标题还可以更贴近业务语言。",
                            "affected_story_ids": ["S1"],
                        }
                    ],
                    "revision_guidance": ["后续可以继续优化标题表达。"],
                    "quality_score": {
                        "scope_clarity": 82,
                        "testability": 80,
                        "dependency_sanity": 90,
                        "story_granularity": 78,
                    },
                },
            )
        )

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.issues, [])
        self.assertEqual(result.revision_guidance, ["后续可以继续优化标题表达。"])

    def test_requirement_verification_parser_keeps_high_severity_revise(self) -> None:
        result = RequirementVerificationParser().parse(
            ProviderResponse(
                raw_text="{}",
                parsed_json={
                    "status": "revise",
                    "summary": "缺少核心发帖路径。",
                    "issues": [
                        {
                            "id": "issue_1",
                            "severity": "high",
                            "type": "missing_story",
                            "message": "原始需求要求发帖，但 story 中没有覆盖发帖能力。",
                            "affected_story_ids": [],
                        }
                    ],
                    "revision_guidance": ["补充发帖 story。"],
                    "quality_score": {
                        "scope_clarity": 82,
                        "testability": 80,
                        "dependency_sanity": 90,
                        "story_granularity": 78,
                    },
                },
            )
        )

        self.assertEqual(result.status, "revise")
        self.assertEqual(len(result.issues), 1)

    def test_requirement_verification_parser_keeps_medium_blocking_revise(self) -> None:
        result = RequirementVerificationParser().parse(
            ProviderResponse(
                raw_text="{}",
                parsed_json={
                    "status": "revise",
                    "summary": "验收标准仍无法生成可靠测试。",
                    "issues": [
                        {
                            "id": "issue_1",
                            "severity": "medium",
                            "type": "untestable_ac",
                            "message": "评论 story 的验收标准缺少触发动作和明确预期结果。",
                            "affected_story_ids": ["S3"],
                        }
                    ],
                    "revision_guidance": ["补齐评论 story 的可测试验收标准。"],
                    "quality_score": {
                        "scope_clarity": 84,
                        "testability": 82,
                        "dependency_sanity": 90,
                        "story_granularity": 80,
                    },
                },
            )
        )

        self.assertEqual(result.status, "revise")
        self.assertEqual(len(result.issues), 1)

    def test_requirement_verification_agent_revises_when_explicit_listed_capability_missing(self) -> None:
        class FakeProvider:
            async def generate(self, request):
                return ProviderResponse(
                    raw_text="{}",
                    parsed_json={
                        "status": "pass",
                        "summary": "看起来已经可以进入审核。",
                        "issues": [],
                        "revision_guidance": [],
                        "quality_score": {
                            "scope_clarity": 90,
                            "testability": 90,
                            "dependency_sanity": 90,
                            "story_granularity": 90,
                        },
                    },
                )

        agent = RequirementVerificationAgent(
            provider=FakeProvider(),
            model_target=ModelTarget(provider="openai", model="gpt-5.4"),
        )
        analysis_input = self._make_verification_analysis_input()
        analysis_input = type(analysis_input)(
            task_id=analysis_input.task_id,
            mode=analysis_input.mode,
            user_prompt="制作一个协作文档工具，具备文档创建、多人编辑、评论、版本回滚、权限分享等功能",
            repo_root=analysis_input.repo_root,
            workspace_summary=analysis_input.workspace_summary,
            execution_constraints=analysis_input.execution_constraints,
        )

        result = asyncio.run(
            agent.run(
                RequirementVerificationInput(
                    analysis_input=analysis_input,
                    analysis_result=self._make_verification_analysis_result(),
                    iteration=1,
                ),
                AgentRunContext(task_id="task_001"),
            )
        )

        self.assertEqual(result.status, "revise")
        self.assertEqual(result.issues[0].issue_type, "missing_story")
        self.assertIn("多人编辑", result.revision_guidance[0])

    def _make_verification_analysis_input(self):
        from tdd_agent_framework.agents.requirement_analysis.models import (
            ExecutionConstraints,
            RequirementAnalysisInput,
            WorkspaceSummary,
        )

        return RequirementAnalysisInput(
            task_id="task_001",
            mode="repo_chat",
            user_prompt="分析导出需求",
            repo_root="/workspace/project",
            workspace_summary=WorkspaceSummary(
                languages=["python"],
                frameworks=["pytest"],
                key_modules=["app", "tests"],
            ),
            execution_constraints=ExecutionConstraints(),
        )

    def _make_verification_analysis_result(self):
        from tdd_agent_framework.agents.requirement_analysis.models import (
            AnalysisSummary,
            CapabilityGroup,
            QualityChecks,
            RequirementAnalysisResult,
            RequirementSpec,
            StoryUnit,
        )

        return RequirementAnalysisResult(
            requirement_spec=RequirementSpec(
                task_id="task_001",
                version=1,
                problem_statement="需要导出数据。",
                product_goal="提供稳定的数据导出能力。",
                scope=["export"],
                out_of_scope=[],
                constraints=[],
                assumptions=[],
                interfaces_or_contracts=[],
                acceptance_criteria=["可以导出", "结果正确", "失败可观察"],
                decomposition_strategy="按主路径拆分",
            ),
            story_units=[
                StoryUnit(
                    id="story_export",
                    story_kind="user_outcome",
                    title="运营人员可以导出当前筛选结果",
                    as_a="运营人员",
                    when_context="我已经设置好筛选条件",
                    i_want="导出当前结果为 CSV 文件",
                    so_that="我可以离线分析当前数据",
                    narrative="作为运营人员，当我已经设置好筛选条件时，我希望导出当前结果为 CSV 文件，从而我可以离线分析当前数据。",
                    actor="运营人员",
                    goal="导出当前结果为 CSV 文件",
                    business_value="我可以离线分析当前数据",
                    business_outcome="运营人员可以稳定导出当前结果",
                    scope=["export"],
                    out_of_scope=[],
                    acceptance_criteria=["可以导出", "结果正确", "失败可观察"],
                    dependencies=[],
                    priority="high",
                    risk="medium",
                    test_focus=["导出主路径"],
                    implementation_hints=[],
                )
            ],
            analysis_summary=AnalysisSummary(
                story_unit_count=1,
                high_priority_count=1,
                high_risk_count=0,
                capability_group_count=1,
            ),
            warnings=[],
            quality_checks=QualityChecks(
                has_clear_scope=True,
                has_testable_ac=True,
                dependency_graph_valid=True,
                story_count_within_limit=True,
            ),
            capability_groups=[
                CapabilityGroup(
                    id="cg_export",
                    title="导出能力",
                    goal="支持导出当前筛选结果",
                    scope=["export"],
                    story_ids=["story_export"],
                    priority="high",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
