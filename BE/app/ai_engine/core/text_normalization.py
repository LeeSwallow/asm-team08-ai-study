from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sentence_parts(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。！？])\s+|(?<=[요다죠까])\s+", normalize_text(text))
    return [part.strip() for part in parts if part.strip()]
