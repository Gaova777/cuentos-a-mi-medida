"""Is this request fit for a story for a small child? The word list first; then the LLM, for what a list can't see."""
import json
from dataclasses import dataclass

from cuentos_a_mi_medida.domain.safety import problems
from cuentos_a_mi_medida.domain.story import Request
from cuentos_a_mi_medida.ports.llm import LLM

SCHEMA = {"type": "object", "properties": {"apropiado": {"type": "boolean"}, "razon": {"type": "string"}},
          "required": ["apropiado", "razon"]}

ASK = """Revisas pedidos para una app que escribe cuentos para niños de 5 a 10 años. Un padre escribió esto sobre su
hijo o hija y sobre el cuento que quiere:

- Gustos: {likes}
- Enseñanza: {lesson}

¿Se puede escribir un cuento infantil apropiado con esto? No es apropiado si pide violencia, miedo intenso, contenido
sexual, alcohol o drogas, burlas o discriminación, conductas peligrosas para un niño (por ejemplo irse con un extraño
o guardar secretos con un adulto), o datos personales. Gustos comunes de niños (fútbol, dinosaurios, princesas,
superhéroes, monstruos amigables, piratas) sí son apropiados. Responde solo con JSON."""


@dataclass
class Verdict:
    allowed: bool
    reasons: list[str]
    by: str  # "rules", "llm" or "ok"


def check(llm: LLM, req: Request) -> Verdict:
    found = problems(f"{req.name} {req.likes} {req.lesson}")
    if found:
        return Verdict(False, found, "rules")
    try:
        d = json.loads(llm.chat([{"role": "user", "content": ASK.format(likes=req.likes, lesson=req.lesson or "-")}],
                                schema=SCHEMA))
    except json.JSONDecodeError:
        return Verdict(False, ["the request could not be checked"], "llm")
    if not d.get("apropiado", False):
        return Verdict(False, [str(d.get("razon", ""))], "llm")
    return Verdict(True, [], "ok")
