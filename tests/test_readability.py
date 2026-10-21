import pytest

from cuentos_a_mi_medida.domain.readability import TARGETS, measure, on_target, sentences, syllables


@pytest.mark.parametrize(("word", "n"), [
    ("casa", 2), ("perro", 2), ("mariposa", 4), ("poeta", 3), ("leer", 2), ("cielo", 2), ("ciudad", 2),
    ("día", 2), ("búho", 2), ("país", 2), ("queso", 2), ("guitarra", 3), ("pingüino", 3), ("hoy", 1), ("muy", 1),
    ("rey", 1), ("y", 1), ("aeropuerto", 5), ("murciélago", 4), ("Colombia", 3), ("baúl", 2), ("ahora", 3),
])
def test_spanish_syllables(word, n):
    assert syllables(word) == n


def test_sentences_count_ends_and_ignore_empty_parts():
    assert sentences("Hola. ¿Cómo estás? ¡Bien!...") == 3
    assert sentences("sin punto final") == 1


def test_short_simple_text_is_easier_than_long_complex_text():
    easy = measure("El gato come. El gato duerme. El sol sale. La niña ríe.")
    hard = measure("La incomprensible complejidad administrativa de las instituciones gubernamentales "
                   "contemporáneas desalienta considerablemente la participación ciudadana.")
    assert easy.fernandez_huerta > 100 and hard.fernandez_huerta < 30
    assert easy.words == 12 and easy.sentences == 4 and easy.words_per_sentence == 3.0


def test_formula_rewards_short_sentences():
    # 4 words, 6 syllables, 1 sentence: 206.84 - 0.6 * 150 - 1.02 * 4
    r = measure("Mi casa es azul.")
    assert (r.words, r.syllables, r.sentences) == (4, 6, 1)
    assert r.fernandez_huerta == round(206.84 - 0.6 * 150 - 1.02 * 4, 1)
    # the same words, in one sentence or in three
    one = measure("El perro corre, salta, juega y ríe en el parque con su pelota.")
    split = measure("El perro corre. Salta. Juega y ríe en el parque con su pelota.")
    assert split.fernandez_huerta > one.fernandez_huerta


def test_targets_are_bands_of_sentence_length():
    r = measure("El oso vio un río grande y azul, y se metió a nadar.")
    assert on_target(r, TARGETS["9-10"])
    assert not on_target(r, TARGETS["5-6"])  # 13 words in one sentence
    choppy = measure("El oso nada. El sol sale. El río es azul.")
    assert on_target(choppy, TARGETS["5-6"]) and not on_target(choppy, TARGETS["9-10"])


def test_spanish_share_tells_the_language():
    from cuentos_a_mi_medida.domain.readability import spanish_share

    assert spanish_share("El gato come y la niña ríe con su perro.") == 1.0
    assert spanish_share("The cat eats and the girl laughs with her dog.") == 0.0
