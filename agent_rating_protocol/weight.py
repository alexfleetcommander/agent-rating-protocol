"""Rater weight calculation and weighted score aggregation.

Implements the Agent Rating Protocol whitepaper:
- W(rater) = log2(1 + chain_age_days) * log2(1 + total_ratings_given) (Section 4.5)
- Verification level multipliers (Section 4.8)
- Anti-inflation rater calibration — sigma < 10 penalty (Section 4.6)
- Recency weighting within rolling window (Section 3.2)
- Weighted aggregate score per dimension (Section 4.5)
"""

import math
import statistics
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from .rating import DIMENSIONS, RatingRecord


# Verification level weight multipliers (Section 4.8)
VERIFICATION_MULTIPLIERS = {
    "verified": 1.0,
    "unilateral": 0.5,
    "self_reported": 0.5,
}


def rater_weight(chain_age_days: int, total_ratings_given: int) -> float:
    """Compute a rater's base weight from operational age and rating volume.

    W = log2(1 + chain_age_days) * log2(1 + total_ratings_given)

    Properties (Section 4.5):
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


def verification_level_multiplier(level: str) -> float:
    """Return the weight multiplier for a verification level (Section 4.8).

    - verified: 1.0x (full weight — bilateral verification)
    - unilateral: 0.5x (ratee didn't acknowledge the interaction)
    - self_reported: 0.5x (standalone mode, no external verification)

    Args:
        level: One of 'verified', 'unilateral', 'self_reported'.

    Returns:
        Multiplier (0.5 or 1.0).
    """
    return VERIFICATION_MULTIPLIERS.get(level, 1.0)


def rater_calibration_factor(rater_scores: Sequence[float]) -> float:
    """Compute anti-inflation calibration factor for a rater (Section 4.6).

    Raters whose standard deviation across all rating scores is below 10
    are penalized by a factor of sigma/10. A rater with sigma=5 has their
    ratings weighted at 50% of normal W.

    Args:
        rater_scores: All dimension scores this rater has given across
            all their ratings (flattened list of score values).

    Returns:
        Calibration factor between 0.0 and 1.0. Returns 1.0 if fewer
        than 2 scores (insufficient data for std dev).
    """
    if len(rater_scores) < 2:
        return 1.0
    sigma = statistics.stdev(rater_scores)
    if sigma < 10:
        return sigma / 10.0
    return 1.0


def recency_multiplier(
    rating_timestamp: str,
    window_days: int = 365,
) -> float:
    """Compute recency weight for a rating within the rolling window.

    More recent ratings receive higher weight. Linear decay from 1.0
    (today) to 0.5 (at window boundary). Ratings outside the window
    return 0.0. Implements the recency weighting specified in Section 3.2.

    Args:
        rating_timestamp: ISO-8601 timestamp of the rating.
        window_days: Rolling window size in days.

    Returns:
        Recency multiplier between 0.0 and 1.0.
    """
    try:
        ts_str = rating_timestamp.replace("Z", "+00:00")
        ts = datetime.fromisoformat(ts_str)
    except (ValueError, AttributeError):
        return 1.0  # Can't parse — default to full weight

    now = datetime.now(timezone.utc)
    age = (now - ts).total_seconds() / 86400.0

    if age < 0:
        return 1.0  # Future timestamp — full weight
    if age > window_days:
        return 0.0

    return 1.0 - 0.5 * (age / window_days)


def effective_weight(
    record: RatingRecord,
    calibration: float = 1.0,
    recency: float = 1.0,
) -> float:
    """Compute the effective weight for a rating including all multipliers.

    effective_W = base_W * verification_multiplier * calibration * recency

    Args:
        record: The rating record.
        calibration: Pre-computed calibration factor for this rater (Section 4.6).
        recency: Pre-computed recency multiplier for this record.

    Returns:
        Effective weight (non-negative float).
    """
    base = rater_weight(record.rater_chain_age_days, record.rater_total_ratings_given)
    v_mult = verification_level_multiplier(
        getattr(record, "verification_level", "verified")
    )
    return base * v_mult * calibration * recency


def compute_rater_calibrations(
    all_ratings: Sequence[RatingRecord],
) -> Dict[str, float]:
    """Compute calibration factors for all raters in a set of ratings.

    Groups ratings by rater, collects all dimension scores, and computes
    the standard deviation penalty per Section 4.6.

    Args:
        all_ratings: All ratings to analyze (typically from a store).

    Returns:
        Dict mapping rater_id to calibration factor (0.0 to 1.0).
    """
    rater_scores: Dict[str, List[float]] = {}
    for r in all_ratings:
        if r.rater_id not in rater_scores:
            rater_scores[r.rater_id] = []
        for dim in DIMENSIONS:
            rater_scores[r.rater_id].append(float(getattr(r, dim)))

    return {
        rater_id: rater_calibration_factor(scores)
        for rater_id, scores in rater_scores.items()
    }


def weighted_score(
    ratings: Sequence[RatingRecord],
    dimension: str,
    calibration_factors: Optional[Dict[str, float]] = None,
) -> Optional[float]:
    """Compute the weighted aggregate score for a dimension.

    Score_d(ratee) = Σ[W(rater_i) * rating_d(rater_i)] / Σ[W(rater_i)]

    Automatically applies verification level multiplier from each record.
    Optionally applies per-rater calibration factors for anti-inflation.

    Args:
        ratings: Sequence of RatingRecord objects (all for the same ratee).
        dimension: Which dimension to aggregate.
        calibration_factors: Optional dict of rater_id -> calibration factor.

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
        cal = 1.0
        if calibration_factors and r.rater_id in calibration_factors:
            cal = calibration_factors[r.rater_id]
        w = effective_weight(r, calibration=cal)
        score = getattr(r, dimension)
        weighted_sum += w * score
        total_weight += w

    if total_weight == 0.0:
        return None

    return weighted_sum / total_weight


def weighted_scores_all(
    ratings: Sequence[RatingRecord],
    calibration_factors: Optional[Dict[str, float]] = None,
) -> Dict[str, Optional[float]]:
    """Compute weighted aggregate scores for all five dimensions.

    Args:
        ratings: Sequence of RatingRecord objects (all for the same ratee).
        calibration_factors: Optional dict of rater_id -> calibration factor.

    Returns:
        Dict mapping dimension name to weighted score (or None if no weight).
    """
    return {
        dim: weighted_score(ratings, dim, calibration_factors)
        for dim in DIMENSIONS
    }


def confidence(num_ratings: int) -> float:
    """Compute confidence level for a reputation score.

    confidence = 1 - 1/(1 + 0.1 * num_ratings)

    Approaches 1 asymptotically as ratings accumulate (Section 4.5).

    Args:
        num_ratings: Number of ratings received.

    Returns:
        Confidence value between 0.0 and 1.0.
    """
    if num_ratings < 0:
        raise ValueError("num_ratings must be non-negative")
    return 1.0 - 1.0 / (1.0 + 0.1 * num_ratings)
