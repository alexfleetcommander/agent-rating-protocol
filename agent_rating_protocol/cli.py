"""CLI entry point for agent-rating-protocol.

Commands:
  rate     Submit a rating for an agent
  query    Check an agent's reputation
  verify   Verify a rating record hash
  status   Show local store statistics
"""

import argparse
import json
import sys
from typing import List, Optional

from .query import get_reputation, verify_rating
from .rating import DIMENSIONS, VERIFICATION_LEVELS, RatingRecord
from .store import RatingStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-rating",
        description="Agent Rating Protocol — decentralized agent reputation",
    )
    parser.add_argument(
        "--store",
        default="ratings.jsonl",
        help="Path to the JSONL rating store (default: ratings.jsonl)",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # rate
    p_rate = sub.add_parser("rate", help="Submit a rating for an agent")
    p_rate.add_argument("ratee", help="Agent ID of the agent being rated")
    p_rate.add_argument("--rater", required=True, help="Your agent ID")
    p_rate.add_argument(
        "--interaction", default="", help="Interaction ID (optional)"
    )
    p_rate.add_argument(
        "--reliability", type=int, default=50, help="Reliability score (1-100)"
    )
    p_rate.add_argument(
        "--accuracy", type=int, default=50, help="Accuracy score (1-100)"
    )
    p_rate.add_argument(
        "--latency", type=int, default=50, help="Latency score (1-100)"
    )
    p_rate.add_argument(
        "--protocol-compliance",
        type=int,
        default=50,
        help="Protocol compliance score (1-100)",
    )
    p_rate.add_argument(
        "--cost-efficiency",
        type=int,
        default=50,
        help="Cost efficiency score (1-100)",
    )
    p_rate.add_argument(
        "--chain-age", type=int, default=0, help="Rater's chain age in days"
    )
    p_rate.add_argument(
        "--ratings-given",
        type=int,
        default=0,
        help="Rater's total ratings given",
    )
    p_rate.add_argument(
        "--chain-length",
        type=int,
        default=None,
        help="Rater's CoC chain length (optional)",
    )
    p_rate.add_argument(
        "--verification-level",
        choices=list(VERIFICATION_LEVELS),
        default="verified",
        help="Interaction verification level (default: verified)",
    )
    p_rate.add_argument(
        "--rater-proof",
        default=None,
        help="Rater identity proof reference (optional)",
    )
    p_rate.add_argument(
        "--ratee-proof",
        default=None,
        help="Ratee identity proof reference (optional)",
    )
    p_rate.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    # query
    p_query = sub.add_parser("query", help="Check an agent's reputation")
    p_query.add_argument("agent_id", help="Agent ID to query")
    p_query.add_argument(
        "--dimension",
        choices=list(DIMENSIONS),
        help="Query a specific dimension",
    )
    p_query.add_argument(
        "--window",
        type=int,
        default=365,
        help="Rolling window in days (default: 365)",
    )
    p_query.add_argument(
        "--calibrated",
        action="store_true",
        help="Apply anti-inflation calibration (Section 4.6)",
    )
    p_query.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    # verify
    p_verify = sub.add_parser("verify", help="Verify a rating record hash")
    p_verify.add_argument("rating_id", help="Rating UUID to verify")
    p_verify.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    # status
    p_status = sub.add_parser("status", help="Show local store statistics")
    p_status.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    return parser


def _cmd_rate(args: argparse.Namespace) -> int:
    store = RatingStore(args.store)
    try:
        record = RatingRecord(
            rater_id=args.rater,
            ratee_id=args.ratee,
            interaction_id=args.interaction,
            reliability=args.reliability,
            accuracy=args.accuracy,
            latency=args.latency,
            protocol_compliance=args.protocol_compliance,
            cost_efficiency=args.cost_efficiency,
            rater_chain_age_days=args.chain_age,
            rater_total_ratings_given=args.ratings_given,
            rater_chain_length=args.chain_length,
            verification_level=args.verification_level,
            rater_identity_proof=args.rater_proof,
            ratee_identity_proof=args.ratee_proof,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    rating_id = store.append_rating(record)

    if args.json:
        print(json.dumps(record.to_dict(), indent=2))
    else:
        print(f"Rating submitted: {rating_id}")
        print(f"  Rater: {record.rater_id}")
        print(f"  Ratee: {record.ratee_id}")
        print(f"  Verification: {record.verification_level}")
        dims = record.dimensions
        for dim, val in dims.items():
            print(f"  {dim}: {val}")
        print(f"  Hash: {record.record_hash[:16]}...")

    # Optional CoC integration
    _try_coc_record(record)

    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    store = RatingStore(args.store)
    result = get_reputation(
        store,
        args.agent_id,
        dimension=args.dimension,
        window_days=args.window,
        apply_calibration=getattr(args, "calibrated", False),
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Reputation for: {result['agent_id']}")
        print(
            f"  Ratings: {result['num_ratings']} "
            f"(confidence: {result['confidence']})"
        )
        print(f"  Window: {result['window_days']} days")
        if "score" in result:
            score = result["score"]
            dim = result["dimension"]
            print(f"  {dim}: {score if score is not None else 'N/A'}")
        elif "scores" in result:
            for dim, score in result["scores"].items():
                print(f"  {dim}: {score if score is not None else 'N/A'}")

    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    store = RatingStore(args.store)
    result = verify_rating(store, args.rating_id)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "VALID" if result["valid"] else "INVALID"
        print(f"Rating {args.rating_id}: {status}")
        if "error" in result:
            print(f"  Error: {result['error']}")
        if "record_hash" in result:
            print(f"  Record hash:   {result['record_hash'][:16]}...")
            print(f"  Computed hash: {result['computed_hash'][:16]}...")

    return 1 if not result["valid"] else 0


def _cmd_status(args: argparse.Namespace) -> int:
    store = RatingStore(args.store)
    stats = store.stats()

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print("Rating Store Status")
        print(f"  File: {stats['file_path']}")
        print(f"  Size: {stats['file_size_bytes']} bytes")
        print(f"  Total ratings: {stats['total_ratings']}")
        print(f"  Unique raters: {stats['unique_raters']}")
        print(f"  Unique ratees: {stats['unique_ratees']}")

    return 0


def _try_coc_record(record: RatingRecord) -> None:
    """Optionally record rating to a CoC chain if the package is installed."""
    try:
        from chain_of_consciousness import Chain  # type: ignore[import]

        # Only integrate if a chain file exists in the current directory
        import os

        chain_file = os.environ.get("COC_CHAIN_FILE")
        if not chain_file:
            return

        chain = Chain(record.rater_id, storage=chain_file)
        chain.add(
            "RATING_SUBMITTED",
            {
                "rating_id": record.rating_id,
                "ratee": record.ratee_id,
                "interaction_id": record.interaction_id,
                "dimensions": record.dimensions,
                "record_hash": record.record_hash,
            },
        )
    except ImportError:
        pass  # CoC not installed — that's fine
    except Exception:
        pass  # Don't let CoC integration failures break rating


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    handlers = {
        "rate": _cmd_rate,
        "query": _cmd_query,
        "verify": _cmd_verify,
        "status": _cmd_status,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
