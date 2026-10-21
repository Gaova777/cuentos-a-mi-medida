import json

from cuentos_a_mi_medida.application.storyteller import parse, to_json, write
from cuentos_a_mi_medida.domain.story import PAGES, Request

HARD = "La extraordinaria expedición de Mariana atravesó montañas majestuosas y valles interminables buscando tesoros."
EASY = "Mariana ve un río. El río es azul. Ella ríe."


def story(text):
    return json.dumps({"titulo": "El río", "protagonista_en_ingles": "a girl with curly hair and a yellow raincoat",
                       "paginas": [{"texto_en_espanol": text, "escena_en_ingles": "a girl by a river"}
                                   for _ in range(PAGES)]})


class Scripted:
    name = "scripted"

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def chat(self, messages, schema=None):
        self.prompts.append(messages[-1]["content"])
        return self.replies.pop(0)


REQ = Request("Mariana", "5-6", "los ríos y los peces", "compartir")


def test_guided_rewrites_until_on_target():
    llm = Scripted([story(HARD), story(EASY)])
    trace = write(llm, REQ)
    assert [d.on_target for d in trace.drafts] == [False, True]
    assert "Mariana" in llm.prompts[0] and "compartir" in llm.prompts[0] and "entre 3 y 8 palabras" in llm.prompts[0]
    assert "Fernández-Huerta" in llm.prompts[1] and "la meta es al menos 90" in llm.prompts[1]


def test_baseline_measures_but_never_rewrites():
    trace = write(Scripted([story(HARD)]), REQ, strategy="baseline")
    assert len(trace.drafts) == 1 and not trace.final.on_target


def test_rewrites_are_capped_and_bad_json_is_skipped():
    trace = write(Scripted([story(HARD), "not json", story(HARD)]), REQ, budget=3)
    assert len(trace.drafts) == 2 and not trace.final.on_target


def test_a_worse_rewrite_does_not_replace_a_better_draft():
    close = "Mariana ve un río azul. El río canta. Ella ríe mucho con su amiga."  # near the 5-6 band
    llm = Scripted([story(close), story(HARD), story(HARD)])
    trace = write(llm, REQ)
    assert trace.final.story.pages[0].text == close


def test_best_of_keeps_the_closest_and_stops_when_on_target():
    llm = Scripted([story(HARD), story(EASY), story(HARD)])
    trace = write(llm, REQ, strategy="best_of")
    assert len(trace.drafts) == 2 and trace.final.on_target and len(llm.prompts) == 2
    assert llm.prompts[0] == llm.prompts[1]  # the same request again, not a rewrite


def test_parse_round_trip():
    s = parse(story(EASY))
    assert s.title == "El río" and len(s.pages) == PAGES and parse(to_json(s)).pages[0].text == EASY
    assert parse('{"titulo": "x"}') is None


def test_english_text_is_sent_back_even_if_easy():
    llm = Scripted([story("The girl sees a river. It is blue. She smiles."), story(EASY)])
    trace = write(llm, REQ)
    assert trace.drafts[0].readability.spanish < 0.8 and not trace.drafts[0].on_target
    assert "no está en español" in llm.prompts[1] and trace.final.on_target


def test_telegraphic_text_is_asked_to_join_sentences():
    req = Request("Emiliano", "9-10", "los volcanes")
    choppy = "Emiliano mira el volcán. El sol brilla. Sonríe."
    natural = "Emiliano mira el volcán desde la ventana de su casa. El sol de la tarde pinta el cielo de naranja."
    llm = Scripted([story(choppy), story(natural)])
    trace = write(llm, req)
    assert not trace.drafts[0].on_target and "uniendo oraciones cortas" in llm.prompts[1]
    assert "Sonríe." in llm.prompts[1]  # the actual short sentences are quoted
