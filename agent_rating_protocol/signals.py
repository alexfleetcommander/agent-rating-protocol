"""Signal verification for ARP v2.

Implements Section 5 of the ARP v2 whitepaper:
- Hash-chain verification (basic level)
- Merkle proof verification (standard level)
- ZKP threshold verification (placeholder for future)
- Signal tier classification (public, queryable, private)
"""

import enum
import hashlib
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Signal tiers (Section 6.2)
# ---------------------------------------------------------------------------

class SignalTier(enum.Enum):
    """Visibility classification for signals."""

    PUBLIC = "public"  # Freely queryable
    QUERYABLE = "queryable"  # Rate-limited access
    PRIVATE = "private"  # Internal only

    def __str__(self) -> str:
        return self.value


# Default tier assignments (Section 6.2 table)
DEFAULT_TIER_MAP: Dict[str, SignalTier] = {
    "operational_age": SignalTier.PUBLIC,
    "total_interactions": SignalTier.PUBLIC,
    "tier_level": SignalTier.PUBLIC,
    "composite_score": SignalTier.QUERYABLE,
    "dimension_averages": SignalTier.QUERYABLE,
    "rating_confidence": SignalTier.QUERYABLE,
    "calibration_scores": SignalTier.PRIVATE,
    "collusion_flags": SignalTier.PRIVATE,
    "shadow_metrics": SignalTier.PRIVATE,
    "rotation_parameters": SignalTier.PRIVATE,
}


class VerificationLevel(enum.Enum):
    """Verification levels with explicit security properties (Section 5.5)."""

    BASIC = "basic"  # Hash-chain: individual ratings genuine + timestamped
    STANDARD = "standard"  # Merkle proof: aggregates from genuine ratings
    PRIVACY_PRESERVING = "privacy_preserving"  # ZKP: threshold without value


# ---------------------------------------------------------------------------
# Hash-chain verification (Section 5.2)
# ---------------------------------------------------------------------------

@dataclass
class HashChainVerification:
    """Result of hash-chain verification for a single rating."""

    rating_id: str
    exists: bool
    hash_valid: bool
    timestamp_verified: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "rating_id": self.rating_id,
            "exists": self.exists,
            "hash_valid": self.hash_valid,
            "timestamp_verified": self.timestamp_verified,
            "level": VerificationLevel.BASIC.value,
        }
        if self.error:
            d["error"] = self.error
        return d


def verify_hash_chain(
    record_hash: str,
    computed_hash: str,
    rating_id: str = "",
) -> HashChainVerification:
    """Verify a rating record's hash integrity (Section 5.2).

    Args:
        record_hash: The stored hash from the rating record.
        computed_hash: The freshly computed hash.
        rating_id: Optional rating ID for the result.

    Returns:
        HashChainVerification result.
    """
    if not record_hash or not computed_hash:
        return HashChainVerification(
            rating_id=rating_id,
            exists=False,
            hash_valid=False,
            error="Missing hash data",
        )

    return HashChainVerification(
        rating_id=rating_id,
        exists=True,
        hash_valid=(record_hash == computed_hash),
    )


# ---------------------------------------------------------------------------
# Merkle proof verification (Section 5.3)
# ---------------------------------------------------------------------------

@dataclass
class MerkleProof:
    """A Merkle proof for a single leaf in a Merkle tree."""

    leaf_hash: str
    proof_hashes: List[Tuple[str, str]]  # List of (hash, side) tuples
    root_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leaf_hash": self.leaf_hash,
            "proof_hashes": [
                {"hash": h, "side": s} for h, s in self.proof_hashes
            ],
            "root_hash": self.root_hash,
        }


class MerkleTree:
    """A binary Merkle tree for rating hash verification.

    Used by reputation oracles to provide verifiable evidence that
    a PRB's aggregate scores derive from genuine ratings.
    """

    def __init__(self, leaves: Sequence[str]) -> None:
        """Build a Merkle tree from hex-encoded leaf hashes.

        Args:
            leaves: List of hex-encoded SHA-256 hashes (rating record hashes).
        """
        if not leaves:
            self._root = hashlib.sha256(b"empty").hexdigest()
            self._layers: List[List[str]] = [[self._root]]
            return

        # Normalize to list
        leaf_list = list(leaves)
        self._layers = [leaf_list[:]]
        self._build(leaf_list)

    def _build(self, leaves: List[str]) -> None:
        """Build tree layers from leaves to root."""
        current = leaves[:]
        while len(current) > 1:
            next_layer: List[str] = []
            for i in range(0, len(current), 2):
                left = bytes.fromhex(current[i])
                right_idx = i + 1 if i + 1 < len(current) else i
                right = bytes.fromhex(current[right_idx])
                parent = hashlib.sha256(left + right).hexdigest()
                next_layer.append(parent)
            self._layers.append(next_layer)
            current = next_layer
        self._root = current[0]

    @property
    def root(self) -> str:
        """The Merkle root hash."""
        return self._root

    @property
    def leaf_count(self) -> int:
        return len(self._layers[0])

    def get_proof(self, leaf_index: int) -> MerkleProof:
        """Generate a Merkle proof for a leaf at the given index.

        Args:
            leaf_index: Index of the leaf in the original list.

        Returns:
            MerkleProof containing the sibling hashes needed for verification.

        Raises:
            IndexError: If leaf_index is out of range.
        """
        if leaf_index < 0 or leaf_index >= len(self._layers[0]):
            raise IndexError(
                f"Leaf index {leaf_index} out of range [0, {len(self._layers[0])})"
            )

        proof_hashes: List[Tuple[str, str]] = []
        idx = leaf_index

        for layer in self._layers[:-1]:  # Skip root layer
            if idx % 2 == 0:
                sibling_idx = idx + 1 if idx + 1 < len(layer) else idx
                proof_hashes.append((layer[sibling_idx], "right"))
            else:
                proof_hashes.append((layer[idx - 1], "left"))
            idx //= 2

        return MerkleProof(
            leaf_hash=self._layers[0][leaf_index],
            proof_hashes=proof_hashes,
            root_hash=self._root,
        )


def verify_merkle_proof(proof: MerkleProof) -> bool:
    """Verify a Merkle proof against the claimed root.

    Args:
        proof: The MerkleProof to verify.

    Returns:
        True if the proof is valid.
    """
    current = bytes.fromhex(proof.leaf_hash)

    for sibling_hex, side in proof.proof_hashes:
        sibling = bytes.fromhex(sibling_hex)
        if side == "left":
            current = hashlib.sha256(sibling + current).digest()
        else:
            current = hashlib.sha256(current + sibling).digest()

    return current.hex() == proof.root_hash


@dataclass
class MerkleVerificationResult:
    """Result of Merkle proof verification for a PRB."""

    root_hash_matches: bool
    proofs_verified: int
    proofs_failed: int
    sample_size: int
    total_ratings: int
    level: str = VerificationLevel.STANDARD.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_hash_matches": self.root_hash_matches,
            "proofs_verified": self.proofs_verified,
            "proofs_failed": self.proofs_failed,
            "sample_size": self.sample_size,
            "total_ratings": self.total_ratings,
            "level": self.level,
        }


def verify_prb_merkle(
    claimed_root: str,
    rating_hashes: List[str],
    sample_size: int = 50,
) -> MerkleVerificationResult:
    """Verify a PRB's Merkle root against its underlying ratings.

    Supports sampled verification for large rating sets (Section 5.3).

    Args:
        claimed_root: The ratingsRootHash from the PRB.
        rating_hashes: All rating hashes underlying the bundle.
        sample_size: Number of random proofs to verify (0 = all).

    Returns:
        MerkleVerificationResult.
    """
    if not rating_hashes:
        return MerkleVerificationResult(
            root_hash_matches=False,
            proofs_verified=0,
            proofs_failed=0,
            sample_size=0,
            total_ratings=0,
        )

    tree = MerkleTree(rating_hashes)
    root_matches = tree.root == claimed_root

    total = len(rating_hashes)
    if sample_size <= 0 or sample_size >= total:
        indices = list(range(total))
    else:
        indices = random.sample(range(total), sample_size)

    verified = 0
    failed = 0
    for idx in indices:
        proof = tree.get_proof(idx)
        if verify_merkle_proof(proof):
            verified += 1
        else:
            failed += 1

    return MerkleVerificationResult(
        root_hash_matches=root_matches,
        proofs_verified=verified,
        proofs_failed=failed,
        sample_size=len(indices),
        total_ratings=total,
    )


# ---------------------------------------------------------------------------
# ZKP threshold verification — placeholder (Section 5.4)
# ---------------------------------------------------------------------------

@dataclass
class ZKPThresholdProof:
    """Placeholder for zero-knowledge threshold proof.

    ARP v2 specifies the protocol but the cryptographic implementation
    requires a ZKP library (Groth16, PLONK, or STARKs). This dataclass
    defines the interface; actual proof generation/verification is
    deferred to a future release.
    """

    threshold_composite: float
    threshold_dimension: Optional[float] = None
    threshold_dimension_name: Optional[str] = None
    ratings_root_hash: str = ""
    valid_until: str = ""
    proof_system: str = "placeholder"
    proof_value: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "public_inputs": {
                "threshold_composite": self.threshold_composite,
                "ratingsRootHash": self.ratings_root_hash,
            },
            "valid_until": self.valid_until,
            "proof_system": self.proof_system,
            "proof_value": self.proof_value,
            "level": VerificationLevel.PRIVACY_PRESERVING.value,
        }
        if self.threshold_dimension is not None:
            d["public_inputs"]["threshold_dimension"] = self.threshold_dimension
            d["public_inputs"]["dimension_name"] = self.threshold_dimension_name
        return d


def create_zkp_threshold_proof(
    actual_composite: float,
    threshold_composite: float,
    ratings_root_hash: str = "",
    actual_dimension: Optional[float] = None,
    threshold_dimension: Optional[float] = None,
    dimension_name: Optional[str] = None,
) -> ZKPThresholdProof:
    """Create a ZKP threshold proof (placeholder implementation).

    In production, this would use a real ZKP system (Groth16/PLONK/STARKs).
    The placeholder validates thresholds but does not generate cryptographic proofs.

    Args:
        actual_composite: The agent's real composite score.
        threshold_composite: The threshold to prove exceedance of.
        ratings_root_hash: Merkle root linking to rating evidence.
        actual_dimension: Optional real dimension score.
        threshold_dimension: Optional dimension threshold.
        dimension_name: Name of the threshold dimension.

    Returns:
        ZKPThresholdProof. proof_system is "placeholder" to indicate
        this is not a real ZKP.

    Raises:
        ValueError: If actual scores don't meet thresholds.
    """
    if actual_composite < threshold_composite:
        raise ValueError(
            f"Composite {actual_composite} does not meet "
            f"threshold {threshold_composite}"
        )

    if (
        actual_dimension is not None
        and threshold_dimension is not None
        and actual_dimension < threshold_dimension
    ):
        raise ValueError(
            f"Dimension {dimension_name} score {actual_dimension} "
            f"does not meet threshold {threshold_dimension}"
        )

    return ZKPThresholdProof(
        threshold_composite=threshold_composite,
        threshold_dimension=threshold_dimension,
        threshold_dimension_name=dimension_name,
        ratings_root_hash=ratings_root_hash,
        valid_until="",  # Set by caller
        proof_system="placeholder",
        proof_value="PLACEHOLDER_NOT_CRYPTOGRAPHIC",
    )


def verify_zkp_threshold_proof(proof: ZKPThresholdProof) -> Dict[str, Any]:
    """Verify a ZKP threshold proof (placeholder).

    In production, this would cryptographically verify the proof.
    The placeholder returns a warning that it cannot verify.

    Args:
        proof: The proof to verify.

    Returns:
        Dict with verification result and warnings.
    """
    if proof.proof_system == "placeholder":
        return {
            "verified": False,
            "level": VerificationLevel.PRIVACY_PRESERVING.value,
            "warning": (
                "ZKP verification not available — proof_system is 'placeholder'. "
                "Real ZKP verification requires Groth16, PLONK, or STARKs "
                "integration (see ARP v2 Section 5.4)."
            ),
            "thresholds": proof.to_dict()["public_inputs"],
        }

    # Future: real ZKP verification would go here
    return {
        "verified": False,
        "level": VerificationLevel.PRIVACY_PRESERVING.value,
        "error": f"Unsupported proof system: {proof.proof_system}",
    }
