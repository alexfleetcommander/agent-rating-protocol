"""Signal composition algebra for ARP v2.

Implements Section 3 of the ARP v2 whitepaper:
- Five composition operations (weighted linear, confidence-adjusted,
  threshold gates, diminishing returns, penalty floors)
- Canonical operation order (gates -> transform -> confidence -> combine -> penalty)
- Weight profiles with standard and custom configurations
- Composite signal generation with metadata
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple


# Sentinel for disqualified composites
DISQUALIFIED = "DISQUALIFIED"


@dataclass
class Signal:
    """A structured trust-relevant data object about an agent (Section 2).

    Signals are the atomic inputs to signal composition.
    """

    signal_type: str  # e.g. "rating_dimension", "provenance", "behavioral"
    signal_id: str  # e.g. "arp:reliability:weighted_mean"
    value: float
    confidence: float = 1.0
    source: str = ""
    window: str = "365d"
    sample_size: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "signal_id": self.signal_id,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "window": self.window,
            "sample_size": self.sample_size,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Signal":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ProfileInput:
    """A single input specification within a weight profile."""

    signal_id: str
    weight: float
    operation: str = "linear"  # linear, confidence_adjusted, diminishing_returns
    k: float = 100.0  # diminishing returns steepness parameter
    weight_bounds: Optional[Dict[str, float]] = None  # {"min": 0.15, "max": 0.35}

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "signal_id": self.signal_id,
            "weight": self.weight,
            "operation": self.operation,
        }
        if self.operation == "diminishing_returns":
            d["k"] = self.k
        if self.weight_bounds is not None:
            d["weight_bounds"] = self.weight_bounds
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProfileInput":
        return cls(
            signal_id=d["signal_id"],
            weight=d["weight"],
            operation=d.get("operation", "linear"),
            k=d.get("k", 100.0),
            weight_bounds=d.get("weight_bounds"),
        )


@dataclass
class Gate:
    """A threshold gate that disqualifies composites if not met."""

    signal_id: str
    threshold: float
    gate_type: str = "minimum"  # "minimum" or "maximum"

    def evaluate(self, value: float) -> bool:
        """Return True if the gate passes."""
        if self.gate_type == "minimum":
            return value >= self.threshold
        elif self.gate_type == "maximum":
            return value <= self.threshold
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "threshold": self.threshold,
            "gate_type": self.gate_type,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Gate":
        return cls(
            signal_id=d["signal_id"],
            threshold=d["threshold"],
            gate_type=d.get("gate_type", "minimum"),
        )


@dataclass
class PenaltyFloor:
    """A penalty floor that drags down composites for catastrophically low signals."""

    signal_id: str
    floor: float
    max_penalty: float

    def compute_penalty(self, raw_value: float) -> float:
        """Compute penalty amount. Returns 0 if above floor."""
        if raw_value >= self.floor:
            return 0.0
        return self.max_penalty * (self.floor - raw_value) / self.floor

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "floor": self.floor,
            "max_penalty": self.max_penalty,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PenaltyFloor":
        return cls(
            signal_id=d["signal_id"],
            floor=d["floor"],
            max_penalty=d["max_penalty"],
        )


@dataclass
class WeightProfile:
    """A named composition configuration (Section 3.4).

    Specifies which signals are composed, with what weights,
    for a particular domain or use case.
    """

    profile_id: str
    version: str = ""
    description: str = ""
    inputs: List[ProfileInput] = field(default_factory=list)
    gates: List[Gate] = field(default_factory=list)
    penalty_floors: List[PenaltyFloor] = field(default_factory=list)
    output_range: Tuple[float, float] = (0.0, 100.0)
    rotation_schedule: str = "quarterly"
    governance_approved: str = ""
    effective_until: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "description": self.description,
            "inputs": [inp.to_dict() for inp in self.inputs],
            "gates": [g.to_dict() for g in self.gates],
            "penalty_floors": [pf.to_dict() for pf in self.penalty_floors],
            "output_range": list(self.output_range),
            "rotation_schedule": self.rotation_schedule,
            "governance_approved": self.governance_approved,
            "effective_until": self.effective_until,
        }

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WeightProfile":
        out_range = d.get("output_range", [0, 100])
        return cls(
            profile_id=d["profile_id"],
            version=d.get("version", ""),
            description=d.get("description", ""),
            inputs=[ProfileInput.from_dict(i) for i in d.get("inputs", [])],
            gates=[Gate.from_dict(g) for g in d.get("gates", [])],
            penalty_floors=[
                PenaltyFloor.from_dict(pf) for pf in d.get("penalty_floors", [])
            ],
            output_range=(float(out_range[0]), float(out_range[1])),
            rotation_schedule=d.get("rotation_schedule", "quarterly"),
            governance_approved=d.get("governance_approved", ""),
            effective_until=d.get("effective_until", ""),
        )

    @classmethod
    def from_json(cls, s: str) -> "WeightProfile":
        return cls.from_dict(json.loads(s))


@dataclass
class CompositeSignal:
    """A composite signal produced by composition (Section 3.5)."""

    profile_id: str
    value: float
    confidence: float
    input_count: int
    weakest_input: Optional[Dict[str, Any]] = None
    gate_status: str = "all_passed"
    computed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    valid_until: str = ""
    computed_by: str = ""

    def __post_init__(self) -> None:
        if not self.valid_until:
            now = datetime.now(timezone.utc)
            self.valid_until = (now + timedelta(days=7)).isoformat()

    def is_valid(self) -> bool:
        """Check if the composite is still within its validity window."""
        try:
            until = datetime.fromisoformat(
                self.valid_until.replace("Z", "+00:00")
            )
            return datetime.now(timezone.utc) <= until
        except (ValueError, AttributeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_id": self.profile_id,
            "value": round(self.value, 2),
            "confidence": round(self.confidence, 4),
            "input_count": self.input_count,
            "gate_status": self.gate_status,
            "computed_at": self.computed_at,
            "valid_until": self.valid_until,
        }
        if self.weakest_input:
            d["weakest_input"] = self.weakest_input
        if self.computed_by:
            d["computed_by"] = self.computed_by
        return d


# ---------------------------------------------------------------------------
# Composition operations (Section 3.3)
# ---------------------------------------------------------------------------

def diminishing_returns_transform(value: float, k: float) -> float:
    """Operation 4: Apply diminishing returns curve.

    transformed = 100 * (1 - e^(-value/k))

    Args:
        value: Raw signal value.
        k: Steepness parameter (profile-specific).

    Returns:
        Transformed value in [0, 100).
    """
    if k <= 0:
        raise ValueError("k must be positive")
    return 100.0 * (1.0 - math.exp(-value / k))


def compose(
    signals: Sequence[Signal],
    profile: WeightProfile,
    computed_by: str = "",
    validity_days: int = 7,
) -> CompositeSignal:
    """Compose signals into a composite using a weight profile.

    Applies the five operations in canonical order (Section 3.3):
    1. Gates (on raw values) — disqualify if any gate fails
    2. Diminishing returns transform — for signals that specify it
    3. Confidence adjustment — down-weight low-confidence signals
    4. Weighted linear combination — produce raw composite
    5. Penalty floors (on raw values) — apply penalties

    Args:
        signals: Input signals to compose.
        profile: The weight profile to use.
        computed_by: DID of the computing oracle.
        validity_days: How many days the composite is valid.

    Returns:
        CompositeSignal with the result. If disqualified, value=-1
        and gate_status indicates failure.
    """
    # Build signal lookup by signal_id
    sig_map: Dict[str, Signal] = {s.signal_id: s for s in signals}

    # --- Step 1: Gates (Operation 3) on raw values ---
    failed_gates: List[str] = []
    for gate in profile.gates:
        sig = sig_map.get(gate.signal_id)
        if sig is None:
            failed_gates.append(f"{gate.signal_id}: missing signal")
            continue
        if not gate.evaluate(sig.value):
            failed_gates.append(
                f"{gate.signal_id}: {sig.value} fails "
                f"{gate.gate_type} threshold {gate.threshold}"
            )

    if failed_gates:
        now = datetime.now(timezone.utc)
        return CompositeSignal(
            profile_id=profile.profile_id,
            value=-1.0,
            confidence=0.0,
            input_count=len(signals),
            gate_status=f"failed: {'; '.join(failed_gates)}",
            computed_at=now.isoformat(),
            valid_until=(now + timedelta(days=validity_days)).isoformat(),
            computed_by=computed_by,
        )

    # --- Step 2: Diminishing returns transform (Operation 4) ---
    transformed: Dict[str, float] = {}
    for inp in profile.inputs:
        sig = sig_map.get(inp.signal_id)
        if sig is None:
            continue
        if inp.operation == "diminishing_returns":
            transformed[inp.signal_id] = diminishing_returns_transform(
                sig.value, inp.k
            )
        else:
            transformed[inp.signal_id] = sig.value

    # --- Step 3 & 4: Confidence-adjusted weighted combination ---
    weighted_sum = 0.0
    weight_sum = 0.0
    weakest_input = None
    weakest_confidence = float("inf")
    input_count = 0

    for inp in profile.inputs:
        sig = sig_map.get(inp.signal_id)
        if sig is None:
            continue
        input_count += 1

        val = transformed.get(inp.signal_id, sig.value)

        if inp.operation == "confidence_adjusted":
            # Operation 2: weight by confidence
            w = inp.weight * sig.confidence
        else:
            # Operation 1: plain linear weight
            w = inp.weight

        weighted_sum += w * val
        weight_sum += w

        if sig.confidence < weakest_confidence:
            weakest_confidence = sig.confidence
            weakest_input = {
                "signal_id": inp.signal_id,
                "confidence": sig.confidence,
            }

    if weight_sum == 0:
        raw_composite = 0.0
    else:
        raw_composite = weighted_sum / weight_sum

    # --- Step 5: Penalty floors (Operation 5) on raw signal values ---
    total_penalty = 0.0
    for pf in profile.penalty_floors:
        sig = sig_map.get(pf.signal_id)
        if sig is None:
            continue
        total_penalty += pf.compute_penalty(sig.value)

    final = max(profile.output_range[0], raw_composite - total_penalty)
    final = min(profile.output_range[1], final)

    # Compute composite confidence as weighted average of input confidences
    conf_sum = 0.0
    conf_weight = 0.0
    for inp in profile.inputs:
        sig = sig_map.get(inp.signal_id)
        if sig is None:
            continue
        conf_sum += inp.weight * sig.confidence
        conf_weight += inp.weight
    composite_confidence = conf_sum / conf_weight if conf_weight > 0 else 0.0

    now = datetime.now(timezone.utc)
    return CompositeSignal(
        profile_id=profile.profile_id,
        value=final,
        confidence=composite_confidence,
        input_count=input_count,
        weakest_input=weakest_input,
        gate_status="all_passed",
        computed_at=now.isoformat(),
        valid_until=(now + timedelta(days=validity_days)).isoformat(),
        computed_by=computed_by,
    )


# ---------------------------------------------------------------------------
# Standard weight profiles (Section 3.4)
# ---------------------------------------------------------------------------

def _standard_gates() -> List[Gate]:
    """Default gates: minimum 5 ratings, minimum 7 days age."""
    return [
        Gate(signal_id="arp:total_ratings_received", threshold=5, gate_type="minimum"),
        Gate(signal_id="coc:operational_age_days", threshold=7, gate_type="minimum"),
    ]


def _standard_penalty_floors() -> List[PenaltyFloor]:
    return [
        PenaltyFloor(
            signal_id="arp:reliability:weighted_mean", floor=30, max_penalty=25
        ),
    ]


GENERAL_PURPOSE = WeightProfile(
    profile_id="urn:absupport:arp:v2:profile:general-purpose",
    version="2026-Q1",
    description="General-purpose agent trust composite",
    inputs=[
        ProfileInput("arp:reliability:weighted_mean", 0.25, "confidence_adjusted"),
        ProfileInput("arp:accuracy:weighted_mean", 0.25, "confidence_adjusted"),
        ProfileInput("arp:latency:weighted_mean", 0.10, "confidence_adjusted"),
        ProfileInput("arp:protocol_compliance:weighted_mean", 0.15, "confidence_adjusted"),
        ProfileInput("arp:cost_efficiency:weighted_mean", 0.10, "confidence_adjusted"),
        ProfileInput("coc:operational_age_days", 0.10, "diminishing_returns", k=365),
        ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
    ],
    gates=_standard_gates(),
    penalty_floors=_standard_penalty_floors(),
    rotation_schedule="quarterly",
)

HIGH_RELIABILITY = WeightProfile(
    profile_id="urn:absupport:arp:v2:profile:high-reliability",
    version="2026-Q1",
    description="High-reliability for infrastructure and payments",
    inputs=[
        ProfileInput("arp:reliability:weighted_mean", 0.40, "confidence_adjusted"),
        ProfileInput("arp:accuracy:weighted_mean", 0.25, "confidence_adjusted"),
        ProfileInput("arp:latency:weighted_mean", 0.05, "confidence_adjusted"),
        ProfileInput("arp:protocol_compliance:weighted_mean", 0.10, "confidence_adjusted"),
        ProfileInput("arp:cost_efficiency:weighted_mean", 0.05, "confidence_adjusted"),
        ProfileInput("coc:operational_age_days", 0.10, "diminishing_returns", k=365),
        ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
    ],
    gates=_standard_gates(),
    penalty_floors=[
        PenaltyFloor("arp:reliability:weighted_mean", floor=50, max_penalty=30),
    ],
    rotation_schedule="quarterly",
)

FAST_TURNAROUND = WeightProfile(
    profile_id="urn:absupport:arp:v2:profile:fast-turnaround",
    version="2026-Q1",
    description="Fast turnaround for content and translation",
    inputs=[
        ProfileInput("arp:reliability:weighted_mean", 0.15, "confidence_adjusted"),
        ProfileInput("arp:accuracy:weighted_mean", 0.25, "confidence_adjusted"),
        ProfileInput("arp:latency:weighted_mean", 0.30, "confidence_adjusted"),
        ProfileInput("arp:protocol_compliance:weighted_mean", 0.10, "confidence_adjusted"),
        ProfileInput("arp:cost_efficiency:weighted_mean", 0.05, "confidence_adjusted"),
        ProfileInput("coc:operational_age_days", 0.10, "diminishing_returns", k=365),
        ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
    ],
    gates=_standard_gates(),
    penalty_floors=_standard_penalty_floors(),
    rotation_schedule="quarterly",
)

COMPLIANCE_FIRST = WeightProfile(
    profile_id="urn:absupport:arp:v2:profile:compliance-first",
    version="2026-Q1",
    description="Compliance-first for regulated industries",
    inputs=[
        ProfileInput("arp:reliability:weighted_mean", 0.15, "confidence_adjusted"),
        ProfileInput("arp:accuracy:weighted_mean", 0.25, "confidence_adjusted"),
        ProfileInput("arp:latency:weighted_mean", 0.05, "confidence_adjusted"),
        ProfileInput("arp:protocol_compliance:weighted_mean", 0.35, "confidence_adjusted"),
        ProfileInput("arp:cost_efficiency:weighted_mean", 0.05, "confidence_adjusted"),
        ProfileInput("coc:operational_age_days", 0.10, "diminishing_returns", k=365),
        ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
    ],
    gates=_standard_gates(),
    penalty_floors=[
        PenaltyFloor("arp:protocol_compliance:weighted_mean", floor=50, max_penalty=30),
    ],
    rotation_schedule="quarterly",
)

COST_OPTIMIZED = WeightProfile(
    profile_id="urn:absupport:arp:v2:profile:cost-optimized",
    version="2026-Q1",
    description="Cost-optimized for bulk processing",
    inputs=[
        ProfileInput("arp:reliability:weighted_mean", 0.25, "confidence_adjusted"),
        ProfileInput("arp:accuracy:weighted_mean", 0.15, "confidence_adjusted"),
        ProfileInput("arp:latency:weighted_mean", 0.10, "confidence_adjusted"),
        ProfileInput("arp:protocol_compliance:weighted_mean", 0.10, "confidence_adjusted"),
        ProfileInput("arp:cost_efficiency:weighted_mean", 0.30, "confidence_adjusted"),
        ProfileInput("coc:operational_age_days", 0.05, "diminishing_returns", k=365),
        ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
    ],
    gates=_standard_gates(),
    penalty_floors=_standard_penalty_floors(),
    rotation_schedule="quarterly",
)

STANDARD_PROFILES: Dict[str, WeightProfile] = {
    "general-purpose": GENERAL_PURPOSE,
    "high-reliability": HIGH_RELIABILITY,
    "fast-turnaround": FAST_TURNAROUND,
    "compliance-first": COMPLIANCE_FIRST,
    "cost-optimized": COST_OPTIMIZED,
}


def get_profile(name: str) -> WeightProfile:
    """Get a standard profile by short name.

    Args:
        name: Profile short name (e.g. "general-purpose").

    Returns:
        The WeightProfile.

    Raises:
        KeyError: If name is not a standard profile.
    """
    if name not in STANDARD_PROFILES:
        raise KeyError(
            f"Unknown profile '{name}'. "
            f"Available: {list(STANDARD_PROFILES.keys())}"
        )
    return STANDARD_PROFILES[name]
