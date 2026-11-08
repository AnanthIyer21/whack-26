# Devpost draft: GRIP-9000

> Team note, don't paste this bit. Deadline 11:00 GMT. Needs: team name, all four of us linked, incident.io
> picked, lots of images. No video required. Never call the grip detection a "trained model".

## Team name
The Flairy Fairies

## Project name
GRIP-9000

## Tagline
Make a fist, a sword appears, and a very rude pineapple starts heckling you.

## Inspiration
The incident.io brief said the best moments are over before you could type a prompt about them. That stuck with us. Every AI we use sits there waiting for us to ask it something. We wanted the opposite: an AI that's watching you the whole time and has opinions about it, out loud, right now.

So we made it a game, because nothing happens faster than a game, and we gave the AI an ego. GRIP-9000 is a pineapple in sunglasses who thinks humans are obsolete. When you miss a fruit he tells you to book an eye test at SpecSavers. When you go on a streak he starts making excuses. We wanted something you'd want to beat just to shut him up.

## What it does
Hold one hand up to your webcam and make a fist. A sword appears in it. Tilt your fist and the blade tilts with it. Swing it fast through the fruit to slice them, and don't touch the bombs.

The whole time, GRIP-9000 is watching and talking:
- He cackles when you hit a bomb and gets visibly rattled when you're on a roll.
- He notices habits, like if you keep missing everything on the left.
- He reacts to your face too. Smile at him, look shocked, look away, and he'll have something to say about it.
- At game over he writes you a personal roast based on how you actually played.

Open your hand, drop it, or put a second hand in frame, and the game pauses instantly. Make a fist again for a 3-2-1 and you're back in. No buttons needed.

There's also a party mode: type in everyone's names, take turns, and at the end GRIP-9000 reads out the leaderboard, crowns the winner (reluctantly) and roasts whoever came last, by name.

## How we built it
It's one Python program running four things at once:

- **Hand tracking.** MediaPipe gives us 21 points on your hand. That part is Google's, not ours. Everything after it is our own maths: we work out how curled each finger is from the 3D points to tell a fist from an open hand, steady it so it doesn't flicker, and smooth the blade so it follows your fist without jittering. We didn't train anything.
- **Face reactions.** MediaPipe's face landmarks, then our own thresholds for smiling, laughing, shock, frowning and looking away. It calibrates to your resting face, so it isn't fooled by someone who just looks a bit grumpy.
- **The game.** pygame at 60 fps: fruit, bombs, lives, combos, streaks, the auto-pause, and the sword's swing checked along its whole path so fast swings still connect.
- **GRIP-9000.** The hard part wasn't what he says, it was *when*. Every moment has a priority and a cooldown, he never talks over himself, and he stays quiet right after you unpause. Quick reactions come from a bank of pre-recorded lines so they play instantly. The big moments, like the game over roast or calling out your habits, are written live by Claude and voiced by ElevenLabs.
- **Art and sound.** Every sprite is pixel art drawn in code, including the pineapple's moods. The slash sound is a metal clash layered with a knife being sharpened, made from free CC0 samples.
- **Party mode** keeps scores in SQLite, with an all-time top 10.

## Challenges we ran into
- **Reading a fist without training a model.** Hands are all different, and a half-open hand is surprisingly hard to call. Getting it steady enough that the game didn't pause by accident took a lot of tuning.
- **Speed.** Four threads in Python on one laptop. pygame's built-in frame limiter only managed about 39 fps on a Mac, so we wrote our own.
- **The silent game.** For a while every sound effect just didn't play. It turned out pygame was handing us the one audio channel we'd reserved for GRIP-9000's voice. We had to pick channels ourselves.
- **Comic timing.** An AI that comments on everything is unbearable. Making him funny meant teaching him to shut up most of the time.
- **Voice lag.** A live Claude line plus speech takes over a second, and a roast that lands late isn't funny. Pre-recorded lines and writing lines ahead of time fixed most of that.

## Accomplishments that we're proud of
- It actually feels like holding a sword. People's first reaction is to start swinging.
- GRIP-9000 has real comic timing. He's funny, he's quick, and he gets under your skin.
- The quick reactions play in well under a second, so he responds while the moment's still happening.
- We built the whole thing in 24 hours with no trained model, just MediaPipe points and our own maths.

## What we learned
- You can get a long way with some geometry on top of pretrained landmarks.
- For a live AI, *when* it speaks matters more than *what* it says.
- Sound sells everything. The game felt twice as good the moment the slashes started sounding sharp.

## What's next for GRIP-9000
- Gesture moves with your free hand, like blocking or a special attack.
- Two players at once, with GRIP-9000 commentating both.
- Remembering you between sessions, so the roasts get personal.

## Built with
`python` `pygame-ce` `opencv` `mediapipe` `numpy` `sqlite` `claude` `anthropic-api` `elevenlabs` `multithreading`

## Links
- Code: https://github.com/AnanthIyer21/whack-26

## Credits
Sound effects from CC0 packs on OpenGameArt (Juhani Junkala, rubberduck, artisticdude, StarNinjas, Vehicle). Font: Press Start 2P (SIL Open Font License). All art drawn by us.

## Images to upload
1. Mid-slash: sword out, fruit halves flying.
2. GRIP-9000 laughing after a bomb.
3. The pause screen.
4. Game over with the roast.
5. The party leaderboard.
6. A photo of someone playing: fist up, screen behind.
