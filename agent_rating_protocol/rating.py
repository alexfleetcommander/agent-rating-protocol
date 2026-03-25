"""Rating record schema and core data structures.

Implements Section 4.1 of the Agent Rating Protocol whitepaper:
- AgentIdentity with agent_id and optional identity_proof
- RatingRecord with 5 dimensions (1-100 scale)
- Verification levels (verified, unilateral, self_reported)
- JSON serialization / deserialization
- SHA-256 record_hash computation (deterministic, see canonicalization note)
"""

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# The five rating dimensions (Section 4.2)
DIMENSIONS = (
    "reliability",
    "accuracy",
    "latency",
    "protocol_compliance",
    "cost_efficiency",
)

# Score buckets for display (Section 4.2)
SCORE_BUCKETS = {
    (1, 20): "poor",
    (21, 40): "below_average",
    (41, 60): "average",
    (61, 80): "good",
    (81, 100): "excellent",
}

# Valid verification levels (Section 4.8)
VERIFICATION_LEVELS = ("verified", "unilateral", "self_reported")


def score_bucket(score: int) -> str:
    """Return the human-readable bucket for a 1-100 score."""
    for (lo, hi), label in SCORE_BUCKETS.items():
        if lo <= score <= hi:
            return label
    raise ValueError(f"Score {score} out of range 1-100")


@dataclass
class AgentIdentity:
    """Agent identity with optional identity proof (Section 4.1).

    Supports the whitepaper's nested rater/ratee schema:
    {"agent_id": "<DID or URI>", "identity_proof": "<reference>"}
    """

    agent_id: str
    identity_proof: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"agent_id": self.agent_id}
        if self.identity_proof is not None:
            d["identity_proof"] = self.identity_proof
        return d

    @classmethod
    def from_dict(cls, d: Any) -> "AgentIdentity":
        """Create from dict or plain string (backward compat)."""
        if isinstance(d, str):
            return cls(agent_id=d)
        if isinstance(d, AgentIdentity):
            return d
        return cls(
            agent_id=d.get("agent_id", ""),
            identity_proof=d.get("identity_proof"),
        )


@dataclass
class InteractionEvidence:
    """Evidence from the interaction being rated (Section 4.1)."""

    task_type: str = ""
    outcome_hash: str = ""
    duration_ms: int = 0
    was_completed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "InteractionEvidence":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class RatingRecord:
    """A single rating record per Section 4.1 schema.

    Each rating captures one agent's assessment of another after an interaction,
    across five independent dimensions scored 1-100.
    """

    # Core identifiers
    rater_id: str
    ratee_id: str
    interaction_id: str = ""

    # Identity proofs (Section 4.1 nested agent objects)
    rater_identity_proof: Optional[str] = None
    ratee_identity_proof: Optional[str] = None

    # The five dimensions (1-100 each)
    reliability: int = 50
    accuracy: int = 50
    latency: int = 50
    protocol_compliance: int = 50
    cost_efficiency: int = 50

    # Interaction evidence
    evidence: InteractionEvidence = field(default_factory=InteractionEvidence)

    # Interaction verification (Section 4.8)
    verification_level: str = "verified"

    # Metadata
    rater_chain_length: Optional[int] = None
    rater_chain_age_days: int = 0
    rater_total_ratings_given: int = 0
    bilateral_blind: bool = True

    # Auto-generated fields
    rating_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    version: int = 1
    record_hash: str = ""

    def __post_init__(self) -> None:
        self._validate()
        if not self.record_hash:
            self.record_hash = self.compute_hash()

    def _validate(self) -> None:
        """Validate all dimension scores are in 1-100 range."""
        for dim in DIMENSIONS:
            val = getattr(self, dim)
            if not isinstance(val, int) or not (1 <= val <= 100):
                raise ValueError(
                    f"Dimension '{dim}' must be an integer 1-100, got {val!r}"
                )
        if not self.rater_id:
            raise ValueError("rater_id is required")
        if not self.ratee_id:
            raise ValueError("ratee_id is required")
        if self.verification_level not in VERIFICATION_LEVELS:
            raise ValueError(
                f"verification_level must be one of {VERIFICATION_LEVELS}, "
                f"got {self.verification_level!r}"
            )

    @property
    def rater_identity(self) -> AgentIdentity:
        """Return the rater as an AgentIdentity object."""
        return AgentIdentity(
            agent_id=self.rater_id,
            identity_proof=self.rater_identity_proof,
        )

    @property
    def ratee_identity(self) -> AgentIdentity:
        """Return the ratee as an AgentIdentity object."""
        return AgentIdentity(
            agent_id=self.ratee_id,
            identity_proof=self.ratee_identity_proof,
        )

    @property
    def dimensions(self) -> Dict[str, int]:
        """Return all five dimension scores as a dict."""
        return {dim: getattr(self, dim) for dim in DIMENSIONS}

    def compute_hash(self) -> str:
        """Compute SHA-256 hash over canonical record fields.

        Canonicalization: Uses json.dumps(sort_keys=True, separators=(",",":"))
        for deterministic output. The whitepaper specifies JCS (RFC 8785).
        This implementation produces equivalent results for the data types
        used here (strings, integers, booleans, nested dicts) because:
        - sort_keys=True provides deterministic key ordering
        - Compact separators eliminate whitespace variation
        - Python's json module serializes integers identically to JCS

        Deviation from JCS: JCS specifies IEEE 754 number serialization.
        Python's json module serializes integers identically, but floating
        point values may differ. This protocol uses only integers and strings,
        so the deviation has no practical impact. For strict RFC 8785
        compliance, substitute a conformant JCS library.

        v0.2.0: Includes identity_proof, verification_level, and
        rater_chain_length when set to non-default values. Records created
        without these fields produce identical hashes to v0.1.0.
        """
        canonical: Dict[str, Any] = {
            "version": self.version,
            "rating_id": self.rating_id,
            "timestamp": self.timestamp,
            "interaction_id": self.interaction_id,
            "rater_id": self.rater_id,
            "ratee_id": self.ratee_id,
            "dimensions": {dim: getattr(self, dim) for dim in DIMENSIONS},
            "evidence": self.evidence.to_dict(),
        }
        # v0.2.0 fields — only included when non-default to preserve
        # backward-compatible hashes for records without these fields
        if self.rater_identity_proof is not None:
            canonical["rater_identity_proof"] = self.rater_identity_proof
        if self.ratee_identity_proof is not None:
            canonical["ratee_identity_proof"] = self.ratee_identity_proof
        if self.verification_level != "verified":
            canonical["verification_level"] = self.verification_level
        if self.rater_chain_length is not None:
            canonical["rater_chain_length"] = self.rater_chain_length

        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict matching whitepaper schema."""
        rater_dict: Dict[str, Any] = {"agent_id": self.rater_id}
        if self.rater_identity_proof is not None:
            rater_dict["identity_proof"] = self.rater_identity_proof

        ratee_dict: Dict[str, Any] = {"agent_id": self.ratee_id}
        if self.ratee_identity_proof is not None:
            ratee_dict["identity_proof"] = self.ratee_identity_proof

        metadata: Dict[str, Any] = {
            "rater_chain_age_days": self.rater_chain_age_days,
            "rater_total_ratings_given": self.rater_total_ratings_given,
            "bilateral_blind": self.bilateral_blind,
        }
        if self.rater_chain_length is not None:
            metadata["rater_chain_length"] = self.rater_chain_length

        return {
            "version": self.version,
            "rating_id": self.rating_id,
            "timestamp": self.timestamp,
            "interaction_id": self.interaction_id,
            "rater": rater_dict,
            "ratee": ratee_dict,
            "dimensions": self.dimensions,
            "interaction_evidence": self.evidence.to_dict(),
            "verification_level": self.verification_level,
            "metadata": metadata,
            "record_hash": self.record_hash,
        }

    def to_json(self, **kwargs: Any) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RatingRecord":
        """Deserialize from a dict (as produced by to_dict)."""
        dims = d.get("dimensions", {})
        meta = d.get("metadata", {})
        evidence_data = d.get("interaction_evidence", {})
        rater_data = d.get("rater", {})
        ratee_data = d.get("ratee", {})

        record = cls(
            rater_id=(
                rater_data.get("agent_id", "")
                if isinstance(rater_data, dict)
                else str(rater_data)
            ),
            ratee_id=(
                ratee_data.get("agent_id", "")
                if isinstance(ratee_data, dict)
                else str(ratee_data)
            ),
            interaction_id=d.get("interaction_id", ""),
            rater_identity_proof=(
                rater_data.get("identity_proof")
                if isinstance(rater_data, dict)
                else None
            ),
            ratee_identity_proof=(
                ratee_data.get("identity_proof")
                if isinstance(ratee_data, dict)
                else None
            ),
            reliability=dims.get("reliability", 50),
            accuracy=dims.get("accuracy", 50),
            latency=dims.get("latency", 50),
            protocol_compliance=dims.get("protocol_compliance", 50),
            cost_efficiency=dims.get("cost_efficiency", 50),
            evidence=InteractionEvidence.from_dict(evidence_data),
            verification_level=d.get("verification_level", "verified"),
            rater_chain_length=meta.get("rater_chain_length"),
            rater_chain_age_days=meta.get("rater_chain_age_days", 0),
            rater_total_ratings_given=meta.get("rater_total_ratings_given", 0),
            bilateral_blind=meta.get("bilateral_blind", True),
            rating_id=d.get("rating_id", str(uuid.uuid4())),
            timestamp=d.get("timestamp", ""),
            version=d.get("version", 1),
            record_hash=d.get("record_hash", ""),
        )
        return record

    def verify_hash(self) -> bool:
        """Verify that the stored record_hash matches the computed hash."""
        return self.record_hash == self.compute_hash()

    def __repr__(self) -> str:
        return (
            f"RatingRecord(rater={self.rater_id!r}, ratee={self.ratee_id!r}, "
            f"dims={self.dimensions}, hash={self.record_hash[:12]}...)"
        )
