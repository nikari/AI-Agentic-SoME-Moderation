"""Summary agent — synthesises moderation results into a final report.

Owner: person working on the summary agent.

Receives the original post and all moderation results, resolves conflicts,
and returns a DSA Art. 17 compliant ModerationReport.
"""

import litellm

from moderation.models import SUMMARIZER_MODEL
from moderation.schemas import (
    ModerationDecision,
    ModerationReport,
    ModerationResult,
    Post,
    RecommendedAction,
    Severity,
    ViolationCategory,
    ViolationScore,
)
from moderation.utils import parse_json_response

_SYSTEM_PROMPT = """\
You are a compliance officer summarising content moderation decisions for review.

You will receive a social media post and one or more structured moderation results.
Each result includes a `violations` list scoring the post against DSA categories
(0.0–1.0 = likelihood the category applies):
crypto_scam, hate_speech, harassment, misinformation, spam, privacy_violation,
self_harm, csam, terrorism, ip_infringement, other.

Synthesise the agents' results into a single coherent report, resolving any conflicts.

Return a JSON object with exactly these fields:
- "verdict": "allowed" or "flagged"
- "reasoning": 2–4 sentence explanation of the final verdict
- "severity": null if allowed, otherwise "low", "medium", "high", or "critical"
- "violations": list of {"category": <category>, "score": <0.0-1.0>, "reasoning": "<1 sentence>"}
                — only categories with score > 0; sort by score descending; empty list if allowed
- "recommended_action": one of "none", "flag", "remove", "shadow_ban", "escalate"
- "dsa_explanation": formal DSA Art. 17 statement of reasons (2–3 sentences); null if allowed
- "confidence": float 0.0–1.0 — estimated probability that the post violates the DSA
                (0.0 = certainly not, 1.0 = certainly is). Set ONLY when verdict is
                "flagged"; set to null when verdict is "allowed".

Return only the JSON object. No other text.\
"""


def _parse_violations(raw_violations: list[dict]) -> list[ViolationScore]:
    return [
        ViolationScore(
            category=ViolationCategory(v["category"]),
            score=float(v["score"]),
            reasoning=v.get("reasoning"),
        )
        for v in raw_violations
    ]


def _build_user_message(post: Post, results: list[ModerationResult]) -> str:
    results_text = "\n".join(f"Agent {i + 1}: {r.model_dump_json()}" for i, r in enumerate(results))
    return f"Post content:\n{post.content}\n\nModeration results:\n{results_text}"


async def summarize(post: Post, results: list[ModerationResult]) -> ModerationReport:
    """Synthesise moderation results into a final client-facing report."""
    response = await litellm.acompletion(
        model=SUMMARIZER_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(post, results)},
        ],
        response_format={"type": "json_object"},
        max_tokens=1024,
        metadata={
            "generation_name": "summarizer-report",
            "trace_name": "moderation-pipeline",
            "trace_user_id": post.author_id,
        },
    )
    raw = parse_json_response(response.choices[0].message.content)
    verdict = ModerationDecision(raw["verdict"])
    confidence = (
        float(raw["confidence"])
        if verdict == ModerationDecision.FLAGGED and raw.get("confidence") is not None
        else None
    )
    return ModerationReport(
        post_id=post.id,
        verdict=verdict,
        reasoning=raw.get("reasoning"),
        severity=Severity(raw["severity"]) if raw.get("severity") else None,
        violations=_parse_violations(raw.get("violations", [])),
        recommended_action=RecommendedAction(raw["recommended_action"]),
        dsa_explanation=raw.get("dsa_explanation"),
        confidence=confidence,
    )
