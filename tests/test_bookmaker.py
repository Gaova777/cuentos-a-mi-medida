import json

from fastapi.testclient import TestClient
from PIL import Image

from cuentos_a_mi_medida.application.bookmaker import make
from cuentos_a_mi_medida.domain.story import PAGES
from cuentos_a_mi_medida.entrypoints import api

EASY = "Mariana ve un río. El río es azul. Ella ríe."


class MemoryLibrary:
    def __init__(self):
        self.items, self.files, self.queue = {}, {}, []

    def create(self, request):
        sid = f"s{len(self.items) + 1}"
        self.items[sid] = {"story_id": sid, "status": "queued", "created": len(self.items), "request": request}
        self.queue.append({"story_id": sid, **request})
        return sid

    def update(self, sid, status, **fields):
        self.items[sid].update(status=status, **fields)

    def get(self, sid):
        return self.items.get(sid)

    def all(self):
        return sorted(self.items.values(), key=lambda i: -i["created"])

    def put(self, key, body, content_type):
        self.files[key] = (body, content_type)

    def url(self, key, seconds=3600):
        return f"http://files/{key}"


class StoryLLM:
    name = "story"

    def chat(self, messages, schema=None):
        if "apropiado" in json.dumps(schema or {}):
            return json.dumps({"apropiado": True, "razon": ""})
        return json.dumps({"titulo": "El río", "protagonista_en_ingles": "a girl in a yellow raincoat",
                           "paginas": [{"oraciones_en_espanol": [EASY], "escena_en_ingles": "a river"}] * PAGES})


class Blank:
    def draw(self, prompt, seed):
        return Image.new("RGB", (16, 16))


class Silent:
    sample_rate = 1000

    def speak(self, sentence):
        return b"\x00\x00" * 100


def test_make_writes_draws_narrates_and_stores():
    lib = MemoryLibrary()
    sid = lib.create({"name": "Mariana", "ages": "5-6", "likes": "los ríos", "lesson": ""})
    result = make(lib.queue.pop(), lib, StoryLLM(), Blank(), Silent())
    item = lib.get(sid)
    assert result["status"] == "done" and item["status"] == "done" and item["title"] == "El río"
    assert len(item["pages"]) == PAGES and len(item["pages"][0]["cues"]) == 3
    assert item["readability"]["on_target"] and item["readability"]["drafts"] == 1
    assert {k.rsplit(".", 1)[1] for k in lib.files} == {"jpg", "wav"} and len(lib.files) == 2 * PAGES


def test_api_checks_queues_and_serves(monkeypatch):
    lib = MemoryLibrary()
    monkeypatch.setattr(api, "library", lambda: lib)
    monkeypatch.setattr(api, "moderator_llm", lambda: StoryLLM())
    c = TestClient(api.app)
    r = c.post("/stories", json={"name": "Mariana", "ages": "5-6", "likes": "los ríos"})
    assert r.status_code == 202 and lib.queue
    blocked = c.post("/stories", json={"name": "Mariana", "ages": "5-6", "likes": "las pistolas"})
    assert blocked.status_code == 422 and blocked.json()["detail"]["by"] == "rules"
    assert c.post("/stories", json={"name": "Mariana", "ages": "11-12", "likes": "x y"}).status_code == 422
    make(lib.queue.pop(), lib, StoryLLM(), Blank(), Silent())
    s = c.get(f"/stories/{r.json()['story_id']}").json()
    assert s["pages"][0]["image_url"].startswith("http://files/") and s["pages"][0]["audio_url"].endswith(".wav")
    shelf = c.get("/stories").json()[0]
    assert "pages" not in shelf and shelf["cover_url"].endswith("page1.jpg")
    assert c.get("/stories/nope").status_code == 404
