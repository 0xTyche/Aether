"""Pydantic models for the mechanism library.

Two kinds of records live here:

* A **mechanism card** is one causal link: "when trigger T happens and the
  preconditions hold, role R moves in direction D after lag L". A whole
  event story (earthquake -> tsunami -> port damage -> sugar price) is a
  *chain* of cards, never a single card.
* A **case** is one dated historical episode. Cards cite cases as
  supporting, contradicting or mixed evidence.

Every record starts life as a model-drafted prior, so each one carries its
own provenance: cases have a verification status, cards have an evidence
tier and a review status. Nothing here is a fact until a human approves it.
"""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aether.rules.schema import Magnitude


# The seven event categories and five shock natures mirror
# `pipeline/prompts/system_zh.md` step 1, so a classified event can be
# matched to cards without a translation table.
Category = Literal[
    "macro_policy",
    "geopolitical",
    "natural_environmental",
    "industry_supply_chain",
    "company_specific",
    "market_structure_liquidity",
    "tech_system",
]
ShockNature = Literal[
    "supply_side",
    "risk_premium",
    "discount_rate",
    "idiosyncratic",
    "liquidity",
]

# Who is affected, expressed as a relationship to the shock rather than as a
# ticker. The same event moves different roles in opposite directions, which
# is why the role (not the sector name) is the unit a card reasons about.
# Adding a role is a deliberate schema change: keep the vocabulary small.
Role = Literal[
    # --- relationship to the shock ---
    "direct_target",
    "commodity_price",
    "feedstock_price",
    "producer_in_zone",
    "producer_outside_zone",
    "downstream_buyer",
    "upstream_supplier",
    "substitute",
    "freight",
    "insurer",
    "reconstruction",
    "sector_peer",
    "counterparty",
    "leveraged_proxy",
    # --- macro buckets ---
    "local_currency",
    "local_equities",
    "rates",
    "usd",
    "safe_haven",
    "volatility",
    "long_duration_equity",
    "risk_assets",
    "crypto_majors",
    "crypto_alts",
    "stablecoin",
]

EffectDirection = Literal["up", "down", "mixed"]
ObservedDirection = Literal["up", "down", "flat"]
# How fast the market usually prices an effect. "high" = a speed race,
# "low" = the neglected kind this library exists to find.
Crowding = Literal["high", "medium", "low"]
# A = validated against price data, B = backed by several cases, C = logic only.
EvidenceTier = Literal["A", "B", "C"]
ReviewStatus = Literal["draft", "approved", "rejected"]
CaseOutcome = Literal["supports", "contradicts", "mixed"]
Recall = Literal["high", "medium", "low"]
VerificationStatus = Literal["unverified", "web_checked", "price_verified", "disputed"]

_ID_PATTERN = r"^[a-z][a-z0-9_]*$"
_UNIT_MINUTES = {"m": 1, "h": 60, "d": 1440, "w": 10080}
_DURATION_RE = re.compile(r"^(\d+)([mhdw])$")


def duration_minutes(text: str) -> int:
    """Parse '30m' / '4h' / '3d' / '2w' into minutes."""
    m = _DURATION_RE.match(text.strip())
    if m is None:
        raise ValueError(f"bad duration {text!r}: expected e.g. '30m', '4h', '3d', '2w'")
    value = int(m.group(1))
    if value <= 0:
        raise ValueError(f"bad duration {text!r}: must be positive")
    return value * _UNIT_MINUTES[m.group(2)]


def duration_range_minutes(text: str) -> tuple[int, int]:
    """Parse a single duration or a 'low-high' range into (min, max) minutes."""
    parts = text.strip().split("-")
    if len(parts) == 1:
        lo = hi = duration_minutes(parts[0])
    elif len(parts) == 2:
        lo, hi = duration_minutes(parts[0]), duration_minutes(parts[1])
    else:
        raise ValueError(f"bad duration range {text!r}: expected e.g. '5m-4h'")
    if lo > hi:
        raise ValueError(f"bad duration range {text!r}: low end exceeds high end")
    return lo, hi


def _check_range(value: str | None) -> str | None:
    if value is not None:
        duration_range_minutes(value)
    return value


class Lag(BaseModel):
    """When an effect shows up, measured from the triggering event."""

    model_config = ConfigDict(extra="forbid")

    onset: str = Field(..., description="First visible reaction, e.g. '5m-4h'.")
    peak: str = Field(..., description="When the effect is typically largest.")
    fade: str | None = Field(
        None, description="When it has typically reversed. None = persistent."
    )

    _validate_ranges = field_validator("onset", "peak", "fade")(_check_range)

    @property
    def scoring_window_min(self) -> int:
        """Upper bound of `peak`: how long to wait before scoring a prediction."""
        return duration_range_minutes(self.peak)[1]


class Effect(BaseModel):
    """One predicted reaction of one role."""

    model_config = ConfigDict(extra="forbid")

    role: Role
    target: str = Field(..., min_length=1, description="Who exactly, in words.")
    direction: EffectDirection
    magnitude: Magnitude = "medium"
    lag: Lag
    crowding: Crowding
    condition: str = Field(
        "", description="Extra condition for this direction. Required when mixed."
    )
    examples: list[str] = Field(
        default_factory=list,
        description="Illustrative instruments. Free text: not limited to the assets table.",
    )

    @model_validator(mode="after")
    def _mixed_needs_condition(self) -> "Effect":
        if self.direction == "mixed" and not self.condition.strip():
            raise ValueError("direction 'mixed' requires `condition` saying what decides the sign")
        return self


class CaseRef(BaseModel):
    """A card's citation of one case."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=_ID_PATTERN)
    outcome: CaseOutcome
    note: str = ""


class Review(BaseModel):
    """Who drafted a card and whether a human has signed it off."""

    model_config = ConfigDict(extra="forbid")

    status: ReviewStatus = "draft"
    drafted_by: str = "claude"
    drafted_on: date
    reviewed_by: str | None = None
    notes: str = ""


class MechanismCard(BaseModel):
    """One causal link, with the conditions under which it holds and fails."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=_ID_PATTERN, max_length=64)
    name: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1, description="Cause -> effect, 1-2 sentences.")
    categories: list[Category] = Field(..., min_length=1)
    shock_nature: list[ShockNature] = Field(..., min_length=1)
    keywords: list[str] = Field(
        default_factory=list, description="Cheap retrieval hints (zh + en)."
    )
    preconditions: list[str] = Field(..., min_length=1)
    failure_conditions: list[str] = Field(..., min_length=1)
    effects: list[Effect] = Field(..., min_length=1)
    leads_to: list[str] = Field(
        default_factory=list, description="Card ids that commonly follow as the next hop."
    )
    cases: list[CaseRef] = Field(default_factory=list)
    prior: float = Field(
        ...,
        gt=0.0,
        lt=1.0,
        description=(
            "Subjective P(main effects go in the stated direction | trigger fired "
            "and preconditions hold). Multiplied along a chain."
        ),
    )
    evidence_tier: EvidenceTier
    critique: list[str] = Field(
        ..., min_length=1, description="The strongest objections to this card."
    )
    review: Review

    @model_validator(mode="after")
    def _consistency(self) -> "MechanismCard":
        if self.id in self.leads_to:
            raise ValueError(f"card {self.id!r} lists itself in leads_to")
        seen = [c.id for c in self.cases]
        if len(seen) != len(set(seen)):
            raise ValueError(f"card {self.id!r} cites the same case twice")
        supporting = sum(1 for c in self.cases if c.outcome == "supports")
        if self.evidence_tier in ("A", "B") and supporting < 2:
            raise ValueError(
                f"card {self.id!r}: tier {self.evidence_tier} needs >= 2 supporting cases, "
                f"has {supporting}"
            )
        if self.evidence_tier == "A" and self.review.status != "approved":
            raise ValueError(
                f"card {self.id!r}: tier A (data-validated) must be human-approved"
            )
        return self


class Observation(BaseModel):
    """What one asset did during a case."""

    model_config = ConfigDict(extra="forbid")

    asset: str = Field(..., min_length=1, description="Human-readable name.")
    asset_id: str | None = Field(
        None, description="Id in the `assets` table when the instrument is tracked."
    )
    direction: ObservedDirection
    window: str = Field(..., description="Over what horizon, e.g. '1d' or '1w-2w'.")
    note: str = Field("", description="Approximate size and context, in words.")
    recall: Recall = Field(
        ..., description="How sure the drafter is of this from memory, before any check."
    )

    _validate_window = field_validator("window")(_check_range)


class Verification(BaseModel):
    """Provenance of a case's facts."""

    model_config = ConfigDict(extra="forbid")

    status: VerificationStatus = "unverified"
    checked_on: date | None = None
    sources: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def _checked_needs_evidence(self) -> "Verification":
        if self.status in ("web_checked", "price_verified") and self.checked_on is None:
            raise ValueError(f"status {self.status!r} requires `checked_on`")
        if self.status == "web_checked" and not self.sources:
            raise ValueError("status 'web_checked' requires at least one source")
        return self


class Case(BaseModel):
    """One dated historical episode used as evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=_ID_PATTERN, max_length=64)
    title: str = Field(..., min_length=1)
    start_date: date
    end_date: date | None = None
    location: str = ""
    categories: list[Category] = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    observations: list[Observation] = Field(..., min_length=1)
    lessons: list[str] = Field(default_factory=list)
    verification: Verification = Field(default_factory=Verification)

    @model_validator(mode="after")
    def _dates_ordered(self) -> "Case":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError(f"case {self.id!r}: end_date precedes start_date")
        return self
