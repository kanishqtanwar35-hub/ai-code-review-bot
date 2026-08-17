"""Gemini client over plain HTTP.

No SDK on purpose: the REST call is ten lines, it never breaks on a package
upgrade, and you learn what the API actually looks like. Gemini's free tier
makes this project cost nothing.

Get a key at https://aistudio.google.com/apikey
"""

import json
import os
import time
from typing import Optional

import requests

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    """Models sometimes wrap JSON in markdown fences despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        raise LLMError(f"model did not return valid JSON: {text[:200]}") from e


def _read_api_key() -> str:
    """Read and sanitise the key.

    Secrets pasted into a web form or piped from a file routinely arrive with a
    trailing newline or a leading UTF-8 BOM. Both are invisible, and both make
    the request fail deep inside http.client with
    `'latin-1' codec can't encode character '\\ufeff'` — an error that looks
    like a library bug and is actually a whitespace bug. Strip them here, once.
    """
    raw = os.environ.get("GEMINI_API_KEY", "")
    cleaned = raw.strip().lstrip("﻿").strip()
    if not cleaned:
        raise LLMError("GEMINI_API_KEY is not set")
    return cleaned


def review_hunk(system: str, user: str, retries: int = 3) -> dict:
    api_key = _read_api_key()

    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": 0.1,          # review is not a creative task
            "maxOutputTokens": 400,
            "responseMimeType": "application/json",
        },
    }

    url = ENDPOINT.format(model=MODEL)
    last_error: Optional[Exception] = None

    # The key goes in a HEADER, never in the query string. A `?key=...` URL
    # ends up inside requests' exception messages, which get printed straight
    # into CI logs — and Actions only redacts values registered as secrets in
    # the exact form it knows. A key embedded in a URL fragment can slip
    # through. Headers are never echoed back in exception text.
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    for attempt in range(retries):
        try:
            r = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=45,
            )
            # 429 = free-tier rate limit. Back off rather than giving up.
            if r.status_code == 429:
                wait = 2 ** (attempt + 2)
                time.sleep(wait)
                continue
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _extract_json(text)
        except Exception as e:
            last_error = e
            time.sleep(2 ** attempt)

    raise LLMError(f"review failed after {retries} attempts: {last_error}")
