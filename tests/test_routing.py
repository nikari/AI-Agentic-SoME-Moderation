import pytest

from moderation.routing import route_appeal, route_initial
from moderation.schemas import (
    AppealRoute,
    ModerationDecision,
    ModerationReport,
    RecommendedAction,
    Route,
)


def _report(verdict: ModerationDecision, confidence: float) -> ModerationReport:
    return ModerationReport(
        post_id="t",
        verdict=verdict,
        reasoning="x",
        recommended_action=RecommendedAction.NONE,
        dsa_explanation="x",
        confidence=confidence,
    )


@pytest.mark.parametrize("confidence", [0.0, 0.3, 0.5, 0.99])
def test_allowed_always_routes_to_auto_publish(confidence: float) -> None:
    assert route_initial(_report(ModerationDecision.ALLOWED, confidence)) == Route.AUTO_PUBLISH


@pytest.mark.parametrize("confidence", [0.0, 0.10, 0.30])
def test_flagged_at_or_below_30_routes_to_single_review_final(confidence: float) -> None:
    assert (
        route_initial(_report(ModerationDecision.FLAGGED, confidence)) == Route.SINGLE_REVIEW_FINAL
    )


@pytest.mark.parametrize("confidence", [0.31, 0.50, 0.90, 1.00])
def test_flagged_above_30_routes_to_hold_await_appeal(confidence: float) -> None:
    assert route_initial(_report(ModerationDecision.FLAGGED, confidence)) == Route.HOLD_AWAIT_APPEAL


@pytest.mark.parametrize(
    "confidence,expected",
    [
        (1.00, AppealRoute.AI_REEVAL),
        (0.91, AppealRoute.AI_REEVAL),
        (0.90, AppealRoute.HUMAN_REVIEW),
        (0.71, AppealRoute.HUMAN_REVIEW),
        (0.70, AppealRoute.HUMAN_REVIEW_WITH_PANEL),
        (0.50, AppealRoute.HUMAN_REVIEW_WITH_PANEL),
        (0.00, AppealRoute.HUMAN_REVIEW_WITH_PANEL),
    ],
)
def test_route_appeal_brackets(confidence: float, expected: AppealRoute) -> None:
    assert route_appeal(confidence) == expected
