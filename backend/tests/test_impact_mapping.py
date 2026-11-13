"""LLM analysis -> Event / ImpactPrediction mapping, without a database.

The DB-backed flow lives in test_pipeline.py; these tests pin the pure
mapping helpers so the mechanism fields can be checked anywhere.
"""

from datetime import UTC, datetime

import pytest

from aether.mechanisms import MechanismLibrary, load_library
from aether.models.news import RawNews
from aether.pipeline import impact, llm


@pytest.fixture(scope="module")
def library() -> MechanismLibrary:
    return load_library()


def _news() -> RawNews:
    return RawNews(
        id=1, source="test", url="https://test.example/1",
        title="西非外海强震，海啸预警覆盖巴西沿岸", body="",
        published_at=datetime(2026, 11, 13, 8, 0, tzinfo=UTC),
    )


def _analysis() -> llm.LLMAnalysis:
    return llm.LLMAnalysis.model_validate({
        "is_market_relevant": True,
        "severity": "high",
        "origin_country_iso2": "BR",
        "explanation": "海啸将在数小时后登陆巴西",
        "premise_check": "海底垂直错动，海啸预警已发布",
        "mechanisms": [
            "seismic_tsunami_coastal_damage",
            "not_a_real_card",
            "export_node_outage_commodity",
        ],
        "transmission_chain": ["地震", "海啸", "港口停摆"],
        "impacts": [
            {"asset_id": "USD/BRL", "direction": "up", "horizon": "1d",
             "confidence": 0.6, "crowding": "medium",
             "mechanism_id": "disaster_currency_direction", "role": "local_currency",
             "rationale": "雷亚尔承压"},
            {"asset_id": "SPX", "direction": "neutral", "mechanism_id": "made_up"},
            {"asset_id": "PETR4", "direction": "down", "horizon": "3d"},
        ],
        "off_pool": [
            {"name": "原糖期货", "ticker": "SB", "market": "ICE", "direction": "up",
             "horizon": "1w", "confidence": 0.55, "crowding": "low",
             "mechanism_id": "export_node_outage_commodity", "role": "commodity_price"},
        ],
        "rejected": [{"target": "巴西股指", "reason": "已被定价"}],
    })


KNOWN = {"USD/BRL", "SPX"}


def test_mechanism_summary_drops_unknown_cards_and_multiplies_priors(library):
    cards, chain_prior = impact._mechanism_summary(
        ["seismic_tsunami_coastal_damage", "not_a_real_card", "export_node_outage_commodity"],
        library,
    )
    assert [c["id"] for c in cards] == [
        "seismic_tsunami_coastal_damage", "export_node_outage_commodity",
    ]
    expected = (
        library.cards["seismic_tsunami_coastal_damage"].prior
        * library.cards["export_node_outage_commodity"].prior
    )
    assert chain_prior == pytest.approx(expected)
    assert cards[0]["review_status"] == "draft"
    assert impact._mechanism_summary([], library) == ([], None)


def test_predictions_carry_horizon_crowding_and_checked_mechanism(library):
    event = impact._build_event_from_llm(_news(), _analysis(), library=library, off_pool=[])
    preds = impact._predictions_from_llm(event, _analysis(), KNOWN, library)

    assert [p.asset_id for p in preds] == ["USD/BRL", "SPX"]
    brl, spx = preds
    assert brl.timeframe_min == 1440
    assert (brl.crowding, brl.role) == ("medium", "local_currency")
    assert brl.mechanism_id == "disaster_currency_direction"
    # Defaults when the model left fields out; unknown card id dropped.
    assert spx.timeframe_min == 60
    assert (spx.crowding, spx.role, spx.mechanism_id) == (None, None, None)


def test_unknown_assets_and_off_pool_entries_are_kept(library):
    off_pool = impact._off_pool_from_llm(_analysis(), KNOWN, library)

    assert [o["name"] for o in off_pool] == ["PETR4", "原糖期货"]
    petr4, sugar = off_pool
    assert (petr4["ticker"], petr4["timeframe_min"]) == ("PETR4", 4320)
    assert sugar["market"] == "ICE"
    assert sugar["timeframe_min"] == 10080
    assert sugar["mechanism_id"] == "export_node_outage_commodity"
    assert sugar["crowding"] == "low"


def test_event_analysis_holds_the_new_sections(library):
    analysis = _analysis()
    off_pool = impact._off_pool_from_llm(analysis, KNOWN, library)
    event = impact._build_event_from_llm(_news(), analysis, library=library, off_pool=off_pool)

    stored = event.analysis
    assert stored["premise_check"] == "海底垂直错动，海啸预警已发布"
    assert [m["id"] for m in stored["mechanisms"]] == [
        "seismic_tsunami_coastal_damage", "export_node_outage_commodity",
    ]
    assert 0 < stored["chain_prior"] < 1
    assert len(stored["off_pool"]) == 2
    assert stored["rejected"] == [{"target": "巴西股指", "reason": "已被定价"}]


def test_old_style_analysis_adds_no_empty_sections(library):
    analysis = llm.LLMAnalysis.model_validate({
        "is_market_relevant": True,
        "transmission_chain": ["a", "b"],
        "impacts": [{"asset_id": "SPX", "direction": "up"}],
    })
    event = impact._build_event_from_llm(_news(), analysis, library=library, off_pool=[])
    assert event.analysis == {"transmission_chain": ["a", "b"]}


def test_pubsub_payload_includes_the_new_prediction_fields(library):
    event = impact._build_event_from_llm(_news(), _analysis(), library=library, off_pool=[])
    preds = impact._predictions_from_llm(event, _analysis(), KNOWN, library)
    payload = impact._serialize_for_pubsub(event, preds)
    first = payload["predictions"][0]
    assert first["timeframe_min"] == 1440
    assert (first["crowding"], first["role"]) == ("medium", "local_currency")
    assert first["mechanism_id"] == "disaster_currency_direction"
