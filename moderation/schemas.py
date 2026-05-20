"""Shared Pydantic models for the moderation pipeline.

These are the contracts between agents — change carefully and update both
sides (moderator and summarizer) together.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class ModerationDecision(StrEnum):
    ALLOWED = "allowed"
    FLAGGED = "flagged"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationCategory(StrEnum):
    """Broad DSA-aligned violation categories. Crypto_scam is the primary eval focus."""

    CRYPTO_SCAM = "crypto_scam"
    HATE_SPEECH = "hate_speech"
    HARASSMENT = "harassment"
    MISINFORMATION = "misinformation"
    SPAM = "spam"
    PRIVACY_VIOLATION = "privacy_violation"
    SELF_HARM = "self_harm"
    CSAM = "csam"
    TERRORISM = "terrorism"
    IP_INFRINGEMENT = "ip_infringement"
    OTHER = "other"


class ViolationScore(BaseModel):
    """Per-category likelihood score from a moderation agent."""

    category: ViolationCategory
    score: float = Field(ge=0.0, le=1.0)  # likelihood this category applies
    reasoning: str | None = None  # 1-sentence justification


class RecommendedAction(StrEnum):
    NONE = "none"
    FLAG = "flag"
    REMOVE = "remove"
    SHADOW_BAN = "shadow_ban"
    ESCALATE = "escalate"


class Post(BaseModel):
    """A social media post to be moderated."""

    id: str
    content: str = ""
    platform: str | None = None
    author_id: str | None = None
    image_data: bytes | None = None
    image_media_type: str | None = None  # e.g. "image/jpeg", "image/png"


class ModerationResult(BaseModel):
    """Output from a single moderation agent.

    `confidence` is the AI's estimated probability that the post violates DSA
    (0.0 = certainly not a violation, 1.0 = certainly a violation). It is
    present only when `decision == FLAGGED`; `None` for allowed posts.
    """

    post_id: str
    decision: ModerationDecision
    reasoning: str | None = None
    severity: Severity | None = None
    violations: list[ViolationScore] = Field(default_factory=list)
    confidence: float | None = None

    @model_validator(mode="after")
    def _check_confidence(self) -> Self:
        if self.decision == ModerationDecision.FLAGGED:
            if self.confidence is None:
                raise ValueError("confidence is required when decision is flagged")
            if not 0.0 <= self.confidence <= 1.0:
                raise ValueError("confidence must be in [0.0, 1.0]")
        elif self.confidence is not None:
            raise ValueError("confidence must be None when decision is allowed")
        return self


class ModerationReport(BaseModel):
    """Final client-facing report produced by the summarizer.

    `confidence` is the AI's estimated probability that the post violates DSA
    (0.0–1.0). Present only when `verdict == FLAGGED`; `None` for allowed posts.
    """

    post_id: str
    verdict: ModerationDecision
    reasoning: str | None = None
    severity: Severity | None = None
    violations: list[ViolationScore] = Field(default_factory=list)
    recommended_action: RecommendedAction
    dsa_explanation: str | None = None  # DSA Art. 17 statement of reasons; None if allowed
    confidence: float | None = None

    @model_validator(mode="after")
    def _check_confidence(self) -> Self:
        if self.verdict == ModerationDecision.FLAGGED:
            if self.confidence is None:
                raise ValueError("confidence is required when verdict is flagged")
            if not 0.0 <= self.confidence <= 1.0:
                raise ValueError("confidence must be in [0.0, 1.0]")
        elif self.confidence is not None:
            raise ValueError("confidence must be None when verdict is allowed")
        return self


class Route(StrEnum):
    """Initial routing decision derived from a ModerationReport."""

    AUTO_PUBLISH = "auto_publish"
    SINGLE_REVIEW_FINAL = "single_review_final"  # flagged, confidence ≤ 0.30
    HOLD_AWAIT_APPEAL = "hold_await_appeal"  # flagged, confidence > 0.30


class AppealRoute(StrEnum):
    """Sub-route taken when a sender appeals a HOLD_AWAIT_APPEAL case."""

    AI_REEVAL = "ai_reeval"  # confidence > 0.90
    HUMAN_REVIEW = "human_review"  # 0.70 < confidence ≤ 0.90
    HUMAN_REVIEW_WITH_PANEL = "human_review_with_panel"  # confidence ≤ 0.70


class ReviewerVerdict(StrEnum):
    """Verdict returned by a human reviewer (single or panel member)."""

    APPROVE = "approve"  # publish the post (override the AI flag)
    DENY = "deny"  # uphold the block
    UNCERTAIN = "uncertain"  # only valid at HUMAN_REVIEW_WITH_PANEL tier


class CaseStatus(StrEnum):
    PUBLISHED = "published"
    BLOCKED = "blocked"
    PENDING = "pending"  # awaiting some review or appeal


class Case(BaseModel):
    """A single post's journey through the moderation + appeal flow."""

    post_id: str
    report: ModerationReport
    route: Route
    status: CaseStatus = CaseStatus.PENDING
    history: list[str] = Field(default_factory=list)
    final_message_to_sender: str | None = None
