"""What a story is, and what a parent asks for. Only text: there is no field for a photo, by design."""
from dataclasses import dataclass, field

PAGES = 6


@dataclass(frozen=True)
class Request:
    name: str  # the child's first name, who becomes the hero
    ages: str  # a key of readability.TARGETS
    likes: str  # what the child is into, in the parent's words
    lesson: str = ""  # an optional value for the story (sharing, courage, ...)


@dataclass
class Page:
    text: str  # Spanish, for the child
    scene: str  # English, for the illustrator model


@dataclass
class Story:
    title: str
    hero: str  # a fixed visual description of the main character, reused on every page
    pages: list[Page] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)
