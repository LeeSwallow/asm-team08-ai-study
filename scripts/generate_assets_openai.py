from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".secret" / ".env"
OUT = ROOT / "FE" / "public" / "assets"
OUT.mkdir(parents=True, exist_ok=True)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


ASSETS = [
    {
        "file": "mansion-study-bg.png",
        "size": "1536x1024",
        "prompt": "Cinematic noir detective game background, Korean mansion second-floor study crime scene during a stormy night, investigation desk and evidence board, warm desk lamp, rain streaking tall windows, scattered case files, red strings, antique wood, deep navy black and gold palette, premium visual novel web game background, no text, no people, highly detailed.",
    },
    {
        "file": "char_hanseoyeon.png",
        "size": "1024x1024",
        "prompt": "Korean mystery visual novel suspect portrait, Han Seo-yeon, wealthy niece late 20s, elegant burgundy blazer, tense sharp eyes, refined but defensive expression, dark mansion warm rim light, noir detective game character card, semi-realistic illustration, centered bust portrait, no text.",
    },
    {
        "file": "char_yoonjaeho.png",
        "size": "1024x1024",
        "prompt": "Korean mystery visual novel suspect portrait, Yoon Jae-ho, middle-aged butler, charcoal suit, white gloves, composed secretive expression, dignified posture, dark mansion corridor, noir detective game character card, semi-realistic illustration, centered bust portrait, no text.",
    },
    {
        "file": "char_parkmingyu.png",
        "size": "1024x1024",
        "prompt": "Korean mystery visual novel suspect portrait, Park Min-gyu, male physician in his 40s, glasses, calm analytical face, navy coat with subtle medical detail, cold blue lighting, noir detective game character card, semi-realistic illustration, centered bust portrait, no text.",
    },
    {
        "file": "char_choiyuna.png",
        "size": "1024x1024",
        "prompt": "Korean mystery visual novel suspect portrait, Choi Yuna, professional secretary in early 30s, camel beige jacket, cautious intelligent eyes, holding a small notebook, warm office shadow, noir detective game character card, semi-realistic illustration, centered bust portrait, no text.",
    },
]


def call_openai_image(prompt: str, size: str) -> bytes:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")
    payload = {
        "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        "prompt": prompt,
        "size": size,
        "quality": "medium",
        "n": 1,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        "https://api.openai.com/v1/images/generations",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"OpenAI image API HTTP {exc.code}: {detail}") from exc
    item = body["data"][0]
    if "b64_json" in item:
        return base64.b64decode(item["b64_json"])
    if "url" in item:
        with request.urlopen(item["url"], timeout=180) as resp:
            return resp.read()
    raise RuntimeError("No image payload returned")


def main() -> int:
    load_env(ENV)
    failures = []
    for asset in ASSETS:
        path = OUT / asset["file"]
        if path.exists() and path.stat().st_size > 1000:
            print(f"skip existing {path.relative_to(ROOT)}")
            continue
        print(f"generating {path.relative_to(ROOT)} ...", flush=True)
        try:
            blob = call_openai_image(asset["prompt"], asset["size"])
            path.write_bytes(blob)
            print(f"wrote {path.relative_to(ROOT)} ({len(blob)} bytes)")
            time.sleep(1)
        except Exception as exc:
            failures.append(f"{asset['file']}: {exc}")
            print(f"FAILED {asset['file']}: {exc}", file=sys.stderr)
    if failures:
        (OUT / "generation-errors.txt").write_text("\n".join(failures))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
