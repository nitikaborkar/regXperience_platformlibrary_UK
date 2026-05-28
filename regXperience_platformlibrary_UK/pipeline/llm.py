"""
Thin wrapper around the LLM provider.
Set LLM_PROVIDER=anthropic (default) or openai in .env.
"""

from __future__ import annotations
import json
import os
import re


def _strip_fences(text: str) -> str:
    """Remove ```json … ``` or ``` … ``` markdown fences."""
    return re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE).rstrip("```").strip()


def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    expect_json: bool = True,
) -> str:
    """
    Single LLM call. Returns the raw text response.
    Raises RuntimeError on API failure.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()

    if provider == "anthropic":
        return _call_anthropic(system_prompt, user_prompt, max_tokens, temperature)
    elif provider == "openai":
        return _call_openai(system_prompt, user_prompt, max_tokens, temperature)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Use 'anthropic' or 'openai'.")


def call_llm_json(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> dict | list:
    """Convenience wrapper that parses the response as JSON."""
    raw = call_llm(system_prompt, user_prompt, max_tokens=max_tokens, expect_json=True)
    clean = _strip_fences(raw)
    try:
        return json.loads(clean)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}\n\nRaw response:\n{raw}") from exc


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _call_anthropic(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    import anthropic  # type: ignore

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def _call_openai(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content
