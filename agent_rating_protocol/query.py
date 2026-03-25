"""Query interface for reputation scores.

Implements Section 2.5 weighted reputation queries with rolling windows,
confidence scores (Section 4.4), and per-dimension filtering.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from .rating import DIMENSIONS, RatingRecord
from .store import RatingStore
from .weight import confidence, rater_weight, weighted_score, weighted_scores_all


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
) -> Dict[str, Any]:
    """Query an agent's reputation from the local store.

    Args:
        store: The RatingStore to query.
        agent_id: The agent to look up.
        dimension: If specified, return only this dimension. Otherwise all five.
        window_days: Rolling window in days (default 365 per spec).

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

    if dimension:
        score = weighted_score(ratings, dimension)
        result["dimension"] = dimension
        result["score"] = round(score, 2) if score is not None else None
    else:
        scores = weighted_scores_all(ratings)
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
