"""Narration a child can follow: each sentence is spoken on its own and its start and end are kept, so the reader can
highlight the sentence that is being read."""
import io
import re
import wave
from dataclasses import dataclass

from cuentos_a_mi_medida.ports.voice import Voice

PAUSE_S = 0.35
_SENTENCES = re.compile(r"[^.!?¡¿…]*[^.!?…]*[.!?…]+|[^.!?…]+$")


@dataclass
class Cue:
    text: str
    start: float
    end: float


def split(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCES.findall(text.strip()) if s.strip()]


def narrate(voice: Voice, text: str) -> tuple[bytes, list[Cue]]:
    """A WAV file and the cue of each sentence in it."""
    pause = b"\x00\x00" * int(voice.sample_rate * PAUSE_S)
    pcm, cues, t = bytearray(), [], 0.0
    for sentence in split(text):
        audio = voice.speak(sentence)
        seconds = len(audio) / 2 / voice.sample_rate
        cues.append(Cue(sentence, round(t, 3), round(t + seconds, 3)))
        pcm += audio + pause
        t += seconds + PAUSE_S
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(voice.sample_rate)
        w.writeframes(bytes(pcm))
    return buf.getvalue(), cues
