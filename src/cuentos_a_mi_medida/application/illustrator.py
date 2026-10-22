"""One illustration per page. The same character on every page is the hard part for a model that sees each page on its
own: every prompt carries the same character sheet (the story's fixed description of the hero), the same style, and
the same seed. scripts/consistency_benchmark.py measures what the sheet buys.
"""
from PIL import Image

from cuentos_a_mi_medida.domain.story import Story
from cuentos_a_mi_medida.ports.images import ImageModel, SafetyCheck

STYLE = "watercolor children's picture book illustration, soft warm light"


def prompt(story: Story, page: int, sheet: bool = True) -> str:
    """Short style, then the scene, then the sheet. CLIP reads 77 tokens and drops the rest: with a long style first,
    the scene came last and was cut off in 28 of 72 benchmark prompts."""
    scene = story.pages[page].scene
    return f"{STYLE}, {scene}, {story.hero}" if sheet else f"{STYLE}, {scene}"


def illustrate(model: ImageModel, story: Story, seed: int, sheet: bool = True, safety: SafetyCheck | None = None,
               max_unsafe: float = 0.5, retries: int = 2) -> list[Image.Image | None]:
    """An image the safety check flags is drawn again with another seed; if it keeps failing the page has no
    picture (None) rather than a doubtful one."""
    out = []
    for i in range(len(story.pages)):
        image = None
        for attempt in range(retries + 1):
            candidate = model.draw(prompt(story, i, sheet), seed + 1000 * attempt)
            if safety is None or safety.unsafe(candidate) < max_unsafe:
                image = candidate
                break
        out.append(image)
    return out
