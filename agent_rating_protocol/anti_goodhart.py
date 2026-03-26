"""Anti-Goodhart mechanisms for ARP v2.

Implements Section 6 of the ARP v2 whitepaper:
- Metric rotation with published bounds (Section 6.3)
- Shadow metric tracking and divergence detection (Section 6.4)
- Differential privacy noise injection for queries (Section 6.5)
"""

import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .composition import ProfileInput, WeightProfile


# ---------------------------------------------------------------------------
# Metric rotation (Section 6.3)
# ---------------------------------------------------------------------------

@dataclass
class RotationBound:
    """Min/max weight bounds for a signal during rotation."""

    signal_id: str
    min_weight: float
    max_weight: float
    current_weight: Optional[float] = None  # None = "ROTATED" (hidden)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "signal_id": self.signal_id,
            "weight_bounds": {"min": self.min_weight, "max": self.max_weight},
        }
        if self.current_weight is not None:
            d["current_weight"] = self.current_weight
        else:
            d["current_weight"] = "ROTATED"
        return d

    def validate_weight(self, weight: float) -> bool:
        """Check if a weight is within bounds."""
        return self.min_weight <= weight <= self.max_weight


@dataclass
class RotationEvent:
    """Record of a weight rotation event."""

    profile_id: str
    timestamp: str
    previous_weights: Dict[str, float]
    new_weights: Dict[str, float]
    announcement: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "timestamp": self.timestamp,
            "previous_weights": self.previous_weights,
            "new_weights": self.new_weights,
            "announcement": self.announcement,
        }


def generate_rotation_bounds(
    profile: WeightProfile,
    bound_fraction: float = 0.4,
) -> List[RotationBound]:
    """Generate rotation bounds for a profile's inputs.

    Each weight gets min/max bounds = current_weight ± (bound_fraction * current_weight),
    clamped to [0, 1].

    Args:
        profile: The weight profile.
        bound_fraction: How much the weight can vary (default ±40%).

    Returns:
        List of RotationBound for each input.
    """
    bounds: List[RotationBound] = []
    for inp in profile.inputs:
        if inp.weight_bounds:
            bounds.append(RotationBound(
                signal_id=inp.signal_id,
                min_weight=inp.weight_bounds["min"],
                max_weight=inp.weight_bounds["max"],
            ))
        else:
            delta = inp.weight * bound_fraction
            lo = max(0.0, inp.weight - delta)
            hi = min(1.0, inp.weight + delta)
            bounds.append(RotationBound(
                signal_id=inp.signal_id,
                min_weight=round(lo, 4),
                max_weight=round(hi, 4),
            ))
    return bounds


def rotate_weights(
    profile: WeightProfile,
    bounds: List[RotationBound],
    seed: Optional[int] = None,
) -> Tuple[WeightProfile, RotationEvent]:
    """Rotate weights within published bounds (Section 6.3).

    Generates new weights randomly within bounds, then normalizes to sum=1.

    Args:
        profile: The current weight profile.
        bounds: Rotation bounds per input signal.
        seed: Optional random seed for reproducibility.

    Returns:
        Tuple of (new_profile, rotation_event).
    """
    rng = random.Random(seed)
    bound_map = {b.signal_id: b for b in bounds}

    old_weights: Dict[str, float] = {}
    new_raw: Dict[str, float] = {}

    for inp in profile.inputs:
        old_weights[inp.signal_id] = inp.weight
        bound = bound_map.get(inp.signal_id)
        if bound:
            new_raw[inp.signal_id] = rng.uniform(bound.min_weight, bound.max_weight)
        else:
            new_raw[inp.signal_id] = inp.weight

    # Normalize to sum = 1
    total = sum(new_raw.values())
    new_weights: Dict[str, float] = {}
    if total > 0:
        for sid, w in new_raw.items():
            new_weights[sid] = round(w / total, 4)
    else:
        new_weights = new_raw

    # Build new profile with rotated weights
    new_inputs: List[ProfileInput] = []
    for inp in profile.inputs:
        new_inputs.append(ProfileInput(
            signal_id=inp.signal_id,
            weight=new_weights.get(inp.signal_id, inp.weight),
            operation=inp.operation,
            k=inp.k,
            weight_bounds=(
                {"min": bound_map[inp.signal_id].min_weight,
                 "max": bound_map[inp.signal_id].max_weight}
                if inp.signal_id in bound_map else inp.weight_bounds
            ),
        ))

    now = datetime.now(timezone.utc).isoformat()
    new_profile = WeightProfile(
        profile_id=profile.profile_id,
        version=now[:10],  # Date-based version
        description=profile.description,
        inputs=new_inputs,
        gates=profile.gates,
        penalty_floors=profile.penalty_floors,
        output_range=profile.output_range,
        rotation_schedule=profile.rotation_schedule,
        governance_approved=now,
    )

    event = RotationEvent(
        profile_id=profile.profile_id,
        timestamp=now,
        previous_weights=old_weights,
        new_weights=new_weights,
        announcement=(
            f"Weights for {profile.profile_id} have been updated as of {now[:10]}"
        ),
    )

    return new_profile, event


# ---------------------------------------------------------------------------
# Shadow metrics (Section 6.4)
# ---------------------------------------------------------------------------

@dataclass
class ShadowMetric:
    """A private-tier metric that monitors a public/queryable signal."""

    primary_signal_id: str
    shadow_signal_id: str
    description: str = ""
    primary_value: float = 0.0
    shadow_value: float = 0.0
    divergence_threshold: float = 2.0  # Standard deviations
    _history: List[float] = field(default_factory=list, repr=False)

    def record(self, primary: float, shadow: float) -> None:
        """Record a new observation pair."""
        self.primary_value = primary
        self.shadow_value = shadow
        # Track the difference for divergence detection
        self._history.append(primary - shadow)

    def divergence_detected(self) -> bool:
        """Check if primary and shadow have diverged beyond threshold.

        Uses z-score of the latest difference relative to the history.
        """
        if len(self._history) < 3:
            return False

        mean = statistics.mean(self._history)
        stdev = statistics.stdev(self._history)
        if stdev == 0:
            return False

        latest = self._history[-1]
        z_score = abs(latest - mean) / stdev
        return z_score > self.divergence_threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_signal_id": self.primary_signal_id,
            "shadow_signal_id": self.shadow_signal_id,
            "primary_value": self.primary_value,
            "shadow_value": self.shadow_value,
            "divergence_detected": self.divergence_detected(),
            "observations": len(self._history),
        }


# Default shadow metric definitions (Section 6.4 table)
DEFAULT_SHADOW_METRICS = [
    {
        "primary": "composite_score",
        "shadow": "score_stability_variance",
        "description": "Score stability (30/90/180 day variance)",
    },
    {
        "primary": "arp:reliability:weighted_mean",
        "shadow": "repeat_interaction_rate",
        "description": "Repeat interaction rate (do agents re-hire?)",
    },
    {
        "primary": "arp:accuracy:weighted_mean",
        "shadow": "downstream_verification_rate",
        "description": "Downstream error detection rate",
    },
    {
        "primary": "arp:latency:weighted_mean",
        "shadow": "task_complexity_ratio",
        "description": "Latency relative to task complexity",
    },
    {
        "primary": "arp:cost_efficiency:weighted_mean",
        "shadow": "value_per_token_ratio",
        "description": "Output quality per compute unit",
    },
    {
        "primary": "behavioral:rating_participation_rate",
        "shadow": "rating_reciprocity_balance",
        "description": "Rating reciprocity balance",
    },
]


@dataclass
class ShadowMetricCommitment:
    """Hash-based audit mechanism for shadow metric integrity (Section 6.4).

    Oracles publish a commitment hash proving computation occurred
    without revealing shadow metric values.
    """

    oracle_id: str
    cycle_timestamp: str
    commitment_hash: str  # SHA-256 of shadow metric computation
    agent_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "oracle_id": self.oracle_id,
            "cycle_timestamp": self.cycle_timestamp,
            "commitment_hash": self.commitment_hash,
            "agent_count": self.agent_count,
        }


def compute_shadow_commitment(
    oracle_id: str,
    shadow_data: Dict[str, Any],
) -> ShadowMetricCommitment:
    """Compute a shadow metric commitment hash.

    Args:
        oracle_id: The oracle's identifier.
        shadow_data: Dict of agent_id -> shadow metric values.

    Returns:
        ShadowMetricCommitment with the commitment hash.
    """
    canonical = json.dumps(shadow_data, sort_keys=True, separators=(",", ":"))
    commitment = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat()

    return ShadowMetricCommitment(
        oracle_id=oracle_id,
        cycle_timestamp=now,
        commitment_hash=commitment,
        agent_count=len(shadow_data),
    )


def verify_shadow_commitment(
    commitment: ShadowMetricCommitment,
    revealed_data: Dict[str, Any],
) -> bool:
    """Verify revealed shadow data against a published commitment.

    Args:
        commitment: The published commitment.
        revealed_data: The revealed shadow metric data.

    Returns:
        True if the data matches the commitment.
    """
    canonical = json.dumps(revealed_data, sort_keys=True, separators=(",", ":"))
    computed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return computed == commitment.commitment_hash


@dataclass
class AnomalyFlag:
    """An anomaly flag raised by shadow metric divergence detection."""

    agent_id: str
    primary_signal: str
    shadow_signal: str
    severity: str  # "warning", "enhanced_monitoring", "governance_review"
    confidence_adjustment: float = 1.0  # Multiplier for score confidence
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "primary_signal": self.primary_signal,
            "shadow_signal": self.shadow_signal,
            "severity": self.severity,
            "confidence_adjustment": self.confidence_adjustment,
            "timestamp": self.timestamp,
            "details": self.details,
        }


def check_anomalies(
    agent_id: str,
    shadow_metrics: Sequence[ShadowMetric],
    confidence_penalty: float = 0.8,
) -> List[AnomalyFlag]:
    """Check shadow metrics for anomalies and generate flags.

    Args:
        agent_id: The agent being monitored.
        shadow_metrics: Shadow metrics for this agent.
        confidence_penalty: Confidence multiplier when flagged (default 0.8).

    Returns:
        List of AnomalyFlags (empty if no anomalies detected).
    """
    flags: List[AnomalyFlag] = []

    for sm in shadow_metrics:
        if sm.divergence_detected():
            flags.append(AnomalyFlag(
                agent_id=agent_id,
                primary_signal=sm.primary_signal_id,
                shadow_signal=sm.shadow_signal_id,
                severity="enhanced_monitoring",
                confidence_adjustment=confidence_penalty,
                details=(
                    f"Divergence detected between {sm.primary_signal_id} "
                    f"and {sm.shadow_signal_id} "
                    f"(primary={sm.primary_value:.1f}, "
                    f"shadow={sm.shadow_value:.1f})"
                ),
            ))

    return flags


# ---------------------------------------------------------------------------
# Differential privacy (Section 6.5)
# ---------------------------------------------------------------------------

def laplace_noise(sensitivity: float, epsilon: float) -> float:
    """Generate Laplace-distributed noise for differential privacy.

    noise ~ Laplace(0, sensitivity/epsilon)

    Args:
        sensitivity: Maximum change from a single rating.
        epsilon: Privacy parameter (higher = less noise, less privacy).

    Returns:
        A random noise value.
    """
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    if sensitivity < 0:
        raise ValueError("sensitivity must be non-negative")

    scale = sensitivity / epsilon
    # Laplace distribution via inverse CDF
    u = random.random() - 0.5
    return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))


def add_dp_noise(
    true_value: float,
    sensitivity: float = 5.0,
    epsilon: float = 1.0,
    output_range: Tuple[float, float] = (0.0, 100.0),
) -> float:
    """Add calibrated differential privacy noise to a composite score.

    At epsilon=1.0, expected noise magnitude is ~±2 points on a 100-point
    scale (Section 6.5).

    Args:
        true_value: The actual composite score.
        sensitivity: Max score change from one rating (default 5.0).
        epsilon: Privacy budget (default 1.0).
        output_range: Clamp output to this range.

    Returns:
        Noised composite score, clamped to output_range.
    """
    noise = laplace_noise(sensitivity, epsilon)
    noised = true_value + noise
    return max(output_range[0], min(output_range[1], noised))


def dp_response(
    true_value: float,
    agent_seed: Optional[int] = None,
    sensitivity: float = 5.0,
    epsilon: float = 1.0,
) -> float:
    """Generate a DP-noised response with optional per-agent correlated noise.

    Per-agent correlated noise (Section 7.5 defense 1): using a seed
    derived from the querying agent's ID ensures repeated queries from
    the same agent get correlated noise, limiting averaging attacks.

    Args:
        true_value: The actual score.
        agent_seed: Hash-derived seed for per-agent noise correlation.
        sensitivity: Max score change from one rating.
        epsilon: Privacy parameter.

    Returns:
        Noised score.
    """
    if agent_seed is not None:
        old_state = random.getstate()
        random.seed(agent_seed)
        result = add_dp_noise(true_value, sensitivity, epsilon)
        random.setstate(old_state)
        return result
    return add_dp_noise(true_value, sensitivity, epsilon)
