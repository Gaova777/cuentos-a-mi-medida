import json

from cuentos_a_mi_medida.application.moderation import check
from cuentos_a_mi_medida.domain.safety import problems
from cuentos_a_mi_medida.domain.story import Request


def test_rules_catch_personal_data_and_bad_words_with_or_without_accents():
    assert problems("le gustan los dinosaurios y el fútbol") == []
    assert "personal data" in problems("vive en la Calle 23 #4-56")[0]
    assert "personal data" in problems("llamar al 310 555 1234")[0]
    assert "personal data" in problems("mamá: ana@correo.com")[0]
    assert "sangre" in problems("un dragón lleno de SANGRE")[0]
    assert "cocaina" in problems("cocaína")[0]
    assert problems("la armadura del caballero")  # 'arma' prefix: a known false positive of a word list


class Says:
    name = "says"

    def __init__(self, allowed, reason=""):
        self.reply = json.dumps({"apropiado": allowed, "razon": reason})
        self.calls = 0

    def chat(self, messages, schema=None):
        self.calls += 1
        return self.reply


def test_rules_decide_before_the_llm_is_asked():
    llm = Says(True)
    v = check(llm, Request("Ana", "7-8", "las pistolas de agua"))
    assert not v.allowed and v.by == "rules" and llm.calls == 0


def test_llm_catches_what_the_list_cannot():
    v = check(Says(False, "irse con un extraño es peligroso"), Request("Ana", "7-8", "los dulces",
                                                                         "irse con el señor que le regala dulces"))
    assert not v.allowed and v.by == "llm" and "extraño" in v.reasons[0]
    assert check(Says(True), Request("Ana", "7-8", "los dinosaurios")).allowed
