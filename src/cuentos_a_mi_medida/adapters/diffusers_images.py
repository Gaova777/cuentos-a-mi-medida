"""SDXL-Turbo through diffusers: one step at 512 px. On an RTX 4060, about 1.4 s per picture: 0.2 s on the GPU, the rest
encoding the prompt on the CPU."""
import torch
from PIL import Image

SDXL_VAE = "madebyollin/sdxl-vae-fp16-fix"


class TurboImages:
    def __init__(self, repo: str = "stabilityai/sdxl-turbo", steps: int = 1, size: int = 512):
        from diffusers import AutoencoderKL, AutoPipelineForText2Image

        self.pipe = AutoPipelineForText2Image.from_pretrained(repo, torch_dtype=torch.float16, variant="fp16")
        self.sdxl = "sdxl" in repo
        if self.sdxl:
            # the whole SDXL pipeline is 6.5 GB in fp16 and doesn't fit next to the desktop on 8 GB: the two text
            # encoders stay on the CPU and only the UNet and the VAE go to the GPU
            self.pipe.vae = AutoencoderKL.from_pretrained(SDXL_VAE, torch_dtype=torch.float16)
            self.pipe.unet.to("cuda")
            self.pipe.vae.to("cuda")
        else:
            self.pipe.to("cuda")
        self.steps, self.size = steps, size

    def draw(self, prompt: str, seed: int) -> Image.Image:
        text = {"prompt": prompt}
        if self.sdxl:
            with torch.no_grad():
                embeds, _, pooled, _ = self.pipe.encode_prompt(prompt, device="cpu", do_classifier_free_guidance=False)
            text = {"prompt_embeds": embeds.to("cuda", torch.float16),
                    "pooled_prompt_embeds": pooled.to("cuda", torch.float16)}
        return self.pipe(**text, num_inference_steps=self.steps, guidance_scale=0.0, height=self.size,
                         width=self.size, generator=torch.Generator("cuda").manual_seed(seed)).images[0]


class NsfwCheck:
    """Falconsai/nsfw_image_detection (ViT, Apache-2.0): probability that an image is not safe for work."""

    def __init__(self, device: str = "cuda"):
        from transformers import pipeline

        self.clf = pipeline("image-classification", model="Falconsai/nsfw_image_detection", device=device)

    def unsafe(self, image: Image.Image) -> float:
        return next((r["score"] for r in self.clf(image) if r["label"] == "nsfw"), 0.0)
