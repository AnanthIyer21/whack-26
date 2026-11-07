"""Head-to-head of two finalist voices across GRIP-9000's moods.

    python tools/voice_faceoff.py            # plays each line by Eric, then Edward
"""

import os
import sys
import time

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
OUT_DIR = os.path.join(ROOT, "logs", "audition", "faceoff")

VOICES = (
    ("eric", "cjVigY5qzO86Huf0OWal"),
    ("edward", "zYcjlYFOd3taleS0gkk3"),
)
# (mood, model, line)
LINES = (
    ("smug", "eleven_multilingual_v2", "Ah, a human. Hold the sword by the pointy end's opposite. Good luck."),
    ("rattled", "eleven_multilingual_v2", "Fifteen in a row? No. No, that's a glitch. Recalibrating. Stop that."),
    ("defensive", "eleven_multilingual_v2", "New best score? Fine. I wasn't even trying. I was running at four percent."),
    ("gloating", "eleven_multilingual_v2", "Last life. I've prepared a short eulogy. It's mostly about your left arm."),
    ("final roast (LIVE flash)", "eleven_flash_v2_5",
     "One hundred and forty points, three bombs, and seven misses on the left. Humanity had a good run. Mostly."),
)


def main():
    from elevenlabs.client import ElevenLabs
    import pygame
    os.makedirs(OUT_DIR, exist_ok=True)
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    index = 0
    for mood, model, line in LINES:
        for name, voice_id in VOICES:
            path = os.path.join(OUT_DIR, name + "_" + str(index) + ".mp3")
            if not os.path.exists(path):
                audio = client.text_to_speech.convert(voice_id=voice_id, text=line, model_id=model,
                                                      output_format="mp3_44100_128")
                with open(path, "wb") as f:
                    for chunk in audio:
                        f.write(chunk)
        index += 1
    if "--generate-only" in sys.argv:
        return
    pygame.mixer.init(44100, -16, 2, 512)
    index = 0
    for mood, model, line in LINES:
        print("")
        print("[" + mood + "] " + line)
        for name, voice_id in VOICES:
            print("   " + name)
            channel = pygame.mixer.Sound(os.path.join(OUT_DIR, name + "_" + str(index) + ".mp3")).play()
            while channel.get_busy():
                time.sleep(0.05)
            time.sleep(0.5)
        index += 1
    pygame.mixer.quit()


if __name__ == "__main__":
    main()
