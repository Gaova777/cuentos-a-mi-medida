"""The one GPU worker: takes story jobs from the queue and makes the books. Models load once and stay; the LLM unloads
after each call (keep_alive 0) so the image model has the card.

usage: uv run python -m cuentos_a_mi_medida.entrypoints.worker
"""
import logging
import time

from cuentos_a_mi_medida.adapters.aws import Library
from cuentos_a_mi_medida.adapters.diffusers_images import NsfwCheck, TurboImages
from cuentos_a_mi_medida.adapters.ollama import OllamaLLM
from cuentos_a_mi_medida.adapters.piper_voice import PiperVoice
from cuentos_a_mi_medida.application.bookmaker import make

log = logging.getLogger("worker")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    library, llm, images, voice, safety = Library(), OllamaLLM(), TurboImages(), PiperVoice(), NsfwCheck()
    log.info("ready")
    while True:
        job = library.next_job()
        if job is None:
            continue
        body, receipt = job
        start = time.time()
        try:
            result = make(body, library, llm, images, voice, safety)
            library.done(receipt)
            log.info("%s %s in %.0f s", result["story_id"], result["status"], time.time() - start)
        except Exception:
            # left in the queue: it comes back after the visibility timeout, and to the dead-letter queue after 3
            log.exception("story %s failed", body.get("story_id"))
            library.update(body["story_id"], "retrying")


if __name__ == "__main__":
    main()
