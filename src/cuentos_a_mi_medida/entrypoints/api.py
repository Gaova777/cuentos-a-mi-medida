"""HTTP API for the story app.

POST /stories        a request (first name, age band, likes, lesson) -> checked, then queued for the worker
GET  /stories        the library, newest first
GET  /stories/{id}   one story: its status while it is made, then its pages with picture and narration links
GET  /health
"""
import os
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from cuentos_a_mi_medida.application.moderation import check
from cuentos_a_mi_medida.domain.story import Request

app = FastAPI(title="cuentos-a-mi-medida")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CUENTOS_CORS", "http://localhost:3002").split(","),
                   allow_methods=["*"], allow_headers=["*"])


@lru_cache
def library():
    from cuentos_a_mi_medida.adapters.aws import Library

    return Library()


@lru_cache
def moderator_llm():
    from cuentos_a_mi_medida.adapters.ollama import OllamaLLM

    return OllamaLLM(temperature=0.0)


class StoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    ages: Literal["5-6", "7-8", "9-10"]
    likes: str = Field(min_length=2, max_length=200)
    lesson: str = Field(default="", max_length=120)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/stories", status_code=202)
def create(body: StoryRequest):
    verdict = check(moderator_llm(), Request(body.name, body.ages, body.likes, body.lesson))
    if not verdict.allowed:
        raise HTTPException(422, {"reasons": verdict.reasons, "by": verdict.by})
    return {"story_id": library().create(body.model_dump()), "status": "queued"}


@app.get("/stories")
def stories():
    lib = library()
    out = []
    for s in lib.all():
        first = (s.get("pages") or [{}])[0].get("image")
        out.append({**{k: v for k, v in s.items() if k != "pages"}, "cover_url": lib.url(first) if first else None})
    return out


@app.get("/stories/{story_id}")
def story(story_id: str):
    lib = library()
    s = lib.get(story_id)
    if s is None:
        raise HTTPException(404, "no such story")
    for page in s.get("pages", []):
        page["image_url"] = lib.url(page["image"]) if page.get("image") else None
        page["audio_url"] = lib.url(page["audio"])
    return s
