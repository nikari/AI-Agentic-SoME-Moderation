"""Streamlit UI for the moderation pipeline.

Run with:
    uv run streamlit run scripts/app.py
"""

import asyncio

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from moderation.agents.moderator import _run_agent  # noqa: E402
from moderation.models import APPEAL_MODEL  # noqa: E402
from moderation.pipeline import REPORT_RATE_THRESHOLD, run_pipeline  # noqa: E402
from moderation.routing import route_appeal, route_initial  # noqa: E402
from moderation.schemas import (  # noqa: E402
    AppealRoute,
    ModerationDecision,
    Post,
    RecommendedAction,
    Route,
    ViolationCategory,
)
from moderation.tracing import setup_tracing  # noqa: E402

setup_tracing()


def _reset() -> None:
    for key in (
        "stage",
        "report",
        "route",
        "post",
        "appeal_route",
        "panel_votes",
        "final_message",
        "pending_reports",
    ):
        st.session_state[key] = {"stage": "input", "pending_reports": []}.get(key)
    st.session_state.stage = "input"


_ACTION_LABELS: dict[RecommendedAction, str] = {
    RecommendedAction.NONE: "No action",
    RecommendedAction.FLAG: "Flag for review",
    RecommendedAction.REMOVE: "Remove",
    RecommendedAction.SHADOW_BAN: "Shadow ban",
    RecommendedAction.ESCALATE: "Escalate to human",
}

_ROUTE_LABELS: dict[Route, str] = {
    Route.AUTO_PUBLISH: "✅ Auto-published",
    Route.SINGLE_REVIEW_FINAL: "👤 Single human review (no appeal)",
    Route.HOLD_AWAIT_APPEAL: "⏸️ Held — sender may appeal",
}

# ── Session state init ────────────────────────────────────────────────────────

for _key, _default in [
    ("stage", "input"),  # input | moderated | appealing | done
    ("report", None),
    ("route", None),
    ("post", None),
    ("appeal_route", None),
    ("panel_votes", []),
    ("final_message", None),
    ("pending_reports", []),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

# ── Page chrome ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="Content Moderator", page_icon="🛡️", layout="centered")
st.title("🛡️ AI Content Moderator")


# ── Stage: input ──────────────────────────────────────────────────────────────

if st.session_state.stage == "input":
    post_text = st.text_area(
        "Paste a social media post to moderate",
        height=150,
        placeholder="e.g. Send me 1 ETH and I'll send back 10x — limited time only!",
    )

    views_input = st.number_input("Views", min_value=0, value=0, step=1)
    post_views = int(views_input) if views_input > 0 else None

    st.write("**Image** (optional)")
    uploaded_image = st.file_uploader(
        "Upload an image",
        type=["jpg", "jpeg", "png", "gif", "webp"],
        label_visibility="collapsed",
    )
    if uploaded_image:
        image_bytes = uploaded_image.read()
        image_type = uploaded_image.type
        st.image(image_bytes, caption="Uploaded image", width=300)
    else:
        image_bytes = None
        image_type = None

    def _run_analysis() -> None:
        post = Post(
            id="ui-post",
            content=post_text.strip(),
            image_data=image_bytes,
            image_media_type=image_type,
            views=post_views,
            report_types=[ViolationCategory(r) for r in st.session_state.pending_reports],
        )
        try:
            report = asyncio.run(run_pipeline(post))
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.exception(e)
            st.stop()
        st.session_state.post = post
        st.session_state.report = report
        st.session_state.route = route_initial(report)
        st.session_state.stage = "moderated"

    st.write("**Reports**")
    _CATEGORY_LABELS = {v: v.value.replace("_", " ").title() for v in ViolationCategory}
    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        selected_type = st.selectbox(
            "Report type",
            options=list(ViolationCategory),
            format_func=lambda v: _CATEGORY_LABELS[v],
            label_visibility="collapsed",
        )
    with col_btn:
        st.write("")  # vertical alignment nudge
        if st.button("Add", use_container_width=True):
            st.session_state.pending_reports.append(selected_type.value)
            n = len(st.session_state.pending_reports)
            threshold_crossed = post_views and n / post_views >= REPORT_RATE_THRESHOLD
            if threshold_crossed and (post_text.strip() or image_bytes):
                with st.spinner(f"Threshold reached ({n}/{post_views}) — analysing…"):
                    _run_analysis()
            st.rerun()

    if st.session_state.pending_reports:
        counts: dict[str, int] = {}
        for r in st.session_state.pending_reports:
            counts[r] = counts.get(r, 0) + 1
        summary = "  |  ".join(
            f"{k.replace('_', ' ').title()} ×{v}" for k, v in counts.items()
        )
        col_sum, col_clr = st.columns([4, 1])
        with col_sum:
            st.caption(f"Added: {summary}")
        with col_clr:
            if st.button("Clear", use_container_width=True):
                st.session_state.pending_reports = []
                st.rerun()


# ── Stage: moderated ──────────────────────────────────────────────────────────

if st.session_state.stage in ("moderated", "appealing", "done"):
    report = st.session_state.report
    route = st.session_state.route
    post = st.session_state.post

    st.divider()

    if post.image_data:
        st.image(post.image_data, caption="Submitted image", use_container_width=True)

    skipped = (
        post.views
        and report.verdict == ModerationDecision.ALLOWED
        and "threshold" in (report.reasoning or "")
    )
    if skipped:
        n = len(post.report_types)
        rate = n / post.views  # type: ignore[operator]
        st.info(
            f"AI moderation skipped — report rate {n}/{post.views}"
            f" ({rate:.1%}) is below the 5% threshold."
        )

    # Verdict banner
    if report.verdict == ModerationDecision.FLAGGED:
        st.error("⚠️ Post flagged")
    else:
        st.success("✅ Post allowed")

    # Metrics
    col1, col2 = st.columns(2)
    with col1:
        conf_display = "—" if report.confidence is None else f"{report.confidence:.0%}"
        st.metric("Confidence", conf_display)
    with col2:
        st.metric("Severity", report.severity.value.capitalize() if report.severity else "—")

    if report.violations:
        st.subheader("Violation scores")
        for v in report.violations:
            label = v.category.value.replace("_", " ").title()
            st.progress(v.score, text=f"{label} — {v.score:.0%}")

    if report.recommended_action != RecommendedAction.NONE:
        st.subheader("Recommended action")
        st.info(_ACTION_LABELS[report.recommended_action])

    if report.reasoning:
        st.subheader("Reasoning")
        st.write(report.reasoning)

    if report.dsa_explanation:
        with st.expander("DSA Art. 17 Statement of Reasons"):
            st.write(report.dsa_explanation)

    # Route badge
    st.divider()
    col_route, col_new = st.columns([4, 1])
    with col_route:
        st.subheader("Routing decision")
        st.write(_ROUTE_LABELS[route])
    with col_new:
        st.write("")
        if st.button("＋ New post", use_container_width=True):
            _reset()
            st.rerun()

    # ── SINGLE_REVIEW_FINAL: inline human review ──────────────────────────────
    if route == Route.SINGLE_REVIEW_FINAL and st.session_state.stage == "moderated":
        st.info("Low-confidence flag — one human reviewer makes the final call.")
        col_a, col_b = st.columns(2)
        if col_a.button("✅ Approve (publish)", use_container_width=True):
            st.session_state.final_message = "Human reviewer approved — post published."
            st.session_state.stage = "done"
            st.rerun()
        if col_b.button("🚫 Deny (block)", use_container_width=True):
            st.session_state.final_message = (
                "Human reviewer upheld the block. This decision is final."
            )
            st.session_state.stage = "done"
            st.rerun()

    # ── HOLD_AWAIT_APPEAL: appeal button ──────────────────────────────────────
    if route == Route.HOLD_AWAIT_APPEAL and st.session_state.stage == "moderated":
        st.info("Post is held. The sender has been notified and may appeal.")
        if st.button("📨 Sender submits appeal", type="secondary"):
            appeal_route = route_appeal(report.confidence)
            st.session_state.appeal_route = appeal_route
            st.session_state.stage = "appealing"
            st.rerun()

    # ── Appeal flow ───────────────────────────────────────────────────────────
    if st.session_state.stage == "appealing":
        appeal_route = st.session_state.appeal_route
        st.divider()
        st.subheader("Appeal")

        # AI re-evaluation
        if appeal_route == AppealRoute.AI_REEVAL:
            st.write(
                f"Confidence {report.confidence:.0%} > 90% → "
                "AI re-evaluation with a stronger model."
            )
            if st.button("▶️ Run AI re-evaluation", type="primary"):
                with st.spinner("Re-evaluating…"):
                    try:
                        reeval = asyncio.run(_run_agent(post, model=APPEAL_MODEL))
                    except Exception as e:
                        st.error(f"Re-evaluation error: {e}")
                        st.stop()
                if reeval.decision == ModerationDecision.ALLOWED:
                    st.session_state.final_message = (
                        "Appeal granted — AI re-evaluation no longer flags this content."
                    )
                    st.session_state.stage = "done"
                else:
                    st.write(f"**Re-eval confidence:** {reeval.confidence:.0%}")
                    if reeval.confidence > 0.90:
                        st.session_state.final_message = (
                            f"Appeal denied — AI re-evaluation upheld the block "
                            f"(confidence {reeval.confidence:.0%}). Reason: {reeval.reasoning}"
                        )
                        st.session_state.stage = "done"
                    else:
                        # Drop to human review with new confidence
                        new_route = route_appeal(reeval.confidence)
                        st.session_state.appeal_route = new_route
                        st.session_state.report = st.session_state.report.model_copy(
                            update={"confidence": reeval.confidence}
                        )
                st.rerun()

        # Human review (single reviewer)
        elif appeal_route == AppealRoute.HUMAN_REVIEW:
            st.write(f"Confidence {report.confidence:.0%} → single human reviewer.")
            col_a, col_b = st.columns(2)
            if col_a.button("✅ Approve (publish)", use_container_width=True):
                st.session_state.final_message = (
                    "Human reviewer approved the appeal — post published."
                )
                st.session_state.stage = "done"
                st.rerun()
            if col_b.button("🚫 Deny (uphold block)", use_container_width=True):
                st.session_state.final_message = "Human reviewer denied the appeal — block stands."
                st.session_state.stage = "done"
                st.rerun()

        # 3-person panel
        elif appeal_route == AppealRoute.HUMAN_REVIEW_WITH_PANEL:
            st.write(f"Confidence {report.confidence:.0%} ≤ 70% → 3-person panel. Majority rules.")
            votes = st.session_state.panel_votes
            for i in range(3):
                if i < len(votes):
                    icon = "✅" if votes[i] == "approve" else "🚫"
                    label = "Approve" if votes[i] == "approve" else "Deny"
                    st.write(f"Reviewer {i + 1}: {icon} {label}")
                else:
                    col_a, col_b = st.columns(2)
                    if col_a.button(f"✅ Reviewer {i + 1} approves", use_container_width=True):
                        st.session_state.panel_votes = votes + ["approve"]
                        st.rerun()
                    if col_b.button(f"🚫 Reviewer {i + 1} denies", use_container_width=True):
                        st.session_state.panel_votes = votes + ["deny"]
                        st.rerun()
                    break  # only show one pending reviewer at a time

            if len(st.session_state.panel_votes) == 3:
                approves = st.session_state.panel_votes.count("approve")
                if approves >= 2:
                    st.session_state.final_message = (
                        f"Panel approved ({approves}/3) — post published."
                    )
                else:
                    st.session_state.final_message = (
                        f"Panel denied ({approves}/3 approve) — block stands."
                    )
                st.session_state.stage = "done"
                st.rerun()

# ── Stage: done ───────────────────────────────────────────────────────────────

if st.session_state.stage == "done":
    st.divider()
    st.subheader("Final outcome")
    msg = st.session_state.final_message or "Case resolved."
    if "published" in msg.lower() or "approved" in msg.lower():
        st.success(msg)
    else:
        st.error(msg)

    if st.button("＋ New post"):
        _reset()
        st.rerun()
