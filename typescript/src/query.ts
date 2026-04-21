import { DIMENSIONS, type Dimension } from "./types";
import { RatingRecord, scoreBucket } from "./rating";
import type { RatingStore } from "./store";
import {
  confidence,
  computeRaterCalibrations,
  raterWeight,
  signalsFromRatings,
  weightedScore,
  weightedScoresAll,
} from "./weight";

function parseTimestamp(ts: string): Date {
  const normalized = ts.replace("Z", "+00:00");
  const d = new Date(normalized);
  if (isNaN(d.getTime())) {
    return new Date(normalized.split(".")[0] + "+00:00");
  }
  return d;
}

function filterByWindow(
  ratings: RatingRecord[],
  windowDays: number
): RatingRecord[] {
  if (windowDays <= 0) return ratings;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - windowDays);

  return ratings.filter((r) => {
    try {
      return parseTimestamp(r.timestamp) >= cutoff;
    } catch {
      return false;
    }
  });
}

export function getReputation(
  store: RatingStore,
  agentId: string,
  dimension?: Dimension,
  windowDays: number = 365,
  applyCalibration: boolean = false
): Record<string, unknown> {
  if (
    dimension !== undefined &&
    !(DIMENSIONS as readonly string[]).includes(dimension)
  ) {
    throw new Error(
      `Unknown dimension '${dimension}'. Must be one of: ${DIMENSIONS.join(", ")}`
    );
  }

  const allRatings = store.getRatingsFor(agentId);
  const ratings = filterByWindow(allRatings, windowDays);
  const numRatings = ratings.length;
  const conf = confidence(numRatings);

  const result: Record<string, unknown> = {
    agent_id: agentId,
    num_ratings: numRatings,
    confidence: Math.round(conf * 10000) / 10000,
    window_days: windowDays,
  };

  if (numRatings === 0) {
    if (dimension) {
      result.dimension = dimension;
      result.score = null;
    } else {
      const scores: Record<string, null> = {};
      for (const dim of DIMENSIONS) scores[dim] = null;
      result.scores = scores;
    }
    return result;
  }

  let calFactors: Record<string, number> | undefined;
  if (applyCalibration) {
    calFactors = computeRaterCalibrations(store.getAll());
  }

  if (dimension) {
    const score = weightedScore(ratings, dimension, calFactors);
    result.dimension = dimension;
    result.score =
      score !== null ? Math.round(score * 100) / 100 : null;
  } else {
    const scores = weightedScoresAll(ratings, calFactors);
    const rounded: Record<string, number | null> = {};
    for (const [dim, s] of Object.entries(scores)) {
      rounded[dim] = s !== null ? Math.round(s * 100) / 100 : null;
    }
    result.scores = rounded;
  }

  return result;
}

export function getReputationSummary(
  store: RatingStore,
  agentId: string,
  windowDays: number = 365
): Record<string, unknown> {
  const rep = getReputation(store, agentId, undefined, windowDays);

  const scores = rep.scores as Record<string, number | null> | undefined;
  if (scores) {
    const buckets: Record<string, string> = {};
    for (const [dim, score] of Object.entries(scores)) {
      buckets[dim] = score !== null ? scoreBucket(Math.round(score)) : "unrated";
    }
    rep.buckets = buckets;
  }

  return rep;
}

export function getGovernanceWeights(
  store: RatingStore,
  cap: number = 0.10
): Record<string, number> {
  const allRatings = store.getAll();

  const agentStats: Record<string, { chain_age_days: number; ratings_given: number }> = {};
  for (const r of allRatings) {
    if (!agentStats[r.raterId]) {
      agentStats[r.raterId] = {
        chain_age_days: r.raterChainAgeDays,
        ratings_given: 0,
      };
    }
    agentStats[r.raterId].ratings_given++;
    if (r.raterChainAgeDays > agentStats[r.raterId].chain_age_days) {
      agentStats[r.raterId].chain_age_days = r.raterChainAgeDays;
    }
  }

  const rawWeights: Record<string, number> = {};
  for (const [agentId, stats] of Object.entries(agentStats)) {
    rawWeights[agentId] = raterWeight(stats.chain_age_days, stats.ratings_given);
  }

  const total = Object.values(rawWeights).reduce((a, b) => a + b, 0);
  if (total === 0) return rawWeights;

  const maxWeight = cap * total;
  const capped: Record<string, number> = {};
  for (const [agentId, w] of Object.entries(rawWeights)) {
    capped[agentId] = Math.min(w, maxWeight);
  }
  return capped;
}

export function verifyRating(
  store: RatingStore,
  ratingId: string
): Record<string, unknown> {
  const record = store.getRating(ratingId);
  if (!record) {
    return {
      rating_id: ratingId,
      valid: false,
      error: "Rating not found in store",
    };
  }
  const isValid = record.verifyHash();
  const result: Record<string, unknown> = {
    rating_id: ratingId,
    valid: isValid,
    record_hash: record.recordHash,
    computed_hash: record.computeHash(),
  };
  if (!isValid) {
    result.error = "Hash mismatch — record may have been tampered";
  }
  return result;
}

export function getComposite(
  store: RatingStore,
  agentId: string,
  profileName: string = "general-purpose",
  windowDays: number = 365,
  applyCalibration: boolean = false,
  cocAgeDays: number = 0,
  ratingParticipationRate: number = 0,
  computedBy: string = ""
): Record<string, unknown> {
  const { compose, getProfile } = require("./composition");

  const allRatings = store.getRatingsFor(agentId);
  const ratings = filterByWindow(allRatings, windowDays);

  let calFactors: Record<string, number> | undefined;
  if (applyCalibration) {
    calFactors = computeRaterCalibrations(store.getAll());
  }

  const signals = signalsFromRatings(
    ratings,
    calFactors,
    "",
    cocAgeDays,
    ratingParticipationRate
  );

  const profile = getProfile(profileName);
  const composite = compose(signals, profile, computedBy);

  return {
    agent_id: agentId,
    profile: profileName,
    composite: composite.toDict(),
    num_ratings: ratings.length,
    window_days: windowDays,
  };
}

function stdev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance =
    values.reduce((s, v) => s + (v - mean) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

export function generatePrbFromStore(opts: {
  store: RatingStore;
  agentId: string;
  issuerId: string;
  profileName?: string;
  windowDays?: number;
  cocAgeDays?: number;
  cocChainLength?: number;
  cocChainHeadHash?: string;
  lastAnchorTimestamp?: string;
  totalInteractions?: number;
  ratingParticipationRate?: number;
  disputeRate?: number;
  avgResponseTimeMs?: number;
  issuerName?: string;
  issuerReliability?: number;
  issuerConfidence?: number;
  verificationEndpoint?: string;
  validityDays?: number;
}): Record<string, unknown> {
  const { compose, getProfile } = require("./composition");
  const {
    DimensionSummary,
    ProvenanceSummary,
    BehavioralSummary,
    generatePrb,
  } = require("./portability");

  const profileName = opts.profileName ?? "general-purpose";
  const windowDays = opts.windowDays ?? 365;
  const cocAgeDays = opts.cocAgeDays ?? 0;
  const ratingParticipationRate = opts.ratingParticipationRate ?? 0;

  const allRatings = opts.store.getRatingsFor(opts.agentId);
  const ratings = filterByWindow(allRatings, windowDays);

  if (ratings.length === 0) {
    return { error: "No ratings found for agent", agent_id: opts.agentId };
  }

  const signals = signalsFromRatings(
    ratings,
    undefined,
    "",
    cocAgeDays,
    ratingParticipationRate
  );
  const profile = getProfile(profileName);
  const composite = compose(signals, profile, opts.issuerId);

  const num = ratings.length;
  const conf = confidence(num);
  const dims: Record<string, InstanceType<typeof DimensionSummary>> = {};
  for (const dim of DIMENSIONS) {
    const values = ratings.map((r: RatingRecord) => r.getDimension(dim as Dimension));
    const mean = values.reduce((a: number, b: number) => a + b, 0) / values.length;
    const std = stdev(values);
    dims[dim] = new DimensionSummary(mean, std, conf, num);
  }

  const ratingHashes = ratings
    .map((r: RatingRecord) => r.recordHash)
    .filter((h: string) => h);

  const provenance = new ProvenanceSummary({
    cocChainAge: cocAgeDays,
    cocChainLength: opts.cocChainLength ?? 0,
    lastAnchorTimestamp: opts.lastAnchorTimestamp ?? "",
    anchorType: "dual_ots_tsa",
  });

  const behavioral = new BehavioralSummary({
    totalInteractions: opts.totalInteractions ?? num,
    ratingParticipationRate,
    disputeRate: opts.disputeRate ?? 0,
    averageResponseTimeMs: opts.avgResponseTimeMs ?? 0,
  });

  const prb = generatePrb({
    issuerId: opts.issuerId,
    subjectId: opts.agentId,
    composite,
    dimensions: dims,
    ratingHashes,
    provenance,
    behavioral,
    issuerName: opts.issuerName,
    issuerReliability: opts.issuerReliability,
    issuerConfidence: opts.issuerConfidence,
    cocChainHeadHash: opts.cocChainHeadHash,
    verificationEndpoint: opts.verificationEndpoint,
    validityDays: opts.validityDays,
  });

  return prb.toVc();
}
