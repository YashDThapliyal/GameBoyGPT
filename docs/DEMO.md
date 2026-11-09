# The demo

`docs/demo/system_override_demo.mp4` is about 77 seconds of browser footage, recorded by `tools/capture_demo.mjs` with Playwright. The GIF is the same footage at a lower frame rate and size.

**What's real:** the emulator runs the real ROM at real speed in the real page. Nothing is sped up. Tokens are read from emulated RAM at the end of each reply, and the script fails unless they equal the integer reference. They're stored in `docs/demo/demo_tokens.json`.

**What was chosen or added:**

- The sampler seeds in `tools/demo_seeds.json`, written into emulated RAM through the emulator's debug interface before each reply. `tools/find_demo_seeds.py` searched them on the reference for short, good replies, so this is a best take and not a typical run.
- The video opens with two seconds of its own ending, then plays from the start.
- The intro is skipped with button presses.
- A drawn mouse cursor, because headless browsers show none.

The takeover's page effects and big lines are scripted, and the screen says so. They use the ROM's real sprite and real save.

To rerecord: `make demo`.
