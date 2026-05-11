from __future__ import annotations

import unittest

from tdd_agent_framework.agents.requirement_feedback import (
    GlobalFeedback,
    StoryFeedback,
    feedback_to_revision_focus,
)


class RequirementFeedbackModelsTest(unittest.TestCase):
    def test_global_feedback_parses(self) -> None:
        feedback = GlobalFeedback.from_dict(
            {
                "feedback_id": "gfb_001",
                "package_id": "reqpkg_001",
                "task_id": "task_001",
                "kind": "global_feedback",
                "author_role": "user",
                "feedback_type": "scope_adjustment",
                "feedback_text": "导出能力第一期只允许仓库管理员使用。",
                "applies_to": {
                    "capability_group_ids": ["capability_export_flow"],
                    "story_ids": [],
                },
                "expected_action": "refine_existing_stories",
                "created_at": "2026-05-11T12:00:00Z",
            }
        )

        self.assertEqual(feedback.kind, "global_feedback")
        self.assertEqual(feedback.applies_to.capability_group_ids, ["capability_export_flow"])

    def test_story_feedback_parses(self) -> None:
        feedback = StoryFeedback.from_dict(
            {
                "feedback_id": "sfb_001",
                "package_id": "reqpkg_001",
                "task_id": "task_001",
                "kind": "story_feedback",
                "author_role": "user",
                "story_id": "story_export_selected_records",
                "feedback_type": "granularity_issue",
                "feedback_text": "这条 story 太大了，应该拆开。",
                "expected_action": "split_story",
                "created_at": "2026-05-11T12:02:00Z",
            }
        )

        self.assertEqual(feedback.kind, "story_feedback")
        self.assertEqual(feedback.story_id, "story_export_selected_records")

    def test_feedback_to_revision_focus_maps_both_feedback_types(self) -> None:
        global_feedback = GlobalFeedback.from_dict(
            {
                "feedback_id": "gfb_001",
                "package_id": "reqpkg_001",
                "task_id": "task_001",
                "kind": "global_feedback",
                "author_role": "user",
                "feedback_type": "scope_adjustment",
                "feedback_text": "补充权限控制相关 stories。",
            }
        )
        story_feedback = StoryFeedback.from_dict(
            {
                "feedback_id": "sfb_001",
                "package_id": "reqpkg_001",
                "task_id": "task_001",
                "kind": "story_feedback",
                "author_role": "user",
                "story_id": "story_export_selected_records",
                "feedback_type": "granularity_issue",
                "feedback_text": "拆分导出成功路径与权限控制。",
            }
        )

        focus = feedback_to_revision_focus(global_feedback, story_feedback)

        self.assertEqual(
            focus,
            [
                "补充权限控制相关 stories。",
                "针对 story_export_selected_records：拆分导出成功路径与权限控制。",
            ],
        )


if __name__ == "__main__":
    unittest.main()
