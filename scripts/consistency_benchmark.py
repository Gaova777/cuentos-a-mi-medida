"""Does the character sheet keep the hero the same across pages? 12 stories, each illustrated twice with SDXL-Turbo
and the same seed: once with the sheet in every prompt, once with the scene alone.

- Consistency: mean cosine similarity between the pages of a story, on DINOv2 features (which respond to what an object
  looks like more than to what it is).
- Scene fidelity: CLIP similarity between each page and its scene text, so the sheet doesn't buy consistency by
  drawing the same picture six times.

usage: uv run --group repro scripts/consistency_benchmark.py   (stories are written first, with the LLM)
"""
import itertools
import json
from pathlib import Path

import numpy as np
import torch

from cuentos_a_mi_medida.application.illustrator import illustrate
from cuentos_a_mi_medida.application.storyteller import parse, to_json, write
from cuentos_a_mi_medida.domain.story import Request

OUT = Path("data/consistency")
REQUESTS = [
    Request("Salomé", "5-6", "los colibríes y bailar cumbia"), Request("Emiliano", "9-10", "los volcanes y el fútbol"),
    Request("Valentina", "7-8", "los dinosaurios"), Request("Thiago", "7-8", "los trenes y la finca del abuelo"),
    Request("Luciana", "5-6", "pintar y los gatos"), Request("Samuel", "9-10", "el mar y los delfines"),
    Request("Isabella", "7-8", "las estrellas y los cohetes"), Request("Jerónimo", "9-10", "la bicicleta"),
    Request("Mariana", "5-6", "los ríos y los peces"), Request("Matías", "7-8", "los robots"),
    Request("Antonella", "9-10", "la música y la guacharaca"), Request("Martín", "5-6", "las arepas y cocinar"),
]


def stories() -> list:
    path = OUT / "stories.json"
    if path.exists():
        return [parse(s) for s in json.loads(path.read_text())]
    from cuentos_a_mi_medida.adapters.ollama import OllamaLLM

    llm = OllamaLLM()
    out = [write(llm, r).final.story for r in REQUESTS]
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([to_json(s) for s in out], ensure_ascii=False, indent=1))
    return out


@torch.no_grad()
def main():
    from transformers import AutoImageProcessor, AutoModel, CLIPModel, CLIPProcessor

    from cuentos_a_mi_medida.adapters.diffusers_images import TurboImages

    torch.cuda.set_per_process_memory_fraction(0.85)
    tales = stories()
    model = TurboImages()
    for k, story in enumerate(tales):
        for sheet in (True, False):
            folder = OUT / f"story{k:02d}_{'sheet' if sheet else 'scene'}"
            if folder.exists():
                continue
            folder.mkdir(parents=True)
            for i, img in enumerate(illustrate(model, story, seed=1000 + k, sheet=sheet)):
                img.save(folder / f"page{i + 1}.png")
    del model
    torch.cuda.empty_cache()

    dino_proc = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
    dino = AutoModel.from_pretrained("facebook/dinov2-small").cuda().eval()
    clip_proc = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
    clip = CLIPModel.from_pretrained("openai/clip-vit-large-patch14").cuda().eval()
    from PIL import Image

    rows = []
    for k, story in enumerate(tales):
        for cond in ("sheet", "scene"):
            imgs = [Image.open(OUT / f"story{k:02d}_{cond}" / f"page{i + 1}.png") for i in range(len(story.pages))]
            feats = dino(**dino_proc(images=imgs, return_tensors="pt").to("cuda")).last_hidden_state[:, 0]
            feats = torch.nn.functional.normalize(feats, dim=-1)
            pairs = [float(feats[a] @ feats[b]) for a, b in itertools.combinations(range(len(imgs)), 2)]
            inputs = clip_proc(text=[p.scene for p in story.pages], images=imgs, return_tensors="pt", padding=True,
                               truncation=True).to("cuda")
            out = clip(**inputs)
            img_e = torch.nn.functional.normalize(out.image_embeds, dim=-1)
            txt_e = torch.nn.functional.normalize(out.text_embeds, dim=-1)
            rows.append({"story": k, "condition": cond, "consistency": float(np.mean(pairs)),
                         "scene_clip": float((img_e * txt_e).sum(-1).mean())})
    summary = {}
    for cond in ("sheet", "scene"):
        rs = [r for r in rows if r["condition"] == cond]
        summary[cond] = {"consistency": round(float(np.mean([r["consistency"] for r in rs])), 4),
                         "scene_clip": round(float(np.mean([r["scene_clip"] for r in rs])), 4)}
    better = sum(a["consistency"] > b["consistency"] for a, b in zip(rows[::2], rows[1::2], strict=True))
    summary["stories_more_consistent_with_sheet"] = f"{better}/{len(tales)}"
    Path("results/consistency").mkdir(parents=True, exist_ok=True)
    Path("results/consistency/summary.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
