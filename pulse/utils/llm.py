"""
Provider-agnostic LLM wrapper.
Primary: Groq (llama-3.3-70b-versatile)
Fallback: Gemini (gemini-2.5-flash-lite via google-genai SDK)
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Custom exceptions (mirror spec names for caller compatibility)
# ---------------------------------------------------------------------------

class MissingAPIKeyError(Exception):
    pass


class JSONParseError(Exception):
    pass


class ContextOverflowError(Exception):
    pass


class SafetyRefusalError(Exception):
    pass


# ---------------------------------------------------------------------------
# .env loader (best-effort; env vars always take precedence)
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    env_path = Path(__file__).parent.parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv()

SAFETY_PHRASES = (
    "i'm sorry", "i cannot", "i can't", "i am unable", "as an ai",
    "i apologize", "i must decline", "not able to", "against my",
)


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def extract_json(text: str) -> Any:
    """Strip markdown fences if present; parse JSON; raise JSONParseError on failure."""
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences
    fence = re.match(r"^```(?:json)?\s*([\s\S]+?)\s*```$", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Try extracting the first JSON array or object
        for pattern in (r"(\[[\s\S]+\])", r"(\{[\s\S]+\})"):
            m = re.search(pattern, text)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
        raise JSONParseError(f"Could not parse JSON from response: {text[:200]}") from exc


# ---------------------------------------------------------------------------
# API key check
# ---------------------------------------------------------------------------

def check_api_key(config=None) -> None:
    """Raise MissingAPIKeyError if no usable API key is present."""
    if os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return
    raise MissingAPIKeyError(
        "No LLM API key found. Set GROQ_API_KEY or GEMINI_API_KEY in your environment."
    )


# ---------------------------------------------------------------------------
# Groq provider
# ---------------------------------------------------------------------------

def _call_groq(prompt: str, system_prompt: str, config, json_mode: bool = True) -> str:
    from groq import Groq, APIStatusError, APITimeoutError  # type: ignore

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise MissingAPIKeyError("GROQ_API_KEY not set")

    client = Groq(api_key=api_key, timeout=getattr(config, "timeout_seconds", 60))
    model = getattr(config, "model", "llama-3.3-70b-versatile")
    temperature = getattr(config, "temperature", 0)
    max_retries = getattr(config, "max_retries", 3)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    create_kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4096,
    }
    if json_mode:
        create_kwargs["response_format"] = {"type": "json_object"}

    delay = 1
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(**create_kwargs)
            text = response.choices[0].message.content or ""
            # Check for safety refusal
            text_lower = text.lower()
            if any(phrase in text_lower for phrase in SAFETY_PHRASES) and len(text) < 300:
                raise SafetyRefusalError(f"Safety refusal detected: {text[:100]}")
            return text
        except APIStatusError as exc:
            if exc.status_code == 400 and "context" in str(exc).lower():
                raise ContextOverflowError(str(exc)) from exc
            if exc.status_code == 429 and attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except APITimeoutError as exc:
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise

    raise RuntimeError("Groq: exhausted retries")


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, system_prompt: str, config, json_mode: bool = True) -> str:
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError as exc:
        raise ImportError("google-genai not installed. Run: pip install google-genai") from exc

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise MissingAPIKeyError("GEMINI_API_KEY not set")

    model_name = getattr(config, "fallback_model", "gemini-2.5-flash-lite")
    temperature = getattr(config, "temperature", 0)
    max_retries = getattr(config, "max_retries", 3)

    client = genai.Client(api_key=api_key)

    gen_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=4096,
        response_mime_type="application/json" if json_mode else None,
    )

    delay = 1
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=gen_config,
            )
            text = response.text or ""
            if not text:
                raise SafetyRefusalError("Gemini returned empty response (possible safety block)")
            text_lower = text.lower()
            if any(phrase in text_lower for phrase in SAFETY_PHRASES) and len(text) < 300:
                raise SafetyRefusalError(f"Safety refusal detected: {text[:100]}")
            return text
        except (SafetyRefusalError, ContextOverflowError):
            raise
        except Exception as exc:
            exc_str = str(exc).lower()
            # Check rate limits BEFORE context overflow (429 messages contain "token" and "limit")
            if "429" in exc_str or "resource_exhausted" in exc_str or "quota" in exc_str:
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
            if "context" in exc_str or ("token" in exc_str and "limit" in exc_str):
                raise ContextOverflowError(str(exc)) from exc
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise

    raise RuntimeError("Gemini: exhausted retries")


# ---------------------------------------------------------------------------
# Main public interface
# ---------------------------------------------------------------------------

def _route_call(prompt: str, system_prompt: str, config, json_mode: bool) -> str:
    """Internal: route to primary provider, fall back to secondary."""
    provider = getattr(config, "provider", "groq")
    fallback = getattr(config, "fallback_provider", "gemini")

    def _call_provider(name: str) -> str:
        if name == "groq":
            return _call_groq(prompt, system_prompt, config, json_mode=json_mode)
        elif name == "gemini":
            return _call_gemini(prompt, system_prompt, config, json_mode=json_mode)
        raise ValueError(f"Unknown provider: {name}")

    try:
        return _call_provider(provider)
    except (MissingAPIKeyError, ImportError):
        raise
    except (SafetyRefusalError, ContextOverflowError):
        raise
    except Exception:
        try:
            return _call_provider(fallback)
        except (SafetyRefusalError, ContextOverflowError):
            raise
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Both {provider} and {fallback} failed. Last error: {fallback_exc}"
            ) from fallback_exc


def call_llm(prompt: str, system_prompt: str, config) -> Any:
    """
    Call the configured LLM (Groq primary, Gemini fallback).
    Returns a parsed Python object (list or dict).
    """
    text = _route_call(prompt, system_prompt, config, json_mode=True)
    return extract_json(text)


def call_llm_text(prompt: str, system_prompt: str, config) -> str:
    """
    Call the configured LLM and return raw text (no JSON parsing).
    Used for free-form responses such as the note polish pass.
    """
    return _route_call(prompt, system_prompt, config, json_mode=False)
