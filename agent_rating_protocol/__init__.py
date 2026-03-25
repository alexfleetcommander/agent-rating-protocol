"""Agent Rating Protocol — decentralized agent reputation system.

A pip-installable implementation of the Decentralized Agent Rating Protocol,
companion to the Chain of Consciousness specification.
"""

from .blind import BlindExchange, BlindCommitment, commit, generate_nonce, reveal
from .query import get_reputation, verify_rating
from .rating import DIMENSIONS, InteractionEvidence, RatingRecord
from .store import RatingStore
from .weight import confidence, rater_weight, weighted_score, weighted_scores_all

__all__ = [
    "BlindCommitment",
    "BlindExchange",
    "DIMENSIONS",
    "InteractionEvidence",
    "RatingRecord",
    "RatingStore",
    "commit",
    "confidence",
    "generate_nonce",
    "get_reputation",
    "rater_weight",
    "reveal",
    "verify_rating",
    "weighted_score",
    "weighted_scores_all",
]

__version__ = "0.1.0"
