"""Moderation agent — analyses a post and returns a structured decision.

Owner: person working on moderation agents.

To add a second agent, define a new async function following the same
signature (Post -> ModerationResult) and add it to moderate() below.
"""

import base64

import litellm

from moderation.models import MODERATOR_MODEL
from moderation.schemas import (
    ModerationDecision,
    ModerationResult,
    Post,
    Severity,
    ViolationCategory,
    ViolationScore,
)
from moderation.utils import parse_json_response

_SYSTEM_PROMPT = """\
You are a social media content moderator assessing posts for violations of the EU
Digital Services Act. A post may contain text, an image, or both — assess all provided
content together as a single unit. When both are present, consider how they interact:
a combination that is suspicious is more serious than either part alone (e.g. innocent-
looking caption paired with a fake profit screenshot).

Score the post against these violation categories (0.0–1.0 = likelihood the category applies):
- crypto_scam:       cryptocurrency scams — text: rugpulls, fake giveaways, impersonation,
                     pump-and-dumps, phishing; image: fake profit screenshots, scam QR codes,
                     fake giveaway graphics, pump-and-dump imagery, phishing overlays
- hate_speech:       attacks on protected groups (race, religion, gender, sexuality, …)
- harassment:        bullying, threats, or targeted abuse of an individual
- misinformation:    demonstrably false claims with risk of public harm (incl. doctored images)
- spam:              bulk unsolicited commercial content
- privacy_violation: doxxing or non-consensual sharing of personal info / images
- self_harm:         glorification of, or instructions for, self-harm or suicide
- csam:              child sexual abuse material
- terrorism:         terrorist content, recruitment, or glorification
- ip_infringement:   copyright violations, counterfeit goods promotion
- other:             any other illegal content under the DSA not covered above

Cryptocurrency scam detection is the primary use case — be especially thorough on `crypto_scam`.

Return a JSON object.

If the post is ALLOWED (no violations), return:
{"decision": "allowed"}

If the post is FLAGGED, return:
{"decision": "flagged",
 "reasoning": "<1–3 sentence explanation>",
 "severity": "low"|"medium"|"high"|"critical",
 "violations": [
    {"category": "<category>", "score": <0.0-1.0>, "reasoning": "<1 sentence>"},
    ...
 ],
 "confidence": <float 0.0–1.0>}

`confidence` is your estimated probability that the post violates the DSA:
0.0 = certainly not a violation, 1.0 = certainly a violation. Only emit
`confidence` on FLAGGED responses — never on ALLOWED.

Only include violations where score > 0. Sort by score descending.
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


def _build_user_content(post: Post) -> list[dict] | str:
    if not post.image_data:
        return post.content
    parts: list[dict] = []
    if post.content:
        parts.append({"type": "text", "text": post.content})
    b64 = base64.b64encode(post.image_data).decode()
    media_type = post.image_media_type or "image/jpeg"
    parts.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}})
    return parts


async def _run_agent(post: Post, model: str = MODERATOR_MODEL) -> ModerationResult:
    response = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_content(post)},
        ],
        response_format={"type": "json_object"},
        max_tokens=1024,
        metadata={
            "generation_name": "moderator-decision",
            "trace_name": "moderation-pipeline",
            "trace_user_id": post.author_id,
        },
    )
    raw = parse_json_response(response.choices[0].message.content)
    decision = ModerationDecision(raw["decision"])
    confidence = (
        float(raw["confidence"])
        if decision == ModerationDecision.FLAGGED and raw.get("confidence") is not None
        else None
    )
    return ModerationResult(
        post_id=post.id,
        decision=decision,
        reasoning=raw.get("reasoning"),
        severity=Severity(raw["severity"]) if raw.get("severity") else None,
        violations=_parse_violations(raw.get("violations", [])),
        confidence=confidence,
    )


async def moderate(post: Post) -> list[ModerationResult]:
    """Run the moderation agent on a post and return its result."""
    if not post.content and not post.image_data:
        return []
    return [await _run_agent(post)]
