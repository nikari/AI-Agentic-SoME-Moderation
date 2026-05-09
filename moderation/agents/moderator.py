"""Moderation agent — analyses a post and returns a structured decision.

Owner: person working on moderation agents.

To add a second agent, define a new async function following the same
signature (Post -> ModerationResult) and add it to moderate() below.
"""

import json

import litellm

from moderation.models import MODERATOR_MODEL
from moderation.schemas import (
    ModerationDecision,
    ModerationResult,
    Post,
    ScamCategory,
    Severity,
)

_SYSTEM_PROMPT = """\
You are a social media content moderator specialising in cryptocurrency scam detection.

Analyse the post and return a JSON object with exactly these fields:
- "decision": "allowed" or "flagged"
- "reasoning": 1–3 sentence explanation
- "severity": null if allowed, otherwise "low", "medium", "high", or "critical"
- "scam_category": null if allowed, otherwise one of:
  "rugpull", "fake_giveaway", "impersonation", "pump_and_dump", "phishing", "other"
- "confidence": float 0.0–1.0

Return only the JSON object. No other text.\
"""


async def _run_agent(post: Post) -> ModerationResult:
    response = await litellm.acompletion(
        model=MODERATOR_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": post.content},
        ],
        response_format={"type": "json_object"},
        max_tokens=512,
        metadata={
            "generation_name": "moderator-decision",
            "trace_name": "moderation-pipeline",
            "trace_user_id": post.author_id,
        },
    )
    raw = json.loads(response.choices[0].message.content)
    return ModerationResult(
        post_id=post.id,
        decision=ModerationDecision(raw["decision"]),
        reasoning=raw["reasoning"],
        severity=Severity(raw["severity"]) if raw.get("severity") else None,
        scam_category=ScamCategory(raw["scam_category"]) if raw.get("scam_category") else None,
        confidence=float(raw["confidence"]),
    )


async def moderate(post: Post) -> list[ModerationResult]:
    """Run all moderation agents on a post and return their results."""
    return [await _run_agent(post)]
