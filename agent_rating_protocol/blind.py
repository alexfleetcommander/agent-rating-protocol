"""Bilateral blind commit-reveal protocol.

Implements Section 2.4 of the Agent Rating System Design:
- Commit phase: SHA-256(rating_json || nonce) -> commitment_hash
- Reveal phase: verify rating + nonce against commitment
- Window-based reveal trigger
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


def generate_nonce(nbytes: int = 32) -> str:
    """Generate a cryptographically secure random nonce (hex-encoded)."""
    return os.urandom(nbytes).hex()


def commit(rating_dict: Dict[str, Any], nonce: str) -> str:
    """Create a commitment hash for a rating.

    commitment = SHA-256(canonical_json(rating) || nonce)

    Args:
        rating_dict: The rating record as a dict (from RatingRecord.to_dict()).
        nonce: A random nonce string.

    Returns:
        Hex-encoded SHA-256 commitment hash.
    """
    payload = json.dumps(rating_dict, sort_keys=True, separators=(",", ":"))
    combined = payload + nonce
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def reveal(
    rating_dict: Dict[str, Any], nonce: str, commitment: str
) -> bool:
    """Verify a rating against its commitment.

    Args:
        rating_dict: The revealed rating record as a dict.
        nonce: The nonce used during commitment.
        commitment: The commitment hash to verify against.

    Returns:
        True if the rating + nonce match the commitment.
    """
    computed = commit(rating_dict, nonce)
    # Constant-time comparison to prevent timing attacks
    return _constant_time_compare(computed, commitment)


def _constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode(), b.encode()):
        result |= x ^ y
    return result == 0


@dataclass
class BlindCommitment:
    """Represents one side of a bilateral blind exchange."""

    agent_id: str
    interaction_id: str
    commitment_hash: str
    committed_at: float = field(default_factory=time.time)
    revealed: bool = False
    rating_dict: Optional[Dict[str, Any]] = None
    nonce: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "agent_id": self.agent_id,
            "interaction_id": self.interaction_id,
            "commitment_hash": self.commitment_hash,
            "committed_at": self.committed_at,
            "revealed": self.revealed,
        }
        if self.revealed and self.rating_dict is not None:
            d["rating_dict"] = self.rating_dict
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BlindCommitment":
        return cls(
            agent_id=d["agent_id"],
            interaction_id=d["interaction_id"],
            commitment_hash=d["commitment_hash"],
            committed_at=d.get("committed_at", 0.0),
            revealed=d.get("revealed", False),
            rating_dict=d.get("rating_dict"),
        )


@dataclass
class BlindExchange:
    """Manages a bilateral blind rating exchange for one interaction.

    Implements the three-phase protocol from Section 2.4:
    1. Both agents submit commitments
    2. When both commitments exist (or window expires), reveal phase triggers
    3. Ratings become visible simultaneously
    """

    interaction_id: str
    window_seconds: float = 86400.0  # 24 hours default
    created_at: float = field(default_factory=time.time)
    commitment_a: Optional[BlindCommitment] = None
    commitment_b: Optional[BlindCommitment] = None

    @property
    def both_committed(self) -> bool:
        """True when both sides have submitted commitments."""
        return self.commitment_a is not None and self.commitment_b is not None

    @property
    def both_revealed(self) -> bool:
        """True when both sides have revealed their ratings."""
        return (
            self.commitment_a is not None
            and self.commitment_a.revealed
            and self.commitment_b is not None
            and self.commitment_b.revealed
        )

    @property
    def window_expired(self) -> bool:
        """True if the commitment window has expired."""
        return (time.time() - self.created_at) > self.window_seconds

    @property
    def reveal_triggered(self) -> bool:
        """True if the reveal phase should begin (both committed or window expired)."""
        return self.both_committed or self.window_expired

    def submit_commitment(
        self,
        agent_id: str,
        rating_dict: Dict[str, Any],
        nonce: str,
    ) -> BlindCommitment:
        """Submit a commitment for one side of the exchange.

        Args:
            agent_id: The committing agent's identifier.
            rating_dict: The rating being committed.
            nonce: The nonce for this commitment.

        Returns:
            The BlindCommitment object.

        Raises:
            ValueError: If the agent already committed or the window expired.
        """
        if self.window_expired:
            raise ValueError("Commitment window has expired")

        commitment_hash = commit(rating_dict, nonce)
        bc = BlindCommitment(
            agent_id=agent_id,
            interaction_id=self.interaction_id,
            commitment_hash=commitment_hash,
        )

        if self.commitment_a is None:
            self.commitment_a = bc
        elif self.commitment_b is None:
            if self.commitment_a.agent_id == agent_id:
                raise ValueError(
                    f"Agent {agent_id} has already committed to this exchange"
                )
            self.commitment_b = bc
        else:
            raise ValueError("Both sides have already committed")

        return bc

    def reveal_rating(
        self,
        agent_id: str,
        rating_dict: Dict[str, Any],
        nonce: str,
    ) -> bool:
        """Reveal a rating and verify it against the commitment.

        Args:
            agent_id: The revealing agent's identifier.
            rating_dict: The rating being revealed.
            nonce: The nonce used during commitment.

        Returns:
            True if the reveal was verified successfully.

        Raises:
            ValueError: If no commitment found for agent or reveal not triggered.
        """
        if not self.reveal_triggered:
            raise ValueError(
                "Reveal phase not yet triggered — "
                "waiting for both commitments or window expiry"
            )

        target = self._find_commitment(agent_id)
        if target is None:
            raise ValueError(f"No commitment found for agent {agent_id}")

        if target.revealed:
            raise ValueError(f"Agent {agent_id} has already revealed")

        if not reveal(rating_dict, nonce, target.commitment_hash):
            raise ValueError(
                "Reveal verification failed — "
                "rating or nonce does not match commitment"
            )

        target.revealed = True
        target.rating_dict = rating_dict
        target.nonce = nonce
        return True

    def get_results(self) -> Optional[Tuple[Optional[Dict], Optional[Dict]]]:
        """Get the exchange results after reveal phase.

        Returns:
            Tuple of (rating_a, rating_b) if reveal is complete/window expired.
            Each element is a rating dict or None if that agent didn't commit.
            Returns None if reveal phase hasn't started.
        """
        if not self.reveal_triggered:
            return None

        rating_a = None
        rating_b = None

        if self.commitment_a is not None and self.commitment_a.revealed:
            rating_a = self.commitment_a.rating_dict
        if self.commitment_b is not None and self.commitment_b.revealed:
            rating_b = self.commitment_b.rating_dict

        return (rating_a, rating_b)

    def _find_commitment(self, agent_id: str) -> Optional[BlindCommitment]:
        if self.commitment_a and self.commitment_a.agent_id == agent_id:
            return self.commitment_a
        if self.commitment_b and self.commitment_b.agent_id == agent_id:
            return self.commitment_b
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "window_seconds": self.window_seconds,
            "created_at": self.created_at,
            "commitment_a": self.commitment_a.to_dict()
            if self.commitment_a
            else None,
            "commitment_b": self.commitment_b.to_dict()
            if self.commitment_b
            else None,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BlindExchange":
        ex = cls(
            interaction_id=d["interaction_id"],
            window_seconds=d.get("window_seconds", 86400.0),
            created_at=d.get("created_at", time.time()),
        )
        if d.get("commitment_a"):
            ex.commitment_a = BlindCommitment.from_dict(d["commitment_a"])
        if d.get("commitment_b"):
            ex.commitment_b = BlindCommitment.from_dict(d["commitment_b"])
        return ex
