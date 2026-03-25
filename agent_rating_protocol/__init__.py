"""Agent Rating Protocol — decentralized agent reputation system.

A pip-installable implementation of the Agent Rating Protocol,
companion to the Chain of Consciousness specification.
"""

from .blind import BlindExchange, BlindCommitment, commit, generate_nonce, reveal
from .query import get_governance_weights, get_reputation, verify_rating
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
    verification_level_multiplier,
    weighted_score,
    weighted_scores_all,
)

__all__ = [
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
]

__version__ = "0.2.0"
