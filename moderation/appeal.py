"""Appeal flow orchestration.

When a sender appeals a HOLD_AWAIT_APPEAL case, `handle_appeal` walks the
confidence-based decision tree (AI re-eval / human review / panel) and turns
the Case into a terminal PUBLISHED or BLOCKED state.

Human-touching steps (`single_review`, `panel_review`, `notify_sender`) come
from `moderation.review` — see that module's docstring for how to wire real
implementations.
"""

from moderation.agents.moderator import _run_agent
from moderation.models import APPEAL_MODEL
from moderation.review import notify_sender, panel_review, single_review
from moderation.routing import route_appeal
from moderation.schemas import (
    AppealRoute,
    Case,
    CaseStatus,
    ModerationResult,
    Post,
    ReviewerVerdict,
    Route,
)


async def handle_appeal(post: Post, case: Case) -> Case:
    """Run the appeal flow on a HOLD_AWAIT_APPEAL case until it terminates."""
    if case.route != Route.HOLD_AWAIT_APPEAL:
        raise ValueError(f"appeal only valid on HOLD_AWAIT_APPEAL cases, got {case.route.value}")
    if case.status != CaseStatus.PENDING:
        raise ValueError(f"case is already terminal: {case.status.value}")

    case.history.append("appeal received")
    return await _process_appeal(post, case, case.report.confidence)


async def _process_appeal(post: Post, case: Case, confidence: float) -> Case:
    """Dispatch the appeal by current confidence; recurses after AI re-eval."""
    appeal_route = route_appeal(confidence)
    case.history.append(f"appeal route: {appeal_route.value} (confidence={confidence:.2f})")

    if appeal_route == AppealRoute.AI_REEVAL:
        return await _handle_ai_reeval(post, case)
    if appeal_route == AppealRoute.HUMAN_REVIEW:
        return await _handle_human_review(post, case, allow_uncertain=False)
    return await _handle_human_review(post, case, allow_uncertain=True)


async def _handle_ai_reeval(post: Post, case: Case) -> Case:
    from moderation.schemas import ModerationDecision

    result = await _ai_reevaluate(post)
    if result.decision == ModerationDecision.ALLOWED:
        case.history.append("AI re-eval: now allowed — appeal granted")
        return _finalize(
            case,
            CaseStatus.PUBLISHED,
            "Your appeal has been granted: AI re-evaluation no longer flags this content.",
            post,
        )
    case.history.append(f"AI re-eval confidence: {result.confidence:.2f}")
    if result.confidence > 0.90:
        return _finalize(
            case,
            CaseStatus.BLOCKED,
            "Appeal denied: AI re-evaluation upheld the original decision. "
            f"Reason: {result.reasoning}",
            post,
        )
    # Confidence dropped — re-route by the new score (won't loop into AI_REEVAL).
    return await _process_appeal(post, case, result.confidence)


async def _handle_human_review(post: Post, case: Case, *, allow_uncertain: bool) -> Case:
    verdict = await single_review(post, case.report, allow_uncertain=allow_uncertain)
    case.history.append(f"human review verdict: {verdict.value}")

    if verdict == ReviewerVerdict.APPROVE:
        return _finalize(
            case,
            CaseStatus.PUBLISHED,
            "Your appeal has been reviewed by a human and your post has been published.",
            post,
        )
    if verdict == ReviewerVerdict.DENY:
        return _finalize(
            case,
            CaseStatus.BLOCKED,
            "Your appeal has been reviewed by a human; the decision to block stands.",
            post,
        )

    # UNCERTAIN
    if not allow_uncertain:
        raise ValueError(
            "single_review returned UNCERTAIN at HUMAN_REVIEW tier, "
            "where only APPROVE or DENY are valid"
        )
    return await _escalate_to_panel(post, case)


async def _escalate_to_panel(post: Post, case: Case) -> Case:
    case.history.append("escalated to 3-person panel")
    panel_verdicts = await panel_review(post, case.report)
    if len(panel_verdicts) != 3:
        raise ValueError(f"panel_review must return exactly 3 verdicts, got {len(panel_verdicts)}")
    approves = sum(1 for v in panel_verdicts if v == ReviewerVerdict.APPROVE)
    case.history.append(
        f"panel verdicts: {[v.value for v in panel_verdicts]} ({approves}/3 approve)"
    )
    if approves >= 2:
        return _finalize(
            case,
            CaseStatus.PUBLISHED,
            "A 3-person panel reviewed your appeal and approved publication.",
            post,
        )
    return _finalize(
        case,
        CaseStatus.BLOCKED,
        "A 3-person panel reviewed your appeal and the decision to block stands.",
        post,
    )


def _finalize(case: Case, status: CaseStatus, message: str, post: Post) -> Case:
    case.status = status
    case.final_message_to_sender = message
    case.history.append(f"finalized: {status.value}")
    notify_sender(post, message)
    return case


async def _ai_reevaluate(post: Post) -> ModerationResult:
    return await _run_agent(post, model=APPEAL_MODEL)
