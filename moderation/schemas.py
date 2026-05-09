"""Shared Pydantic models for the moderation pipeline.

These are the contracts between agents — change carefully and update both
sides (moderator and summarizer) together.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class ModerationDecision(StrEnum):
    ALLOWED = "allowed"
    FLAGGED = "flagged"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScamCategory(StrEnum):
    RUGPULL = "rugpull"
    FAKE_GIVEAWAY = "fake_giveaway"
    IMPERSONATION = "impersonation"
    PUMP_AND_DUMP = "pump_and_dump"
    PHISHING = "phishing"
    OTHER = "other"


class RecommendedAction(StrEnum):
    NONE = "none"
    FLAG = "flag"
    REMOVE = "remove"
    SHADOW_BAN = "shadow_ban"
    ESCALATE = "escalate"


class Post(BaseModel):
    """A social media post to be moderated."""

    id: str
    content: str
    platform: str | None = None
    author_id: str | None = None


class ModerationResult(BaseModel):
    """Output from a single moderation agent."""

    post_id: str
    decision: ModerationDecision
    reasoning: str
    severity: Severity | None = None
    scam_category: ScamCategory | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ModerationReport(BaseModel):
    """Final client-facing report produced by the summarizer."""

    post_id: str
    verdict: ModerationDecision
    reasoning: str
    severity: Severity | None = None
    scam_category: ScamCategory | None = None
    recommended_action: RecommendedAction
    dsa_explanation: str  # DSA Art. 17 statement of reasons
    confidence: float = Field(ge=0.0, le=1.0)


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
