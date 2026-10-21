from PIL import Image

from cuentos_a_mi_medida.application.illustrator import STYLE, illustrate, prompt
from cuentos_a_mi_medida.domain.story import Page, Story

STORY = Story("El río", "a girl with curly hair and a yellow raincoat",
              [Page("Mariana ve un río.", "a girl by a river"), Page("Mariana nada.", "a girl swimming")])


class Recorder:
    def __init__(self):
        self.calls = []

    def draw(self, prompt, seed):
        self.calls.append((prompt, seed))
        return Image.new("RGB", (8, 8))


class FlagsFirst:
    """Flags the first n images it sees."""

    def __init__(self, n):
        self.n = n

    def unsafe(self, image):
        self.n -= 1
        return 0.9 if self.n >= 0 else 0.1


def test_every_page_carries_the_character_sheet_and_the_same_seed():
    model = Recorder()
    images = illustrate(model, STORY, seed=7)
    assert len(images) == 2 and all(images)
    assert all(STORY.hero in p and p.startswith(STYLE) for p, _ in model.calls)
    assert {s for _, s in model.calls} == {7}
    assert STORY.hero not in prompt(STORY, 0, sheet=False)


def test_flagged_images_are_redrawn_then_dropped():
    model = Recorder()
    images = illustrate(model, STORY, seed=7, safety=FlagsFirst(1))
    assert all(images) and [s for _, s in model.calls] == [7, 1007, 7]
    model = Recorder()
    assert illustrate(model, STORY, seed=7, safety=FlagsFirst(3), retries=2)[0] is None
