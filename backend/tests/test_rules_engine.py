"""Rule engine: schema validation, YAML loader, matching algorithm."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from aether.rules import Rule, RuleStore, load_rules, match
from aether.rules.matcher import MatchInput, matches
from aether.rules.schema import Impact, Origin, Trigger


# ---------- schema -------------------------------------------------------

def test_minimal_rule_validates():
    rule = Rule(
        id="t1",
        name="Test",
        priority=50,
        trigger=Trigger(keywords_any=["foo"]),
        origin=Origin(country="us", lat=0, lng=0),  # lowercased input
        impacts=[Impact(asset="SPX", direction="up")],
    )
    assert rule.origin.country == "US"  # field_validator upper-cases


def test_rule_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        Rule.model_validate({
            "id": "t1",
            "name": "Test",
            "trigger": {"keywords_any": ["foo"], "junk": 1},
            "origin": {"country": "US", "lat": 0, "lng": 0},
            "impacts": [{"asset": "SPX", "direction": "up"}],
        })


def test_impact_rejects_bad_direction():
    with pytest.raises(ValidationError):
        Impact(asset="SPX", direction="sideways")


def test_impact_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        Impact(asset="SPX", direction="up", confidence=1.5)


def test_rule_requires_at_least_one_impact():
    with pytest.raises(ValidationError):
        Rule.model_validate({
            "id": "t1",
            "name": "Test",
            "trigger": {"keywords_any": ["foo"]},
            "origin": {"country": "US", "lat": 0, "lng": 0},
            "impacts": [],
        })


# ---------- loader -------------------------------------------------------

def _write_rule_yaml(dir_: Path, name: str, body: dict) -> None:
    (dir_ / name).write_text(yaml.safe_dump(body), encoding="utf-8")


def _base_rule(id_: str, priority: int = 50) -> dict:
    return {
        "id": id_,
        "name": f"Rule {id_}",
        "priority": priority,
        "trigger": {"keywords_any": ["foo"]},
        "origin": {"country": "US", "lat": 0, "lng": 0},
        "impacts": [{"asset": "SPX", "direction": "up"}],
    }


def test_loader_handles_empty_dir(tmp_path: Path) -> None:
    store = load_rules(tmp_path)
    assert isinstance(store, RuleStore)
    assert len(store) == 0


def test_loader_loads_and_sorts_by_priority(tmp_path: Path) -> None:
    _write_rule_yaml(tmp_path, "a.yaml", _base_rule("low", 10))
    _write_rule_yaml(tmp_path, "b.yaml", _base_rule("high", 90))
    _write_rule_yaml(tmp_path, "c.yaml", _base_rule("mid", 50))
    store = load_rules(tmp_path)
    assert [r.id for r in store.rules] == ["high", "mid", "low"]


def test_loader_raises_on_duplicate_id(tmp_path: Path) -> None:
    _write_rule_yaml(tmp_path, "a.yaml", _base_rule("same"))
    _write_rule_yaml(tmp_path, "b.yaml", _base_rule("same"))
    with pytest.raises(RuntimeError, match="duplicate rule id"):
        load_rules(tmp_path)


def test_loader_raises_on_validation_error(tmp_path: Path) -> None:
    bad = _base_rule("x")
    bad["impacts"][0]["direction"] = "sideways"
    _write_rule_yaml(tmp_path, "x.yaml", bad)
    with pytest.raises(RuntimeError, match="Validation error"):
        load_rules(tmp_path)


def test_loader_raises_on_bad_yaml(tmp_path: Path) -> None:
    (tmp_path / "broken.yaml").write_text(":\n: nope: :\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_rules(tmp_path)


def test_loader_by_id_round_trip(tmp_path: Path) -> None:
    _write_rule_yaml(tmp_path, "a.yaml", _base_rule("alpha"))
    store = load_rules(tmp_path)
    r = store.by_id("alpha")
    assert r is not None
    assert r.name == "Rule alpha"
    assert store.by_id("missing") is None


# ---------- matcher ------------------------------------------------------

def _make_rule(**trigger_kwargs) -> Rule:
    return Rule(
        id="r",
        name="r",
        trigger=Trigger(**trigger_kwargs),
        origin=Origin(country="US", lat=0, lng=0),
        impacts=[Impact(asset="SPX", direction="up")],
    )


def test_matches_when_keyword_any_present():
    rule = _make_rule(keywords_any=["hike", "raise"])
    assert matches(rule, MatchInput("Fed", "Fed raises rates", ""))


def test_no_match_when_keyword_any_missing():
    rule = _make_rule(keywords_any=["dovish"])
    assert not matches(rule, MatchInput("Fed", "Hawkish remarks", ""))


def test_keywords_all_must_be_present():
    rule = _make_rule(keywords_all=["bank", "rate"])
    assert matches(rule, MatchInput("Fed", "Bank Rate hike", ""))
    assert not matches(rule, MatchInput("Fed", "Bank announcement", ""))


def test_keywords_none_excludes():
    rule = _make_rule(keywords_any=["rate"], keywords_none=["unchanged"])
    assert matches(rule, MatchInput("Fed", "raises rate", ""))
    assert not matches(rule, MatchInput("Fed", "rate unchanged", ""))


def test_source_whitelist_blocks_other_sources():
    rule = _make_rule(source=["Fed"], keywords_any=["rate"])
    assert matches(rule, MatchInput("Fed", "rate", ""))
    assert not matches(rule, MatchInput("ECB", "rate", ""))


def test_keyword_check_is_case_insensitive():
    rule = _make_rule(keywords_any=["fomc"])
    assert matches(rule, MatchInput("Fed", "FOMC Statement", ""))


def test_match_returns_first_in_priority_order():
    high = Rule(
        id="hi", name="hi", priority=90,
        trigger=Trigger(keywords_any=["rate"]),
        origin=Origin(country="US", lat=0, lng=0),
        impacts=[Impact(asset="SPX", direction="up")],
    )
    low = Rule(
        id="lo", name="lo", priority=10,
        trigger=Trigger(keywords_any=["rate"]),
        origin=Origin(country="US", lat=0, lng=0),
        impacts=[Impact(asset="SPX", direction="down")],
    )
    sorted_rules = sorted([low, high], key=lambda r: -r.priority)
    hit = match(sorted_rules, MatchInput("Fed", "rate", ""))
    assert hit is not None and hit.id == "hi"


def test_match_returns_none_when_no_rule_fires():
    rule = _make_rule(keywords_any=["lunar"])
    assert match([rule], MatchInput("Fed", "rate", "")) is None


# ---------- bundled production rules ------------------------------------

def test_production_rules_load():
    store = load_rules()
    assert len(store) >= 20


def test_fed_rate_hike_rule_fires_on_realistic_headline():
    store = load_rules()
    item = MatchInput(
        source="Fed",
        title="Federal Reserve raises federal funds target range by 25 basis points",
        body="The Federal Open Market Committee voted to raise the target range...",
    )
    hit = match(store.rules, item)
    assert hit is not None and hit.id == "fed_rate_hike"


def test_fed_rate_hold_excludes_when_hike_keywords_present():
    """Negative-keyword guard: 'unchanged' AND 'raise' must not match hold."""
    store = load_rules()
    item = MatchInput(
        source="Fed",
        title="Fed leaves federal funds rate unchanged but signals possible raise",
        body="",
    )
    hit = match(store.rules, item)
    # Should not be hold (keywords_none has 'raise'); could fall through to hike
    # (keywords_none has 'unchanged') — also rejected.
    assert hit is None or hit.id not in {"fed_rate_hold", "fed_rate_hike"}


def test_boj_rate_hike_fires_for_boj_source():
    store = load_rules()
    item = MatchInput(
        source="BoJ", title="Bank of Japan raises policy rate to 0.50%", body=""
    )
    hit = match(store.rules, item)
    assert hit is not None and hit.id == "boj_rate_hike"
