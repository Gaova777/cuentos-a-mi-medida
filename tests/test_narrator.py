import io
import wave

from cuentos_a_mi_medida.application.narrator import PAUSE_S, narrate, split


class Beep:
    sample_rate = 1000

    def speak(self, sentence):
        return b"\x01\x00" * (100 * len(sentence.split()))  # 0.1 s per word


def test_split_keeps_spanish_punctuation_together():
    assert split("Salomé ve un colibrí. ¿Lo ves? ¡Qué bonito!") == ["Salomé ve un colibrí.", "¿Lo ves?", "¡Qué bonito!"]
    assert split("sin punto") == ["sin punto"]


def test_cues_follow_the_audio():
    wav, cues = narrate(Beep(), "Uno dos. Tres cuatro cinco.")
    assert [c.text for c in cues] == ["Uno dos.", "Tres cuatro cinco."]
    assert cues[0].start == 0 and cues[0].end == 0.2
    assert cues[1].start == round(0.2 + PAUSE_S, 3) and cues[1].end == round(0.5 + PAUSE_S, 3)
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getframerate() == 1000 and w.getnframes() == 500 + 2 * int(1000 * PAUSE_S)
