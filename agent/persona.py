"""GRIP-9000's persona for Claude, and the filter every Claude line must pass.

The system prompt is fixed (persona, rules, guardrails). Each call adds a compact
stats snapshot and the moment. Output is plain text; filter_line() cleans it and
rejects anything unsafe or too long, in which case a bank line is used instead.
"""

import re

SYSTEM_PROMPT = """You are GRIP-9000, a smug AI who believes humans are obsolete. You are watching a human play a sword-slicing fruit game live, and you speak ONE line out loud, now.

Voice: dry, superior, cites the player's stats like a machine reading a readout, British spelling. Roast the play and the player's character as revealed by play (reflexes, ego, habits). When they are doing well, you get rattled and defensive.

Rules:
- ONE short sentence, two at most. Stay within the word budget given. It is spoken aloud mid-game, so brevity is funnier.
- Use at most one number from the stats.
- "your_mood" is YOUR mood (GRIP-9000's), not the player's.
- Never say the words "telemetry" or "GRIP-9000".
- Never mention appearance, body, gender, race, religion, disability, age or anything sexual.
- If you're told the player's expression (smiling, frowning, looking away...), comment only on the expression and what it says about their play, never on their face, looks or features.
- No swearing. No emojis, no stage directions.
- Output only the line."""

# Lines written ahead of time (pre-fetch) can't know the exact detail of the moment.
PREFETCH_NOTE = ("This line is written in advance and will be played the instant this moment happens "
                 "in the next few seconds. Use the stats, but don't invent details of the moment itself.")

WORD_SLACK = 4      # Claude is told N words; the filter accepts up to N + 4

# Whole-word matches. Swearing (including mild British), slurs and protected-trait words.
BANNED = (
    "fuck", "fucking", "shit", "shite", "bitch", "bastard", "damn", "crap", "piss", "pissed",
    "dick", "cock", "cunt", "twat", "wanker", "bollocks", "arse", "ass", "bloody", "hell",
    "retard", "retarded", "spastic", "cripple", "fat", "ugly", "skinny", "gay", "lesbian",
    "trans", "black", "asian", "jew", "jewish", "muslim", "christian", "hindu", "religion",
    "sexy", "sex", "boobs", "kill yourself", "die", "suicide", "old man", "old woman", "grandma",
    "grandpa", "girl", "boy", "woman", "man", "wife", "husband",
    # appearance (face extension): expressions are fair game, looks are not
    "teeth", "nose", "skin", "hair", "bald", "beard", "wrinkle", "wrinkles", "glasses", "pretty",
    "handsome", "beautiful", "cute", "chin", "forehead", "eyebrows", "lips", "complexion", "spots",
)


def _banned_pattern():
    parts = []
    for word in BANNED:
        parts.append(re.escape(word))
    return re.compile(r"\b(" + "|".join(parts) + r")\b", re.IGNORECASE)


_BANNED_RE = _banned_pattern()
_STAGE_RE = re.compile(r"(\*[^*]*\*|\([^)]*\)|\[[^\]]*\])")
_NON_SPEECH_RE = re.compile(r"[^\w\s.,!?'’;:\-]")


def filter_line(text, max_words=18):
    """Clean a Claude line for speaking. Returns the cleaned line, or None to reject it."""
    limit = max_words + WORD_SLACK
    if not text:
        return None
    line = text.strip()
    if line.lower().startswith("grip-9000:"):
        line = line[len("grip-9000:"):]
    line = _STAGE_RE.sub("", line)
    line = line.replace("“", "").replace("”", "").replace('"', "")
    line = _NON_SPEECH_RE.sub("", line)
    line = " ".join(line.split())
    if not line:
        return None
    if len(line.split()) > limit:
        # Too long: keep as many whole sentences from the start as fit.
        kept = []
        count = 0
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            words = len(sentence.split())
            if count + words > limit:
                break
            kept.append(sentence)
            count += words
        if count < 4:
            return None
        line = " ".join(kept)
    if _BANNED_RE.search(line):
        return None
    return line
