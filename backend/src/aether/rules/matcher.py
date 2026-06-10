"""Rule-matching algorithm.

For each candidate rule (already sorted by descending priority), check:
  1. source whitelist: news.source must be in `trigger.source` if set
  2. keywords_all: every token in the haystack
  3. keywords_any: at least one token in the haystack (if set)
  4. keywords_none: zero tokens in the haystack

First rule whose checks all pass wins. No "fall-through".
"""

from dataclasses import dataclass

from aether.rules.schema import Rule


@dataclass(slots=True, frozen=True)
class MatchInput:
    """The fields a rule looks at on a single news item."""

    source: str
    title: str
    body: str = ""

    @property
    def haystack(self) -> str:
        return f"{self.title}\n{self.body}".lower()


def _haystack_contains(haystack: str, needle: str) -> bool:
    """Case-insensitive substring check.

    Substring on the lowercased haystack is intentionally permissive — rule
    authors phrase keywords like "rate hike", "FOMC", "降息" and we want to
    catch them whether the source uses sentence-cased headlines or all caps.
    """
    return needle.strip().lower() in haystack


def matches(rule: Rule, item: MatchInput) -> bool:
    """True iff `item` satisfies every trigger constraint on `rule`."""
    trig = rule.trigger
    if trig.source and item.source not in trig.source:
        return False

    haystack = item.haystack
    if any(not _haystack_contains(haystack, kw) for kw in trig.keywords_all):
        return False
    if trig.keywords_any and not any(
        _haystack_contains(haystack, kw) for kw in trig.keywords_any
    ):
        return False
    if any(_haystack_contains(haystack, kw) for kw in trig.keywords_none):
        return False

    return True


def match(rules: list[Rule], item: MatchInput) -> Rule | None:
    """Return the highest-priority rule that fires, or None."""
    for rule in rules:
        if matches(rule, item):
            return rule
    return None
