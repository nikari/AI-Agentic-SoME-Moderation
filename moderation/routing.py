"""Pure, deterministic routing decisions over a ModerationReport's confidence.

These functions never call LLMs, never touch I/O, and are trivially unit-testable.
The boundary convention is upper-inclusive at every step: 0.30, 0.70, 0.90.
"""

from moderation.schemas import AppealRoute, ModerationDecision, ModerationReport, Route


def route_initial(report: ModerationReport) -> Route:
    """Decide the initial route for a fresh ModerationReport."""
    if report.verdict == ModerationDecision.ALLOWED:
        return Route.AUTO_PUBLISH
    if report.confidence <= 0.30:
        return Route.SINGLE_REVIEW_FINAL
    return Route.HOLD_AWAIT_APPEAL


def route_appeal(confidence: float) -> AppealRoute:
    """Decide the appeal sub-route for a held case at the given confidence."""
    if confidence > 0.90:
        return AppealRoute.AI_REEVAL
    if confidence > 0.70:
        return AppealRoute.HUMAN_REVIEW
    return AppealRoute.HUMAN_REVIEW_WITH_PANEL
