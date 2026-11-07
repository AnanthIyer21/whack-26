"""Audition ElevenLabs voices for GRIP-9000.

    python tools/audition_voices.py              # generate (if needed) and play round 2
    python tools/audition_voices.py --round 1    # play round 1
    python tools/audition_voices.py --only lily  # replay one candidate
    python tools/audition_voices.py --list       # just print the candidates

Each candidate says the same lines with eleven_multilingual_v2 (the model for the
cached bank), then one line with eleven_flash_v2_5 (the model for live Claude
lines), so you can hear whether the live voice still matches. Clips are saved in
logs/audition/ (gitignored), so replays cost nothing.
Put the winner's id in .env as ELEVENLABS_VOICE_ID.
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

OUT_DIR = os.path.join(ROOT, "logs", "audition")
BANK_MODEL = "eleven_multilingual_v2"
LIVE_MODEL = "eleven_flash_v2_5"

# (round, name, voice_id, blurb). Round 2 voices come from the ElevenLabs shared library.
CANDIDATES = (
    (1, "daniel", "onwK4e9ZLuTAKqWW03F9", "British broadcaster, formal: cold machine reading your stats"),
    (1, "george", "JBFqnCBsd6RMkjVDRZzb", "British, mature storyteller: posh condescension"),
    (1, "lily", "pFZP5JQG7iQjIQuC4Bku", "British, velvety, confident: female smug AI"),
    (1, "callum", "N2lVS1w4EtoT3dr4eOWO", "Husky trickster: the most 'villain'"),
    (1, "eric", "cjVigY5qzO86Huf0OWal", "American, smooth: slick and patronising"),
    (2, "eric", "cjVigY5qzO86Huf0OWal", "BENCHMARK: round 1 favourite"),
    (2, "edward", "zYcjlYFOd3taleS0gkk3", "American, 'smug and charismatic, wicked charm' (83k uses)"),
    (2, "matthew", "JlPfrZoXeAKnNaogINHc", "American, robotic and deadpan, smooth"),
    (2, "james", "Myb1gsDenT3mlMlj7vib", "American, sarcastic, casual, skeptical"),
    (2, "sigma", "bAq8AI9QURijOtmeFFqT", "American, calm space-computer AI"),
    (2, "josh", "NXaTw4ifg0LAguvKuIwZ", "British RP, 'arrogant, smug' (16k uses)"),
    (2, "nigel", "50lF5fQMqcxbDQOW6qOs", "British, sarcastic, cynical about everything"),
)

LINES = (
    "GRIP-9000 online. Please try not to embarrass your entire species.",
    "Left-side accuracy: thirty-one percent. Is your left arm decorative?",
    "Twelve in a row? That is... statistically irritating. Stop it.",
    "You hugged the bomb. Bold. Stupid, but bold.",
)
LIVE_LINE = "Twelve in a row, and then you hug a bomb. Magnificent."


def clip_path(name, index, model):
    tag = "bank" if model == BANK_MODEL else "live"
    return os.path.join(OUT_DIR, name + "_" + str(index) + "_" + tag + ".mp3")


def generate(client, name, voice_id):
    jobs = []
    index = 0
    for line in LINES:
        jobs.append((index, line, BANK_MODEL))
        index += 1
    jobs.append((index, LIVE_LINE, LIVE_MODEL))

    for index, line, model in jobs:
        path = clip_path(name, index, model)
        if os.path.exists(path):
            continue
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            text=line,
            model_id=model,
            output_format="mp3_44100_128",
        )
        with open(path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        print("  generated " + os.path.basename(path))


def play(name):
    import pygame
    index = 0
    total = len(LINES) + 1
    while index < total:
        model = BANK_MODEL if index < len(LINES) else LIVE_MODEL
        path = clip_path(name, index, model)
        if os.path.exists(path):
            label = "bank" if model == BANK_MODEL else "LIVE (flash)"
            print("    [" + label + "] " + (LINES[index] if index < len(LINES) else LIVE_LINE))
            sound = pygame.mixer.Sound(path)
            channel = sound.play()
            while channel.get_busy():
                time.sleep(0.05)
            time.sleep(0.4)
        index += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="candidate name, e.g. lily")
    parser.add_argument("--round", type=int, default=2, help="which round of candidates to play")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    chosen = []
    for round_no, name, voice_id, blurb in CANDIDATES:
        if args.only is not None:
            if args.only == name:
                chosen.append((name, voice_id, blurb))
                break
        elif round_no == args.round:
            chosen.append((name, voice_id, blurb))
    if args.list or not chosen:
        for round_no, name, voice_id, blurb in CANDIDATES:
            print("round " + str(round_no) + "  " + name.ljust(8) + voice_id + "  " + blurb)
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    from elevenlabs.client import ElevenLabs
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    for name, voice_id, blurb in chosen:
        print("Generating " + name + "...")
        generate(client, name, voice_id)

    import pygame
    pygame.mixer.init(44100, -16, 2, 512)
    for name, voice_id, blurb in chosen:
        print("")
        print("=== " + name.upper() + "  (" + voice_id + ")  " + blurb)
        play(name)
        time.sleep(0.8)
    pygame.mixer.quit()
    print("")
    print("Replay one with: python tools/audition_voices.py --only <name>")


if __name__ == "__main__":
    main()
