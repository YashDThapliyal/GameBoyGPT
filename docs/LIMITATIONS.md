# Known limitations

- **No physical hardware.** Everything ran on emulators: PyBoy for tests and timing, SameBoy for the self-test ROM only, binjgb in the browser. The SP weight stream and head tables have never run on silicon.
- **Narrow domain.** It talks about itself, you, the handheld and a few topics. It isn't general chat, and typed input reaches it only as an intent and a topic.
- **The parser is keywords.** "WHO WON THE GAME LAST NIGHT" hits the WHO cue and gets an identity line. Negation only flips insult and praise. Measured misrouting is in [RESULTS.md](../RESULTS.md).
- **It mostly recombines.** Nearly every valid sentence was written by a person. Novelty is mainly in the combinations.
- **It isn't always coherent.** A response can parse as valid sentences and still be a non sequitur, because grammar validity is the only automatic check. Invalid responses also occur at a measured rate.
- **Memory is limited.** One name, one like, one echoed word, counters and a few moods. It can't recall what you actually said beyond those.
- **Speed.** A response takes on the order of ten seconds. Words appear as they're generated, so it reads like slow typing.
- **Cartridge RAM stays enabled during part of each token.** Saves are in another bank with a checksum, and a bad save is discarded. A real cartridge losing power at the wrong moment should lose only the scratch tables, but this hasn't been tested.
- **Audio is one blip per word.** It runs in the browser and was not checked by ear in this work.
- **Browser timing is not the benchmark.** The panel's live seconds come from the ROM's frame counter. They are emulated time and assume the browser keeps up with real time.
- **Readability and fun are for a person to judge.** Tests check correctness, not whether it's funny.
