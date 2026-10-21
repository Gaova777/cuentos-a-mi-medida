"""Does the story land at the child's reading level? 12 requests x 3 age bands, written once with the age in the prompt
(baseline) and again with the measure-and-rewrite loop (guided, up to 2 rewrites).

Resumable: one JSON line per story in data/readability/<model>.jsonl.

usage: uv run scripts/readability_benchmark.py
"""
import argparse
import json
import time
from pathlib import Path

from cuentos_a_mi_medida.adapters.ollama import OllamaLLM
from cuentos_a_mi_medida.application.storyteller import write
from cuentos_a_mi_medida.domain.readability import TARGETS
from cuentos_a_mi_medida.domain.story import Request

CHILDREN = [
    ("Salomé", "los colibríes y bailar cumbia", "pedir ayuda cuando algo es difícil"),
    ("Emiliano", "los volcanes y el fútbol", ""),
    ("Valentina", "los dinosaurios", "decir la verdad"),
    ("Thiago", "los trenes y el café de la finca del abuelo", "ser paciente"),
    ("Luciana", "pintar y los gatos", "compartir"),
    ("Samuel", "el mar y los delfines", ""),
    ("Isabella", "las estrellas y los cohetes", "no rendirse"),
    ("Jerónimo", "la bicicleta y las montañas", "cuidar la naturaleza"),
    ("Mariana", "los ríos y los peces", "hacer amigos nuevos"),
    ("Matías", "los robots", "pedir perdón"),
    ("Antonella", "la música y la guacharaca", ""),
    ("Martín", "las arepas y cocinar con la abuela", "ayudar en casa"),
]


def main(args):
    out = Path("data/readability") / f"{args.model.replace(':', '_')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {(r["name"], r["ages"], r["mode"]) for r in map(json.loads, out.open())} if out.exists() else set()
    llm = OllamaLLM(args.model)
    with out.open("a") as f:
        for name, likes, lesson in CHILDREN:
            for ages in TARGETS:
                for mode in ("baseline", "guided"):
                    if (name, ages, mode) in done:
                        continue
                    start = time.time()
                    trace = write(llm, Request(name, ages, likes, lesson), guided=mode == "guided")
                    if not trace.drafts:
                        row = {"name": name, "ages": ages, "mode": mode, "failed": True}
                    else:
                        d = trace.final
                        row = {"name": name, "ages": ages, "mode": mode, "on_target": d.on_target,
                               "drafts": len(trace.drafts), "seconds": round(time.time() - start),
                               **{k: getattr(d.readability, k) for k in
                                  ("fernandez_huerta", "words_per_sentence", "spanish", "words")},
                               "first": {"fernandez_huerta": trace.drafts[0].readability.fernandez_huerta,
                                         "words_per_sentence": trace.drafts[0].readability.words_per_sentence,
                                         "on_target": trace.drafts[0].on_target},
                               "title": d.story.title, "text": d.story.text}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                    print(f"  {name:10} {ages:5} {mode:8} {row.get('on_target')} "
                          f"FH {row.get('fernandez_huerta')} wps {row.get('words_per_sentence')}", flush=True)
    summarize(out)


def summarize(path: Path):
    rows = [json.loads(line) for line in path.open()]
    summary = {"model": path.stem, "stories": len(rows)}
    for mode in ("baseline", "guided"):
        for ages in [*TARGETS, "all"]:
            rs = [r for r in rows if r["mode"] == mode and (ages == "all" or r["ages"] == ages) and not r.get("failed")]
            if not rs:
                continue
            summary[f"{mode}_{ages}"] = {
                "n": len(rs), "on_target": sum(r["on_target"] for r in rs) / len(rs),
                "mean_index": round(sum(r["fernandez_huerta"] for r in rs) / len(rs), 1),
                "mean_words_per_sentence": round(sum(r["words_per_sentence"] for r in rs) / len(rs), 1),
                "mean_drafts": round(sum(r["drafts"] for r in rs) / len(rs), 2),
                "spanish_ok": sum(r["spanish"] >= 0.8 for r in rs) / len(rs)}
    Path("results/readability").mkdir(parents=True, exist_ok=True)
    Path(f"results/readability/{path.stem}.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:4b-instruct")
    main(parser.parse_args())
