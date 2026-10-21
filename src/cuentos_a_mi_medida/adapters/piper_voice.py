from pathlib import Path


class PiperVoice:
    """Piper TTS, on the CPU. The default voice is es_MX "ald" (medium): the closest Latin American Spanish voice
    Piper has; there is no Colombian one."""

    def __init__(self, model: Path = Path("data/voices/es_MX-ald-medium.onnx")):
        from piper import PiperVoice as _Voice

        self.voice = _Voice.load(str(model))
        self.sample_rate = self.voice.config.sample_rate

    def speak(self, sentence: str) -> bytes:
        return b"".join(chunk.audio_int16_bytes for chunk in self.voice.synthesize(sentence))
