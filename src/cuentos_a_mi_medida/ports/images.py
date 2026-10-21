from typing import Protocol

from PIL import Image


class ImageModel(Protocol):
    def draw(self, prompt: str, seed: int) -> Image.Image: ...


class SafetyCheck(Protocol):
    def unsafe(self, image: Image.Image) -> float: ...
