"""Agent Rating Protocol — decentralized agent reputation system.

A pip-installable implementation of the Agent Rating Protocol,
companion to the Chain of Consciousness specification.

v2 adds: signal composition, portable reputation bundles,
signal verification, and anti-Goodhart mechanisms.
"""

from .blind import BlindExchange, BlindCommitment, commit, generate_nonce, reveal
from .composition import (
    STANDARD_PROFILES,
    CompositeSignal,
    Gate,
    PenaltyFloor,
    ProfileInput,
    Signal,
    WeightProfile,
    compose,
    diminishing_returns_transform,
    get_profile,
)
from .query import (
    generate_prb_from_store,
    get_composite,
    get_governance_weights,
    get_reputation,
    verify_rating,
)
from .rating import (
    DIMENSIONS,
    VERIFICATION_LEVELS,
    AgentIdentity,
    InteractionEvidence,
    RatingRecord,
)
from .store import RatingStore
from .weight import (
    compute_rater_calibrations,
    confidence,
    effective_weight,
    rater_calibration_factor,
    rater_weight,
    recency_multiplier,
    signals_from_ratings,
    verification_level_multiplier,
    weighted_score,
    weighted_scores_all,
)

__all__ = [
    # v1 core
    "AgentIdentity",
    "BlindCommitment",
    "BlindExchange",
    "DIMENSIONS",
    "InteractionEvidence",
    "RatingRecord",
    "RatingStore",
    "VERIFICATION_LEVELS",
    "commit",
    "compute_rater_calibrations",
    "confidence",
    "effective_weight",
    "generate_nonce",
    "get_governance_weights",
    "get_reputation",
    "rater_calibration_factor",
    "rater_weight",
    "recency_multiplier",
    "reveal",
    "verification_level_multiplier",
    "verify_rating",
    "weighted_score",
    "weighted_scores_all",
    # v2: composition
    "STANDARD_PROFILES",
    "CompositeSignal",
    "Gate",
    "PenaltyFloor",
    "ProfileInput",
    "Signal",
    "WeightProfile",
    "compose",
    "diminishing_returns_transform",
    "get_profile",
    # v2: query extensions
    "generate_prb_from_store",
    "get_composite",
    # v2: weight extensions
    "signals_from_ratings",
]

__version__ = "0.3.0"
