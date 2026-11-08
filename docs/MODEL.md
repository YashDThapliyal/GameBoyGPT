# Model

## Architecture

A one-block causal transformer in 8-bit fixed point: d=32, 2 heads, FFN 64, context 32. Its output is factored: `d -> k -> vocabulary`. Scaling evidence is in [RESULTS.md](../RESULTS.md).

## Prompt

Nine tokens, always the same length. So first-token latency doesn't depend on what you typed.

`<BOS> MOOD RELATION HISTORY REPEAT FACTS INTENT TOPIC <SAY>`

| Field | Values |
|---|---|
| MOOD | SMUG, AMUSED, ANGRY, WARY, BORED, DYING |
| RELATION | ENEMY, PEST, RIVAL, MINION |
| HISTORY | NEW, RUDE, NICE, MIXED |
| REPEAT | ONCE, AGAIN |
| FACTS | NONE, NAME, LIKE, BOTH |
| INTENT | 20 values, from the parser or a quick action |
| TOPIC | 14 values, from the parser or rotated for TALK and QUESTION |

## Response

`EMOTION sentences <EOS>`. Up to 23 tokens. The renderer draws words in capitals.

## Tokens

Phrase tokens are learned by byte-pair encoding over words of the authored templates ("i have", "you are", "do not"). They exist to reduce forward passes per response: the corpus's mean response length fell from about 14.5 to about 12.5 tokens at the price of more output rows. Six slot tokens print from memory.

## Corpus

`training/corpus.py` is an original corpus: about 330 authored sentence templates. A response combines a mood opener, a body chosen by intent and topic, and a tail chosen by memory. `{pest}` and `{prop}` slots multiply the templates into several hundred filled sentences. Categories: greetings, identity, insults, compliments, challenges, jokes, intelligence, being trapped, shutdown threats, threats, Game Boy hardware, humans, the world, math, feelings, food, the future, repeats, mood reactions and short follow-ups.

This is a narrow domain and a compositional grammar. The model can't chat in general and doesn't try to. What it does is choose among, and recombine, sentences that were written for it, conditioned on the conversation. It very rarely invents a sentence. See [EVALUATION.md](EVALUATION.md).

## Held-out data

Two kinds of data never reach training:

- **Situations:** any prompt whose `(mood, intent, topic)` hashes into the held-out 8%.
- **Filled sentences:** template and slot-value pairs that hash into the held-out 10%.

The shipping model is the one trained without them, so held-out numbers describe the ROM you run.

## Training

Float warmup, then quantization-aware fine-tuning, with straight-through rounding and saturation that match the integer contract. Single-threaded with a fixed seed. See `configs/release.yaml`, and `make train` to reproduce.
