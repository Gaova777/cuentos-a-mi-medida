"""Score the reproduction set the way the paper does, plus two stand-ins for what a 1k-sample run can't do:

- CLIP score with ViT-g-14 trained on LAION-2B (the paper's model): cosine between caption and image.
- FID and KID against the 1,000 real COCO images, at 512 px (clean-fid). With 1k samples FID is biased upward, so it
  is only for comparing models here, not with the paper's FID-5k; KID is unbiased at this size.
- PickScore (Kirstain et al., 2023), a model trained on human preferences between images: a stand-in for the paper's
  user study.
- Diversity: mean LPIPS between the 4 seeds of the same caption (the paper says ADD's samples are less diverse than
  its teacher's).

usage: uv run --group repro scripts/evaluate_add.py
"""
import itertools
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

OUT = Path("data/repro")


def real_folder(items) -> Path:
    folder = OUT / "real512"
    folder.mkdir(parents=True, exist_ok=True)
    for it in items:
        dst = folder / f"{it['image_id']}.png"
        if not dst.exists():
            img = Image.open(Path("data/raw/val2017") / it["file"]).convert("RGB")
            s = min(img.size)
            left, top = (img.width - s) // 2, (img.height - s) // 2
            img.crop((left, top, left + s, top + s)).resize((512, 512), Image.BICUBIC).save(dst)
    return folder


def resized(folder: Path) -> Path:
    """clean-fid compares at 299 px internally, but the 1024 px models get the same 512 px treatment as the rest."""
    out = folder.with_name(folder.name + "_512")
    out.mkdir(exist_ok=True)
    for p in folder.glob("*.png"):
        dst = out / p.name
        if not dst.exists():
            Image.open(p).convert("RGB").resize((512, 512), Image.BICUBIC).save(dst)
    return out


@torch.no_grad()
def clip_scores(models, items) -> dict:
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms("ViT-g-14", pretrained="laion2b_s12b_b42k",
                                                                 device="cuda", precision="fp16")
    tokenizer = open_clip.get_tokenizer("ViT-g-14")
    out = {}
    for name in models:
        sims = []
        for i in range(0, len(items), 32):
            batch = items[i:i + 32]
            imgs = torch.stack([preprocess(Image.open(OUT / name / f"{it['image_id']}.png")) for it in batch]).cuda()
            text = tokenizer([it["caption"] for it in batch]).cuda()
            a = model.encode_image(imgs.half())
            b = model.encode_text(text)
            sims += torch.nn.functional.cosine_similarity(a, b).float().tolist()
        out[name] = float(np.mean(sims))
    del model
    torch.cuda.empty_cache()
    return out


@torch.no_grad()
def pick_scores(models, items) -> dict:
    from transformers import AutoModel, AutoProcessor

    processor = AutoProcessor.from_pretrained("laion/CLIP-ViT-H-14-laion2B-s32B-b79K")
    model = AutoModel.from_pretrained("yuvalkirstain/PickScore_v1", torch_dtype=torch.float16).cuda().eval()
    out = {}
    for name in models:
        scores = []
        for i in range(0, len(items), 32):
            batch = items[i:i + 32]
            imgs = processor(images=[Image.open(OUT / name / f"{it['image_id']}.png") for it in batch],
                             return_tensors="pt")["pixel_values"].cuda().half()
            text = processor(text=[it["caption"] for it in batch], padding=True, truncation=True, max_length=77,
                             return_tensors="pt").to("cuda")
            a = torch.nn.functional.normalize(model.get_image_features(pixel_values=imgs), dim=-1)
            b = torch.nn.functional.normalize(model.get_text_features(**text), dim=-1)
            scores += (model.logit_scale.exp() * (a * b).sum(-1)).float().tolist()
        out[name] = float(np.mean(scores))
    del model
    torch.cuda.empty_cache()
    return out


@torch.no_grad()
def diversity(models) -> dict:
    import lpips

    loss = lpips.LPIPS(net="alex", verbose=False).cuda()

    def tensor(p):
        a = np.asarray(Image.open(p).convert("RGB").resize((256, 256)), dtype=np.float32) / 127.5 - 1
        return torch.from_numpy(a).permute(2, 0, 1)[None].cuda()

    out = {}
    for name in models:
        folder = OUT / f"{name}_div"
        groups = {}
        for p in folder.glob("*.png"):
            groups.setdefault(p.stem.rsplit("_", 1)[0], []).append(p)
        dists = [float(loss(tensor(a), tensor(b))) for ps in groups.values() for a, b in itertools.combinations(ps, 2)]
        out[name] = float(np.mean(dists)) if dists else None
    return out


def main():
    from cleanfid import fid

    items = json.loads((OUT / "prompts.json").read_text())
    models = [m for m in ("sdxl_turbo_1", "sdxl_turbo_4", "sd_turbo_1", "lcm_sdxl_4", "sdxl_base_25")
              if (OUT / m).exists() and len(list((OUT / m).glob("*.png"))) >= len(items)]
    real = str(real_folder(items))
    results = {m: {} for m in models}
    for m in models:
        gen = str(resized(OUT / m))
        results[m]["fid_1k"] = round(float(fid.compute_fid(real, gen, mode="clean", num_workers=0)), 2)
        results[m]["kid_1k"] = round(float(fid.compute_kid(real, gen, mode="clean", num_workers=0)), 5)
        timing = OUT / m / "timing.json"
        if timing.exists():
            results[m]["seconds_per_image"] = json.loads(timing.read_text())["median_s"]
    for key, fn in (("clip_score", clip_scores), ("pick_score", pick_scores)):
        for m, v in fn(models, items).items():
            results[m][key] = round(v, 4)
    for m, v in diversity(models).items():
        results[m]["lpips_diversity"] = None if v is None else round(v, 4)
    Path("results/reproduction").mkdir(parents=True, exist_ok=True)
    Path("results/reproduction/coco_1k.json").write_text(json.dumps(results, indent=1) + "\n")
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
