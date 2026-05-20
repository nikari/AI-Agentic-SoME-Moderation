"""Pipeline: Post → moderation agents → summarizer → ModerationReport → Case."""

from moderation.agents.moderator import moderate
from moderation.agents.summarizer import summarize
from moderation.review import notify_sender, single_review
from moderation.routing import route_initial
from moderation.schemas import (
    Case,
    CaseStatus,
    ModerationDecision,
    ModerationReport,
    Post,
    RecommendedAction,
    ReviewerVerdict,
    Route,
)

REPORT_RATE_THRESHOLD = 0.05  # skip AI moderation below this reports/views ratio


def _below_report_threshold(post: Post) -> bool:
    if post.views is None or post.views == 0:
        return False
    return len(post.report_types) / post.views < REPORT_RATE_THRESHOLD


async def run_pipeline(post: Post) -> ModerationReport:
    """Run the AI portion of the moderation pipeline on a single post."""
    if _below_report_threshold(post):
        n = len(post.report_types)
        rate = n / post.views  # type: ignore[operator]
        return ModerationReport(
            post_id=post.id,
            verdict=ModerationDecision.ALLOWED,
            recommended_action=RecommendedAction.NONE,
            reasoning=(
                f"Report rate {n}/{post.views} ({rate:.1%}) is below the"
                f" {REPORT_RATE_THRESHOLD:.0%} threshold — AI moderation skipped."
            ),
        )
    results = await moderate(post)
    if all(r.decision == ModerationDecision.ALLOWED for r in results):
        return ModerationReport(
            post_id=post.id,
            verdict=ModerationDecision.ALLOWED,
            recommended_action=RecommendedAction.NONE,
        )
    return await summarize(post, results)


async def run_pipeline_with_routing(post: Post) -> Case:
    """Run the AI pipeline and apply the initial routing decision.

    Outcomes:
      - AUTO_PUBLISH         → terminal Case (status=PUBLISHED)
      - SINGLE_REVIEW_FINAL  → calls the single_review stub immediately;
                                terminal Case (PUBLISHED or BLOCKED)
      - HOLD_AWAIT_APPEAL    → PENDING Case; sender notified; appeal handled
                                separately via moderation.appeal.handle_appeal
    """
    report = await run_pipeline(post)
    route = route_initial(report)
    case = Case(post_id=post.id, report=report, route=route)
    conf_str = "n/a" if report.confidence is None else f"{report.confidence:.2f}"
    case.history.append(f"initial route: {route.value} (confidence={conf_str})")

    if route == Route.AUTO_PUBLISH:
        case.status = CaseStatus.PUBLISHED
        case.final_message_to_sender = "Your post has been published."
        case.history.append("auto-published")
        return case

    if route == Route.SINGLE_REVIEW_FINAL:
        verdict = await single_review(post, report, allow_uncertain=False)
        case.history.append(f"single reviewer verdict: {verdict.value}")
        if verdict == ReviewerVerdict.UNCERTAIN:
            raise ValueError(
                "single_review returned UNCERTAIN at SINGLE_REVIEW_FINAL tier, "
                "where only APPROVE or DENY are valid"
            )
        if verdict == ReviewerVerdict.APPROVE:
            case.status = CaseStatus.PUBLISHED
            case.final_message_to_sender = "Your post has been reviewed by a human and published."
        else:
            case.status = CaseStatus.BLOCKED
            case.final_message_to_sender = (
                "Your post has been reviewed by a human and not published. This decision is final."
            )
        notify_sender(post, case.final_message_to_sender)
        return case

    # HOLD_AWAIT_APPEAL
    msg = (
        f"Your post is currently held for moderation. {report.dsa_explanation or ''} "
        "You may appeal this decision."
    ).strip()
    case.final_message_to_sender = msg
    case.history.append("notified sender; awaiting appeal")
    notify_sender(post, msg)
    return case
