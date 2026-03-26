"""Portable Reputation Bundles (PRBs) for ARP v2.

Implements Section 4 of the ARP v2 whitepaper:
- PRB generation in W3C Verifiable Credential format
- Multi-oracle attestation with divergence detection
- Trust discount model for cross-platform reputation transfer
- Bundle verification
"""

import hashlib
import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .composition import CompositeSignal


@dataclass
class DimensionSummary:
    """Per-dimension reputation statistics for a PRB."""

    mean: float
    stddev: float
    confidence: float
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean": round(self.mean, 1),
            "stddev": round(self.stddev, 1),
            "confidence": round(self.confidence, 4),
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DimensionSummary":
        return cls(
            mean=d["mean"],
            stddev=d["stddev"],
            confidence=d["confidence"],
            count=d["count"],
        )


@dataclass
class ProvenanceSummary:
    """CoC chain provenance data for a PRB."""

    coc_chain_age: int = 0
    coc_chain_length: int = 0
    last_anchor_timestamp: str = ""
    anchor_type: str = "dual_ots_tsa"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cocChainAge": self.coc_chain_age,
            "cocChainLength": self.coc_chain_length,
            "lastAnchorTimestamp": self.last_anchor_timestamp,
            "anchorType": self.anchor_type,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProvenanceSummary":
        return cls(
            coc_chain_age=d.get("cocChainAge", 0),
            coc_chain_length=d.get("cocChainLength", 0),
            last_anchor_timestamp=d.get("lastAnchorTimestamp", ""),
            anchor_type=d.get("anchorType", "dual_ots_tsa"),
        )


@dataclass
class BehavioralSummary:
    """Behavioral statistics for a PRB."""

    total_interactions: int = 0
    rating_participation_rate: float = 0.0
    dispute_rate: float = 0.0
    average_response_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "totalInteractions": self.total_interactions,
            "ratingParticipationRate": round(self.rating_participation_rate, 4),
            "disputeRate": round(self.dispute_rate, 4),
            "averageResponseTimeMs": self.average_response_time_ms,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BehavioralSummary":
        return cls(
            total_interactions=d.get("totalInteractions", 0),
            rating_participation_rate=d.get("ratingParticipationRate", 0.0),
            dispute_rate=d.get("disputeRate", 0.0),
            average_response_time_ms=d.get("averageResponseTimeMs", 0),
        )


@dataclass
class OracleAttestation:
    """A single oracle's attestation within a multi-oracle PRB."""

    oracle_id: str
    composite_value: float
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "oracle": self.oracle_id,
            "compositeValue": round(self.composite_value, 1),
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OracleAttestation":
        return cls(
            oracle_id=d["oracle"],
            composite_value=d["compositeValue"],
            signature=d.get("signature", ""),
        )


@dataclass
class PortableReputationBundle:
    """A W3C Verifiable Credential containing agent reputation (Section 4.2).

    The PRB is the unit of cross-platform reputation transfer.
    """

    # Issuer (reputation oracle) info
    issuer_id: str
    issuer_name: str = ""
    issuer_reliability: float = 0.0
    issuer_confidence: float = 0.0

    # Subject (rated agent) info
    subject_id: str = ""

    # Composite scores
    composite_scores: List[Dict[str, Any]] = field(default_factory=list)

    # Per-dimension summaries
    dimensions: Dict[str, DimensionSummary] = field(default_factory=dict)

    # Provenance and behavioral
    provenance: Optional[ProvenanceSummary] = None
    behavioral: Optional[BehavioralSummary] = None

    # Evidence chain
    ratings_root_hash: str = ""
    coc_chain_head_hash: str = ""
    verification_endpoint: str = ""

    # Multi-oracle attestation
    multi_oracle: Optional[Dict[str, Any]] = None

    # Validity
    valid_from: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    valid_until: str = ""

    # Proof
    proof_type: str = "DataIntegrityProof"
    proof_cryptosuite: str = "eddsa-jcs-2022"
    proof_value: str = ""

    def __post_init__(self) -> None:
        if not self.valid_until:
            now = datetime.now(timezone.utc)
            self.valid_until = (now + timedelta(days=30)).isoformat()

    def is_valid(self) -> bool:
        """Check if the PRB is within its validity window."""
        try:
            until = datetime.fromisoformat(
                self.valid_until.replace("Z", "+00:00")
            )
            return datetime.now(timezone.utc) <= until
        except (ValueError, AttributeError):
            return False

    def to_vc(self) -> Dict[str, Any]:
        """Serialize to W3C Verifiable Credential format (Section 4.2)."""
        vc: Dict[str, Any] = {
            "@context": [
                "https://www.w3.org/ns/credentials/v2",
                "https://absupport.ai/credentials/agent-reputation-bundle/v2",
            ],
            "type": ["VerifiableCredential", "AgentReputationBundle"],
            "issuer": {
                "id": self.issuer_id,
            },
            "validFrom": self.valid_from,
            "validUntil": self.valid_until,
            "credentialSubject": {
                "id": self.subject_id,
                "reputationSummary": {
                    "compositeScores": self.composite_scores,
                    "dimensions": {
                        dim: summary.to_dict()
                        for dim, summary in self.dimensions.items()
                    },
                },
                "evidenceChain": {
                    "ratingsRootHash": self.ratings_root_hash,
                    "cocChainHeadHash": self.coc_chain_head_hash,
                    "verificationEndpoint": self.verification_endpoint,
                },
            },
        }

        if self.issuer_name:
            vc["issuer"]["name"] = self.issuer_name
        if self.issuer_reliability > 0:
            vc["issuer"]["arp_reputation"] = {
                "reliability": round(self.issuer_reliability, 1),
                "confidence": round(self.issuer_confidence, 4),
            }

        if self.provenance:
            vc["credentialSubject"]["reputationSummary"]["provenance"] = (
                self.provenance.to_dict()
            )
        if self.behavioral:
            vc["credentialSubject"]["reputationSummary"]["behavioral"] = (
                self.behavioral.to_dict()
            )

        if self.multi_oracle:
            vc["credentialSubject"]["multiOracleAttestation"] = self.multi_oracle

        vc["proof"] = {
            "type": self.proof_type,
            "cryptosuite": self.proof_cryptosuite,
            "verificationMethod": f"{self.issuer_id}#key-1",
            "proofPurpose": "assertionMethod",
            "proofValue": self.proof_value,
        }

        return vc

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_vc(), **kwargs)

    @classmethod
    def from_vc(cls, vc: Dict[str, Any]) -> "PortableReputationBundle":
        """Deserialize from a W3C VC dict."""
        issuer = vc.get("issuer", {})
        subject = vc.get("credentialSubject", {})
        summary = subject.get("reputationSummary", {})
        evidence = subject.get("evidenceChain", {})
        proof = vc.get("proof", {})

        dims = {}
        for dim_name, dim_data in summary.get("dimensions", {}).items():
            dims[dim_name] = DimensionSummary.from_dict(dim_data)

        prov = None
        if "provenance" in summary:
            prov = ProvenanceSummary.from_dict(summary["provenance"])

        behav = None
        if "behavioral" in summary:
            behav = BehavioralSummary.from_dict(summary["behavioral"])

        arp_rep = issuer.get("arp_reputation", {})

        return cls(
            issuer_id=issuer.get("id", ""),
            issuer_name=issuer.get("name", ""),
            issuer_reliability=arp_rep.get("reliability", 0.0),
            issuer_confidence=arp_rep.get("confidence", 0.0),
            subject_id=subject.get("id", ""),
            composite_scores=summary.get("compositeScores", []),
            dimensions=dims,
            provenance=prov,
            behavioral=behav,
            ratings_root_hash=evidence.get("ratingsRootHash", ""),
            coc_chain_head_hash=evidence.get("cocChainHeadHash", ""),
            verification_endpoint=evidence.get("verificationEndpoint", ""),
            multi_oracle=subject.get("multiOracleAttestation"),
            valid_from=vc.get("validFrom", ""),
            valid_until=vc.get("validUntil", ""),
            proof_type=proof.get("type", "DataIntegrityProof"),
            proof_cryptosuite=proof.get("cryptosuite", "eddsa-jcs-2022"),
            proof_value=proof.get("proofValue", ""),
        )


# ---------------------------------------------------------------------------
# PRB generation helpers
# ---------------------------------------------------------------------------

def compute_ratings_root_hash(rating_hashes: List[str]) -> str:
    """Compute a Merkle root hash from a list of rating record hashes.

    Uses a simple binary Merkle tree. For an odd number of leaves,
    the last leaf is duplicated.

    Args:
        rating_hashes: List of hex-encoded SHA-256 hashes.

    Returns:
        Hex-encoded SHA-256 Merkle root.
    """
    if not rating_hashes:
        return hashlib.sha256(b"empty").hexdigest()

    # Build leaf layer
    layer = [bytes.fromhex(h) for h in rating_hashes]

    while len(layer) > 1:
        next_layer: List[bytes] = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1] if i + 1 < len(layer) else layer[i]
            combined = hashlib.sha256(left + right).digest()
            next_layer.append(combined)
        layer = next_layer

    return layer[0].hex()


def generate_prb(
    issuer_id: str,
    subject_id: str,
    composite: CompositeSignal,
    dimensions: Dict[str, DimensionSummary],
    rating_hashes: List[str],
    provenance: Optional[ProvenanceSummary] = None,
    behavioral: Optional[BehavioralSummary] = None,
    issuer_name: str = "",
    issuer_reliability: float = 0.0,
    issuer_confidence: float = 0.0,
    coc_chain_head_hash: str = "",
    verification_endpoint: str = "",
    validity_days: int = 30,
) -> PortableReputationBundle:
    """Generate a Portable Reputation Bundle from computed data.

    Args:
        issuer_id: DID of the issuing reputation oracle.
        subject_id: DID of the rated agent.
        composite: Pre-computed composite signal.
        dimensions: Per-dimension summaries.
        rating_hashes: List of rating record hashes for Merkle root.
        provenance: Optional CoC chain provenance.
        behavioral: Optional behavioral summary.
        issuer_name: Human-readable oracle name.
        issuer_reliability: Oracle's own ARP reliability score.
        issuer_confidence: Oracle's reputation confidence.
        coc_chain_head_hash: Hash of agent's latest CoC chain entry.
        verification_endpoint: URL for online bundle verification.
        validity_days: Bundle validity in days.

    Returns:
        A PortableReputationBundle.
    """
    now = datetime.now(timezone.utc)
    root_hash = compute_ratings_root_hash(rating_hashes)

    composite_entry = composite.to_dict()
    # Add extra PRB-specific fields
    composite_entry["ratingCount"] = composite.input_count
    composite_entry["windowDays"] = 365

    return PortableReputationBundle(
        issuer_id=issuer_id,
        issuer_name=issuer_name,
        issuer_reliability=issuer_reliability,
        issuer_confidence=issuer_confidence,
        subject_id=subject_id,
        composite_scores=[composite_entry],
        dimensions=dimensions,
        provenance=provenance,
        behavioral=behavioral,
        ratings_root_hash=root_hash,
        coc_chain_head_hash=coc_chain_head_hash,
        verification_endpoint=verification_endpoint,
        valid_from=now.isoformat(),
        valid_until=(now + timedelta(days=validity_days)).isoformat(),
    )


# ---------------------------------------------------------------------------
# Multi-oracle attestation (Section 4.3)
# ---------------------------------------------------------------------------

def multi_oracle_attestation(
    attestations: List[OracleAttestation],
    threshold: int = 3,
    max_divergence: float = 10.0,
) -> Dict[str, Any]:
    """Build a multi-oracle attestation block.

    Uses median consensus. Flags as disputed if divergence exceeds threshold.

    Args:
        attestations: List of oracle attestations.
        threshold: Minimum number of oracles required.
        max_divergence: Maximum allowed divergence before flagging.

    Returns:
        Dict suitable for inclusion in a PRB.

    Raises:
        ValueError: If fewer attestations than threshold.
    """
    if len(attestations) < threshold:
        raise ValueError(
            f"Need at least {threshold} attestations, got {len(attestations)}"
        )

    values = [a.composite_value for a in attestations]
    consensus = statistics.median(values)
    divergence = max(values) - min(values)

    status = "consensus"
    if divergence > max_divergence:
        status = "disputed"

    return {
        "threshold": threshold,
        "attestations": [a.to_dict() for a in attestations],
        "consensusValue": round(consensus, 1),
        "consensusMethod": "median",
        "maxDivergence": round(divergence, 1),
        "status": status,
    }


# ---------------------------------------------------------------------------
# Trust discount model (Section 4.5)
# ---------------------------------------------------------------------------

def trust_discount(
    imported_score: float,
    oracle_trust: float = 1.0,
    domain_overlap: float = 1.0,
    rating_volume_factor: float = 1.0,
    is_single_oracle: bool = False,
    is_bootstrap_period: bool = False,
) -> float:
    """Apply trust discount to an imported PRB score (Section 4.5).

    effective_score = imported_score * discount

    Args:
        imported_score: The composite score from the PRB.
        oracle_trust: Receiving platform's trust in the oracle (0-1).
        domain_overlap: How well the source domain matches target (0-1).
        rating_volume_factor: Factor based on rating count (0-1).
        is_single_oracle: If True, apply single-oracle discount.
        is_bootstrap_period: If True, use bootstrap-period discount.

    Returns:
        The discounted effective score.
    """
    discount = oracle_trust * domain_overlap * rating_volume_factor

    if is_single_oracle:
        if is_bootstrap_period:
            discount *= 0.7  # Bootstrap period: reduced penalty
        else:
            discount *= 0.5  # Steady state: stronger penalty

    return imported_score * min(1.0, max(0.0, discount))
