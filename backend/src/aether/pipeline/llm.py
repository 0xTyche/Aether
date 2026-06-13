"""DeepSeek-backed impact analysis fallback (called only when no rule matches).

We use the OpenAI SDK against DeepSeek's OpenAI-compatible endpoint
because:
  - DeepSeek auto-caches prompts ≥1024 tokens for ~1 hour, so a static
    system prompt listing every asset id stays cheap on repeat calls.
  - JSON mode (`response_format={"type": "json_object"}`) gives structured
    output we can validate with Pydantic.
  - Provider portability — swapping to another OpenAI-compatible vendor
    later is a one-line config change.

Concurrency / cost guards:
  - Token-bucket-ish rate limit via Redis (a sliding-window count of
    calls in the last 60s; reject if >= limit).
  - Per-call timeout from settings.
  - One corrective retry on Pydantic validation failure before giving up.
"""

import json
from collections.abc import Iterable
from typing import Literal

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aether.config import get_settings
from aether.pipeline.prompts import SYSTEM_ZH
from aether.storage import redis_ as r


logger = structlog.get_logger(__name__)

Severity = Literal["low", "medium", "high"]
Direction = Literal["up", "down", "neutral"]
Magnitude = Literal["small", "medium", "large"]

RATE_LIMIT_KEY_PREFIX = "rate:llm:"

# The system prompt lives in `aether/pipeline/prompts/system_zh.md` so it
# can be iterated on without changing Python. Dynamic asset_ids and
# region_ids are appended at runtime by `build_system_prompt`.
SYSTEM_PROMPT_HEADER = SYSTEM_ZH


class LLMImpact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_id: str
    direction: Direction
    magnitude: Magnitude = "medium"
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    rationale: str = ""


class LLMClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    primary_category: str = ""
    shock_nature: list[str] = Field(default_factory=list)


class LLMAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    is_market_relevant: bool
    severity: Severity = "low"
    origin_country_iso2: str | None = None
    explanation: str = ""
    affected_regions: list[str] = Field(default_factory=list)
    # Richer reasoning surfaced to the UI's "deep analysis" panel. Both
    # fields are populated only when is_market_relevant=true; the
    # rule-engine path leaves them None / empty.
    classification: LLMClassification | None = None
    transmission_chain: list[str] = Field(default_factory=list)
    impacts: list[LLMImpact] = Field(default_factory=list)


class LLMRateLimited(Exception):
    """Raised (and swallowed by callers) when the per-minute cap is hit."""


def build_system_prompt(asset_ids: Iterable[str], region_ids: Iterable[str]) -> str:
    """Compose the static system prompt that DeepSeek will cache."""
    assets = sorted(set(asset_ids))
    regions = sorted(set(region_ids))
    return (
        SYSTEM_PROMPT_HEADER
        + "\nAvailable asset_ids:\n"
        + ", ".join(assets)
        + "\n\nAvailable region ids:\n"
        + ", ".join(regions)
        + "\n"
    )


def build_user_message(source: str, title: str, body: str | None) -> str:
    parts = [f"Source: {source}", f"Title: {title}"]
    if body:
        snippet = body[:1500]
        parts.append(f"Body: {snippet}")
    return "\n".join(parts)


async def _allow_call() -> bool:
    """Sliding-window rate limit: at most N calls per rolling 60s."""
    limit = get_settings().llm_rate_limit_per_min
    client = r.get_redis()
    bucket_key = f"{RATE_LIMIT_KEY_PREFIX}{int(__import__('time').time() // 60)}"
    n = await client.incr(bucket_key)
    if n == 1:
        await client.expire(bucket_key, 120)
    if n > limit:
        logger.warning("llm.rate_limited", current=n, limit=limit)
        return False
    return True


def _get_client() -> AsyncOpenAI:
    s = get_settings()
    if not s.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not configured")
    return AsyncOpenAI(
        api_key=s.deepseek_api_key,
        base_url=s.deepseek_base_url,
        timeout=s.llm_timeout_seconds,
    )


def _parse_or_none(raw: str) -> LLMAnalysis | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("llm.json_parse_failed", error=str(exc), raw=raw[:200])
        return None
    try:
        return LLMAnalysis.model_validate(data)
    except ValidationError as exc:
        logger.warning("llm.schema_failed", error=str(exc), raw=raw[:200])
        return None


async def analyze_news(
    *,
    system_prompt: str,
    source: str,
    title: str,
    body: str | None,
    model: str | None = None,
    client: AsyncOpenAI | None = None,
) -> LLMAnalysis | None:
    """Run one analysis pass. Returns None on rate-limit or unrecoverable failure."""
    if not await _allow_call():
        raise LLMRateLimited

    settings = get_settings()
    model = model or settings.deepseek_model
    cli = client or _get_client()

    user_msg = build_user_message(source, title, body)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]

    try:
        res = await cli.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000,
        )
    except Exception as exc:
        logger.exception("llm.api_failed", error=str(exc))
        return None

    raw = (res.choices[0].message.content or "").strip()
    parsed = _parse_or_none(raw)
    if parsed is not None:
        return parsed

    # One corrective retry — tell the model exactly what was wrong.
    correction = (
        "Your previous response did not match the required JSON schema. "
        "Respond again with valid JSON only, conforming to the schema above. "
        "No prose, no markdown, no comments."
    )
    messages_retry = messages + [
        {"role": "assistant", "content": raw},
        {"role": "user", "content": correction},
    ]
    try:
        res2 = await cli.chat.completions.create(
            model=model,
            messages=messages_retry,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=2000,
        )
    except Exception as exc:
        logger.exception("llm.retry_failed", error=str(exc))
        return None

    raw2 = (res2.choices[0].message.content or "").strip()
    return _parse_or_none(raw2)
