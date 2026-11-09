# The demo

`docs/demo/system_override_demo.mp4` is about 78 seconds of browser footage, recorded by `tools/capture_demo.mjs` with Playwright. The GIF is the same footage at a lower frame rate and size.

**What's real:** the emulator runs the real ROM at real speed in the real page. Nothing is sped up. Tokens are read from emulated RAM at the end of each reply, and the script fails unless they equal the integer reference. They're stored in `docs/demo/demo_tokens.json`.

**What was chosen or added:**

- The sampler seeds in `tools/demo_seeds.json`, written into emulated RAM through the emulator's debug interface before each reply. `tools/find_demo_seeds.py` searched them on the reference for short, good replies, so this is a best take and not a typical run.
- The video opens with two seconds of its own ending, then plays from the start.
- The intro is skipped with button presses.
- A drawn mouse cursor, because headless browsers show none.

The takeover's page effects and big lines are scripted, and the screen says so. They use the ROM's real sprite and real save.

`docs/demo/system_override_short.mp4` is the same footage cut to about 33 seconds by `tools/make_short_demo.py`, with captions and an end card. Every beat has its own speed, up to 10 times, and a "Sped up" tag shows whenever anything is. The cold open and the takeover play at real speed.

The recorder logs the moment of each beat. Screencast time drifts from real time, so `tools/capture_demo.mjs` ties both to two moments visible in the footage, the LED lighting up and the takeover filling the page, and corrects the full video to true speed.

To rerecord: `make demo`, then `make demo-short`.
