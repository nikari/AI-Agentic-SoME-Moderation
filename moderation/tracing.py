"""Langfuse tracing setup via LiteLLM callbacks.

Call setup_tracing() once at application startup before any LLM calls.
Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env.
"""

import os

import litellm


def setup_tracing() -> None:
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        return
    if "langfuse" not in (litellm.success_callback or []):
        litellm.success_callback = ["langfuse"]
    if "langfuse" not in (litellm.failure_callback or []):
        litellm.failure_callback = ["langfuse"]
