# The demo

`docs/demo/system_override_demo.mp4` is about 30 seconds of real browser footage, recorded by `tools/capture_demo.mjs` with Playwright. The GIF is the same footage, cropped and at a lower frame rate.

**What's real:** the emulator runs the real ROM at real speed in the real page, and buttons are pressed with a simulated mouse. Tokens are read from emulated RAM at the end of each response, stored in `docs/demo/demo_tokens.json`, and were checked equal to the integer reference for these seeds.

**What was chosen:**

- The two sampler seeds in `tools/demo_seeds.json`, written into emulated RAM through the emulator's debug interface before each response. `tools/find_demo_seeds.py` searched them on the reference for short replies where the second visibly remembers the first. Replies of this kind are common but not guaranteed: see the memory rates in RESULTS.md.
- The fixed intro lines are skipped after about half a second each.

**What's labelled:** the side panel in the footage is the page's real panel in a compact layout. Its live values come from emulated RAM and its build values from `web/rom/build.json`. The plastic is CSS, as the footage says on screen.

To rerecord: `make demo`.
