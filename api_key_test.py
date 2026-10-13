"""Quick check that an Anthropic API key is valid and can reach the API.

Usage:
    uv run python api_key_test.py

The key is read from ANTHROPIC_API_KEY (environment variable or a .env file).
"""

import os
import sys

import anthropic

try:
    from dotenv import load_dotenv

    # Load .env from this folder, if present
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

MODEL = "claude-opus-5-5"


def main() -> int:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ANTHROPIC_API_KEY is not set (env var or .env file).")
        return 1
    print(f"Using key: {key[:10]}...{key[-4:]}")

    client = anthropic.Anthropic(api_key=key)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": "Reply with exactly: API key works!"}],
        )
    except anthropic.AuthenticationError:
        print("FAIL: invalid API key (401).")
        return 1
    except anthropic.PermissionDeniedError:
        print("FAIL: key lacks permission for this model/resource (403).")
        return 1
    except anthropic.RateLimitError:
        print("Key is valid, but you are rate limited (429). Try again shortly.")
        return 1
    except anthropic.APIStatusError as e:
        print(f"FAIL: API error {e.status_code}: {e.message}")
        return 1
    except anthropic.APIConnectionError as e:
        print(f"FAIL: could not connect to the API: {e}")
        return 1

    text = "".join(b.text for b in response.content if b.type == "text")
    print(f"SUCCESS ({response.model}): {text.strip()}")
    print(f"Tokens used: {response.usage.input_tokens} in / {response.usage.output_tokens} out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
