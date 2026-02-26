"""Shared model resolution for all agents.

Reads MODEL_NAME from the environment and returns the appropriate ADK model:
  - gemini-*          → passed directly to ADK (uses GOOGLE_API_KEY)
  - openrouter/*      → LiteLlm wrapper (uses OPENROUTER_API_KEY)
  - ollama_chat/*     → LiteLlm wrapper pointing at OLLAMA_API_BASE
  - anything else     → treated as Ollama model name (prefixed with ollama_chat/)
"""
from __future__ import annotations

import os


def _litellm_model_name() -> str:
    """Return the raw LiteLLM model string (for direct litellm.completion calls)."""
    name = os.getenv("MODEL_NAME", "gemini-2.0-flash")
    if name.startswith("openrouter/") or name.startswith("gemini"):
        return name
    # Ollama
    return name if name.startswith("ollama") else f"ollama_chat/{name}"


def resolve_model():
    """Return an ADK-compatible model identifier based on MODEL_NAME env var."""
    name = os.getenv("MODEL_NAME", "gemini-2.0-flash")

    if name.startswith("gemini"):
        return name

    from google.adk.models.lite_llm import LiteLlm

    if name.startswith("openrouter/"):
        return LiteLlm(model=name)

    # Ollama — ensure the ollama_chat/ prefix LiteLLM expects
    litellm_name = name if name.startswith("ollama") else f"ollama_chat/{name}"
    return LiteLlm(model=litellm_name)
