"""Voice every line in agent/lines.json with GRIP-9000's voice and cache it on disk.

    python tools/voice_bank.py           # voice new/changed lines, prune orphans
    python tools/voice_bank.py --dry     # just count what would be voiced

Files: assets/voice/cache/<hash>.mp3, plus manifest.json mapping text -> file and
duration. The hash covers text + voice + model, so editing a line (or changing
voice) re-voices only that line. The cache is committed so teammates hear it too.
"""

import argparse
import hashlib
import json
import os
import sys

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

from agent.lines import Bank  # noqa: E402

CACHE_DIR = os.path.join(ROOT, "assets", "voice", "cache")
MANIFEST = os.path.join(CACHE_DIR, "manifest.json")
BANK_MODEL = "eleven_multilingual_v2"


def clip_name(text, voice_id, model):
    digest = hashlib.sha1((text + "|" + voice_id + "|" + model).encode("utf-8")).hexdigest()
    return digest[:16] + ".mp3"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    if not voice_id:
        print("ELEVENLABS_VOICE_ID is empty in .env")
        sys.exit(1)

    bank = Bank()
    lines = bank.all_texts()
    os.makedirs(CACHE_DIR, exist_ok=True)

    old = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as f:
            old = json.load(f).get("lines", {})

    todo = []
    chars = 0
    for key, text in lines:
        name = clip_name(text, voice_id, BANK_MODEL)
        if not os.path.exists(os.path.join(CACHE_DIR, name)):
            todo.append((key, text, name))
            chars += len(text)
    print(str(len(lines)) + " lines in the bank, " + str(len(todo)) + " to voice (" + str(chars) + " characters)")
    if args.dry:
        return

    if todo:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        done = 0
        for key, text, name in todo:
            audio = client.text_to_speech.convert(voice_id=voice_id, text=text, model_id=BANK_MODEL,
                                                  output_format="mp3_44100_128")
            path = os.path.join(CACHE_DIR, name)
            with open(path + ".part", "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            os.replace(path + ".part", path)
            done += 1
            print("  [" + str(done) + "/" + str(len(todo)) + "] " + key + ": " + text)

    # Manifest with durations (needed for subtitle timing).
    import pygame
    pygame.mixer.init(44100, -16, 2, 512)
    manifest = {}
    keep = set()
    for key, text in lines:
        name = clip_name(text, voice_id, BANK_MODEL)
        keep.add(name)
        duration = None
        previous = old.get(text)
        if previous is not None and previous.get("file") == name:
            duration = previous.get("duration")
        if duration is None:
            duration = round(pygame.mixer.Sound(os.path.join(CACHE_DIR, name)).get_length(), 3)
        manifest[text] = {"file": name, "duration": duration, "key": key}
    pygame.mixer.quit()

    with open(MANIFEST, "w") as f:
        json.dump({"voice_id": voice_id, "model": BANK_MODEL, "lines": manifest}, f, indent=1, sort_keys=True)

    pruned = 0
    for name in os.listdir(CACHE_DIR):
        if name.endswith(".mp3") and name not in keep:
            os.remove(os.path.join(CACHE_DIR, name))
            pruned += 1
    total = 0.0
    for text in manifest:
        total += manifest[text]["duration"]
    print("manifest: " + str(len(manifest)) + " clips, " + str(round(total)) + " s of audio, pruned " + str(pruned))


if __name__ == "__main__":
    main()
