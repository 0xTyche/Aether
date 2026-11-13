"""Mechanism library package.

Causal links ("mechanism cards") and the dated historical cases that back
them, stored as YAML in `aether/mechanisms_data/`. Where the rule engine
maps one known headline to fixed per-asset impacts, this library holds the
reusable reasoning steps that chain into second-order effects, each with
its conditions, lags, evidence tier and the objections against it.
"""

from aether.mechanisms.loader import Chain, MechanismLibrary, load_library
from aether.mechanisms.schema import (
    Case,
    CaseRef,
    Effect,
    Lag,
    MechanismCard,
    Observation,
    Review,
    Verification,
    duration_minutes,
    duration_range_minutes,
)

__all__ = [
    "Case",
    "CaseRef",
    "Chain",
    "Effect",
    "Lag",
    "MechanismCard",
    "MechanismLibrary",
    "Observation",
    "Review",
    "Verification",
    "duration_minutes",
    "duration_range_minutes",
    "load_library",
]
