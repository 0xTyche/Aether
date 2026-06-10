"""YAML rule discovery + parse + validation.

Rules live as one YAML file per rule in `aether/rules_data/*.yaml`.
The loader is called once on app startup; failures are loud so a
misconfigured rule never silently disables matching.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import structlog
import yaml
from pydantic import ValidationError

from aether.rules.schema import Rule


logger = structlog.get_logger(__name__)


DEFAULT_RULES_DIR = Path(__file__).parent.parent / "rules_data"


@dataclass(slots=True)
class RuleStore:
    """A loaded rule set, pre-sorted by descending priority for fast matching."""

    rules: list[Rule] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.rules)

    def by_id(self, rule_id: str) -> Rule | None:
        for r in self.rules:
            if r.id == rule_id:
                return r
        return None


def _iter_yaml_files(rules_dir: Path) -> Iterable[Path]:
    if not rules_dir.exists():
        return []
    return sorted(rules_dir.glob("*.yaml"))


def load_rules(rules_dir: Path | None = None) -> RuleStore:
    """Parse every YAML file in `rules_dir`. Raises on validation failure.

    Detects duplicate rule ids across files so a typo or copy-paste accident
    can't silently shadow another rule.
    """
    rules_dir = rules_dir or DEFAULT_RULES_DIR
    rules: list[Rule] = []
    seen_ids: dict[str, Path] = {}

    for path in _iter_yaml_files(rules_dir):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise RuntimeError(f"YAML parse error in {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise RuntimeError(f"{path}: top-level must be a mapping, got {type(raw).__name__}")
        try:
            rule = Rule.model_validate(raw)
        except ValidationError as exc:
            raise RuntimeError(f"Validation error in {path}: {exc}") from exc

        prior = seen_ids.get(rule.id)
        if prior is not None:
            raise RuntimeError(f"duplicate rule id {rule.id!r} in {path} and {prior}")
        seen_ids[rule.id] = path
        rules.append(rule)

    rules.sort(key=lambda r: -r.priority)
    logger.info("rules.loaded", count=len(rules), dir=str(rules_dir))
    return RuleStore(rules=rules)
