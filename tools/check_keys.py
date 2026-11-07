"""Check the API keys in .env work, without ever printing them.

    python tools/check_keys.py

Run it on demo morning too. Costs: one ~20-token Claude Haiku call, and
ElevenLabs voices one short line (~40 characters).
"""

import os
import sys
import time

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

CLAUDE_MODEL = "claude-haiku-5-5"
EL_FLASH_MODEL = "eleven_flash_v2_5"
TEST_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # ElevenLabs premade voice "George", only used if no voice is chosen yet
TEST_LINE = "GRIP-9000 online. Your keys are acceptable."

ok_all = True


def report(name, ok, detail):
    global ok_all
    if not ok:
        ok_all = False
    print(("PASS  " if ok else "FAIL  ") + name + "  (" + detail + ")")


def safe_error(exc):
    """Error text with any key value scrubbed out, just in case."""
    text = type(exc).__name__ + ": " + str(exc)
    for var in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"):
        secret = os.environ.get(var) or ""
        if secret:
            text = text.replace(secret, "<" + var + ">")
    return text[:300]


def check_anthropic():
    import anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        report("Anthropic key", False, "ANTHROPIC_API_KEY is empty in .env")
        return
    client = anthropic.Anthropic(timeout=10.0, max_retries=0)
    started = time.monotonic()
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=20,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": "Reply with exactly: ready"}],
        )
    except Exception as exc:
        report("Anthropic key + " + CLAUDE_MODEL, False, safe_error(exc))
        return
    ms = round((time.monotonic() - started) * 1000)
    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text
    report("Anthropic key + " + CLAUDE_MODEL, True, "replied " + repr(text.strip()) + " in " + str(ms) + " ms")


def check_elevenlabs():
    from elevenlabs.client import ElevenLabs
    if not os.environ.get("ELEVENLABS_API_KEY"):
        report("ElevenLabs key", False, "ELEVENLABS_API_KEY is empty in .env")
        return
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

    try:
        sub = client.user.subscription.get()
        left = sub.character_limit - sub.character_count
        report("ElevenLabs quota (User: Read)", True,
               "tier " + str(sub.tier) + ", " + str(left) + " of " + str(sub.character_limit) + " characters left")
    except Exception as exc:
        report("ElevenLabs quota (User: Read)", False, safe_error(exc))

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or TEST_VOICE_ID
    started = time.monotonic()
    first_chunk_ms = None
    total = 0
    try:
        stream = client.text_to_speech.stream(
            voice_id=voice_id,
            text=TEST_LINE,
            model_id=EL_FLASH_MODEL,
            output_format="pcm_22050",
        )
        for chunk in stream:
            if first_chunk_ms is None:
                first_chunk_ms = round((time.monotonic() - started) * 1000)
            total += len(chunk)
    except Exception as exc:
        report("ElevenLabs TTS stream (Text to Speech)", False, safe_error(exc))
        return
    seconds = total / 2 / 22050.0
    report("ElevenLabs TTS stream (Text to Speech)", total > 0,
           "first audio in " + str(first_chunk_ms) + " ms, " + str(round(seconds, 1)) + " s of audio")


def main():
    check_anthropic()
    check_elevenlabs()
    print("")
    print("KEYS: " + ("ALL GOOD" if ok_all else "PROBLEM (see FAIL lines)"))
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
