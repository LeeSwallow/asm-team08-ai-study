from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field

from app.ai_engine.schemas.base import FlexibleModel


class PromptSection(FlexibleModel):
    """A typed prompt section before final rendering to provider text."""

    title: str
    content: str | list[str] | dict[str, Any]
    kind: Literal["instruction", "context", "constraint", "input", "output"] = "context"

    def render(self) -> str:
        if isinstance(self.content, str):
            body = self.content.strip()
        elif isinstance(self.content, list):
            body = "\n".join(f"- {str(item).strip()}" for item in self.content if str(item).strip())
        else:
            body = json.dumps(self.content, ensure_ascii=False, indent=2, default=str)
        if not body:
            return ""
        return f"## {self.title}\n{body}"


class LLMChatPrompt(FlexibleModel):
    """Structured prompt contract used internally by agents and rendered only at the LLM boundary."""

    systemPrompt: str
    sections: list[PromptSection] = Field(default_factory=list)
    outputInstruction: str = "용의자의 다음 대사만 출력하라."

    def render_prompt(self) -> str:
        rendered_sections = [section.render() for section in self.sections]
        rendered_sections = [section for section in rendered_sections if section]
        return "\n\n".join([self.systemPrompt.strip(), *rendered_sections]).strip()

    def render_user_message(self, fact_anchor: str) -> str:
        return (
            f"{self.render_prompt()}\n\n"
            "## FACT ANCHOR\n"
            "보존할 공개 사실이며 말투 템플릿이 아니다.\n"
            f"{fact_anchor.strip()}\n\n"
            f"## Output\n{self.outputInstruction.strip()}"
        )


PromptInput = str | LLMChatPrompt
