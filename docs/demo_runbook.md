# Demo runbook (Sunday)

> Owner: RBadiadka7. Feature freeze **08:00**. Submit by **10:30** (deadline 11:00).

## Before 08:00: reliability check (all four of us, Ananth's laptop, ~25 min)
```bash
cd whack-26 && source .venv/bin/activate && git pull origin staging
# one run per person per hand, 40 prompts each (~3 min). Same spot and lighting as the demo.
python tools/reliability_check.py --person Aaron --hand left  --lighting "demo spot"
python tools/reliability_check.py --person Aaron --hand right --lighting "demo spot"
#   ...same for Ananth, Pricysquirrl, RBadiadka7
python tools/reliability_summary.py                   # table -> results/reliability_table.md
python tools/smoke_test.py --game real                # note the fps it prints
python tools/latency_report.py                        # after a few --rival real runs
python tools/make_numbers_slide.py --game-fps 60      # -> results/numbers_slide.png (use the measured fps)
git add results/ && git commit -m "Reliability + latency results and numbers slide" && git push
```
In each run: one hand in view, SPACE to start, do what the screen says (GRIP! / OPEN!), R redoes a trial if
you weren't ready, ESC saves and quits. Failures count; that's the point.

## 08:00 to 10:30 schedule
| Time | What | Who |
|---|---|---|
| 08:00 | Feature freeze. Final staging → main merge once everyone's happy (Ananth) | all |
| 08:00 to 08:45 | Record demo video (see `docs/demo_video.md`) | Aaron plays, RBadiadka7 records |
| 08:45 to 09:15 | Edit + upload video (unlisted); fill numbers into Devpost | RBadiadka7 |
| 08:45 to 09:15 | Screenshots, README credits/results links | Ananth, Pricysquirrl |
| 09:15 to 09:35 | **Rehearsal 1** (full 2:30 + one forced failure, e.g. pull the camera) | all |
| 09:35 to 09:50 | Fix the script / roles | all |
| 09:50 to 10:10 | **Rehearsal 2** | all |
| 10:10 to 10:30 | Final Devpost check, all four members added, incident.io challenge selected, **SUBMIT** | RBadiadka7 + Ananth |

## Pre-flight checklist (before every rehearsal and the real pitch)
- [ ] Laptop charged + charger plugged in; Do Not Disturb on; notifications off
- [ ] Volume up, sound on in Settings, test one GRIP-9000 line out loud
- [ ] Camera permission OK; external cams unplugged (or `CAMERA_INDEX` set)
- [ ] Front light on the player's hand; plain background; nobody else's hand in frame
- [ ] `.env` present (Claude + ElevenLabs keys); `python tools/check_keys.py` passes
- [ ] Game started and sitting on the title screen: `python main.py --vision real --game real --rival real`
- [ ] Backup video on the desktop **and** a USB stick, QuickTime open, ready to play
- [ ] Phone hotspot ready (Pricysquirrl)
- [ ] Numbers slide open in Preview on a second space (`Ctrl+→`)

## Fallback commands
```bash
python main.py --vision mouse --game real --rival real            # camera dead: mouse sword
python main.py --vision real --game real --rival real --offline   # wifi/APIs dead: pre-voiced bank
python main.py --vision mouse --game real --rival real --offline  # both
```
