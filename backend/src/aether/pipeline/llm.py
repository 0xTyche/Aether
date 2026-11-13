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
from collections.abc import Callable, Iterable
from typing import Annotated, Any, Literal, get_args

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

from aether.config import get_settings
from aether.mechanisms.catalog import ROLE_IDS, default_library, render_catalog
from aether.mechanisms.loader import MechanismLibrary
from aether.mechanisms.schema import duration_minutes
from aether.pipeline.prompts import SYSTEM_ZH
from aether.storage import redis_ as r


logger = structlog.get_logger(__name__)

Severity = Literal["low", "medium", "high"]
Direction = Literal["up", "down", "neutral"]
Magnitude = Literal["small", "medium", "large"]
Crowding = Literal["high", "medium", "low"]

RATE_LIMIT_KEY_PREFIX = "rate:llm:"

# The richer schema (per-impact horizon and crowding, off-pool assets,
# rejected candidates) roughly doubles the answer; 2000 tokens truncated it.
MAX_OUTPUT_TOKENS = 3000

# Horizons the prompt offers. The watcher scores a prediction at
# occurred_at + horizon, so this is "when the move should be largest".
HORIZONS: dict[str, int] = {
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "3d": 4320,
    "1w": 10080,
    "4w": 40320,
}
DEFAULT_HORIZON_MIN = 60
MIN_HORIZON_MIN = 5
MAX_HORIZON_MIN = HORIZONS["4w"]

MAX_MECHANISMS = 4
MAX_OFF_POOL = 5
MAX_REJECTED = 3

# The system prompt lives in `aether/pipeline/prompts/system_zh.md` so it
# can be iterated on without changing Python. Dynamic asset_ids, region_ids,
# role ids and the mechanism catalogue are appended by `build_system_prompt`.
SYSTEM_PROMPT_HEADER = SYSTEM_ZH


def horizon_minutes(horizon: str | None) -> int:
    """Map the model's horizon to minutes. Missing or unparseable means 60."""
    if not horizon:
        return DEFAULT_HORIZON_MIN
    try:
        minutes = duration_minutes(horizon.strip().lower())
    except ValueError:
        return DEFAULT_HORIZON_MIN
    return min(max(minutes, MIN_HORIZON_MIN), MAX_HORIZON_MIN)


# ---- lenient field coercion ----------------------------------------------
# The fields added for the mechanism library are auxiliary. A malformed one
# is dropped to None or skipped rather than failing the whole analysis,
# which would cost a retry and possibly the event.

def _optional_choice(allowed: Iterable[str]) -> Callable[[Any], str | None]:
    choices = frozenset(allowed)

    def coerce(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip().lower()
        return value if value in choices else None

    return coerce


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return None if value.lower() in {"", "null", "none"} else value


def _horizon_text(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return f"{int(value)}m"  # a bare number is read as minutes
    return _optional_text(value)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "；".join(str(v).strip() for v in value if v)
    return str(value).strip()


def _id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _optional_text(item)
        if text is not None and text not in out:
            out.append(text)
    return out[:MAX_MECHANISMS]


def _keep_valid(model: type[BaseModel], limit: int) -> Callable[[Any], list[BaseModel]]:
    def coerce(items: Any) -> list[BaseModel]:
        if not isinstance(items, list):
            return []
        kept: list[BaseModel] = []
        for item in items:
            try:
                kept.append(model.model_validate(item))
            except ValidationError:
                logger.warning("llm.item_dropped", model=model.__name__, item=str(item)[:200])
        return kept[:limit]

    return coerce


OptionalCrowding = Annotated[Crowding | None, BeforeValidator(_optional_choice(get_args(Crowding)))]
OptionalRole = Annotated[str | None, BeforeValidator(_optional_choice(ROLE_IDS))]
OptionalText = Annotated[str | None, BeforeValidator(_optional_text)]


class LLMImpactBase(BaseModel):
    """What the model says about one affected asset, in or out of the pool."""

    model_config = ConfigDict(extra="ignore")
    direction: Direction
    magnitude: Magnitude = "medium"
    horizon: Annotated[str | None, BeforeValidator(_horizon_text)] = None
    # Probability that the direction is right at the horizon. Crowding and
    # tradability are separate fields, not discounts on this number.
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    crowding: OptionalCrowding = None
    # Card id from the mechanism catalogue; checked against the library in
    # `pipeline.impact`, where unknown ids are dropped.
    mechanism_id: OptionalText = None
    role: OptionalRole = None
    rationale: str = ""

    @property
    def horizon_min(self) -> int:
        return horizon_minutes(self.horizon)


class LLMImpact(LLMImpactBase):
    asset_id: str


class LLMOffPoolImpact(LLMImpactBase):
    """An asset the model thinks is affected but that is not in our pool."""

    name: str = Field(..., min_length=1)
    ticker: OptionalText = None
    market: Annotated[str, BeforeValidator(_as_text)] = ""


class LLMRejected(BaseModel):
    """A candidate the model considered and dropped, with the reason."""

    model_config = ConfigDict(extra="ignore")
    target: str = Field(..., min_length=1)
    reason: Annotated[str, BeforeValidator(_as_text)] = ""


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
    # Richer reasoning surfaced to the UI's "deep analysis" panel. All of
    # these are populated only when is_market_relevant=true; the
    # rule-engine path leaves them None / empty.
    classification: LLMClassification | None = None
    premise_check: Annotated[str, BeforeValidator(_as_text)] = ""
    mechanisms: Annotated[list[str], BeforeValidator(_id_list)] = Field(default_factory=list)
    transmission_chain: list[str] = Field(default_factory=list)
    impacts: list[LLMImpact] = Field(default_factory=list)
    off_pool: Annotated[
        list[LLMOffPoolImpact], BeforeValidator(_keep_valid(LLMOffPoolImpact, MAX_OFF_POOL))
    ] = Field(default_factory=list)
    rejected: Annotated[
        list[LLMRejected], BeforeValidator(_keep_valid(LLMRejected, MAX_REJECTED))
    ] = Field(default_factory=list)


class LLMRateLimited(Exception):
    """Raised (and swallowed by callers) when the per-minute cap is hit."""


def build_system_prompt(
    asset_ids: Iterable[str],
    region_ids: Iterable[str],
    library: MechanismLibrary | None = None,
) -> str:
    """Compose the static system prompt that DeepSeek will cache."""
    assets = sorted(set(asset_ids))
    regions = sorted(set(region_ids))
    library = library if library is not None else default_library()
    return (
        SYSTEM_PROMPT_HEADER
        + "\nAvailable asset_ids:\n"
        + ", ".join(assets)
        + "\n\nAvailable region ids:\n"
        + ", ".join(regions)
        + "\n\nAvailable role ids:\n"
        + ", ".join(ROLE_IDS)
        + "\n\nAvailable mechanism cards:\n"
        + render_catalog(library)
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
            max_tokens=MAX_OUTPUT_TOKENS,
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
            max_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:
        logger.exception("llm.retry_failed", error=str(exc))
        return None

    raw2 = (res2.choices[0].message.content or "").strip()
    return _parse_or_none(raw2)
