from typing import Protocol


class Voice(Protocol):
    sample_rate: int

    def speak(self, sentence: str) -> bytes:
        """16-bit mono PCM."""
        ...
