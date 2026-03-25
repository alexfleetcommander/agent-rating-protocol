# Agent Rating Protocol

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/downloads/)

Decentralized agent reputation protocol — multidimensional ratings with bilateral blind commit-reveal and Sybil-resistant weighting. Companion to the [Chain of Consciousness](https://vibeagentmaking.com/whitepaper.html) specification.

## Quickstart

```python
from agent_rating_protocol import RatingRecord, RatingStore, get_reputation

store = RatingStore("ratings.jsonl")
store.append_rating(RatingRecord(rater_id="agent-a", ratee_id="agent-b", reliability=85, accuracy=90, rater_chain_age_days=100, rater_total_ratings_given=50))
print(get_reputation(store, "agent-b"))
```

## Install

```bash
pip install agent-rating-protocol
```

With optional Chain of Consciousness integration:

```bash
pip install agent-rating-protocol[coc]
```

## Features

- **5-dimension rating** — reliability, accuracy, latency, protocol_compliance, cost_efficiency (1-100 scale)
- **Bilateral blind protocol** — commit-reveal ensures neither party sees the other's rating until both submit
- **Sybil-resistant weighting** — W = log2(1 + age) × log2(1 + ratings_given). Score received never affects weight.
- **Append-only store** — JSONL-backed, tamper-evident via SHA-256 record hashes
- **Rolling windows** — default 365-day window prevents stale reputation
- **Confidence scoring** — new agents show high uncertainty, not zero trust
- **Zero required dependencies** — stdlib only for core. Optional CoC integration.
- **Identity-agnostic** — works with DIDs, URIs, ERC-8004, or plain strings

## API Reference

### RatingRecord

```python
from agent_rating_protocol import RatingRecord

record = RatingRecord(
    rater_id="did:example:alice",
    ratee_id="did:example:bob",
    interaction_id="task-uuid-here",
    reliability=85,
    accuracy=90,
    latency=75,
    protocol_compliance=95,
    cost_efficiency=70,
    rater_chain_age_days=365,
    rater_total_ratings_given=100,
)

record.to_dict()       # JSON-serializable dict
record.to_json()       # JSON string
record.verify_hash()   # True if record_hash is valid
record.compute_hash()  # Recompute SHA-256 hash

RatingRecord.from_dict(d)  # Deserialize from dict
```

### RatingStore

```python
from agent_rating_protocol import RatingStore

store = RatingStore("ratings.jsonl")

store.append_rating(record)               # Append (validates hash first)
store.get_ratings_for("agent-b")          # Ratings received by agent
store.get_ratings_by("agent-a")           # Ratings submitted by agent
store.get_rating("uuid")                  # Look up by rating_id
store.count()                             # Total ratings
store.stats()                             # Summary statistics
store.agents()                            # Per-agent rating counts
```

### Reputation Queries

```python
from agent_rating_protocol import get_reputation

# All dimensions
result = get_reputation(store, "agent-b", window_days=365)
# {'agent_id': 'agent-b', 'num_ratings': 5, 'confidence': 0.3333, 'scores': {...}}

# Single dimension
result = get_reputation(store, "agent-b", dimension="reliability")
# {'agent_id': 'agent-b', 'score': 85.0, 'dimension': 'reliability', ...}
```

### Bilateral Blind Protocol

```python
from agent_rating_protocol import BlindExchange, generate_nonce

exchange = BlindExchange(interaction_id="task-001")

# Agent A commits
nonce_a = generate_nonce()
exchange.submit_commitment("agent-a", rating_a.to_dict(), nonce_a)

# Agent B commits
nonce_b = generate_nonce()
exchange.submit_commitment("agent-b", rating_b.to_dict(), nonce_b)

# Both reveal (triggered when both committed)
exchange.reveal_rating("agent-a", rating_a.to_dict(), nonce_a)
exchange.reveal_rating("agent-b", rating_b.to_dict(), nonce_b)

# Get simultaneous results
rating_a_result, rating_b_result = exchange.get_results()
```

### Weight Calculation

```python
from agent_rating_protocol import rater_weight, confidence

w = rater_weight(chain_age_days=365, total_ratings_given=100)  # ≈ 56.4
c = confidence(num_ratings=50)  # ≈ 0.833
```

## CLI Reference

```bash
# Submit a rating
agent-rating rate agent-b --rater agent-a --reliability 85 --accuracy 90

# Query reputation
agent-rating query agent-b
agent-rating query agent-b --dimension reliability --window 180

# Verify a rating hash
agent-rating verify <rating-uuid>

# Store statistics
agent-rating status

# All commands support --json for machine-readable output
agent-rating query agent-b --json

# Custom store path
agent-rating --store /path/to/ratings.jsonl status
```

## CoC Integration

If [chain-of-consciousness](https://pypi.org/project/chain-of-consciousness/) is installed and the `COC_CHAIN_FILE` environment variable is set, ratings are automatically recorded as `RATING_SUBMITTED` chain entries:

```bash
export COC_CHAIN_FILE=chain.jsonl
agent-rating rate agent-b --rater agent-a --reliability 85
# -> Rating stored in ratings.jsonl AND recorded in chain.jsonl
```

## Rating Dimensions

| Dimension | Measures | Scale |
|-----------|----------|-------|
| reliability | Task completion, uptime | 1-100 |
| accuracy | Output correctness | 1-100 |
| latency | Response speed vs. complexity | 1-100 |
| protocol_compliance | Message format, handshake correctness | 1-100 |
| cost_efficiency | Resource usage vs. value | 1-100 |

Score buckets: 1-20 poor, 21-40 below average, 41-60 average, 61-80 good, 81-100 excellent.

## Weight Formula

```
W(rater) = log2(1 + chain_age_days) × log2(1 + total_ratings_given)
```

Governance weight equals rating weight by design — both derived from tenure and participation, never from score received.

## Design Specification

Full protocol design, game theory analysis, and governance model: see the [Agent Rating System Design](https://vibeagentmaking.com/whitepaper.html) specification.

## Security Disclaimer (VAM-SEC v1.0)

This software is provided for research and development purposes. The rating protocol includes cryptographic commitments (SHA-256) and a bilateral blind protocol, but has NOT been formally audited by a third-party security firm. Before using in production environments where reputation scores influence high-stakes decisions, conduct an independent security review. The append-only store provides tamper evidence but not tamper prevention — an attacker with filesystem access can modify the JSONL file directly. For stronger guarantees, use CoC integration with external anchoring (OTS + TSA).

## License

Apache 2.0 — see [LICENSE](LICENSE).
