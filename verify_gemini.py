"""Verify that NetSage can reach Gemini using the configured key.

Run:
    python verify_gemini.py

The script never prints the API key.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from src.ai_client import AIClient

load_dotenv()

client = AIClient()

print("NetSage Gemini configuration check")
print("-----------------------------------")
print(f"Provider: {client.provider}")
print(f"Model: {client.model}")
print(f"API key configured: {'yes' if client.api_key else 'no'}")

if not client.is_available():
    print("\nGemini is not configured.")
    print("Create a .env file from .env.example and add GEMINI_API_KEY.")
    raise SystemExit(1)

response = client.generate_json(
    """
You are checking a network-diagnostics AI connection.
Return only JSON with:
root_cause, osi_layer, confidence, evidence, next_command, fix_steps.
Use a simple test diagnosis and do not claim any real network change was made.
""",
    """
This is a connection test for NetSage AI.
There is no real network incident in this test.
""",
)

if not response.ok:
    print(f"\nGemini request failed: {response.error}")
    raise SystemExit(1)

print("\nGemini API connection: SUCCESS")
print(f"Model response received from: {response.model}")
