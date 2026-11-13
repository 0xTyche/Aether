"""Mechanism library: schema validation, loader cross-checks, chain maths, shipped data."""

from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from aether.mechanisms import (
    Case,
    Effect,
    Lag,
    MechanismCard,
    MechanismLibrary,
    Verification,
    duration_minutes,
    duration_range_minutes,
    load_library,
)


# ---------- helpers ------------------------------------------------------

def _effect(**overrides) -> dict:
    base = {
        "role": "commodity_price",
        "target": "the commodity",
        "direction": "up",
        "lag": {"onset": "5m-4h", "peak": "1d-5d"},
        "crowding": "high",
    }
    return base | overrides


def _card(card_id: str = "card_a", **overrides) -> dict:
    base = {
        "id": card_id,
        "name": "Test card",
        "statement": "X causes Y.",
        "categories": ["industry_supply_chain"],
        "shock_nature": ["supply_side"],
        "preconditions": ["node matters"],
        "failure_conditions": ["inventories are ample"],
        "effects": [_effect()],
        "prior": 0.5,
        "evidence_tier": "C",
        "critique": ["only logic so far"],
        "review": {"drafted_on": "2026-01-01"},
    }
    return base | overrides


def _case(case_id: str = "case_a", **overrides) -> dict:
    base = {
        "id": case_id,
        "title": "Test case",
        "start_date": "2020-01-01",
        "categories": ["industry_supply_chain"],
        "summary": "Something happened.",
        "observations": [
            {"asset": "Oil", "direction": "up", "window": "1d", "recall": "high"}
        ],
    }
    return base | overrides


def _write_library(root: Path, cards: list[dict], cases: list[dict]) -> Path:
    (root / "cards").mkdir(parents=True)
    (root / "cases").mkdir(parents=True)
    for card in cards:
        (root / "cards" / f"{card['id']}.yaml").write_text(
            yaml.safe_dump(card, allow_unicode=True), encoding="utf-8"
        )
    (root / "cases" / "all.yaml").write_text(
        yaml.safe_dump({"cases": cases}, allow_unicode=True), encoding="utf-8"
    )
    return root


# ---------- durations ----------------------------------------------------

@pytest.mark.parametrize(
    ("text", "minutes"),
    [("30m", 30), ("4h", 240), ("3d", 4320), ("2w", 20160)],
)
def test_duration_minutes(text: str, minutes: int):
    assert duration_minutes(text) == minutes


@pytest.mark.parametrize("text", ["4x", "h", "", "1.5h", "0m", "-3d"])
def test_duration_rejects_garbage(text: str):
    with pytest.raises(ValueError):
        duration_minutes(text)


def test_duration_range():
    assert duration_range_minutes("5m-4h") == (5, 240)
    assert duration_range_minutes("1d") == (1440, 1440)


@pytest.mark.parametrize("text", ["4h-5m", "1d-2d-3d", "1d-"])
def test_duration_range_rejects_bad_ranges(text: str):
    with pytest.raises(ValueError):
        duration_range_minutes(text)


def test_lag_scoring_window_is_upper_bound_of_peak():
    lag = Lag(onset="5m-4h", peak="1d-5d", fade="1w-4w")
    assert lag.scoring_window_min == 5 * 1440


def test_lag_rejects_bad_duration():
    with pytest.raises(ValidationError):
        Lag(onset="soon", peak="1d")


# ---------- schema -------------------------------------------------------

def test_minimal_card_validates():
    card = MechanismCard.model_validate(_card())
    assert card.review.status == "draft"
    assert card.review.drafted_on == date(2026, 1, 1)
    assert card.effects[0].magnitude == "medium"


def test_card_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        MechanismCard.model_validate(_card(junk=1))


def test_effect_rejects_unknown_role():
    with pytest.raises(ValidationError):
        Effect.model_validate(_effect(role="vibes"))


def test_mixed_direction_requires_condition():
    with pytest.raises(ValidationError):
        Effect.model_validate(_effect(direction="mixed"))
    ok = Effect.model_validate(_effect(direction="mixed", condition="depends on inventories"))
    assert ok.direction == "mixed"


def test_card_requires_a_critique():
    with pytest.raises(ValidationError):
        MechanismCard.model_validate(_card(critique=[]))


@pytest.mark.parametrize("prior", [0.0, 1.0, 1.2, -0.1])
def test_prior_must_be_strictly_between_zero_and_one(prior: float):
    with pytest.raises(ValidationError):
        MechanismCard.model_validate(_card(prior=prior))


def test_card_cannot_lead_to_itself():
    with pytest.raises(ValidationError):
        MechanismCard.model_validate(_card("loop", leads_to=["loop"]))


def test_card_cannot_cite_a_case_twice():
    refs = [{"id": "case_a", "outcome": "supports"}, {"id": "case_a", "outcome": "mixed"}]
    with pytest.raises(ValidationError):
        MechanismCard.model_validate(_card(cases=refs))


def test_tier_b_needs_two_supporting_cases():
    one = [{"id": "case_a", "outcome": "supports"}, {"id": "case_b", "outcome": "mixed"}]
    with pytest.raises(ValidationError):
        MechanismCard.model_validate(_card(evidence_tier="B", cases=one))
    two = [{"id": "case_a", "outcome": "supports"}, {"id": "case_b", "outcome": "supports"}]
    assert MechanismCard.model_validate(_card(evidence_tier="B", cases=two)).evidence_tier == "B"


def test_tier_a_needs_human_approval():
    two = [{"id": "case_a", "outcome": "supports"}, {"id": "case_b", "outcome": "supports"}]
    with pytest.raises(ValidationError):
        MechanismCard.model_validate(_card(evidence_tier="A", cases=two))
    approved = _card(
        evidence_tier="A",
        cases=two,
        review={"drafted_on": "2026-01-01", "status": "approved", "reviewed_by": "someone"},
    )
    assert MechanismCard.model_validate(approved).evidence_tier == "A"


def test_case_rejects_end_before_start():
    with pytest.raises(ValidationError):
        Case.model_validate(_case(end_date="2019-12-31"))


def test_web_checked_needs_date_and_source():
    with pytest.raises(ValidationError):
        Verification(status="web_checked")
    with pytest.raises(ValidationError):
        Verification(status="web_checked", checked_on=date(2026, 1, 1))
    ok = Verification(
        status="web_checked", checked_on=date(2026, 1, 1), sources=["https://example.com"]
    )
    assert ok.status == "web_checked"


# ---------- loader -------------------------------------------------------

def test_loader_reads_cards_and_cases(tmp_path: Path):
    root = _write_library(
        tmp_path / "lib",
        cards=[_card("card_a", cases=[{"id": "case_a", "outcome": "supports"}])],
        cases=[_case("case_a")],
    )
    lib = load_library(root)
    assert set(lib.cards) == {"card_a"}
    assert set(lib.cases) == {"case_a"}
    ref, case = lib.cases_for("card_a")[0]
    assert ref.outcome == "supports"
    assert case.title == "Test case"
    assert lib.unreferenced_cases() == []


def test_loader_rejects_dangling_leads_to(tmp_path: Path):
    root = _write_library(tmp_path / "lib", cards=[_card("card_a", leads_to=["ghost"])], cases=[])
    with pytest.raises(RuntimeError, match="leads_to unknown card"):
        load_library(root)


def test_loader_rejects_dangling_case(tmp_path: Path):
    root = _write_library(
        tmp_path / "lib",
        cards=[_card("card_a", cases=[{"id": "ghost", "outcome": "supports"}])],
        cases=[],
    )
    with pytest.raises(RuntimeError, match="cites unknown case"):
        load_library(root)


def test_loader_rejects_duplicate_case_ids(tmp_path: Path):
    root = _write_library(tmp_path / "lib", cards=[], cases=[_case("dup"), _case("dup")])
    with pytest.raises(RuntimeError, match="duplicate case id"):
        load_library(root)


def test_loader_rejects_file_name_mismatch(tmp_path: Path):
    root = _write_library(tmp_path / "lib", cards=[_card("card_a")], cases=[])
    (root / "cards" / "card_a.yaml").rename(root / "cards" / "other_name.yaml")
    with pytest.raises(RuntimeError, match="file name must match"):
        load_library(root)


def test_loader_reports_invalid_card_with_its_path(tmp_path: Path):
    root = _write_library(tmp_path / "lib", cards=[_card("card_a", prior=2)], cases=[])
    with pytest.raises(RuntimeError, match="card_a.yaml"):
        load_library(root)


def test_unreferenced_cases_are_reported(tmp_path: Path):
    root = _write_library(tmp_path / "lib", cards=[_card("card_a")], cases=[_case("orphan")])
    assert load_library(root).unreferenced_cases() == ["orphan"]


# ---------- chains -------------------------------------------------------

@pytest.fixture
def chain_library(tmp_path: Path) -> MechanismLibrary:
    root = _write_library(
        tmp_path / "lib",
        cards=[
            _card("a", prior=0.8, leads_to=["b", "c"]),
            _card("b", prior=0.5, leads_to=["c"]),
            _card("c", prior=0.9, leads_to=["a"]),  # cycle back to the start
        ],
        cases=[],
    )
    return load_library(root)


def test_chain_joint_prior_is_the_product(chain_library: MechanismLibrary):
    chains = {c.card_ids: c for c in chain_library.chains("a", max_hops=2)}
    assert set(chains) == {("a",), ("a", "b"), ("a", "c"), ("a", "b", "c")}
    assert chains[("a",)].joint_prior == pytest.approx(0.8)
    assert chains[("a", "b", "c")].joint_prior == pytest.approx(0.8 * 0.5 * 0.9)
    assert chains[("a", "b", "c")].hops == 2


def test_chains_are_sorted_by_descending_joint_prior(chain_library: MechanismLibrary):
    priors = [c.joint_prior for c in chain_library.chains("a", max_hops=3)]
    assert priors == sorted(priors, reverse=True)


def test_chains_respect_max_hops_and_never_revisit(chain_library: MechanismLibrary):
    assert [c.card_ids for c in chain_library.chains("a", max_hops=0)] == [("a",)]
    for chain in chain_library.chains("a", max_hops=10):  # the cycle must terminate
        assert len(chain.card_ids) == len(set(chain.card_ids))


def test_chains_reject_unknown_start(chain_library: MechanismLibrary):
    with pytest.raises(KeyError):
        chain_library.chains("ghost")


# ---------- shipped library ----------------------------------------------

@pytest.fixture(scope="module")
def shipped() -> MechanismLibrary:
    return load_library()


def test_shipped_library_loads(shipped: MechanismLibrary):
    assert len(shipped.cards) >= 20
    assert len(shipped.cases) >= 40


def test_shipped_library_has_no_orphan_cases(shipped: MechanismLibrary):
    assert shipped.unreferenced_cases() == []


def test_shipped_cards_are_unreviewed_drafts(shipped: MechanismLibrary):
    """Model-drafted cards must not ship as approved or as data-validated."""
    for card in shipped.cards.values():
        assert card.review.status == "draft", card.id
        assert card.evidence_tier != "A", card.id


def test_shipped_low_crowding_effects_exist(shipped: MechanismLibrary):
    """The library's purpose is the neglected second-order effects."""
    low = [
        (card.id, eff.target)
        for card in shipped.cards.values()
        for eff in card.effects
        if eff.crowding == "low"
    ]
    assert len(low) >= 15


def test_tsunami_story_is_a_chain_and_weaker_than_any_link(shipped: MechanismLibrary):
    story = (
        "seismic_tsunami_coastal_damage",
        "export_node_outage_commodity",
        "hawkish_surprise_duration_repricing",
    )
    chains = {c.card_ids: c for c in shipped.chains(story[0], max_hops=2)}
    assert story in chains
    joint = chains[story].joint_prior
    assert joint == pytest.approx(0.6 * 0.65 * 0.75)
    assert joint < min(shipped.cards[c].prior for c in story)


def test_shipped_observation_asset_ids_exist_in_the_seed(shipped: MechanismLibrary):
    pytest.importorskip("sqlalchemy")
    from scripts.seed_assets import ALL_ASSETS

    known = {a["id"] for a in ALL_ASSETS}
    unknown = sorted(
        {
            f"{case.id}:{obs.asset_id}"
            for case in shipped.cases.values()
            for obs in case.observations
            if obs.asset_id is not None and obs.asset_id not in known
        }
    )
    assert unknown == []
