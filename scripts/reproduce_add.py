"""Generate the reproduction set: 1,000 COCO 2017 val captions through SDXL-Turbo (1 and 4 steps), SD-Turbo, LCM-SDXL
(4 steps) and SDXL 1.0 base (25 steps), plus a diversity set (50 captions x 4 seeds). Then scripts/evaluate_add.py.

The paper's FID uses 5k samples and SDXL at 50 steps; on one 8 GB card that is days, so this is 1k samples and 25
steps. Resumable: existing images are skipped.

usage: uv run --group repro scripts/reproduce_add.py [--models sdxl_turbo_1 ...]
"""
import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch

OUT = Path("data/repro")
SDXL_VAE = "madebyollin/sdxl-vae-fp16-fix"  # SDXL's own VAE overflows in fp16 at 1024 px

# name: (repo, size, steps, guidance, kind)
MODELS = {
    "sdxl_turbo_1": ("stabilityai/sdxl-turbo", 512, 1, 0.0, "turbo"),
    "sdxl_turbo_4": ("stabilityai/sdxl-turbo", 512, 4, 0.0, "turbo"),
    "sd_turbo_1": ("stabilityai/sd-turbo", 512, 1, 0.0, "turbo"),
    "lcm_sdxl_4": ("latent-consistency/lcm-sdxl", 1024, 4, 8.0, "lcm"),
    "sdxl_base_25": ("stabilityai/stable-diffusion-xl-base-1.0", 1024, 25, 5.0, "sdxl"),
}


def prompts(n: int, seed: int = 0) -> list[dict]:
    path = OUT / "prompts.json"
    if path.exists():
        return json.loads(path.read_text())
    caps = json.loads(Path("data/raw/annotations/captions_val2017.json").read_text())
    first = {}
    for a in caps["annotations"]:
        first.setdefault(a["image_id"], a["caption"].strip())
    ids = sorted(first)
    random.Random(seed).shuffle(ids)
    out = [{"image_id": i, "file": f"{i:012d}.jpg", "caption": first[i]} for i in ids[:n]]
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    return out


def load(name: str):
    from diffusers import (
        AutoencoderKL,
        AutoPipelineForText2Image,
        DiffusionPipeline,
        LCMScheduler,
        UNet2DConditionModel,
    )

    repo, _, _, _, kind = MODELS[name]
    if kind == "turbo":
        pipe = AutoPipelineForText2Image.from_pretrained(repo, torch_dtype=torch.float16, variant="fp16")
        if "sdxl" in repo:
            pipe.vae = AutoencoderKL.from_pretrained(SDXL_VAE, torch_dtype=torch.float16)
            return pipe  # stays on the CPU until the prompts are encoded; see encode_then_move
        return pipe.to("cuda")
    vae = AutoencoderKL.from_pretrained(SDXL_VAE, torch_dtype=torch.float16)
    base = "stabilityai/stable-diffusion-xl-base-1.0"
    if kind == "lcm":
        unet = UNet2DConditionModel.from_pretrained(repo, torch_dtype=torch.float16, variant="fp16")
        pipe = DiffusionPipeline.from_pretrained(base, unet=unet, vae=vae, torch_dtype=torch.float16, variant="fp16")
        pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
    else:
        pipe = DiffusionPipeline.from_pretrained(base, vae=vae, torch_dtype=torch.float16, variant="fp16")
    # SDXL at 1024 px doesn't fit next to the desktop on 8 GB; offload moves each block to the GPU only when used
    pipe.enable_model_cpu_offload()
    pipe.vae.enable_tiling()
    return pipe


@torch.no_grad()
def encode_then_move(pipe, captions: list[str]) -> dict:
    """SDXL-Turbo whole (6.5 GB in fp16) doesn't fit next to the desktop. Encode every caption with the two text
    encoders first, drop them, and keep only the UNet and the VAE on the GPU; the timing then covers denoising and
    decoding, which is what the paper's one-step claim is about."""
    pipe.text_encoder.to("cuda")
    pipe.text_encoder_2.to("cuda")
    cache = {}
    for i in range(0, len(captions), 16):
        batch = captions[i:i + 16]
        embeds, _, pooled, _ = pipe.encode_prompt(batch, device="cuda", do_classifier_free_guidance=False)
        for j, c in enumerate(batch):
            cache[c] = (embeds[j:j + 1].cpu(), pooled[j:j + 1].cpu())
    pipe.text_encoder.to("cpu")
    pipe.text_encoder_2.to("cpu")
    torch.cuda.empty_cache()
    pipe.unet.to("cuda")
    pipe.vae.to("cuda")
    return cache


def generate(name: str, items: list[dict], div: list[dict]):
    _, size, steps, guidance, _ = MODELS[name]
    folder, div_folder = OUT / name, OUT / f"{name}_div"
    folder.mkdir(parents=True, exist_ok=True)
    div_folder.mkdir(parents=True, exist_ok=True)
    jobs = [(folder / f"{it['image_id']}.png", it["caption"], it["image_id"]) for it in items]
    jobs += [(div_folder / f"{it['image_id']}_{s}.png", it["caption"], it["image_id"] * 10 + s)
             for it in div for s in range(4)]
    jobs = [j for j in jobs if not j[0].exists()]
    if not jobs:
        return
    pipe = load(name)
    cache = encode_then_move(pipe, sorted({c for _, c, _ in jobs})) if MODELS[name][0] == "stabilityai/sdxl-turbo" else None
    times = []
    for i, (path, caption, seed) in enumerate(jobs):
        start = time.perf_counter()
        text = ({"prompt_embeds": cache[caption][0].cuda(), "pooled_prompt_embeds": cache[caption][1].cuda()}
                if cache else {"prompt": caption})
        image = pipe(**text, num_inference_steps=steps, guidance_scale=guidance, height=size, width=size,
                     generator=torch.Generator("cuda").manual_seed(seed)).images[0]
        torch.cuda.synchronize()
        if i >= 3:  # warm-up
            times.append(time.perf_counter() - start)
        image.save(path)
        if i % 100 == 0:
            print(f"  {name}: {i}/{len(jobs)}", flush=True)
    if times:
        timing = {"median_s": round(float(np.median(times)), 3), "images": len(times),
                  "gpu": torch.cuda.get_device_name(), "size": size, "steps": steps}
        (folder / "timing.json").write_text(json.dumps(timing, indent=1))
    del pipe
    torch.cuda.empty_cache()


def main(args):
    torch.cuda.set_per_process_memory_fraction(0.85)  # the same GPU drives the desktop
    items = prompts(args.n)
    for name in args.models:
        generate(name, items, items[: args.diversity])
        print(f"{name} done", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--diversity", type=int, default=50)
    main(parser.parse_args())
