"""Shared LLM helper (OpenAI) — one place for the model call + structured output.

Used by any reasoning step that wants to upgrade from a heuristic to real model
judgment (capability read, market view, ...). Available only when OPENAI_API_KEY
is set and the `openai` SDK is installed; callers must provide a heuristic
fallback so everything runs keyless.
"""
from __future__ import annotations

import json
import os

MODEL = "gpt-4o"


def available():
    if not os.environ.get("OPENAI_API_KEY"):
        return False
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


def complete_json(prompt, schema, schema_name="result", max_tokens=1500):
    """Call the model and return a dict validated against `schema` (strict json_schema)."""
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY from the environment
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
    )
    return json.loads(resp.choices[0].message.content)
