import httpx


class OllamaLLM:
    def __init__(self, model: str = "qwen3:4b-instruct", url: str = "http://localhost:11434", temperature: float = 0.7,
                 num_ctx: int = 8192, max_tokens: int = 2048, keep_alive: str | int = 0):
        self.name = model
        self.url = url
        self.options = {"temperature": temperature, "num_ctx": num_ctx, "num_predict": max_tokens}
        # 0 unloads the model after each call, so the image model can have the GPU
        self.keep_alive = keep_alive
        self.client = httpx.Client(timeout=900)

    def chat(self, messages: list[dict], schema: dict | None = None) -> str:
        body = {"model": self.name, "messages": messages, "stream": False, "think": False, "options": self.options,
                "keep_alive": self.keep_alive}
        if schema:
            body["format"] = schema
        resp = self.client.post(f"{self.url}/api/chat", json=body)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
