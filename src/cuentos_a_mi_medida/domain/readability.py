"""How easy a Spanish text is to read: the Fernández-Huerta index (1959), Flesch's formula adapted to Spanish.

    L = 206.84 - 0.60 P - 1.02 F

P = syllables per 100 words, F = average words per sentence. Higher is easier: 90-100 "muy fácil" (readers of about
fourth grade), 80-90 "fácil", 70-80 "algo fácil", 60-70 "normal". The formula is often quoted with F as sentences
per 100 words, which makes shorter sentences score as harder; F here is words per sentence, as in Flesch's formula,
which this one adapts (Flesch: 206.835 - 84.6 syllables/word - 1.015 words/sentence).

Syllables are counted with the usual Spanish rules: a strong vowel (a, e, o) next to another strong vowel is a hiatus
(two syllables); a weak vowel (i, u) next to any vowel forms a diphthong (one), unless the weak vowel carries an accent
(í, ú), which breaks it; the u in que, qui, gue, gui is silent; a final y after a vowel ("hoy", "muy") closes it.
"""
import re
from dataclasses import dataclass

STRONG = set("aeoáéó")
WEAK = set("iuü")
ACCENTED_WEAK = set("íú")
VOWELS = STRONG | WEAK | ACCENTED_WEAK
WORD = re.compile(r"[a-záéíóúüñ]+", re.IGNORECASE)
SENTENCE_END = re.compile(r"[.!?…]+|\n\s*\n")


def syllables(word: str) -> int:
    w = word.lower()
    w = re.sub(r"(?<=[qg])u(?=[eiéí])", "", w)  # silent u: queso, guitarra
    if w.endswith("y") and len(w) > 1 and w[-2] in VOWELS:
        w = w[:-1] + "i"  # hoy, muy, rey: the y is the end of a diphthong
    count, prev = 0, None
    for ch in w:
        if ch not in VOWELS:
            prev = None
            continue
        if prev is None:
            count += 1
        elif ch in ACCENTED_WEAK or prev in ACCENTED_WEAK:
            count += 1  # día, búho: an accented weak vowel stands alone
        elif ch in STRONG and prev in STRONG:
            count += 1  # hiatus: poeta, leer
        # anything else (a weak vowel with a neighbour) is a diphthong: same syllable
        prev = ch
    return max(1, count)


def words(text: str) -> list[str]:
    return WORD.findall(text)


def sentences(text: str) -> int:
    parts = [p for p in SENTENCE_END.split(text) if WORD.search(p)]
    return max(1, len(parts))


@dataclass(frozen=True)
class Readability:
    words: int
    sentences: int
    syllables: int
    fernandez_huerta: float
    words_per_sentence: float


def measure(text: str) -> Readability:
    ws = words(text)
    n = max(1, len(ws))
    syl = sum(syllables(w) for w in ws)
    s = sentences(text)
    index = 206.84 - 0.60 * (100 * syl / n) - 1.02 * (n / s)
    return Readability(len(ws), s, syl, round(index, 1), round(n / s, 1))


@dataclass(frozen=True)
class Target:
    """What a child of that age can read alone: an easy enough text, in short enough sentences."""
    ages: str
    min_index: float
    max_words_per_sentence: float


# Fernández-Huerta's 90-100 band is about fourth grade (9-10 years); younger readers need easier text and much
# shorter sentences than the index alone asks for, so each band adds a sentence-length cap.
TARGETS = {
    "5-6": Target("5-6", 95, 8),
    "7-8": Target("7-8", 90, 11),
    "9-10": Target("9-10", 85, 15),
}


def on_target(r: Readability, t: Target) -> bool:
    return r.fernandez_huerta >= t.min_index and r.words_per_sentence <= t.max_words_per_sentence
