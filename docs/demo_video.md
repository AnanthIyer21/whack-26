# Demo video: script and shot list

> Owner: RBadiadka7. **Target length: 1:45.** The WHACK 2026 rules do **not** require a video (judging is a
> 3 minute live slot), so this is a nice-to-have for Devpost and, more importantly, the backup if the live demo dies.
> Record 08:00 to 08:45 Sunday on the demo laptop; edit in iMovie; upload to YouTube as **Unlisted**;
> put the link in Devpost. **Never commit the video** (it's gitignored; keep it on the desktop + USB as the live-demo backup).

## Recording setup
- **Screen:** QuickTime → File → New Screen Recording → Options → **Microphone: MacBook mic** (so GRIP-9000 and the game sound are captured; or use "Internal" if available). Record the game window full screen (`F` in game).
- **Player:** a phone on a stand behind/next to the laptop, landscape, filming the player's hand and the screen together. This shot sells "it's a real sword grip".
- Quiet spot, good front lighting on the hand, plain background.
- Do 3 full runs and keep the best moments.

## Shot list (cumulative times)
| Time | Visual | Audio / on-screen text |
|---|---|---|
| 0:00 to 0:08 | Title screen, GRIP-9000 bobbing | Text: "An AI rival that reacts while you play." |
| 0:08 to 0:20 | Phone shot: hand rises, makes a fist; cut to screen: sword appears, 3-2-1-GO | Game sound. Text: "Make a fist. Draw your sword." |
| 0:20 to 0:45 | Screen: slashing fruit, a combo, GRIP-9000 getting rattled | GRIP-9000 lines (no voiceover over it) |
| 0:45 to 1:00 | Bomb hit → explosion → GRIP-9000 cackles | Laugh + roast |
| 1:00 to 1:12 | Phone shot: hand opens → screen freezes (pause screen); fist → 3-2-1 | Text: "Open hand = instant pause." GRIP-9000 mocks the pause |
| 1:12 to 1:25 | Game over screen with the final roast (live Claude) | Roast audio |
| 1:25 to 1:40 | `results/numbers_slide.png` (zoom in slowly) | Voiceover: "MediaPipe landmarks plus our own grip maths, nothing trained. [[NN]] ms camera to game, [[NN]]% grips recognised, quick lines in [[N]] ms." |
| 1:40 to 1:45 | Logo/title + team names + repo | Text: "GRIP-9000 · The Flairy Fairies · WHACK 26" |

## iMovie steps
1. New Project → Movie → import the QuickTime + phone clips and the slide PNG.
2. Drag clips to the timeline in shot order; trim with `Cmd+B` (split) and delete.
3. Titles (`T` button) for the on-screen text; keep them short and lower-third.
4. Voiceover: Window → Record Voiceover over the numbers slide only.
5. Lower background music where GRIP-9000 talks (clip volume), never cover his lines.
6. File → Share → File → 1080p → save to Desktop as `grip9000_demo.mp4`.
7. Upload to YouTube, visibility **Unlisted**, title "GRIP-9000 · WHACK 26", copy the link into `docs/devpost.md` and Devpost.
