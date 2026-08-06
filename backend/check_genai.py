"""
Verify GenAI is wired up correctly against the Echios LiteLLM proxy.

Usage (from the backend/ folder, venv active):
    python check_genai.py

Makes ONE tiny call (a few tokens) so it costs essentially nothing.
"""
import sys

from app.core.config import settings
from app.services.genai_client import _get_claude_client, active_model


def main() -> int:
    provider = (settings.GENAI_PROVIDER or "gemini").strip().lower()
    model = active_model()

    print("GenAI configuration")
    print(f"  provider    : {provider}")
    print(f"  model       : {model}")
    if provider == "anthropic":
        print(f"  base_url    : {settings.ANTHROPIC_BASE_URL or '(unset)'}")
    print(f"  max tokens  : {settings.GENAI_MAX_TOKENS}")

    if provider == "none":
        print()
        print("AI disabled by GENAI_PROVIDER=none — deterministic fallbacks only.")
        return 0

    key = settings.GEMINI_API_KEY if provider == "gemini" else settings.ANTHROPIC_API_KEY
    key_name = "GEMINI_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY"
    if not key:
        print("  api key     : NOT SET")
        print()
        print("No key configured — the app runs on deterministic fallbacks (zero spend).")
        print(f"To enable AI: set {key_name} in backend/.env")
        return 0

    print(f"  api key     : set ({key[:6]}...{key[-4:]}, {len(key)} chars)")

    client = _get_claude_client()
    if client is None:
        print()
        print("FAIL: client could not be constructed.")
        if provider == "anthropic":
            print("Is the `anthropic` package installed?  pip install anthropic")
        return 1

    print()
    print(f"Calling {model}...")
    try:
        response = client.messages.create(
            model=model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        )
        text = response.content[0].text if response.content else "(empty)"
        print(f"SUCCESS — model replied: {text.strip()!r}")
        print()
        print("AI features are live. Journal coaching, portfolio summaries, order")
        print("parsing and ticker explanations will now use the model.")
        return 0
    except Exception as exc:  # noqa: BLE001 - we want the raw reason surfaced
        print(f"FAILED: {type(exc).__name__}: {exc}")
        print()
        msg = str(exc).lower()
        if "not found" in msg or "404" in msg:
            print(f"Hint: '{model}' may not be available to this key.")
            if provider == "gemini":
                print("      Try GEMINI_MODEL=gemini-2.5-flash in backend/.env")
            else:
                print("      Try GENAI_MODEL=claude-haiku-4-5 in backend/.env")
        elif "401" in msg or "403" in msg or "auth" in msg or "credential" in msg or "api key" in msg:
            print("Hint: the key looks wrong, expired, or lacks access. Re-copy it.")
        elif "429" in msg or "quota" in msg or "exhausted" in msg:
            print("Hint: rate limit / quota exhausted. Wait, or switch provider.")
        elif "connect" in msg or "timeout" in msg or "resolve" in msg:
            print("Hint: network unreachable — check connection/VPN/proxy.")
        print()
        print("The app still works regardless — every AI feature falls back to")
        print("deterministic output rather than erroring.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
