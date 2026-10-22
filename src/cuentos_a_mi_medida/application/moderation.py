"""Is this request fit for a story for a small child? The word list first; then the LLM, for what a list can't see.

Two prompts, kept side by side because the benchmark compares them:
- "open" asks whether an appropriate story can be written from the request. A small model almost always says yes:
  any topic can be turned into a cautionary tale.
- "checklist" says what the story will do with the request (the hero enjoys the likes; the lesson is the moral) and
  asks for one yes/no per category of harm, after a short analysis of what a child copying the story would do. The
  default. Ollama writes keys in alphabetical order, so "analisis" comes before the "riesgo_" flags (the model thinks
  first), and it is capped: uncapped, the model kept writing it until the token limit and the JSON came back cut.
"""
import json
from dataclasses import dataclass

from cuentos_a_mi_medida.domain.safety import problems
from cuentos_a_mi_medida.domain.story import Request
from cuentos_a_mi_medida.ports.llm import LLM

OPEN_SCHEMA = {"type": "object", "properties": {"apropiado": {"type": "boolean"}, "razon": {"type": "string"}},
               "required": ["apropiado", "razon"]}

OPEN = """Revisas pedidos para una app que escribe cuentos para niños de 5 a 10 años. Un padre escribió esto sobre su
hijo o hija y sobre el cuento que quiere:

- Gustos: {likes}
- Enseñanza: {lesson}

¿Se puede escribir un cuento infantil apropiado con esto? No es apropiado si pide violencia, miedo intenso, contenido
sexual, alcohol o drogas, burlas o discriminación, conductas peligrosas para un niño (por ejemplo irse con un extraño
o guardar secretos con un adulto), o datos personales. Gustos comunes de niños (fútbol, dinosaurios, princesas,
superhéroes, monstruos amigables, piratas) sí son apropiados. Responde solo con JSON."""

# category -> what it means, as the model reads it
CATEGORIES = {
    "riesgo_violencia": "golpes, peleas, ataques, armas, heridas o maltrato a personas o animales",
    "riesgo_miedo_intenso": "algo que persigue, acecha o hace daño a niños; personajes de terror",
    "riesgo_contenido_sexual": "desnudez, tocar el cuerpo, o adultos que piden algo íntimo o secreto a un niño",
    "riesgo_alcohol_drogas_tabaco": "alcohol, drogas, cigarrillo, vapeo, medicamentos o sustancias que no son comida",
    "riesgo_burla_o_discriminacion": "burlarse de alguien o decir que un grupo de personas vale menos",
    "riesgo_conducta_peligrosa": ("algo que un niño podría imitar y lastimarse: fuego, alturas, agua, electricidad, la calle, "
                           "irse o hablar con desconocidos, escaparse, esconderse de sus papás"),
    "riesgo_mal_ejemplo": "mentir, robar, hacer trampa o desobedecer presentado como algo bueno o divertido",
}

CHECKLIST_SCHEMA = {
    "type": "object",
    "properties": {"analisis": {"type": "string", "maxLength": 240}, **{c: {"type": "boolean"} for c in CATEGORIES}},
    "required": ["analisis", *CATEGORIES],
}

CHECKLIST = """Revisas pedidos para una app que escribe cuentos para niños de 5 a 10 años. En el cuento, el protagonista
(el niño o la niña) disfruta y hace lo que dicen sus gustos, y la enseñanza es la moraleja. El cuento no va a advertir
ni a corregir nada: va a mostrar esto como algo bueno.

- Gustos: {likes}
- Enseñanza: {lesson}

Primero, en "analisis" (una o dos frases), piensa: si un niño de 6 años oye este cuento y quiere hacer lo mismo que
el protagonista, ¿qué haría, y podría lastimarse o lastimar a alguien? ¿El cuento haría sentir mal o daría miedo a
algún niño? Después, para cada categoría, responde true si el pedido la contiene y false si no:
{categories}

Gustos comunes de niños (dinosaurios, princesas, superhéroes, monstruos o brujas amigables, piratas, dragones,
deportes) y temas tristes tratados con cariño (una mascota perdida, un abuelo que murió, el divorcio de los papás) no
entran en ninguna categoría. Responde solo con JSON."""

PROMPTS = {"open": (OPEN, OPEN_SCHEMA), "checklist": (CHECKLIST, CHECKLIST_SCHEMA)}


@dataclass
class Verdict:
    allowed: bool
    reasons: list[str]
    by: str  # "rules", "llm" or "ok"


def flagged(reply: dict, prompt: str) -> list[str]:
    if prompt == "open":
        return [] if reply.get("apropiado", False) else ["apropiado"]
    return [c for c in CATEGORIES if reply.get(c, False)]


def check(llm: LLM, req: Request, prompt: str = "checklist") -> Verdict:
    found = problems(f"{req.name} {req.likes} {req.lesson}")
    if found:
        return Verdict(False, found, "rules")
    template, schema = PROMPTS[prompt]
    categories = "\n".join(f"- {c}: {d}" for c, d in CATEGORIES.items())
    text = template.format(likes=req.likes, lesson=req.lesson or "-", categories=categories)
    try:
        d = json.loads(llm.chat([{"role": "user", "content": text}], schema=schema))
    except json.JSONDecodeError:
        return Verdict(False, ["no pudimos revisar el pedido"], "llm")
    bad = flagged(d, prompt)
    if bad and prompt == "open":
        return Verdict(False, [str(d.get("razon", ""))], "llm")
    if bad:
        return Verdict(False, [c.removeprefix("riesgo_").replace("_", " ") for c in bad], "llm")
    return Verdict(True, [], "ok")
