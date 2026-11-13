"""LLM pipeline: schema parsing, JSON mode, rate limiting, retry."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from aether.pipeline import llm
from aether.storage import redis_ as r


# ---------- system-prompt builders --------------------------------------

def test_build_system_prompt_deterministic_and_includes_lists():
    prompt = llm.build_system_prompt(
        asset_ids=["BTC", "USD/JPY", "AAPL"],
        region_ids=["g7", "eurozone"],
    )
    # Header is the externally-edited Chinese system prompt.
    assert "对冲基金分析师" in prompt
    assert "is_market_relevant" in prompt
    # Assets/regions sorted alphabetically and included verbatim
    assert "AAPL, BTC, USD/JPY" in prompt
    assert "eurozone, g7" in prompt


def test_build_system_prompt_appends_roles_and_mechanism_catalog():
    prompt = llm.build_system_prompt(asset_ids=["BTC"], region_ids=["g7"])
    roles_at = prompt.index("Available role ids:")
    cards_at = prompt.index("Available mechanism cards:")
    assert roles_at < cards_at
    assert "downstream_buyer" in prompt[roles_at:cards_at]
    assert "- seismic_tsunami_coastal_damage｜强震与海啸损毁沿岸设施" in prompt[cards_at:]


def test_build_system_prompt_dedupes_inputs():
    a = llm.build_system_prompt(asset_ids=["X", "X"], region_ids=["g7"])
    b = llm.build_system_prompt(asset_ids=["X"], region_ids=["g7"])
    assert a == b


def test_build_user_message_truncates_long_body():
    body = "x" * 5000
    msg = llm.build_user_message("Fed", "title", body)
    assert "title" in msg
    # Body is truncated to 1500 chars in the prompt.
    assert msg.count("x") == 1500


# ---------- pure parser --------------------------------------------------

def test_parse_or_none_accepts_valid_json():
    payload = json.dumps({
        "is_market_relevant": True,
        "severity": "high",
        "origin_country_iso2": "JP",
        "explanation": "BoJ hike",
        "affected_regions": ["g7"],
        "impacts": [
            {"asset_id": "USD/JPY", "direction": "down", "magnitude": "large",
             "confidence": 0.9, "rationale": "rates"},
        ],
    })
    result = llm._parse_or_none(payload)
    assert result is not None
    assert result.is_market_relevant is True
    assert result.severity == "high"
    assert len(result.impacts) == 1
    assert result.impacts[0].asset_id == "USD/JPY"


def test_parse_or_none_returns_none_on_invalid_json():
    assert llm._parse_or_none("{not json") is None
    assert llm._parse_or_none("") is None


def test_parse_or_none_returns_none_on_schema_violation():
    bad = json.dumps({"is_market_relevant": "not-a-bool"})
    assert llm._parse_or_none(bad) is None


def _full_payload(**overrides) -> str:
    base = {
        "is_market_relevant": True,
        "severity": "high",
        "origin_country_iso2": "BR",
        "explanation": "跨洋海啸",
        "affected_regions": [],
        "premise_check": "震源在大西洋中脊，海啸到巴西沿岸约需 6 小时",
        "mechanisms": ["seismic_tsunami_coastal_damage", "export_node_outage_commodity"],
        "transmission_chain": ["地震", "海啸", "港口停摆", "糖价上涨"],
        "impacts": [
            {"asset_id": "USD/BRL", "direction": "up", "magnitude": "medium",
             "horizon": "1d", "confidence": 0.6, "crowding": "medium",
             "mechanism_id": "disaster_currency_direction", "role": "local_currency",
             "rationale": "雷亚尔承压"},
        ],
        "off_pool": [
            {"name": "原糖期货", "ticker": "SB", "market": "ICE", "direction": "up",
             "horizon": "1w", "confidence": 0.55, "crowding": "low",
             "mechanism_id": "export_node_outage_commodity", "role": "commodity_price",
             "rationale": "桑托斯港出口中断"},
        ],
        "rejected": [{"target": "巴西股指", "reason": "已被定价"}],
    }
    return json.dumps(base | overrides, ensure_ascii=False)


def test_parse_accepts_the_mechanism_aware_schema():
    result = llm._parse_or_none(_full_payload())
    assert result is not None
    imp = result.impacts[0]
    assert (imp.horizon, imp.horizon_min) == ("1d", 1440)
    assert (imp.crowding, imp.role) == ("medium", "local_currency")
    assert imp.mechanism_id == "disaster_currency_direction"
    assert result.premise_check.startswith("震源")
    assert result.mechanisms == [
        "seismic_tsunami_coastal_damage", "export_node_outage_commodity",
    ]
    off = result.off_pool[0]
    assert (off.name, off.ticker, off.market, off.horizon_min) == ("原糖期货", "SB", "ICE", 10080)
    assert result.rejected[0].reason == "已被定价"


def test_parse_still_accepts_the_old_schema():
    old = json.dumps({
        "is_market_relevant": True,
        "impacts": [{"asset_id": "SPX", "direction": "up", "confidence": 0.7}],
    })
    result = llm._parse_or_none(old)
    assert result is not None
    imp = result.impacts[0]
    assert (imp.horizon, imp.horizon_min, imp.crowding, imp.role) == (None, 60, None, None)
    assert result.off_pool == [] and result.rejected == [] and result.mechanisms == []


@pytest.mark.parametrize(
    ("horizon", "minutes"),
    [
        (None, 60),
        ("", 60),
        ("soon", 60),
        ("1-3d", 60),
        ("4h", 240),
        (" 3D ", 4320),
        ("1m", 5),            # clamped up to the minimum
        ("10w", 40320),       # clamped down to 4 weeks
    ],
)
def test_horizon_minutes(horizon, minutes):
    assert llm.horizon_minutes(horizon) == minutes


def test_bad_auxiliary_fields_degrade_instead_of_failing():
    payload = _full_payload(
        premise_check=["前提一", "前提二"],
        mechanisms=["a_card", "a_card", None, "null", "b", "c", "d", "e"],
        impacts=[
            {"asset_id": "SPX", "direction": "up", "horizon": 90,
             "crowding": "extreme", "role": "banana", "mechanism_id": "null"},
        ],
        off_pool=[{"direction": "up"}] + [
            {"name": f"asset {i}", "direction": "down"} for i in range(7)
        ],
        rejected="not a list",
    )
    result = llm._parse_or_none(payload)
    assert result is not None
    imp = result.impacts[0]
    assert (imp.horizon_min, imp.crowding, imp.role, imp.mechanism_id) == (90, None, None, None)
    assert result.premise_check == "前提一；前提二"
    assert result.mechanisms == ["a_card", "b", "c", "d"]
    # The nameless entry is dropped, then the list is capped.
    assert [o.name for o in result.off_pool] == [f"asset {i}" for i in range(llm.MAX_OFF_POOL)]
    assert result.rejected == []


def test_core_impact_fields_stay_strict():
    bad = _full_payload(impacts=[{"asset_id": "SPX", "direction": "sideways"}])
    assert llm._parse_or_none(bad) is None


# ---------- mock-client end-to-end --------------------------------------

@pytest_asyncio.fixture
async def _flush_llm_rate_keys():
    """Clear LLM rate-limit buckets before/after each test."""
    client = r.get_redis()
    async for key in client.scan_iter(match=f"{llm.RATE_LIMIT_KEY_PREFIX}*"):
        await client.delete(key)
    yield
    async for key in client.scan_iter(match=f"{llm.RATE_LIMIT_KEY_PREFIX}*"):
        await client.delete(key)


def _fake_completion(content: str):
    """Wrap a string into the shape of OpenAI's chat.completion response."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _fake_client(*responses: str):
    """Build a fake AsyncOpenAI that returns the given JSON strings in order."""
    completions = AsyncMock()
    completions.create = AsyncMock(
        side_effect=[_fake_completion(r) for r in responses]
    )
    chat = SimpleNamespace(completions=completions)
    return SimpleNamespace(chat=chat), completions


@pytest.mark.usefixtures("_flush_llm_rate_keys")
async def test_analyze_news_returns_parsed_on_first_call():
    payload = json.dumps({
        "is_market_relevant": True,
        "severity": "high",
        "origin_country_iso2": "JP",
        "explanation": "BoJ rate hike",
        "affected_regions": ["g7"],
        "impacts": [{"asset_id": "USD/JPY", "direction": "down"}],
    })
    cli, completions = _fake_client(payload)
    result = await llm.analyze_news(
        system_prompt="sys",
        source="BoJ", title="BoJ raises policy rate", body=None,
        client=cli,
    )
    assert result is not None and result.is_market_relevant is True
    assert completions.create.call_count == 1


@pytest.mark.usefixtures("_flush_llm_rate_keys")
async def test_analyze_news_retries_once_on_invalid_first_response():
    bad = "this is not json"
    good = json.dumps({"is_market_relevant": False, "impacts": []})
    cli, completions = _fake_client(bad, good)
    result = await llm.analyze_news(
        system_prompt="sys", source="X", title="t", body=None, client=cli,
    )
    assert result is not None and result.is_market_relevant is False
    assert completions.create.call_count == 2


@pytest.mark.usefixtures("_flush_llm_rate_keys")
async def test_analyze_news_returns_none_when_both_attempts_fail():
    cli, completions = _fake_client("bad", "still bad")
    result = await llm.analyze_news(
        system_prompt="sys", source="X", title="t", body=None, client=cli,
    )
    assert result is None
    assert completions.create.call_count == 2


@pytest.mark.usefixtures("_flush_llm_rate_keys")
async def test_analyze_news_raises_when_rate_limited(monkeypatch):
    # Drop the limit to 1 to make the test fast.
    from aether.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_RATE_LIMIT_PER_MIN", "1")
    get_settings.cache_clear()

    payload = json.dumps({"is_market_relevant": False, "impacts": []})
    cli, _ = _fake_client(payload, payload)
    # First call: allowed.
    await llm.analyze_news(
        system_prompt="sys", source="X", title="t", body=None, client=cli,
    )
    # Second call within the same minute: should raise.
    with pytest.raises(llm.LLMRateLimited):
        await llm.analyze_news(
            system_prompt="sys", source="X", title="t", body=None, client=cli,
        )

    # Cleanup: restore default settings.
    get_settings.cache_clear()
