"""Render the mechanism library as a compact catalogue for the LLM prompt.

The online model never sees the YAML. It gets one block per card: id,
name, the causal statement, and each effect squeezed into a single token
group (role, direction, crowding, peak lag). That is enough for it to
recognise a card and pick the neglected roles, and small enough to sit in
the cached system prompt.
"""

import re
from functools import cache
from typing import get_args

from aether.mechanisms.loader import MechanismLibrary, load_library
from aether.mechanisms.schema import Role


ROLE_IDS: tuple[str, ...] = get_args(Role)

_ARROW = {"up": "↑", "down": "↓", "mixed": "↕"}
_CROWDING_ZH = {"high": "拥挤", "medium": "一般", "low": "易忽略"}

# YAML folded scalars (`>-`) join lines with a space, which leaves stray
# spaces between Chinese characters. Drop whitespace when both neighbours
# are CJK or full-width punctuation; keep it around Latin words.
_CJK = r"　-〿一-鿿＀-￯"
_CJK_GAP = re.compile(rf"(?<=[{_CJK}])\s+(?=[{_CJK}])")


def squash_cjk_spaces(text: str) -> str:
    return _CJK_GAP.sub("", text.strip())


@cache
def default_library() -> MechanismLibrary:
    """The shipped library, loaded once per process."""
    return load_library()


def render_catalog(library: MechanismLibrary) -> str:
    """One block per card, sorted by id. Rejected cards are left out."""
    blocks: list[str] = []
    for card in sorted(library.cards.values(), key=lambda c: c.id):
        if card.review.status == "rejected":
            continue
        effects = "；".join(
            f"{e.role}{_ARROW[e.direction]} {_CROWDING_ZH[e.crowding]} 峰值 {e.lag.peak}"
            for e in card.effects
        )
        blocks.append(
            f"- {card.id}｜{card.name}\n"
            f"  {squash_cjk_spaces(card.statement)}\n"
            f"  影响：{effects}"
        )
    return "\n".join(blocks)
