"""Download the third-party CC0/OFL assets, convert them to the manifest names, write CREDITS.md.

Usage:  python tools/fetch_assets.py [download_dir]
        (default download_dir: ~/Downloads/whack26_packs; zips are cached there)
Needs:  pip install soundfile   (tool-only: used to write .ogg; the game doesn't need it)

Every sound is: leading silence trimmed, peak-normalised, gain applied, resampled to
44.1 kHz, written as Ogg Vorbis to assets/sounds/<name>.ogg.
"""
import os
import subprocess
import sys
import zipfile

import numpy as np
import soundfile as sf

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
OGA = "https://opengameart.org/sites/default/files/"
SR = 44100

PACKS = {
    # key: (zip url, page url, title, author, licence)
    "sfx512": (OGA + "The%20Essential%20Retro%20Video%20Game%20Sound%20Effects%20Collection%20%5B512%20sounds%5D.zip",
               "https://opengameart.org/content/512-sound-effects-8-bit-style",
               "512 Sound Effects (8-bit style)", "Juhani Junkala (SubspaceAudio)", "CC0"),
    "chip": (OGA + "5%20Action%20Chiptunes%20By%20Juhani%20Junkala.zip",
             "https://opengameart.org/content/5-chiptunes-action",
             "5 Chiptunes (Action)", "Juhani Junkala (SubspaceAudio)", "CC0"),
    "rpg": (OGA + "80-CC0-RPG-SFX_0.zip", "https://opengameart.org/content/80-cc0-rpg-sfx",
            "80 CC0 RPG SFX", "rubberduck", "CC0"),
    "swish": (OGA + "swishes.zip", "https://opengameart.org/content/swishes-sound-pack",
              "Swishes Sound Pack", "artisticdude", "CC0"),
    "synth": (OGA + "50-CC0-retro-synth-SFX.zip", "https://opengameart.org/content/50-cc0-retro-synth-sfx",
              "50 CC0 retro / synth SFX", "rubberduck", "CC0"),
}

SFX512 = "The Essential Retro Video Game Sound Effects Collection [512 sounds] By Juhani Junkala/"
CHIP = "Juhani Junkala [Retro Game Music Pack] "

# output name -> (pack, path inside zip, gain relative to peak 1.0)
# A list of (pack, path, gain, offset_s) instead means: mix those layers, then normalise to the last gain.
SOUNDS = {
    # movie-style slash ("shwing"): a quiet air swish under a bright metal blade ring
    "sfx_slice_1": [("swish", "swishes/swish-3.wav", 0.45, 0.0), ("rpg", "blade_02.ogg", 1.0, 0.02), 0.95],
    "sfx_slice_2": [("swish", "swishes/swish-7.wav", 0.45, 0.0), ("rpg", "blade_03.ogg", 1.0, 0.02), 0.95],
    "sfx_slice_3": [("swish", "swishes/swish-9.wav", 0.45, 0.0),
                    ("sfx512", SFX512 + "Weapons/Melee/sfx_wpn_sword2.wav", 0.7, 0.01),
                    ("rpg", "blade_02.ogg", 0.8, 0.03), 0.95],
    "sfx_whoosh_1": ("swish", "swishes/swish-1.wav", 0.75),
    "sfx_whoosh_2": ("swish", "swishes/swish-5.wav", 0.75),
    "sfx_splat": ("rpg", "creature_slime_03.ogg", 0.7),
    "sfx_explosion": ("sfx512", SFX512 + "Explosions/Long/sfx_exp_long4.wav", 1.0),
    "sfx_countdown_beep": ("synth", "synth_beep_01.ogg", 0.6),
    "sfx_countdown_go": ("synth", "power_up_01.ogg", 0.7),
    "sfx_sword_draw": ("rpg", "blade_01.ogg", 0.8),
    "sfx_sword_sheathe": ("rpg", "blade_03.ogg", 0.5),
    "sfx_combo": ("synth", "retro_coin_01.ogg", 0.6),
    "sfx_streak": ("synth", "power_up_02.ogg", 0.6),
    "sfx_game_over": ("sfx512", SFX512 + "General Sounds/Fanfares/sfx_sounds_fanfare1.wav", 0.7),
    "music_menu": ("chip", CHIP + "Title Screen.wav", 0.8),
    "music_game": ("chip", CHIP + "Level 1.wav", 0.8),
}

FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/pressstart2p/PressStart2P-Regular.ttf"
FONT_LICENSE_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/pressstart2p/OFL.txt"


def fetch(url, dest):
    if not os.path.exists(dest):
        print("downloading", os.path.basename(dest))
        # system curl, not urllib: python.org builds on macOS often lack SSL root certificates
        subprocess.run(["curl", "-fsSL", "-A", "whack26-asset-fetch", "-o", dest + ".part", url], check=True)
        os.replace(dest + ".part", dest)
    return dest


def convert(data, sr, gain, music):
    if not music:  # trim leading silence (keep 5 ms) so the hit lands on time
        loud = np.nonzero(np.abs(data).max(axis=1) > 0.02)[0]
        if len(loud):
            data = data[max(0, loud[0] - int(0.005 * sr)):]
    if sr != SR:
        n = int(len(data) * SR / sr)
        x_old, x_new = np.linspace(0, 1, len(data)), np.linspace(0, 1, n)
        data = np.stack([np.interp(x_new, x_old, data[:, c]) for c in range(data.shape[1])], axis=1)
    peak = np.abs(data).max() or 1.0
    return (data / peak * gain).astype(np.float32)


def main():
    dl = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Downloads/whack26_packs")
    os.makedirs(dl, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "sounds"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "fonts"), exist_ok=True)

    zips = {k: zipfile.ZipFile(fetch(v[0], os.path.join(dl, k + ".zip"))) for k, v in PACKS.items()}
    rows = []
    for name, spec in SOUNDS.items():
        layers = spec[:-1] if isinstance(spec, list) else [(spec[0], spec[1], 1.0, 0.0)]
        gain = spec[-1] if isinstance(spec, list) else spec[2]
        mix = None
        for pack, inner, lgain, offset in layers:
            with zips[pack].open(inner) as f:
                data, sr = sf.read(f, always_2d=True)
            part = convert(data, sr, lgain, name.startswith("music"))
            if part.shape[1] == 1:
                part = np.repeat(part, 2, axis=1)
            pad = int(offset * SR)
            n = max(0 if mix is None else len(mix), pad + len(part))
            new = np.zeros((n, 2), np.float32)
            if mix is not None:
                new[:len(mix)] += mix
            new[pad:pad + len(part)] += part[:, :2]
            mix = new
        out = (mix / (np.abs(mix).max() or 1.0) * gain).astype(np.float32)
        path = os.path.join(ROOT, "sounds", name + ".ogg")
        sf.write(path, out, SR, format="OGG", subtype="VORBIS")
        srcs = " + ".join(os.path.basename(l[1]) for l in layers)
        print(f"wrote sounds/{name}.ogg  {len(out) / SR:.2f}s  <- {srcs}")
        for pack, inner, *_ in layers:
            _, page, title, author, lic = PACKS[pack]
            rows.append(f"| `sounds/{name}.ogg` | {title}: `{os.path.basename(inner)}` | {author} | {lic} | {page} |")

    fetch(FONT_URL, os.path.join(ROOT, "fonts", "PressStart2P-Regular.ttf"))
    fetch(FONT_LICENSE_URL, os.path.join(ROOT, "fonts", "OFL.txt"))
    rows.append("| `fonts/PressStart2P-Regular.ttf` | Press Start 2P | CodeMan38 | SIL OFL 1.1 (see `fonts/OFL.txt`) "
                "| https://fonts.google.com/specimen/Press+Start+2P |")

    with open(os.path.join(ROOT, "CREDITS.md"), "w") as f:
        f.write("# Asset credits\n\n"
                "Third-party assets are CC0 (public domain) or SIL OFL. CC0 doesn't require credit, "
                "but we give it anyway.\nThis file is generated by `tools/fetch_assets.py`; edit that, not this.\n\n"
                "All images (fruit, halves, splats, bomb, explosion, sword, glow, lives, the pineapple rival, "
                "speech bubble, backgrounds) were made by the team (RBadiadka7) for WHACK 26 with "
                "`tools/gen_art.py`.\n\n"
                "| File | Source | Author | Licence | URL |\n|---|---|---|---|---|\n")
        f.write("\n".join(rows) + "\n")
    print("wrote CREDITS.md")


if __name__ == "__main__":
    main()
