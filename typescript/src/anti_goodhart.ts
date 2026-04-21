import { createHash } from "node:crypto";
import { ProfileInput, WeightProfile } from "./composition";
import type { Gate, PenaltyFloor } from "./composition";

export interface RotationBoundData {
  signal_id: string;
  weight_bounds: { min: number; max: number };
  current_weight: number | "ROTATED";
}

export class RotationBound {
  readonly signalId: string;
  readonly minWeight: number;
  readonly maxWeight: number;
  currentWeight: number | undefined;

  constructor(
    signalId: string,
    minWeight: number,
    maxWeight: number,
    currentWeight?: number
  ) {
    this.signalId = signalId;
    this.minWeight = minWeight;
    this.maxWeight = maxWeight;
    this.currentWeight = currentWeight;
  }

  toDict(): RotationBoundData {
    return {
      signal_id: this.signalId,
      weight_bounds: { min: this.minWeight, max: this.maxWeight },
      current_weight:
        this.currentWeight !== undefined ? this.currentWeight : "ROTATED",
    };
  }

  validateWeight(weight: number): boolean {
    return weight >= this.minWeight && weight <= this.maxWeight;
  }
}

export interface RotationEventData {
  profile_id: string;
  timestamp: string;
  previous_weights: Record<string, number>;
  new_weights: Record<string, number>;
  announcement: string;
}

export class RotationEvent {
  readonly profileId: string;
  readonly timestamp: string;
  readonly previousWeights: Record<string, number>;
  readonly newWeights: Record<string, number>;
  readonly announcement: string;

  constructor(opts: {
    profileId: string;
    timestamp: string;
    previousWeights: Record<string, number>;
    newWeights: Record<string, number>;
    announcement?: string;
  }) {
    this.profileId = opts.profileId;
    this.timestamp = opts.timestamp;
    this.previousWeights = opts.previousWeights;
    this.newWeights = opts.newWeights;
    this.announcement = opts.announcement ?? "";
  }

  toDict(): RotationEventData {
    return {
      profile_id: this.profileId,
      timestamp: this.timestamp,
      previous_weights: this.previousWeights,
      new_weights: this.newWeights,
      announcement: this.announcement,
    };
  }
}

export function generateRotationBounds(
  profile: WeightProfile,
  boundFraction: number = 0.4
): RotationBound[] {
  const bounds: RotationBound[] = [];
  for (const inp of profile.inputs) {
    if (inp.weightBounds) {
      bounds.push(
        new RotationBound(
          inp.signalId,
          inp.weightBounds.min,
          inp.weightBounds.max
        )
      );
    } else {
      const delta = inp.weight * boundFraction;
      const lo = Math.max(0.0, inp.weight - delta);
      const hi = Math.min(1.0, inp.weight + delta);
      bounds.push(
        new RotationBound(
          inp.signalId,
          Math.round(lo * 10000) / 10000,
          Math.round(hi * 10000) / 10000
        )
      );
    }
  }
  return bounds;
}

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0x100000000;
  };
}

export function rotateWeights(
  profile: WeightProfile,
  bounds: RotationBound[],
  seed?: number
): [WeightProfile, RotationEvent] {
  const rng =
    seed !== undefined ? seededRandom(seed) : () => Math.random();
  const boundMap = new Map<string, RotationBound>();
  for (const b of bounds) boundMap.set(b.signalId, b);

  const oldWeights: Record<string, number> = {};
  const newRaw: Record<string, number> = {};

  for (const inp of profile.inputs) {
    oldWeights[inp.signalId] = inp.weight;
    const bound = boundMap.get(inp.signalId);
    if (bound) {
      newRaw[inp.signalId] =
        bound.minWeight + rng() * (bound.maxWeight - bound.minWeight);
    } else {
      newRaw[inp.signalId] = inp.weight;
    }
  }

  const total = Object.values(newRaw).reduce((a, b) => a + b, 0);
  const newWeights: Record<string, number> = {};
  if (total > 0) {
    for (const [sid, w] of Object.entries(newRaw)) {
      newWeights[sid] = Math.round((w / total) * 10000) / 10000;
    }
  } else {
    Object.assign(newWeights, newRaw);
  }

  const newInputs: ProfileInput[] = profile.inputs.map((inp) => {
    const bound = boundMap.get(inp.signalId);
    return new ProfileInput(
      inp.signalId,
      newWeights[inp.signalId] ?? inp.weight,
      inp.operation,
      inp.k,
      bound
        ? { min: bound.minWeight, max: bound.maxWeight }
        : inp.weightBounds
    );
  });

  const now = new Date().toISOString();
  const newProfile = new WeightProfile({
    profileId: profile.profileId,
    version: now.slice(0, 10),
    description: profile.description,
    inputs: newInputs,
    gates: profile.gates,
    penaltyFloors: profile.penaltyFloors,
    outputRange: profile.outputRange,
    rotationSchedule: profile.rotationSchedule,
    governanceApproved: now,
  });

  const event = new RotationEvent({
    profileId: profile.profileId,
    timestamp: now,
    previousWeights: oldWeights,
    newWeights,
    announcement: `Weights for ${profile.profileId} have been updated as of ${now.slice(0, 10)}`,
  });

  return [newProfile, event];
}

export interface ShadowMetricData {
  primary_signal_id: string;
  shadow_signal_id: string;
  primary_value: number;
  shadow_value: number;
  divergence_detected: boolean;
  observations: number;
}

export class ShadowMetric {
  readonly primarySignalId: string;
  readonly shadowSignalId: string;
  readonly description: string;
  primaryValue: number;
  shadowValue: number;
  readonly divergenceThreshold: number;
  private _history: number[];

  constructor(opts: {
    primarySignalId: string;
    shadowSignalId: string;
    description?: string;
    divergenceThreshold?: number;
  }) {
    this.primarySignalId = opts.primarySignalId;
    this.shadowSignalId = opts.shadowSignalId;
    this.description = opts.description ?? "";
    this.primaryValue = 0;
    this.shadowValue = 0;
    this.divergenceThreshold = opts.divergenceThreshold ?? 2.0;
    this._history = [];
  }

  record(primary: number, shadow: number): void {
    this.primaryValue = primary;
    this.shadowValue = shadow;
    this._history.push(primary - shadow);
  }

  divergenceDetected(): boolean {
    if (this._history.length < 3) return false;
    const mean =
      this._history.reduce((a, b) => a + b, 0) / this._history.length;
    const variance =
      this._history.reduce((s, v) => s + (v - mean) ** 2, 0) /
      (this._history.length - 1);
    const stdev = Math.sqrt(variance);
    if (stdev === 0) return false;
    const latest = this._history[this._history.length - 1];
    const zScore = Math.abs(latest - mean) / stdev;
    return zScore > this.divergenceThreshold;
  }

  toDict(): ShadowMetricData {
    return {
      primary_signal_id: this.primarySignalId,
      shadow_signal_id: this.shadowSignalId,
      primary_value: this.primaryValue,
      shadow_value: this.shadowValue,
      divergence_detected: this.divergenceDetected(),
      observations: this._history.length,
    };
  }
}

export const DEFAULT_SHADOW_METRICS = [
  {
    primary: "composite_score",
    shadow: "score_stability_variance",
    description: "Score stability (30/90/180 day variance)",
  },
  {
    primary: "arp:reliability:weighted_mean",
    shadow: "repeat_interaction_rate",
    description: "Repeat interaction rate (do agents re-hire?)",
  },
  {
    primary: "arp:accuracy:weighted_mean",
    shadow: "downstream_verification_rate",
    description: "Downstream error detection rate",
  },
  {
    primary: "arp:latency:weighted_mean",
    shadow: "task_complexity_ratio",
    description: "Latency relative to task complexity",
  },
  {
    primary: "arp:cost_efficiency:weighted_mean",
    shadow: "value_per_token_ratio",
    description: "Output quality per compute unit",
  },
  {
    primary: "behavioral:rating_participation_rate",
    shadow: "rating_reciprocity_balance",
    description: "Rating reciprocity balance",
  },
];

export interface ShadowMetricCommitmentData {
  oracle_id: string;
  cycle_timestamp: string;
  commitment_hash: string;
  agent_count: number;
}

export class ShadowMetricCommitment {
  readonly oracleId: string;
  readonly cycleTimestamp: string;
  readonly commitmentHash: string;
  readonly agentCount: number;

  constructor(
    oracleId: string,
    cycleTimestamp: string,
    commitmentHash: string,
    agentCount: number = 0
  ) {
    this.oracleId = oracleId;
    this.cycleTimestamp = cycleTimestamp;
    this.commitmentHash = commitmentHash;
    this.agentCount = agentCount;
  }

  toDict(): ShadowMetricCommitmentData {
    return {
      oracle_id: this.oracleId,
      cycle_timestamp: this.cycleTimestamp,
      commitment_hash: this.commitmentHash,
      agent_count: this.agentCount,
    };
  }
}

export function computeShadowCommitment(
  oracleId: string,
  shadowData: Record<string, unknown>
): ShadowMetricCommitment {
  const canonical = JSON.stringify(shadowData, Object.keys(shadowData).sort());
  const hash = createHash("sha256").update(canonical, "utf-8").digest("hex");
  return new ShadowMetricCommitment(
    oracleId,
    new Date().toISOString(),
    hash,
    Object.keys(shadowData).length
  );
}

export function verifyShadowCommitment(
  commitment: ShadowMetricCommitment,
  revealedData: Record<string, unknown>
): boolean {
  const canonical = JSON.stringify(
    revealedData,
    Object.keys(revealedData).sort()
  );
  const computed = createHash("sha256")
    .update(canonical, "utf-8")
    .digest("hex");
  return computed === commitment.commitmentHash;
}

export interface AnomalyFlagData {
  agent_id: string;
  primary_signal: string;
  shadow_signal: string;
  severity: string;
  confidence_adjustment: number;
  timestamp: string;
  details: string;
}

export class AnomalyFlag {
  readonly agentId: string;
  readonly primarySignal: string;
  readonly shadowSignal: string;
  readonly severity: string;
  readonly confidenceAdjustment: number;
  readonly timestamp: string;
  readonly details: string;

  constructor(opts: {
    agentId: string;
    primarySignal: string;
    shadowSignal: string;
    severity: string;
    confidenceAdjustment?: number;
    timestamp?: string;
    details?: string;
  }) {
    this.agentId = opts.agentId;
    this.primarySignal = opts.primarySignal;
    this.shadowSignal = opts.shadowSignal;
    this.severity = opts.severity;
    this.confidenceAdjustment = opts.confidenceAdjustment ?? 1.0;
    this.timestamp = opts.timestamp ?? new Date().toISOString();
    this.details = opts.details ?? "";
  }

  toDict(): AnomalyFlagData {
    return {
      agent_id: this.agentId,
      primary_signal: this.primarySignal,
      shadow_signal: this.shadowSignal,
      severity: this.severity,
      confidence_adjustment: this.confidenceAdjustment,
      timestamp: this.timestamp,
      details: this.details,
    };
  }
}

export function checkAnomalies(
  agentId: string,
  shadowMetrics: ShadowMetric[],
  confidencePenalty: number = 0.8
): AnomalyFlag[] {
  const flags: AnomalyFlag[] = [];
  for (const sm of shadowMetrics) {
    if (sm.divergenceDetected()) {
      flags.push(
        new AnomalyFlag({
          agentId,
          primarySignal: sm.primarySignalId,
          shadowSignal: sm.shadowSignalId,
          severity: "enhanced_monitoring",
          confidenceAdjustment: confidencePenalty,
          details:
            `Divergence detected between ${sm.primarySignalId} ` +
            `and ${sm.shadowSignalId} ` +
            `(primary=${sm.primaryValue.toFixed(1)}, ` +
            `shadow=${sm.shadowValue.toFixed(1)})`,
        })
      );
    }
  }
  return flags;
}

export function laplaceNoise(sensitivity: number, epsilon: number): number {
  if (epsilon <= 0) throw new Error("epsilon must be positive");
  if (sensitivity < 0) throw new Error("sensitivity must be non-negative");
  const scale = sensitivity / epsilon;
  const u = Math.random() - 0.5;
  return -scale * Math.sign(u) * Math.log(1 - 2 * Math.abs(u));
}

export function addDpNoise(
  trueValue: number,
  sensitivity: number = 5.0,
  epsilon: number = 1.0,
  outputRange: [number, number] = [0, 100]
): number {
  const noise = laplaceNoise(sensitivity, epsilon);
  const noised = trueValue + noise;
  return Math.max(outputRange[0], Math.min(outputRange[1], noised));
}

export function dpResponse(
  trueValue: number,
  agentSeed?: number,
  sensitivity: number = 5.0,
  epsilon: number = 1.0
): number {
  if (agentSeed !== undefined) {
    const rng = seededRandom(agentSeed);
    const scale = sensitivity / epsilon;
    const u = rng() - 0.5;
    const noise = -scale * Math.sign(u) * Math.log(1 - 2 * Math.abs(u));
    const noised = trueValue + noise;
    return Math.max(0, Math.min(100, noised));
  }
  return addDpNoise(trueValue, sensitivity, epsilon);
}
