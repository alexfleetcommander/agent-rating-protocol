"""Query interface for reputation scores.

Implements the Agent Rating Protocol whitepaper:
- Section 4.5: weighted reputation queries with rolling windows
- Section 4.5: confidence scores
- Section 4.6: anti-inflation calibration (optional)
- Section 5.4: governance weight cap (10% per agent)
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from .rating import DIMENSIONS, RatingRecord
from .store import RatingStore
from .weight import (
    confidence,
    compute_rater_calibrations,
    rater_weight,
    weighted_score,
    weighted_scores_all,
)


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string to datetime."""
    # Handle both Z suffix and +00:00
    ts = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        # Fallback: strip microseconds if needed
        return datetime.fromisoformat(ts.split(".")[0] + "+00:00")


def _filter_by_window(
    ratings: List[RatingRecord], window_days: int
) -> List[RatingRecord]:
    """Filter ratings to only those within the rolling window."""
    if window_days <= 0:
        return ratings

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    filtered = []
    for r in ratings:
        try:
            ts = _parse_timestamp(r.timestamp)
            if ts >= cutoff:
                filtered.append(r)
        except (ValueError, TypeError):
            # Skip ratings with unparseable timestamps
            continue
    return filtered


def get_reputation(
    store: RatingStore,
    agent_id: str,
    dimension: Optional[str] = None,
    window_days: int = 365,
    apply_calibration: bool = False,
) -> Dict[str, Any]:
    """Query an agent's reputation from the local store.

    Args:
        store: The RatingStore to query.
        agent_id: The agent to look up.
        dimension: If specified, return only this dimension. Otherwise all five.
        window_days: Rolling window in days (default 365 per spec).
        apply_calibration: If True, apply anti-inflation rater calibration
            (Section 4.6). Requires reading all ratings to compute per-rater
            standard deviations.

    Returns:
        Dict with scores, confidence, num_ratings, and agent_id.
        If dimension is specified, 'score' is a single float.
        Otherwise, 'scores' is a dict of all dimensions.

    Raises:
        ValueError: If dimension is not one of the five defined dimensions.
    """
    if dimension is not None and dimension not in DIMENSIONS:
        raise ValueError(
            f"Unknown dimension '{dimension}'. Must be one of: {DIMENSIONS}"
        )

    # Get all ratings for this agent within the window
    all_ratings = store.get_ratings_for(agent_id)
    ratings = _filter_by_window(all_ratings, window_days)

    num_ratings = len(ratings)
    conf = confidence(num_ratings)

    result: Dict[str, Any] = {
        "agent_id": agent_id,
        "num_ratings": num_ratings,
        "confidence": round(conf, 4),
        "window_days": window_days,
    }

    if num_ratings == 0:
        if dimension:
            result["dimension"] = dimension
            result["score"] = None
        else:
            result["scores"] = {dim: None for dim in DIMENSIONS}
        return result

    # Compute calibration factors if requested (Section 4.6)
    cal_factors = None
    if apply_calibration:
        all_store_ratings = store.get_all()
        cal_factors = compute_rater_calibrations(all_store_ratings)

    if dimension:
        score = weighted_score(ratings, dimension, cal_factors)
        result["dimension"] = dimension
        result["score"] = round(score, 2) if score is not None else None
    else:
        scores = weighted_scores_all(ratings, cal_factors)
        result["scores"] = {
            dim: round(s, 2) if s is not None else None
            for dim, s in scores.items()
        }

    return result


def get_reputation_summary(
    store: RatingStore,
    agent_id: str,
    window_days: int = 365,
) -> Dict[str, Any]:
    """Get a human-readable reputation summary for an agent.

    Args:
        store: The RatingStore to query.
        agent_id: The agent to look up.
        window_days: Rolling window in days.

    Returns:
        Dict with scores, confidence, rating count, and score buckets.
    """
    rep = get_reputation(store, agent_id, window_days=window_days)

    from .rating import score_bucket

    if rep["scores"]:
        buckets = {}
        for dim, score in rep["scores"].items():
            if score is not None:
                buckets[dim] = score_bucket(int(round(score)))
            else:
                buckets[dim] = "unrated"
        rep["buckets"] = buckets

    return rep


def get_governance_weights(
    store: RatingStore,
    cap: float = 0.10,
) -> Dict[str, float]:
    """Compute governance weights for all agents with a per-agent cap.

    Per Section 5.4, no agent can hold more than 10% of effective voting
    weight. GovWeight uses the same formula as rating weight:
    log2(1 + age) * log2(1 + ratings_given).

    The cap is applied as a fraction of the pre-cap total weight. This
    prevents any single agent from dominating governance decisions.

    Args:
        store: The RatingStore to analyze.
        cap: Maximum fraction of total weight any agent can hold (default 0.10).

    Returns:
        Dict mapping agent_id to capped governance weight.
    """
    all_ratings = store.get_all()

    # Collect per-agent stats (age and rating count)
    agent_stats: Dict[str, Dict[str, int]] = {}
    for r in all_ratings:
        if r.rater_id not in agent_stats:
            agent_stats[r.rater_id] = {
                "chain_age_days": r.rater_chain_age_days,
                "ratings_given": 0,
            }
        agent_stats[r.rater_id]["ratings_given"] += 1
        # Use the highest age seen for this rater
        if r.rater_chain_age_days > agent_stats[r.rater_id]["chain_age_days"]:
            agent_stats[r.rater_id]["chain_age_days"] = r.rater_chain_age_days

    # Compute raw governance weights
    raw_weights: Dict[str, float] = {}
    for agent_id, stats in agent_stats.items():
        raw_weights[agent_id] = rater_weight(
            stats["chain_age_days"], stats["ratings_given"]
        )

    # Apply per-agent cap (Section 5.4)
    total = sum(raw_weights.values())
    if total == 0:
        return raw_weights

    max_weight = cap * total
    capped: Dict[str, float] = {}
    for agent_id, w in raw_weights.items():
        capped[agent_id] = min(w, max_weight)

    return capped


def verify_rating(store: RatingStore, rating_id: str) -> Dict[str, Any]:
    """Verify a specific rating record's hash integrity.

    Args:
        store: The RatingStore containing the rating.
        rating_id: The UUID of the rating to verify.

    Returns:
        Dict with rating_id, valid (bool), and details.
    """
    record = store.get_rating(rating_id)
    if record is None:
        return {
            "rating_id": rating_id,
            "valid": False,
            "error": "Rating not found in store",
        }

    is_valid = record.verify_hash()
    result: Dict[str, Any] = {
        "rating_id": rating_id,
        "valid": is_valid,
        "record_hash": record.record_hash,
        "computed_hash": record.compute_hash(),
    }
    if not is_valid:
        result["error"] = "Hash mismatch — record may have been tampered"

    return result
