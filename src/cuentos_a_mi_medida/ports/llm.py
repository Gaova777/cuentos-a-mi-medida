from typing import Protocol


class LLM(Protocol):
    name: str

    def chat(self, messages: list[dict], schema: dict | None = None) -> str: ...
