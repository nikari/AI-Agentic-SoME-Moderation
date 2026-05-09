"""Streamlit UI for the moderation pipeline.

Run with:
    uv run streamlit run scripts/app.py
"""

import asyncio

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from moderation.pipeline import run_pipeline  # noqa: E402
from moderation.schemas import ModerationDecision, Post, RecommendedAction  # noqa: E402
from moderation.tracing import setup_tracing  # noqa: E402

setup_tracing()

_ACTION_LABELS: dict[RecommendedAction, str] = {
    RecommendedAction.NONE: "No action",
    RecommendedAction.FLAG: "Flag for review",
    RecommendedAction.REMOVE: "Remove",
    RecommendedAction.SHADOW_BAN: "Shadow ban",
    RecommendedAction.ESCALATE: "Escalate to human",
}

_SEVERITY_COLOURS: dict[str, str] = {
    "low": "#f0ad4e",
    "medium": "#d9534f",
    "high": "#c9302c",
    "critical": "#7b0000",
}

st.set_page_config(page_title="Content Moderator", page_icon="🛡️", layout="centered")
st.title("🛡️ AI Content Moderator")
st.caption("Crypto scam detection · DSA Art. 17 compliant")

post_text = st.text_area(
    "Paste a social media post to moderate",
    height=150,
    placeholder="e.g. Send me 1 ETH and I'll send back 10x — limited time only!",
)

if st.button("Analyse", type="primary", disabled=not post_text.strip()):
    with st.spinner("Analysing post…"):
        post = Post(id="ui-post", content=post_text.strip())
        try:
            report = asyncio.run(run_pipeline(post))
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.exception(e)
            st.stop()

    st.divider()

    if report.verdict == ModerationDecision.FLAGGED:
        st.error("⚠️ Post flagged")
    else:
        st.success("✅ Post allowed")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Confidence", f"{report.confidence:.0%}")

    with col2:
        severity_label = report.severity.value.capitalize() if report.severity else "—"
        st.metric("Severity", severity_label)

    st.subheader("Violations")
    if report.violations:
        for v in report.violations:
            label = v.category.value.replace("_", " ").title()
            st.progress(v.score, text=f"{label} — {v.score:.0%}")
            if v.reasoning:
                st.caption(v.reasoning)
    else:
        st.write("—")

    st.subheader("Recommended action")
    st.info(_ACTION_LABELS[report.recommended_action])

    if report.reasoning:
        st.subheader("Reasoning")
        st.write(report.reasoning)

    if report.dsa_explanation:
        with st.expander("DSA Art. 17 Statement of Reasons"):
            st.write(report.dsa_explanation)
