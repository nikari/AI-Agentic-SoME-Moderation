"""Summary agent — synthesises moderation results into a final report.

Owner: person working on the summary agent.

Receives the original post and all moderation results, resolves conflicts,
and returns a DSA Art. 17 compliant ModerationReport.
"""

import litellm

from moderation.models import SUMMARIZER_MODEL
from moderation.utils import parse_json_response
from moderation.schemas import (
    ModerationDecision,
    ModerationReport,
    ModerationResult,
    Post,
    RecommendedAction,
    ScamCategory,
    Severity,
)

_SYSTEM_PROMPT = """\
You are a compliance officer summarising content moderation decisions for review.

You will receive a social media post and one or more structured moderation results.
Synthesise them into a single coherent report, resolving any conflicts between agents.

Return a JSON object with exactly these fields:
- "verdict": "allowed" or "flagged"
- "reasoning": 2–4 sentence explanation of the final verdict
- "severity": null if allowed, otherwise "low", "medium", "high", or "critical"
- "scam_category": null if allowed, otherwise the most applicable category
- "recommended_action": one of "none", "flag", "remove", "shadow_ban", "escalate"
- "dsa_explanation": formal DSA Art. 17 statement of reasons (2–3 sentences)
- "confidence": float 0.0–1.0 reflecting overall confidence in the verdict

Return only the JSON object. No other text.\
"""


def _build_user_message(results: list[ModerationResult]) -> str:
    return "\n".join(f"Agent {i + 1}: {r.model_dump_json()}" for i, r in enumerate(results))


async def summarize(post: Post, results: list[ModerationResult]) -> ModerationReport:
    """Synthesise moderation results into a final client-facing report."""
    response = await litellm.acompletion(
        model=SUMMARIZER_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(results)},
        ],
        response_format={"type": "json_object"},
        max_tokens=512,
        metadata={
            "generation_name": "summarizer-report",
            "trace_name": "moderation-pipeline",
            "trace_user_id": post.author_id,
        },
    )
    raw = parse_json_response(response.choices[0].message.content)
    return ModerationReport(
        post_id=post.id,
        verdict=ModerationDecision(raw["verdict"]),
        reasoning=raw["reasoning"],
        severity=Severity(raw["severity"]) if raw.get("severity") else None,
        scam_category=ScamCategory(raw["scam_category"]) if raw.get("scam_category") else None,
        recommended_action=RecommendedAction(raw["recommended_action"]),
        dsa_explanation=raw["dsa_explanation"],
        confidence=float(raw["confidence"]),
    )
