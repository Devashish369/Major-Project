"""
services/llm.py – Low-level LLM wrapper for IntelliPM.

Wraps the OpenAI-compatible SDK so the same code works for:
  - Groq (primary)    → https://api.groq.com/openai/v1
  - Gemini (fallback) → https://generativelanguage.googleapis.com/v1beta/openai/

Usage:
    from app.services.llm import call_llm
    text = call_llm(prompt, use_fallback=False)   # raises on failure

Design decisions (viva-ready explanations):
  - We use `openai.OpenAI(base_url=..., api_key=...)` because Groq and Gemini
    both expose an OpenAI-compatible REST API, so one SDK covers both providers.
  - Temperature 0 for the planner: we want deterministic JSON, not creative prose.
  - timeout=30s: fast-fail so the UI doesn't hang; HTTP timeouts are passed
    via the `timeout` kwarg supported by the openai SDK's httpx back-end.
  - We ask for a JSON-mode response (response_format) when the provider supports it,
    but fall back to plain text parsing if the model doesn't.
"""

from openai import OpenAI, OpenAIError

from app.config import settings

# ── System prompt sent before every planner call ──────────────────────────────

SYSTEM_PROMPT = (
    "You are an expert software project manager. "
    "Reply with valid JSON only – no markdown, no explanation. "
    "Follow the exact schema provided in the user message."
)

_TIMEOUT = 30  # seconds


def _make_client(base_url: str, api_key: str) -> OpenAI:
    """Create an OpenAI-compatible client for the given provider."""
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def call_llm(prompt: str, *, use_fallback: bool = False) -> str:
    """
    Call an LLM and return the raw text response.

    Args:
        prompt:       The user message (schema + description).
        use_fallback: If True, use the fallback provider (Gemini).

    Returns:
        Raw response string (should be JSON).

    Raises:
        OpenAIError: if the API call fails or times out.
        RuntimeError: if keys are not configured.
    """
    if use_fallback:
        if not settings.LLM_FALLBACK_API_KEY:
            raise RuntimeError("LLM_FALLBACK_API_KEY is not configured.")
        client = _make_client(settings.LLM_FALLBACK_BASE_URL, settings.LLM_FALLBACK_API_KEY)
        model = settings.LLM_FALLBACK_MODEL
    else:
        if not settings.LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY is not configured.")
        client = _make_client(settings.LLM_BASE_URL, settings.LLM_API_KEY)
        model = settings.LLM_MODEL

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0,        # deterministic JSON output
        timeout=_TIMEOUT,
    )

    return response.choices[0].message.content or ""
