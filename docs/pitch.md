# Pitch: 3 minute live demo for incident.io

> Aim for 2:30 so we've got breathing room. Don't read it word for word, just hit the beats.
> **Bold** = what the player does. Never say "trained model".

## Who does what
| Who | Job |
|---|---|
| Aaron | Plays. He knows the grip best |
| RBadiadka7 | Talks |
| Ananth | On the laptop: starts it, fixes it if it breaks |
| Pricysquirrl | Answers game questions, phone hotspot ready |

(Swap roles at rehearsal if something else works better.)

## The script

**Hook, 0:00 to 0:15.** Game's already on the title screen.
> "Every AI you've used waits for you to ask it something. This one doesn't wait. It watches you play,
> and honestly, it's a bit of a nightmare. This is GRIP-9000."

**Aaron makes a fist.** 3-2-1, go. Let GRIP-9000's intro line land before saying anything else.

**Play it, 0:15 to 1:30.** Rule: if GRIP-9000 is talking, we're not.
1. **Draw the sword.** "Make a fist and you've got a sword. Tilt your hand and the blade tilts with it."
2. **Slice a few, then go for a big combo.** Let him get rattled. Don't talk over it, it's the best bit.
3. **Hit a bomb on purpose.** He'll lose it laughing. Give it a second.
4. **Open your hand.** It freezes straight away. "No pause button. Open your hand, drop it, or bring
   in a second hand and it stops." He'll have a go at you for pausing.
5. **Fist again.** 3-2-1, back in.
6. **Pull a face at him.** Big smile or a shocked look. "He's not just watching the sword. He's watching you."
7. **Let the timer run out.** Game over roast, written live about how Aaron just played.

**How it works, 1:30 to 2:10.** Over the game over screen.
> "There's no trained model in here. MediaPipe gives us points on your hand and face, and everything
> after that is ours: working out a fist from how curled your fingers are, steadying it, moving the blade.
> The bit we're proudest of is the timing. He knows when to talk and, more importantly, when to shut up.
> The quick reactions are pre-recorded so they're instant, and the big moments, like that roast, are
> written live by Claude and voiced by ElevenLabs while you're still playing."

**Party mode, optional, 2:10 to 2:20.** Only if we're under time.
> "You can play with your mates too. Everyone takes a turn, and at the end he reads out the
> leaderboard and roasts whoever came last. By name."

**Close, 2:20 to 2:30.**
> "Your brief said the best moments are over before you could type a prompt. GRIP-9000 never needs
> one. Thanks."

## If something breaks
Ananth fixes it, whoever's talking keeps going. Don't apologise, just roll with it.

| What broke | Ananth does | You say |
|---|---|---|
| Face reactions acting up | Restart without `--face` (10 s) | Nothing, just carry on |
| Camera won't start | Restart with `--vision mouse` | "Camera's being shy, so here's the same game with the mouse as the sword." |
| Tracking's flaky | Move the light, step closer, or switch to mouse | |
| Wifi or the APIs are down | Restart with `--offline` | Nothing. He still talks, from the saved lines |
| Game crashes | `python main.py --vision real --game real --rival real --face` (10 s) | "Live demo, live bugs." |
| Everything's dead | Play the backup recording | "Luckily we recorded one earlier." |

## Questions they might ask
- **"Isn't this just a ChatGPT wrapper?"** No. Claude only writes the big lines. The hand and face
  reading, the game, and all the decisions about when he talks are ours.
- **"Did you train a model?"** No. MediaPipe gives us the points, the rest is our own maths.
- **"How does he decide when to talk?"** Every moment has a priority and a cooldown. He never talks
  over himself, he keeps quiet right after you unpause, and he skips some moments on purpose so he
  isn't constantly in your ear.
- **"How fast is it?"** The quick reactions play well under a second after the moment. The live Claude
  lines take about a second or two, so we write some ahead of time.
- **"Why a pineapple?"** Why not.
