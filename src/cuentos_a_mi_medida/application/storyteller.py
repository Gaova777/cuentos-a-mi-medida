"""The LLM writes the story; the readability index decides whether a child of that age can read it. Two ways to use
the measurement, with the same budget of three LLM calls:

- "rewrite": tell the LLM what is off (which sentences to join or split, which words to replace) and let it rewrite;
- "best_of": write three stories and keep the one closest to the target.

Either way the story kept is the draft closest to the target, never just the last one: a small model's rewrite can
make things worse. "baseline" (one story, age in the prompt, no measurement) is the control.
"""
import json
from dataclasses import dataclass, field

from cuentos_a_mi_medida.domain.readability import (
    TARGETS,
    Readability,
    distance,
    long_words,
    measure,
    on_target,
    sentence_list,
)
from cuentos_a_mi_medida.domain.story import PAGES, Page, Request, Story
from cuentos_a_mi_medida.ports.llm import LLM

SENTENCES = 3  # per page
# words per sentence asked for, inside each age's band: a model asked for an average writes short; asked for each
# sentence's length, it writes to it (measured: 9-10 year-olds' stories went from 5 to 11 words per sentence)
SENTENCE_WORDS = {"5-6": (4, 7), "7-8": (6, 10), "9-10": (9, 13)}

SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "protagonista_en_ingles": {"type": "string"},
        "paginas": {"type": "array", "minItems": PAGES, "maxItems": PAGES, "items": {
            "type": "object",
            "properties": {"oraciones_en_espanol": {"type": "array", "minItems": SENTENCES, "maxItems": SENTENCES,
                                                     "items": {"type": "string"}},
                           "escena_en_ingles": {"type": "string"}},
            "required": ["oraciones_en_espanol", "escena_en_ingles"]}},
    },
    "required": ["titulo", "protagonista_en_ingles", "paginas"],
}

WRITE = """Eres autor de cuentos infantiles colombianos. Escribe un cuento corto en español de Colombia, cálido y con
un final feliz, para leer en voz alta.

- Protagonista: {name}, un niño o niña de {ages} años. Le gusta: {likes}.
{lesson}- Exactamente {pages} páginas, cada una con exactamente 3 oraciones en español.
- Nada de violencia, miedo intenso, marcas comerciales ni personajes con derechos de autor.
- "protagonista_en_ingles": una descripción visual fija del protagonista, en inglés (edad, pelo, ropa, un detalle
  que lo identifique), sin nombres propios, para que un ilustrador lo dibuje igual en todas las páginas.
- "escena_en_ingles": para cada página, la escena en inglés para el ilustrador (qué pasa, dónde, sin texto).
{level}
Responde solo con JSON."""

LEVEL = ("- Para que lo lea solo un niño de {ages} años: CADA oración tiene entre {lo} y {hi} palabras (cuéntalas), "
         "con palabras cortas y comunes.")

REWRITE = """Este cuento es para que lo lea solo un niño de {ages} años. {problem}
{details}
Reescribe "oraciones_en_espanol" de cada página, en español, {how}, sin cambiar la historia, el título, el
protagonista ni las escenas. Responde solo con el mismo JSON."""

NOT_SPANISH = "Pero el texto de las páginas no está en español, y tiene que estarlo."
OFF_TARGET = ("Pero no está al nivel de esa edad: su índice de lecturabilidad Fernández-Huerta es {index} (la meta es "
              "al menos {min_index}) y tiene {wps} palabras por oración (la meta es entre {lo} y {hi}).")


@dataclass
class Draft:
    story: Story
    readability: Readability
    on_target: bool


@dataclass
class Trace:
    drafts: list[Draft] = field(default_factory=list)
    target: object = None

    @property
    def final(self) -> Draft:
        return min(self.drafts, key=lambda d: distance(d.readability, self.target))


def parse(reply: str) -> Story | None:
    try:
        d = json.loads(reply)
        pages = [Page(" ".join(str(o).strip() for o in p["oraciones_en_espanol"]).strip(),
                      str(p["escena_en_ingles"]).strip()) for p in d["paginas"]]
        if not pages or not all(p.text for p in pages):
            return None
        return Story(str(d["titulo"]).strip(), str(d["protagonista_en_ingles"]).strip(), pages)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def to_json(story: Story) -> str:
    return json.dumps({"titulo": story.title, "protagonista_en_ingles": story.hero,
                       "paginas": [{"oraciones_en_espanol": sentence_list(p.text), "escena_en_ingles": p.scene}
                                   for p in story.pages]},
                      ensure_ascii=False)


def feedback(story: Story, r: Readability, target) -> tuple[str, str, str]:
    """What is off, the concrete examples, and how to fix it."""
    lo, hi = int(target.min_words_per_sentence), int(target.max_words_per_sentence)
    if r.spanish < 0.8:
        return NOT_SPANISH, "", "con oraciones cortas y palabras comunes"
    problem = OFF_TARGET.format(index=r.fernandez_huerta, min_index=target.min_index, wps=r.words_per_sentence,
                                lo=lo, hi=hi)
    sentences = sentence_list(story.text)
    details, how = [], []
    if r.words_per_sentence < lo:
        short = [s for s in sentences if len(s.split()) < lo][:4]
        details.append("Oraciones demasiado cortas, que debes unir con otras (con y, pero, porque, entonces): "
                       + " / ".join(short))
        how.append(f"uniendo oraciones cortas hasta que cada una tenga entre {lo} y {hi} palabras")
    elif r.words_per_sentence > hi:
        long = sorted(sentences, key=lambda s: -len(s.split()))[:3]
        details.append("Oraciones demasiado largas, que debes partir: " + " / ".join(long))
        how.append(f"partiendo oraciones largas hasta que cada una tenga entre {lo} y {hi} palabras")
    if r.fernandez_huerta < target.min_index:
        hard = long_words(story.text)[:8]
        if hard:
            details.append("Palabras largas que debes cambiar por otras más cortas y comunes: " + ", ".join(hard))
        how.append("con palabras más cortas y comunes")
    return problem, "\n".join(details) + ("\n" if details else ""), " y ".join(how) or "sin cambiar el nivel"


def write(llm: LLM, req: Request, strategy: str = "rewrite", budget: int = 3) -> Trace:
    """strategy: "baseline" (one story), "rewrite" (write, then up to budget-1 rewrites) or "best_of" (budget stories).
    The kept story is Trace.final: the draft closest to the target."""
    target = TARGETS[req.ages]
    lesson = f"- El cuento enseña, sin sermones: {req.lesson}.\n" if req.lesson else ""
    lo, hi = SENTENCE_WORDS[req.ages]
    level = LEVEL.format(ages=req.ages, lo=lo, hi=hi)
    prompt = WRITE.format(name=req.name, ages=req.ages, likes=req.likes, lesson=lesson, pages=PAGES, level=level)
    trace = Trace(target=target)

    def keep(story: Story | None) -> Draft | None:
        if story is None:
            return None
        r = measure(story.text)
        d = Draft(story, r, on_target(r, target))
        trace.drafts.append(d)
        return d

    first = keep(parse(llm.chat([{"role": "user", "content": prompt}], schema=SCHEMA)))
    if strategy == "baseline":
        return trace
    if strategy == "best_of":
        for _ in range(budget - 1):
            if trace.drafts and trace.final.on_target:
                break
            keep(parse(llm.chat([{"role": "user", "content": prompt}], schema=SCHEMA)))
        return trace
    current = first
    for _ in range(budget - 1):
        if current is None or current.on_target:
            break
        problem, details, how = feedback(current.story, current.readability, target)
        ask = REWRITE.format(ages=req.ages, problem=problem, details=details, how=how) + "\n\n" + to_json(
            current.story)
        current = keep(parse(llm.chat([{"role": "user", "content": ask}], schema=SCHEMA))) or current
    return trace
