"""From a request in the queue to a finished book in the library: write, check, illustrate, narrate, store. One job at
a time, because there is one GPU."""
import io
import random
from dataclasses import asdict

from cuentos_a_mi_medida.application.illustrator import illustrate
from cuentos_a_mi_medida.application.narrator import narrate
from cuentos_a_mi_medida.application.storyteller import write
from cuentos_a_mi_medida.domain.readability import TARGETS
from cuentos_a_mi_medida.domain.story import Request


def make(job: dict, library, llm, images, voice, safety=None) -> dict:
    story_id = job["story_id"]
    req = Request(job["name"], job["ages"], job["likes"], job.get("lesson", ""))
    library.update(story_id, "writing")
    trace = write(llm, req, strategy=job.get("strategy", "rewrite"))
    if not trace.drafts:
        library.update(story_id, "failed", error="the story could not be written")
        return {"story_id": story_id, "status": "failed"}
    draft = trace.final
    story = draft.story
    library.update(story_id, "drawing", title=story.title)
    seed = random.Random(story_id).randrange(2**31)
    pictures = illustrate(images, story, seed, safety=safety)
    library.update(story_id, "narrating", title=story.title)
    pages = []
    for i, (page, picture) in enumerate(zip(story.pages, pictures, strict=True)):
        entry = {"text": page.text, "image": None}
        if picture is not None:
            buf = io.BytesIO()
            picture.save(buf, format="JPEG", quality=90)
            entry["image"] = f"{story_id}/page{i + 1}.jpg"
            library.put(entry["image"], buf.getvalue(), "image/jpeg")
        wav, cues = narrate(voice, page.text)
        entry["audio"] = f"{story_id}/page{i + 1}.wav"
        entry["cues"] = [asdict(c) for c in cues]
        library.put(entry["audio"], wav, "audio/wav")
        pages.append(entry)
    target = TARGETS[req.ages]
    level = {"fernandez_huerta": draft.readability.fernandez_huerta,
             "words_per_sentence": draft.readability.words_per_sentence, "on_target": draft.on_target,
             "target": {"min_index": target.min_index, "words_per_sentence": [target.min_words_per_sentence,
                                                                             target.max_words_per_sentence]},
             "drafts": len(trace.drafts)}
    library.update(story_id, "done", title=story.title, pages=pages, readability=level)
    return {"story_id": story_id, "status": "done"}
