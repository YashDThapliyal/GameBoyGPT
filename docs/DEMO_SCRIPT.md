# Demo script

Numbers are filled from RESULTS.md at recording time. Don't state anything RESULTS.md doesn't show.

**0-5 s.** Real emulator boot, title `8-BIT ADVENTURE`. Caption: "Emulated original Game Boy."

**5-12 s.** "This console has an 8-bit CPU and 8 KB of built-in RAM. I trained a tiny transformer on a laptop and put its weights in the cartridge."

**12-25 s.** Choose an action. Show words appearing one at a time with the progress bar. Real time. Caption: `action tokens -> integer attention -> story event`.

**25-35 s.** Reset to the same state and choose another action. Show the different text and both input-id lists from `reports/demo_trace.json`.

**35-43 s.** Stats screens side by side: `docs/figures/screen_stats_v0.png` and `screen_stats_ship.png`. Label: "same model, same tokens."

**43-45 s.** "No GPU. No API. Just SM83 assembly." Repo link. "What made it faster?"

Say this plainly somewhere in the post: this is an emulator run, not a physical Game Boy. The model learned a small grammar and is not conversational AI. Credit gbc-transformer, ChatGBC and Elyan Labs; don't say "first."
