"""Local rating store — append-only JSON file storage.

Implements Section 2.3 of the Agent Rating System Design:
- Each rater stores their own outgoing ratings
- Append-only (no deletion, per spec)
- JSON Lines format (one record per line)
- Query by ratee or rater agent_id
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .rating import RatingRecord


class RatingStore:
    """Append-only local rating store backed by a JSONL file.

    Follows the same pattern as Chain of Consciousness:
    one JSON record per line, append-only, no deletion.
    """

    def __init__(self, path: str = "ratings.jsonl") -> None:
        """Initialize the rating store.

        Args:
            path: Path to the JSONL file. Created if it doesn't exist.
        """
        self.path = Path(path)
        self._lock = threading.Lock()
        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_rating(self, record: RatingRecord) -> str:
        """Append a rating record to the store.

        Args:
            record: The RatingRecord to store.

        Returns:
            The rating_id of the stored record.

        Raises:
            ValueError: If the record hash doesn't verify.
        """
        if not record.verify_hash():
            raise ValueError(
                "Record hash verification failed — record may be tampered"
            )

        line = json.dumps(record.to_dict(), separators=(",", ":"))
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        return record.rating_id

    def get_all(self) -> List[RatingRecord]:
        """Read all ratings from the store.

        Returns:
            List of all RatingRecord objects in insertion order.
        """
        if not self.path.exists():
            return []

        records: List[RatingRecord] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    records.append(RatingRecord.from_dict(d))
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Skip malformed lines but don't crash
                    continue
        return records

    def get_ratings_for(self, agent_id: str) -> List[RatingRecord]:
        """Get all ratings received by an agent (as ratee).

        Args:
            agent_id: The agent identifier to query.

        Returns:
            List of RatingRecord objects where agent_id is the ratee.
        """
        return [r for r in self.get_all() if r.ratee_id == agent_id]

    def get_ratings_by(self, agent_id: str) -> List[RatingRecord]:
        """Get all ratings submitted by an agent (as rater).

        Args:
            agent_id: The agent identifier to query.

        Returns:
            List of RatingRecord objects where agent_id is the rater.
        """
        return [r for r in self.get_all() if r.rater_id == agent_id]

    def get_rating(self, rating_id: str) -> Optional[RatingRecord]:
        """Look up a specific rating by its rating_id.

        Args:
            rating_id: The UUID of the rating.

        Returns:
            The RatingRecord, or None if not found.
        """
        for r in self.get_all():
            if r.rating_id == rating_id:
                return r
        return None

    def count(self) -> int:
        """Return the total number of ratings in the store."""
        if not self.path.exists():
            return 0
        count = 0
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def agents(self) -> Dict[str, Dict[str, int]]:
        """Return a summary of agents and their rating counts.

        Returns:
            Dict mapping agent_id to {"ratings_given": N, "ratings_received": M}.
        """
        summary: Dict[str, Dict[str, int]] = {}
        for r in self.get_all():
            if r.rater_id not in summary:
                summary[r.rater_id] = {"ratings_given": 0, "ratings_received": 0}
            if r.ratee_id not in summary:
                summary[r.ratee_id] = {"ratings_given": 0, "ratings_received": 0}
            summary[r.rater_id]["ratings_given"] += 1
            summary[r.ratee_id]["ratings_received"] += 1
        return summary

    def stats(self) -> Dict[str, Any]:
        """Return store statistics.

        Returns:
            Dict with total_ratings, unique_raters, unique_ratees,
            file_path, and file_size_bytes.
        """
        all_records = self.get_all()
        raters = set()
        ratees = set()
        for r in all_records:
            raters.add(r.rater_id)
            ratees.add(r.ratee_id)

        file_size = self.path.stat().st_size if self.path.exists() else 0

        return {
            "total_ratings": len(all_records),
            "unique_raters": len(raters),
            "unique_ratees": len(ratees),
            "file_path": str(self.path),
            "file_size_bytes": file_size,
        }
