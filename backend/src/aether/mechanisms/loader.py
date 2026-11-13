"""YAML discovery, parsing and cross-reference checks for the mechanism library.

Layout under `aether/mechanisms_data/`:

    cards/<card_id>.yaml   one mechanism card per file
    cases/<theme>.yaml     `cases: [...]`, several cases per file

Like the rule loader, failures are loud: a dangling reference or a
duplicate id raises instead of silently dropping a card.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import prod
from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import ValidationError

from aether.mechanisms.schema import Case, CaseRef, MechanismCard


logger = structlog.get_logger(__name__)


DEFAULT_DATA_DIR = Path(__file__).parent.parent / "mechanisms_data"
CARDS_SUBDIR = "cards"
CASES_SUBDIR = "cases"


@dataclass(frozen=True, slots=True)
class Chain:
    """A path through `leads_to` links, with the product of the cards' priors.

    The joint prior is the point: four links at 0.8 each are only ~0.41
    together, so a story that reads smoothly can still be a coin flip.
    """

    card_ids: tuple[str, ...]
    joint_prior: float

    @property
    def hops(self) -> int:
        return len(self.card_ids) - 1


@dataclass(slots=True)
class MechanismLibrary:
    """Loaded cards and cases, already cross-checked."""

    cards: dict[str, MechanismCard] = field(default_factory=dict)
    cases: dict[str, Case] = field(default_factory=dict)

    def card(self, card_id: str) -> MechanismCard | None:
        return self.cards.get(card_id)

    def case(self, case_id: str) -> Case | None:
        return self.cases.get(case_id)

    def cases_for(self, card_id: str) -> list[tuple[CaseRef, Case]]:
        """A card's citations paired with the cases they point at."""
        card = self.cards[card_id]
        return [(ref, self.cases[ref.id]) for ref in card.cases]

    def unreferenced_cases(self) -> list[str]:
        """Case ids no card cites: usually a forgotten link or a stale case."""
        cited = {ref.id for card in self.cards.values() for ref in card.cases}
        return sorted(set(self.cases) - cited)

    def chains(self, start_id: str, max_hops: int = 3) -> list[Chain]:
        """Every simple path from `start_id` with at most `max_hops` links.

        Includes the one-card chain. Sorted by descending joint prior, so the
        first entries are the stories most worth a look.
        """
        if start_id not in self.cards:
            raise KeyError(start_id)
        if max_hops < 0:
            raise ValueError("max_hops must be >= 0")

        out: list[Chain] = []

        def walk(path: tuple[str, ...]) -> None:
            out.append(
                Chain(card_ids=path, joint_prior=prod(self.cards[c].prior for c in path))
            )
            if len(path) - 1 >= max_hops:
                return
            for nxt in self.cards[path[-1]].leads_to:
                if nxt not in path:  # never revisit: keeps cycles finite
                    walk((*path, nxt))

        walk((start_id,))
        out.sort(key=lambda c: (-c.joint_prior, c.card_ids))
        return out


def _iter_yaml_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.yaml"))


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuntimeError(f"YAML parse error in {path}: {exc}") from exc


def load_cases(cases_dir: Path) -> dict[str, Case]:
    """Parse every `cases: [...]` file in `cases_dir`. Raises on any defect."""
    cases: dict[str, Case] = {}
    origin: dict[str, Path] = {}

    for path in _iter_yaml_files(cases_dir):
        raw = _read_yaml(path)
        if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
            raise RuntimeError(f"{path}: top-level must be a mapping with a `cases` list")
        for entry in raw["cases"]:
            try:
                case = Case.model_validate(entry)
            except ValidationError as exc:
                raise RuntimeError(f"Validation error in {path}: {exc}") from exc
            if case.id in cases:
                raise RuntimeError(
                    f"duplicate case id {case.id!r} in {path} and {origin[case.id]}"
                )
            cases[case.id] = case
            origin[case.id] = path

    return cases


def load_cards(cards_dir: Path) -> dict[str, MechanismCard]:
    """Parse one card per YAML file in `cards_dir`. Raises on any defect."""
    cards: dict[str, MechanismCard] = {}
    origin: dict[str, Path] = {}

    for path in _iter_yaml_files(cards_dir):
        raw = _read_yaml(path)
        if not isinstance(raw, dict):
            raise RuntimeError(
                f"{path}: top-level must be a mapping, got {type(raw).__name__}"
            )
        try:
            card = MechanismCard.model_validate(raw)
        except ValidationError as exc:
            raise RuntimeError(f"Validation error in {path}: {exc}") from exc
        if card.id in cards:
            raise RuntimeError(f"duplicate card id {card.id!r} in {path} and {origin[card.id]}")
        if path.stem != card.id:
            raise RuntimeError(f"{path}: file name must match card id {card.id!r}")
        cards[card.id] = card
        origin[card.id] = path

    return cards


def load_library(data_dir: Path | None = None) -> MechanismLibrary:
    """Load cards and cases, then verify every cross-reference resolves."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    cases = load_cases(data_dir / CASES_SUBDIR)
    cards = load_cards(data_dir / CARDS_SUBDIR)

    for card in cards.values():
        for nxt in card.leads_to:
            if nxt not in cards:
                raise RuntimeError(f"card {card.id!r}: leads_to unknown card {nxt!r}")
        for ref in card.cases:
            if ref.id not in cases:
                raise RuntimeError(f"card {card.id!r}: cites unknown case {ref.id!r}")

    logger.info("mechanisms.loaded", cards=len(cards), cases=len(cases), dir=str(data_dir))
    return MechanismLibrary(cards=cards, cases=cases)
