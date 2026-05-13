import pytest

from moderation.routing import route_appeal, route_initial
from moderation.schemas import (
    AppealRoute,
    ModerationDecision,
    ModerationReport,
    RecommendedAction,
    Route,
)


def _flagged_report(confidence: float) -> ModerationReport:
    return ModerationReport(
        post_id="t",
        verdict=ModerationDecision.FLAGGED,
        reasoning="x",
        recommended_action=RecommendedAction.FLAG,
        dsa_explanation="x",
        confidence=confidence,
    )


def _allowed_report() -> ModerationReport:
    return ModerationReport(
        post_id="t",
        verdict=ModerationDecision.ALLOWED,
        recommended_action=RecommendedAction.NONE,
    )


def test_allowed_routes_to_auto_publish() -> None:
    assert route_initial(_allowed_report()) == Route.AUTO_PUBLISH


@pytest.mark.parametrize("confidence", [0.0, 0.10, 0.30])
def test_flagged_at_or_below_30_routes_to_single_review_final(confidence: float) -> None:
    assert route_initial(_flagged_report(confidence)) == Route.SINGLE_REVIEW_FINAL


@pytest.mark.parametrize("confidence", [0.31, 0.50, 0.90, 1.00])
def test_flagged_above_30_routes_to_hold_await_appeal(confidence: float) -> None:
    assert route_initial(_flagged_report(confidence)) == Route.HOLD_AWAIT_APPEAL


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
