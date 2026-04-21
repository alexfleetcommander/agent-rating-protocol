# agent-rating-protocol (TypeScript)

TypeScript reference implementation of the Agent Rating Protocol v2 — a decentralized reputation system for autonomous agent economies.

## What It Does

- **Rating records** — 5-dimension (1–100) bilateral blind rating with SHA-256 hash integrity
- **Blind protocol** — commit-reveal exchange preventing rating bias
- **Weight calculation** — log-based rater weight with verification multipliers, calibration, and recency decay
- **Signal composition** — 5-operation algebra (gates, diminishing returns, confidence-adjusted weighting, penalty floors) with 5 standard profiles
- **Portable Reputation Bundles** — W3C Verifiable Credential format for cross-platform reputation transfer
- **Merkle verification** — Merkle tree proofs linking PRBs to underlying ratings
- **Anti-Goodhart** — metric rotation, shadow metrics, differential privacy noise, anomaly detection
- **ZKP threshold** — placeholder interface for zero-knowledge threshold proofs (Groth16/PLONK/STARKs)

## Install

```bash
npm install agent-rating-protocol
```

Requires Node.js >= 18. Zero runtime dependencies (uses `node:crypto` and `node:fs`).

## Quick Start

```typescript
import {
  RatingRecord,
  RatingStore,
  compose,
  getProfile,
  signalsFromRatings,
  BlindExchange,
  generateNonce,
} from "agent-rating-protocol";

// Create a rating
const rating = new RatingRecord({
  raterId: "did:web:alice.example",
  rateeId: "did:web:bob.example",
  reliability: 85,
  accuracy: 90,
  latency: 70,
  protocolCompliance: 95,
  costEfficiency: 80,
  raterChainAgeDays: 100,
  raterTotalRatingsGiven: 50,
});

// Store it
const store = new RatingStore("ratings.jsonl");
store.appendRating(rating);

// Compute composite trust score
const signals = signalsFromRatings(
  store.getRatingsFor("did:web:bob.example"),
  undefined,
  "",
  100,  // CoC chain age
  0.8   // rating participation rate
);
const composite = compose(signals, getProfile("general-purpose"));
console.log(composite.toDict());
```

## Build

```bash
npm install
npm run build
npm test
```

## Project Structure

```
src/
  index.ts          — main exports
  types.ts          — shared types, enums, interfaces
  rating.ts         — RatingRecord, AgentIdentity, InteractionEvidence
  blind.ts          — bilateral blind commit-reveal protocol
  store.ts          — append-only JSONL rating store
  weight.ts         — rater weight, calibration, recency, confidence
  composition.ts    — Signal, WeightProfile, compose(), 5 standard profiles
  portability.ts    — PortableReputationBundle, W3C VC, multi-oracle attestation
  anti_goodhart.ts  — metric rotation, shadow metrics, differential privacy
  signals.ts        — MerkleTree, hash-chain verification, ZKP placeholders
  query.ts          — high-level query interface, PRB generation from store
tests/
  rating.test.ts    — 43 tests across all modules
```

## Standard Profiles

| Profile | Domain | Key Weights |
|---------|--------|-------------|
| `general-purpose` | Any | Balanced across all signals |
| `high-reliability` | Infrastructure, payments | Reliability 40%, accuracy 25% |
| `fast-turnaround` | Content, translation | Latency 30%, accuracy 25% |
| `compliance-first` | Regulated industries | Protocol compliance 35%, accuracy 25% |
| `cost-optimized` | Bulk processing | Cost efficiency 30%, reliability 25% |

## Configuration

No config files needed. The store path is passed to `RatingStore` constructor. All crypto uses Node.js built-in `node:crypto`.

## License

Apache 2.0
