"""SDXL-Turbo through diffusers: one step at 512 px, about a fifth of a second per picture on an RTX 4060."""
import torch
from PIL import Image

SDXL_VAE = "madebyollin/sdxl-vae-fp16-fix"


class TurboImages:
    def __init__(self, repo: str = "stabilityai/sdxl-turbo", steps: int = 1, size: int = 512):
        from diffusers import AutoencoderKL, AutoPipelineForText2Image

        self.pipe = AutoPipelineForText2Image.from_pretrained(repo, torch_dtype=torch.float16, variant="fp16")
        if "sdxl" in repo:
            self.pipe.vae = AutoencoderKL.from_pretrained(SDXL_VAE, torch_dtype=torch.float16)
        self.pipe.to("cuda")
        self.steps, self.size = steps, size

    def draw(self, prompt: str, seed: int) -> Image.Image:
        return self.pipe(prompt, num_inference_steps=self.steps, guidance_scale=0.0, height=self.size, width=self.size,
                         generator=torch.Generator("cuda").manual_seed(seed)).images[0]


class NsfwCheck:
    """Falconsai/nsfw_image_detection (ViT, Apache-2.0): probability that an image is not safe for work."""

    def __init__(self, device: str = "cuda"):
        from transformers import pipeline

        self.clf = pipeline("image-classification", model="Falconsai/nsfw_image_detection", device=device)

    def unsafe(self, image: Image.Image) -> float:
        return next((r["score"] for r in self.clf(image) if r["label"] == "nsfw"), 0.0)
