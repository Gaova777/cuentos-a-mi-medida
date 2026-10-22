# Writing at the child's reading level

A story for a five-year-old who is learning to read is not the same as one for a ten-year-old. The app measures every
story it writes and rewrites it when it misses the target for the child's age.

**Measure.** The Fernández-Huerta index (1959), the Spanish adaptation of Flesch reading ease:
`L = 206.84 − 0.60·P − 1.02·F`, with P the syllables per 100 words and F the words per sentence (some sources write F
as sentences per 100 words; that version rewards long sentences, which is backwards). Spanish syllables are counted by
rule, with diphthongs, hiatus, accented weak vowels, silent *u* (que, gui) and final *y* (`domain/readability.py`).

**Target.** An index of 90 or more (very easy) is necessary but not enough: the index rewards telegraphic text, so a
model can score 100 with "Ana ve. Ana ríe." The target per age is therefore the index **and** a band of words per
sentence: 3–8 for ages 5–6, 5–11 for 7–8, 7–15 for 9–10. A story must also be in Spanish (a model asked to describe
scenes in English sometimes wrote the whole story in English).

## Results

8 children x 3 age bands = 24 requests per strategy, Qwen3-4B-Instruct on the CPU.

| strategy | LLM calls | on target | 5–6 | 7–8 | 9–10 | time / story |
|---|---:|---:|---:|---:|---:|---:|
| age in the prompt (baseline) | 1 | 42% | 50% | 50% | 25% | 60 s |
| best of 3 (keep the closest) | 2.17 | 58% | 62% | 62% | 50% | 128 s |
| **measure and rewrite with feedback** | 1.92 | **71%** | 75% | 75% | 62% | 122 s |

Raw numbers: [qwen3_4b-instruct.json](qwen3_4b-instruct.json). Rewriting is the app's default: better than sampling
more stories, and cheaper. The feedback is concrete: it quotes the sentences that are too short or too long and the
words of four or more syllables, and gives the range again. The draft kept is the closest to the target, not the
last one, because a rewrite can make a story worse.

## Free text first, then a list of sentences

The first version asked for each page as free text. A 4B model can't hit an average it can't see: it wrote 4–5 words
per sentence for every age, so stories for 9–10 year olds were never on target, rewriting or not
([free_text](free_text/qwen3_4b-instruct.json): 17% baseline, 33% rewrite, 33% best of 3; 0% for 9–10 in all three).

The second version asks for each page as a JSON list of exactly three sentences, with a word range for each sentence.
Counting the words of one sentence is a task a small model can do; averaging over a page is not. Same model, same
requests: baseline from 17% to 42%, rewrite from 33% to 71%, and 9–10 from 0% to 62%.

An example on target, ages 5–6 (index 93.3, 7.2 words per sentence, first try):

> Salomé baila cumbia en el jardín. Las flores danzan al son de la música. El sol brilla sobre su rostro sonriente.
>
> Salomé ve un colibrí en una flor. El colibrí vuela muy lento y suave. Salomé se siente triste por no verlo volar.

Rerun: `./run.sh readability` (about 2 hours on the CPU for 72 stories).
