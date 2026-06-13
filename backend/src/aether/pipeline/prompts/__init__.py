"""Externalised LLM prompts.

Each prompt lives in a sibling `.md` file so it can be iterated on
without touching Python. Files are loaded at import time and cached
on the module.
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def _load(name: str) -> str:
    """Read a prompt file as UTF-8."""
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


# Main impact-analysis system prompt (Chinese, see system_zh.md for the
# editable source). Dynamic asset_ids / region_ids are still appended at
# runtime by `aether.pipeline.llm.build_system_prompt`.
SYSTEM_ZH = _load("system_zh.md")


__all__ = ["SYSTEM_ZH"]
