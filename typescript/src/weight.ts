import { DIMENSIONS, type Dimension } from "./types";
import type { RatingRecord } from "./rating";
import type { Signal } from "./composition";

const VERIFICATION_MULTIPLIERS: Record<string, number> = {
  verified: 1.0,
  unilateral: 0.5,
  self_reported: 0.5,
};

export function raterWeight(
  chainAgeDays: number,
  totalRatingsGiven: number
): number {
  if (chainAgeDays < 0 || totalRatingsGiven < 0) {
    throw new Error("Age and rating count must be non-negative");
  }
  return Math.log2(1 + chainAgeDays) * Math.log2(1 + totalRatingsGiven);
}

export function verificationLevelMultiplier(level: string): number {
  return VERIFICATION_MULTIPLIERS[level] ?? 1.0;
}

export function raterCalibrationFactor(raterScores: number[]): number {
  if (raterScores.length < 2) return 1.0;
  const mean = raterScores.reduce((a, b) => a + b, 0) / raterScores.length;
  const variance =
    raterScores.reduce((sum, s) => sum + (s - mean) ** 2, 0) /
    (raterScores.length - 1);
  const sigma = Math.sqrt(variance);
  if (sigma < 10) return sigma / 10.0;
  return 1.0;
}

export function recencyMultiplier(
  ratingTimestamp: string,
  windowDays: number = 365
): number {
  let ts: Date;
  try {
    ts = new Date(ratingTimestamp.replace("Z", "+00:00"));
    if (isNaN(ts.getTime())) return 1.0;
  } catch {
    return 1.0;
  }

  const now = new Date();
  const ageDays = (now.getTime() - ts.getTime()) / (86400 * 1000);

  if (ageDays < 0) return 1.0;
  if (ageDays > windowDays) return 0.0;
  return 1.0 - 0.5 * (ageDays / windowDays);
}

export function effectiveWeight(
  record: RatingRecord,
  calibration: number = 1.0,
  recency: number = 1.0
): number {
  const base = raterWeight(
    record.raterChainAgeDays,
    record.raterTotalRatingsGiven
  );
  const vMult = verificationLevelMultiplier(record.verificationLevel);
  return base * vMult * calibration * recency;
}

export function computeRaterCalibrations(
  allRatings: RatingRecord[]
): Record<string, number> {
  const raterScores: Record<string, number[]> = {};
  for (const r of allRatings) {
    if (!raterScores[r.raterId]) raterScores[r.raterId] = [];
    for (const dim of DIMENSIONS) {
      raterScores[r.raterId].push(r.getDimension(dim));
    }
  }
  const result: Record<string, number> = {};
  for (const [raterId, scores] of Object.entries(raterScores)) {
    result[raterId] = raterCalibrationFactor(scores);
  }
  return result;
}

export function weightedScore(
  ratings: RatingRecord[],
  dimension: Dimension,
  calibrationFactors?: Record<string, number>
): number | null {
  if (!(DIMENSIONS as readonly string[]).includes(dimension)) {
    throw new Error(
      `Unknown dimension '${dimension}'. Must be one of: ${DIMENSIONS.join(", ")}`
    );
  }

  let totalWeight = 0;
  let weightedSum = 0;

  for (const r of ratings) {
    const cal = calibrationFactors?.[r.raterId] ?? 1.0;
    const w = effectiveWeight(r, cal);
    const score = r.getDimension(dimension);
    weightedSum += w * score;
    totalWeight += w;
  }

  if (totalWeight === 0) return null;
  return weightedSum / totalWeight;
}

export function weightedScoresAll(
  ratings: RatingRecord[],
  calibrationFactors?: Record<string, number>
): Record<Dimension, number | null> {
  const result = {} as Record<Dimension, number | null>;
  for (const dim of DIMENSIONS) {
    result[dim] = weightedScore(ratings, dim, calibrationFactors);
  }
  return result;
}

export function confidence(numRatings: number): number {
  if (numRatings < 0) throw new Error("numRatings must be non-negative");
  return 1.0 - 1.0 / (1.0 + 0.1 * numRatings);
}

export function signalsFromRatings(
  ratings: RatingRecord[],
  calibrationFactors?: Record<string, number>,
  source: string = "",
  cocAgeDays: number = 0,
  ratingParticipationRate: number = 0.0
): Signal[] {
  // Lazy import to avoid circular dependency
  const { Signal: SignalClass } = require("./composition");

  const signals: Signal[] = [];
  const num = ratings.length;
  const conf = confidence(num);

  const scores = weightedScoresAll(ratings, calibrationFactors);
  for (const dim of DIMENSIONS) {
    const score = scores[dim];
    if (score !== null) {
      signals.push(
        new SignalClass({
          signalType: "rating_dimension",
          signalId: `arp:${dim}:weighted_mean`,
          value: score,
          confidence: conf,
          source,
          sampleSize: num,
        })
      );
    }
  }

  signals.push(
    new SignalClass({
      signalType: "behavioral",
      signalId: "arp:total_ratings_received",
      value: num,
      confidence: 1.0,
      source,
    })
  );

  signals.push(
    new SignalClass({
      signalType: "provenance",
      signalId: "coc:operational_age_days",
      value: cocAgeDays,
      confidence: 1.0,
      source,
    })
  );

  signals.push(
    new SignalClass({
      signalType: "behavioral",
      signalId: "behavioral:rating_participation_rate",
      value: ratingParticipationRate * 100.0,
      confidence: 1.0,
      source,
    })
  );

  return signals;
}
