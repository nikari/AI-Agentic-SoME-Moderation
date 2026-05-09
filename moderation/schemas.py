"""Shared Pydantic models for the moderation pipeline.

These are the contracts between agents — change carefully and update both
sides (moderator and summarizer) together.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ModerationDecision(str, Enum):
    ALLOWED = "allowed"
    FLAGGED = "flagged"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScamCategory(str, Enum):
    RUGPULL = "rugpull"
    FAKE_GIVEAWAY = "fake_giveaway"
    IMPERSONATION = "impersonation"
    PUMP_AND_DUMP = "pump_and_dump"
    PHISHING = "phishing"
    OTHER = "other"


class RecommendedAction(str, Enum):
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
