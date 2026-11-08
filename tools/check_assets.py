"""Validate assets/ against tools/asset_spec.py.

Usage:  python tools/check_assets.py          # M1: milestone-2 items are warnings
        python tools/check_assets.py --full   # M2: everything must exist
Exit code 0 = OK, 1 = problems found.
"""
import json
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import asset_spec as S  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "assets")


def main() -> int:
    full = "--full" in sys.argv
    errors, pending = [], []

    def missing(path, m2):
        (pending if (m2 and not full) else errors).append(f"missing: {path}")

    for path, (w, h) in S.IMAGES.items():
        fp = os.path.join(ROOT, path)
        if not os.path.exists(fp):
            missing(path, path in S.M2_IMAGES)
            continue
        try:
            img = pygame.image.load(fp)
        except pygame.error as e:
            errors.append(f"unreadable: {path} ({e})")
            continue
        if img.get_size() != (w, h):
            errors.append(f"wrong size: {path} is {img.get_size()}, want {(w, h)}")
        if img.get_bitsize() != 32 and not path.startswith("bg_"):
            errors.append(f"no alpha channel: {path}")

    for path in S.SOUNDS:
        fp = os.path.join(ROOT, path)
        if not os.path.exists(fp):
            missing(path, path in S.M2_SOUNDS)
            continue
        try:
            pygame.mixer.Sound(fp)
        except pygame.error as e:
            errors.append(f"unplayable: {path} ({e})")

    for path in S.OTHER:
        fp = os.path.join(ROOT, path)
        if not os.path.exists(fp):
            missing(path, path in S.M2_OTHER)
    pal = os.path.join(ROOT, "palette.json")
    if os.path.exists(pal):
        try:
            json.load(open(pal))
        except ValueError as e:
            errors.append(f"palette.json invalid JSON: {e}")

    for p in pending:
        print("PENDING (M2)", p)
    for e in errors:
        print("ERROR      ", e)
    total = len(S.IMAGES) + len(S.SOUNDS) + len(S.OTHER)
    print(f"\n{total - len(errors) - len(pending)}/{total} ok, "
          f"{len(pending)} pending (M2), {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    pygame.mixer.init()
    sys.exit(main())
