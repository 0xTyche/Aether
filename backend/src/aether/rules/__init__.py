"""Rule-engine package.

Macro-event → market-impact rules expressed as YAML files in
`aether/rules_data/*.yaml`. The engine matches an incoming `RawNews`
item against rules in descending priority order and emits structured
impact predictions for the orchestrator.
"""

from aether.rules.loader import RuleStore, load_rules
from aether.rules.matcher import match
from aether.rules.schema import Impact, Origin, Rule, Trigger

__all__ = [
    "Impact",
    "Origin",
    "Rule",
    "RuleStore",
    "Trigger",
    "load_rules",
    "match",
]
