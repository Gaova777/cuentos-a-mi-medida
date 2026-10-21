import json

from cuentos_a_mi_medida.application.storyteller import parse, to_json, write
from cuentos_a_mi_medida.domain.story import PAGES, Request

HARD = "La extraordinaria expedición de Mariana atravesó montañas majestuosas y valles interminables buscando tesoros."
EASY = "Mariana ve un río. El río es azul. Ella ríe."


def story(text):
    return json.dumps({"title": "El río", "hero": "a girl with curly hair and a yellow raincoat",
                       "pages": [{"text": text, "scene": "a girl by a river"} for _ in range(PAGES)]})


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
    assert "Mariana" in llm.prompts[0] and "compartir" in llm.prompts[0] and "máximo 8 palabras" in llm.prompts[0]
    assert "Fernández-Huerta" in llm.prompts[1] and "la meta es al menos 95" in llm.prompts[1]


def test_baseline_measures_but_never_rewrites():
    trace = write(Scripted([story(HARD)]), REQ, guided=False)
    assert len(trace.drafts) == 1 and not trace.final.on_target


def test_rewrites_are_capped_and_bad_json_keeps_the_last_story():
    trace = write(Scripted([story(HARD), "not json", story(HARD)]), REQ, max_rewrites=2)
    assert len(trace.drafts) == 3 and not trace.final.on_target


def test_parse_round_trip():
    s = parse(story(EASY))
    assert s.title == "El río" and len(s.pages) == PAGES and parse(to_json(s)).pages[0].text == EASY
    assert parse('{"title": "x"}') is None
