# Demo runbook (Sunday)

> Team: **The Flairy Fairies**. Owner: RBadiadka7. Devpost submit by **10:30** (hard deadline 11:00 GMT).
> Judging is a **3 minute slot** with the incident.io judges **in the afternoon**, so rehearsals can happen after
> we submit. **Confirmed: it's a live demo** at the slot, so the pre-flight checklist and fallbacks below matter.

## Reliability check (all four of us, Ananth's laptop, ~20 to 25 min; right hands only ~12 min)
```bash
cd whack-26 && source .venv/bin/activate && git pull origin staging
# one run per person per hand, 40 prompts each (~3 min). Same spot and lighting as the demo.
python tools/reliability_check.py --person Aaron --hand left  --lighting "demo spot"
python tools/reliability_check.py --person Aaron --hand right --lighting "demo spot"
#   ...same for Ananth, Pricysquirrl, RBadiadka7
python tools/reliability_summary.py                   # table -> results/reliability_table.md
python tools/smoke_test.py --game real                # note the fps it prints
python main.py --vision real --game real --rival real --face  # play 3-4 games: fills logs/latency.csv
python tools/latency_report.py                        # check the event -> voice numbers
python tools/make_numbers_slide.py --game-fps 60      # -> results/numbers_slide.png (use the measured fps)
git add results/ && git commit -m "Reliability + latency results and numbers slide" && git push
```
In each run: one hand in view, SPACE to start, do what the screen says (GRIP! / OPEN!), R redoes a trial if
you weren't ready, ESC saves and quits. Failures count; that's the point.

## Sunday schedule (team back at 09:30)
| Time | What | Who |
|---|---|---|
| 09:30 to 09:35 | Decide on the new rbadiadka7 commits (roasts, party leaderboard, whiff + name roasts), merge the PR, `git pull origin staging`, pre-flight checklist below | all, Ananth merges |
| 09:35 to 09:40 | `python tools/voice_bank.py` to voice the new roasts (needs the ElevenLabs key) | Ananth |
| 09:35 to 10:00 | Reliability check, 8 runs (commands above). **Short on time?** 4 right-hand runs only, ~12 min | all four, one at a time |
| 10:00 to 10:10 | One **party** round with `--rival real` (fills the voice latency, shows off the leaderboard). Take the Devpost screenshots during it, plus one QuickTime recording as the backup video | all play, RBadiadka7 screenshots + records |
| 10:10 to 10:15 | `reliability_summary.py` + `make_numbers_slide.py`, commit + push `results/` | RBadiadka7 |
| 10:10 to 10:27 | Devpost: fill the numbers, upload images, team name, link all 4 collaborators, choose incident.io | RBadiadka7 + Ananth |
| 10:27 to 10:30 | Final read-through, **SUBMIT** | RBadiadka7 + Ananth |
| After 10:30 | **Rehearsal 1** (full pitch + one forced failure, e.g. pull the camera), fix roles/script, **Rehearsal 2**, before the afternoon slot | all |

## Pre-flight checklist (before every rehearsal and the real pitch)
- [ ] Laptop charged + charger plugged in; Do Not Disturb on; notifications off
- [ ] Volume up, sound on in Settings, test one GRIP-9000 line out loud
- [ ] Camera permission OK; external cams unplugged (or `CAMERA_INDEX` set)
- [ ] Front light on the player's hand; plain background; nobody else's hand in frame
- [ ] `.env` present (Claude + ElevenLabs keys); `python tools/check_keys.py` passes
- [ ] Game started and sitting on the title screen: `python main.py --vision real --game real --rival real --face`
- [ ] Player's face lit and in frame too (face reactions); if face tracking misbehaves, restart without `--face`
- [ ] Backup video on the desktop **and** a USB stick, QuickTime open, ready to play
- [ ] Phone hotspot ready (Pricysquirrl)
- [ ] Numbers slide open in Preview on a second space (`Ctrl+→`)

## Fallback commands
```bash
python main.py --vision real --game real --rival real            # face reactions misbehaving: drop --face
python main.py --vision mouse --game real --rival real            # camera dead: mouse sword
python main.py --vision real --game real --rival real --offline   # wifi/APIs dead: pre-voiced bank
python main.py --vision mouse --game real --rival real --offline  # both
```
