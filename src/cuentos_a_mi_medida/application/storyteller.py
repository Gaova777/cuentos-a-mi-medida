"""The LLM writes the story; the readability index decides whether a child of that age can read it, and if not, the
LLM rewrites it with the numbers in hand. The loop is what this project measures: how often the story lands in the
target band without it, and with it.
"""
import json
from dataclasses import dataclass, field

from cuentos_a_mi_medida.domain.readability import TARGETS, Readability, measure, on_target
from cuentos_a_mi_medida.domain.story import PAGES, Page, Request, Story
from cuentos_a_mi_medida.ports.llm import LLM

SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "protagonista_en_ingles": {"type": "string"},
        "paginas": {"type": "array", "minItems": PAGES, "maxItems": PAGES, "items": {
            "type": "object",
            "properties": {"texto_en_espanol": {"type": "string"}, "escena_en_ingles": {"type": "string"}},
            "required": ["texto_en_espanol", "escena_en_ingles"]}},
    },
    "required": ["titulo", "protagonista_en_ingles", "paginas"],
}

WRITE = """Eres autor de cuentos infantiles colombianos. Escribe un cuento corto en español de Colombia, cálido y con
un final feliz, para leer en voz alta.

- Protagonista: {name}, un niño o niña de {ages} años. Le gusta: {likes}.
{lesson}- Exactamente {pages} páginas, de 2 a 4 oraciones cada una. El título y el texto de las páginas, en español.
- Nada de violencia, miedo intenso, marcas comerciales ni personajes con derechos de autor.
- "protagonista_en_ingles": una descripción visual fija del protagonista, en inglés (edad, pelo, ropa, un detalle
  que lo identifique), sin nombres propios, para que un ilustrador lo dibuje igual en todas las páginas.
- "escena_en_ingles": para cada página, la escena en inglés para el ilustrador (qué pasa, dónde, sin texto).
{level}
Responde solo con JSON."""

LEVEL = ("- Para que lo lea solo un niño de {ages} años: oraciones de entre {lo} y {hi} palabras, con palabras "
         "cortas y comunes.")

REWRITE = """Este cuento es para que lo lea solo un niño de {ages} años. {problem}

Reescribe "texto_en_espanol" de cada página, en español, {how}, sin cambiar la historia, el título, el protagonista
ni las escenas. Responde solo con el mismo JSON."""

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

    @property
    def final(self) -> Draft:
        return self.drafts[-1]


def parse(reply: str) -> Story | None:
    try:
        d = json.loads(reply)
        pages = [Page(str(p["texto_en_espanol"]).strip(), str(p["escena_en_ingles"]).strip()) for p in d["paginas"]]
        if not pages or not all(p.text for p in pages):
            return None
        return Story(str(d["titulo"]).strip(), str(d["protagonista_en_ingles"]).strip(), pages)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def to_json(story: Story) -> str:
    return json.dumps({"titulo": story.title, "protagonista_en_ingles": story.hero,
                       "paginas": [{"texto_en_espanol": p.text, "escena_en_ingles": p.scene} for p in story.pages]},
                      ensure_ascii=False)


def write(llm: LLM, req: Request, max_rewrites: int = 2, guided: bool = True) -> Trace:
    """guided=False is the baseline: the age goes in the prompt, but nobody measures the result."""
    target = TARGETS[req.ages]
    lesson = f"- El cuento enseña, sin sermones: {req.lesson}.\n" if req.lesson else ""
    level = LEVEL.format(ages=req.ages, lo=int(target.min_words_per_sentence), hi=int(target.max_words_per_sentence))
    prompt = WRITE.format(name=req.name, ages=req.ages, likes=req.likes, lesson=lesson, pages=PAGES, level=level)
    trace = Trace()
    story = parse(llm.chat([{"role": "user", "content": prompt}], schema=SCHEMA))
    for attempt in range(max_rewrites + 1):
        if story is None:
            break
        r = measure(story.text)
        trace.drafts.append(Draft(story, r, on_target(r, target)))
        if not guided or on_target(r, target) or attempt == max_rewrites:
            break
        lo, hi = int(target.min_words_per_sentence), int(target.max_words_per_sentence)
        problem = (NOT_SPANISH if r.spanish < 0.8 else
                   OFF_TARGET.format(index=r.fernandez_huerta, min_index=target.min_index, wps=r.words_per_sentence,
                                     lo=lo, hi=hi))
        how = ("uniendo oraciones muy cortas en oraciones naturales" if r.words_per_sentence < lo else
               "con oraciones más cortas") + " y palabras más cortas y comunes"
        ask = REWRITE.format(ages=req.ages, problem=problem, how=how) + "\n\n" + to_json(story)
        story = parse(llm.chat([{"role": "user", "content": ask}], schema=SCHEMA)) or story
    return trace
