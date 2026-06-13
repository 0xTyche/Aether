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
