from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_list_of_str(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    result: list[str] = []
    for item in value:
        result.append(_require_str(item, field_name))
    return result


@dataclass(frozen=True)
class FeedbackAppliesTo:
    capability_group_ids: list[str] = field(default_factory=list)
    story_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FeedbackAppliesTo":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("applies_to must be an object")
        return cls(
            capability_group_ids=_optional_list_of_str(
                data.get("capability_group_ids"),
                "applies_to.capability_group_ids",
            ),
            story_ids=_optional_list_of_str(
                data.get("story_ids"),
                "applies_to.story_ids",
            ),
        )


@dataclass(frozen=True)
class GlobalFeedback:
    feedback_id: str
    package_id: str
    task_id: str
    kind: str
    author_role: str
    feedback_type: str
    feedback_text: str
    applies_to: FeedbackAppliesTo = field(default_factory=FeedbackAppliesTo)
    expected_action: str | None = None
    created_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GlobalFeedback":
        if not isinstance(data, dict):
            raise ValueError("global_feedback must be an object")
        return cls(
            feedback_id=_require_str(data.get("feedback_id"), "global_feedback.feedback_id"),
            package_id=_require_str(data.get("package_id"), "global_feedback.package_id"),
            task_id=_require_str(data.get("task_id"), "global_feedback.task_id"),
            kind=_require_str(data.get("kind"), "global_feedback.kind"),
            author_role=_require_str(data.get("author_role"), "global_feedback.author_role"),
            feedback_type=_require_str(data.get("feedback_type"), "global_feedback.feedback_type"),
            feedback_text=_require_str(data.get("feedback_text"), "global_feedback.feedback_text"),
            applies_to=FeedbackAppliesTo.from_dict(data.get("applies_to")),
            expected_action=(
                _require_str(data.get("expected_action"), "global_feedback.expected_action")
                if data.get("expected_action") is not None
                else None
            ),
            created_at=(
                _require_str(data.get("created_at"), "global_feedback.created_at")
                if data.get("created_at") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class StoryFeedback:
    feedback_id: str
    package_id: str
    task_id: str
    kind: str
    author_role: str
    story_id: str
    feedback_type: str
    feedback_text: str
    expected_action: str | None = None
    created_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryFeedback":
        if not isinstance(data, dict):
            raise ValueError("story_feedback must be an object")
        return cls(
            feedback_id=_require_str(data.get("feedback_id"), "story_feedback.feedback_id"),
            package_id=_require_str(data.get("package_id"), "story_feedback.package_id"),
            task_id=_require_str(data.get("task_id"), "story_feedback.task_id"),
            kind=_require_str(data.get("kind"), "story_feedback.kind"),
            author_role=_require_str(data.get("author_role"), "story_feedback.author_role"),
            story_id=_require_str(data.get("story_id"), "story_feedback.story_id"),
            feedback_type=_require_str(data.get("feedback_type"), "story_feedback.feedback_type"),
            feedback_text=_require_str(data.get("feedback_text"), "story_feedback.feedback_text"),
            expected_action=(
                _require_str(data.get("expected_action"), "story_feedback.expected_action")
                if data.get("expected_action") is not None
                else None
            ),
            created_at=(
                _require_str(data.get("created_at"), "story_feedback.created_at")
                if data.get("created_at") is not None
                else None
            ),
        )


def feedback_to_revision_focus(
    global_feedback: GlobalFeedback | None = None,
    story_feedback: StoryFeedback | None = None,
) -> list[str]:
    focus: list[str] = []
    if global_feedback is not None:
        focus.append(global_feedback.feedback_text)
    if story_feedback is not None:
        focus.append(
            f"针对 {story_feedback.story_id}：{story_feedback.feedback_text}"
        )
    return focus
