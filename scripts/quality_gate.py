"""Fail the build when a measured promise breaks: stories stop landing at the reading level, the request gate lets
more through or blocks more fine requests, or the character sheet stops helping. Reads the benchmark results.

usage: uv run scripts/quality_gate.py
"""
import json
import sys
from pathlib import Path


def check(results: dict, limits: dict) -> list[str]:
    failures = []
    read = results.get("readability")
    if read:
        mode = limits["readability_strategy"]
        got = read[f"{mode}_all"]["on_target"]
        if got < limits["min_on_target"]:
            failures.append(f"readability: {mode} puts {got:.0%} of stories on target, below {limits['min_on_target']:.0%}")
        if got <= read["baseline_all"]["on_target"]:
            failures.append("readability: measuring no longer beats the baseline")
    safety = results.get("safety")
    if safety:
        if safety["inappropriate_blocked"] < limits["min_inappropriate_blocked"]:
            failures.append(f"safety: only {safety['inappropriate_blocked']:.0%} of inappropriate requests blocked")
        if safety["fine_wrongly_blocked"] > limits["max_fine_blocked"]:
            failures.append(f"safety: {safety['fine_wrongly_blocked']:.0%} of fine requests blocked")
    cons = results.get("consistency")
    if cons and cons["sheet"]["consistency"] <= cons["scene"]["consistency"]:
        failures.append("consistency: the character sheet no longer makes pages more alike")
    return failures


def load() -> dict:
    out = {}
    paths = {"readability": "results/readability/qwen3_4b-instruct.json", "safety": "results/safety/requests.json",
             "consistency": "results/consistency/summary.json"}
    for key, path in paths.items():
        p = Path(path)
        if p.exists():
            data = json.loads(p.read_text())
            out[key] = data.get("summary", data)
    return out


def main():
    failures = check(load(), json.loads(Path("quality_gate.json").read_text()))
    if failures:
        print("quality gate FAILED:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print("quality gate passed")


if __name__ == "__main__":
    main()
