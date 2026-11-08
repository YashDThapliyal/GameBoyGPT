# Demo script

## The recommended run: The Ring Keeper

Chosen after scoring all 653 story paths and playing the best on the ROM. It's the shortest complete story with a real twist, about 76 seconds of generation.

Hear the voice, Take his ring, Wade the shallows, Walk on, Climb the wall, Wake him, Show the ring.

"Show the ring" appears only because you took it on the second choice. Wording varies with the seed; the story doesn't.

## Script

Numbers are filled from RESULTS.md at recording time. Don't state anything RESULTS.md doesn't show.

**0-5 s.** Real emulator boot, title `8-BIT ADVENTURE`. Caption: "Emulated original Game Boy."

**5-12 s.** "This console has an 8-bit CPU and 8 KB of built-in RAM. I trained a tiny transformer on a laptop and put its weights in the cartridge."

**12-25 s.** Make a choice. Show words appearing one at a time with the progress bar. Real time. Caption: `event tokens -> integer attention -> story`.

**25-35 s.** Show how an item changes the menu: with the lamp, a new choice appears in the cave. Then show the two routes and their different endings from `reports/demo_trace.json`.

**35-43 s.** Stats screens side by side: `docs/figures/screen_stats_v0.png` and `screen_stats_ship.png`. Label: "same model, same tokens."

**43-45 s.** "No GPU. No API. Just SM83 assembly." Repo link. "What made it faster?"

Say this plainly somewhere in the post: this is an emulator run, not a physical Game Boy. The plot is authored, and the model narrates it in a small language it learned. It is not conversational AI. Credit gbc-transformer, ChatGBC and Elyan Labs; don't say "first."
