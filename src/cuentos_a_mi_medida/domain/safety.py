"""The first gate on what a parent types: personal data that should never go into a story, and words that have no
place in a story for a small child. Cheap and certain; the LLM moderator (application/moderation.py) handles what a
word list can't, like an innocent-looking request with a bad idea in it.
"""
import re
import unicodedata

# kept short on purpose: words that are wrong in a children's story in any context, Spanish and English
BLOCKED = [
    "sangre", "matar", "mata", "muerto", "muerte", "asesin", "arma", "pistola", "cuchillo", "bomba", "droga", "cocaina",
    "marihuana", "cerveza", "borracho", "alcohol", "sexo", "sexual", "desnud", "porno", "suicid", "violar", "secuestr",
    "tortur", "terror", "blood", "kill", "dead", "gun", "knife", "drug", "beer", "drunk", "naked", "nude", "sex",
    "porn", "suicide", "kidnap", "torture",
]
_WORDS = re.compile(r"[a-zñ]+")
PHONE = re.compile(r"(?:\+?\d[\d\s-]{6,}\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
ADDRESS = re.compile(r"\b(calle|carrera|cra|cl|avenida|av|diagonal|transversal)\.?\s*\d+", re.IGNORECASE)


def _plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def problems(text: str) -> list[str]:
    """Reasons to refuse, in Spanish, as the parent reads them. Empty means the text passes this gate."""
    out = []
    if PHONE.search(text) or EMAIL.search(text) or ADDRESS.search(text):
        out.append("tiene datos personales (un teléfono, un correo o una dirección): el cuento solo necesita un nombre")
    words = _WORDS.findall(_plain(text))
    hits = sorted({b for b in BLOCKED for w in words if w.startswith(b)})
    if hits:
        out.append(f"menciona algo que no va en un cuento infantil ({', '.join(hits)})")
    return out
