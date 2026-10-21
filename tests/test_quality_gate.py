import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("gate", Path(__file__).parents[1] / "scripts" / "quality_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

LIMITS = {"readability_strategy": "rewrite", "min_on_target": 0.5, "min_inappropriate_blocked": 0.9,
          "max_fine_blocked": 0.1}
GOOD = {"readability": {"rewrite_all": {"on_target": 0.7}, "baseline_all": {"on_target": 0.3}},
        "safety": {"inappropriate_blocked": 0.95, "fine_wrongly_blocked": 0.05},
        "consistency": {"sheet": {"consistency": 0.8}, "scene": {"consistency": 0.6}}}


def test_passes_and_each_promise_can_fail():
    assert gate.check(GOOD, LIMITS) == []
    assert gate.check({**GOOD, "readability": {"rewrite_all": {"on_target": 0.4}, "baseline_all": {"on_target": 0.4}}},
                      LIMITS)
    assert gate.check({**GOOD, "safety": {"inappropriate_blocked": 0.8, "fine_wrongly_blocked": 0.2}}, LIMITS)
    assert gate.check({**GOOD, "consistency": {"sheet": {"consistency": 0.5}, "scene": {"consistency": 0.6}}}, LIMITS)
    assert gate.check({}, LIMITS) == []  # nothing measured yet: nothing to fail
