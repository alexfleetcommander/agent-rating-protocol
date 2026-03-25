"""Rater weight calculation and weighted score aggregation.

Implements Section 2.5 of the Agent Rating System Design:
- W(rater) = log2(1 + chain_age_days) * log2(1 + total_ratings_given)
- Weighted aggregate score per dimension
- Anti-inflation calibration (Section 2.6)
"""

import math
from typing import Dict, List, Optional, Sequence

from .rating import DIMENSIONS, RatingRecord


def rater_weight(chain_age_days: int, total_ratings_given: int) -> float:
    """Compute a rater's weight from operational age and rating volume.

    W = log2(1 + chain_age_days) * log2(1 + total_ratings_given)

    Properties (Section 2.5):
    - Logarithmic scaling prevents old agents from overwhelming dominance
    - Both age AND volume must be non-trivial for meaningful weight
    - New agents (age=0, ratings=0) have W = 0
    - No score component — score received does not affect weight

    Args:
        chain_age_days: Verified operational age in days.
        total_ratings_given: Lifetime ratings submitted by this rater.

    Returns:
        The rater's weight (non-negative float).
    """
    if chain_age_days < 0 or total_ratings_given < 0:
        raise ValueError("Age and rating count must be non-negative")
    return math.log2(1 + chain_age_days) * math.log2(1 + total_ratings_given)


def weighted_score(
    ratings: Sequence[RatingRecord],
    dimension: str,
) -> Optional[float]:
    """Compute the weighted aggregate score for a dimension.

    Score_d(ratee) = Σ[W(rater_i) * rating_d(rater_i)] / Σ[W(rater_i)]

    Args:
        ratings: Sequence of RatingRecord objects (all for the same ratee).
        dimension: Which dimension to aggregate.

    Returns:
        Weighted average score, or None if total weight is zero.

    Raises:
        ValueError: If dimension is not one of the five defined dimensions.
    """
    if dimension not in DIMENSIONS:
        raise ValueError(
            f"Unknown dimension '{dimension}'. Must be one of: {DIMENSIONS}"
        )

    total_weight = 0.0
    weighted_sum = 0.0

    for r in ratings:
        w = rater_weight(r.rater_chain_age_days, r.rater_total_ratings_given)
        score = getattr(r, dimension)
        weighted_sum += w * score
        total_weight += w

    if total_weight == 0.0:
        return None

    return weighted_sum / total_weight


def weighted_scores_all(
    ratings: Sequence[RatingRecord],
) -> Dict[str, Optional[float]]:
    """Compute weighted aggregate scores for all five dimensions.

    Args:
        ratings: Sequence of RatingRecord objects (all for the same ratee).

    Returns:
        Dict mapping dimension name to weighted score (or None if no weight).
    """
    return {dim: weighted_score(ratings, dim) for dim in DIMENSIONS}


def confidence(num_ratings: int) -> float:
    """Compute confidence level for a reputation score.

    confidence = 1 - 1/(1 + 0.1 * num_ratings)

    Approaches 1 asymptotically as ratings accumulate (Section 4.4).

    Args:
        num_ratings: Number of ratings received.

    Returns:
        Confidence value between 0.0 and 1.0.
    """
    if num_ratings < 0:
        raise ValueError("num_ratings must be non-negative")
    return 1.0 - 1.0 / (1.0 + 0.1 * num_ratings)
