# Demo runbook (Sunday)

> Team: **The Flairy Fairies**. Owner: RBadiadka7. Devpost submit by **10:30** (hard deadline 11:00 GMT).
> Judging is a **3 minute slot** with the incident.io judges **in the afternoon**, so rehearsals can happen after
> we submit. **Confirmed: it's a live demo** at the slot, so the pre-flight checklist and fallbacks below matter.

## Before the demo
```bash
cd whack-26 && source .venv/bin/activate && git pull origin staging
python tools/smoke_test.py --face                              # should say ALL PASS
python main.py --vision real --game real --rival real --face   # leave it on the title screen
```
(The reliability check tool is in `tools/` if we ever want numbers, but we're not running it today.)

## After we submit
1. Rehearsal 1: the whole pitch, and break one thing on purpose (pull the camera) to practise the fallback.
2. Fix whatever felt awkward.
3. Rehearsal 2.
4. Backup recording on the desktop and a USB stick before we walk over.

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

## Fallback commands
```bash
python main.py --vision real --game real --rival real            # face reactions misbehaving: drop --face
python main.py --vision mouse --game real --rival real            # camera dead: mouse sword
python main.py --vision real --game real --rival real --offline   # wifi/APIs dead: pre-voiced bank
python main.py --vision mouse --game real --rival real --offline  # both
```
