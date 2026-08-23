"""
Gemini client used by NetSage AI.

The application can run without an API key. When GEMINI_API_KEY is present,
this module sends the case context to Gemini and requests a JSON diagnosis.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AIResponse:
    ok: bool
    raw_text: str = ""
    provider: str = ""
    model: str = ""
    error: str = ""


class AIClient:
    """Small wrapper around the Google GenAI SDK."""

    def __init__(self) -> None:
        self.provider = os.getenv("AI_PROVIDER", "gemini").strip().lower()
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
        try:
            self.timeout_seconds = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
        except ValueError:
            self.timeout_seconds = 30

    def is_available(self) -> bool:
        return self.provider == "gemini" and bool(self.api_key)

    def status_message(self) -> str:
        if self.provider != "gemini":
            return "Gemini is not selected. Set AI_PROVIDER=gemini."
        if not self.api_key:
            return "Gemini API key not configured — deterministic mode is active."
        return f"Gemini configured — model: {self.model}"

    def generate_json(self, instructions: str, case_input: str) -> AIResponse:
        if not self.is_available():
            return AIResponse(
                ok=False,
                provider="gemini",
                model=self.model,
                error="GEMINI_API_KEY is not configured.",
            )

        try:
            from google import genai
        except ImportError:
            return AIResponse(
                ok=False,
                provider="gemini",
                model=self.model,
                error="google-genai is not installed. Run: pip install -r requirements.txt",
            )

        try:
            client = genai.Client(
                api_key=self.api_key,
                http_options={"timeout": self.timeout_seconds * 1000},
            )
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    f"{instructions}\n\n"
                                    "APPLICATION CASE CONTEXT:\n"
                                    f"{case_input}"
                                )
                            }
                        ],
                    }
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": _diagnosis_schema(),
                    "temperature": 0.2,
                },
            )
            text = getattr(response, "text", "") or ""
            if not text:
                return AIResponse(
                    ok=False,
                    provider="gemini",
                    model=self.model,
                    error="Gemini returned an empty response.",
                )
            return AIResponse(
                ok=True,
                raw_text=text,
                provider="gemini",
                model=self.model,
            )
        except Exception as exc:
            return AIResponse(
                ok=False,
                provider="gemini",
                model=self.model,
                error=str(exc),
            )


def _diagnosis_schema() -> dict[str, Any]:
    """JSON schema requested from Gemini."""
    return {
        "type": "object",
        "properties": {
            "root_cause": {"type": "string"},
            "osi_layer": {"type": "string"},
            "confidence": {"type": "number"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "next_command": {"type": "string"},
            "fix_steps": {"type": "array", "items": {"type": "string"}},
            "concept": {"type": "string"},
            "severity": {"type": "string"},
            "explanation": {"type": "string"},
            "caveats": {"type": "string"},
        },
        "required": [
            "root_cause",
            "osi_layer",
            "confidence",
            "evidence",
            "next_command",
            "fix_steps",
        ],
    }


def extract_json(text: str) -> Optional[dict]:
    """Parse JSON returned by Gemini, with a small safe fallback."""
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
