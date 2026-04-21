import type {
  CompositeSignalData,
  GateData,
  PenaltyFloorData,
  ProfileInputData,
  SignalData,
  WeightProfileData,
} from "./types";

export const DISQUALIFIED = "DISQUALIFIED";

export interface SignalOptions {
  signalType: string;
  signalId: string;
  value: number;
  confidence?: number;
  source?: string;
  window?: string;
  sampleSize?: number;
  timestamp?: string;
}

export class Signal {
  readonly signalType: string;
  readonly signalId: string;
  readonly value: number;
  readonly confidence: number;
  readonly source: string;
  readonly window: string;
  readonly sampleSize: number;
  readonly timestamp: string;

  constructor(opts: SignalOptions) {
    this.signalType = opts.signalType;
    this.signalId = opts.signalId;
    this.value = opts.value;
    this.confidence = opts.confidence ?? 1.0;
    this.source = opts.source ?? "";
    this.window = opts.window ?? "365d";
    this.sampleSize = opts.sampleSize ?? 0;
    this.timestamp = opts.timestamp ?? new Date().toISOString();
  }

  toDict(): SignalData {
    return {
      signal_type: this.signalType,
      signal_id: this.signalId,
      value: this.value,
      confidence: this.confidence,
      source: this.source,
      window: this.window,
      sample_size: this.sampleSize,
      timestamp: this.timestamp,
    };
  }

  static fromDict(d: SignalData): Signal {
    return new Signal({
      signalType: d.signal_type,
      signalId: d.signal_id,
      value: d.value,
      confidence: d.confidence,
      source: d.source,
      window: d.window,
      sampleSize: d.sample_size,
      timestamp: d.timestamp,
    });
  }
}

export class ProfileInput {
  readonly signalId: string;
  readonly weight: number;
  readonly operation: string;
  readonly k: number;
  readonly weightBounds: { min: number; max: number } | undefined;

  constructor(
    signalId: string,
    weight: number,
    operation: string = "linear",
    k: number = 100.0,
    weightBounds?: { min: number; max: number }
  ) {
    this.signalId = signalId;
    this.weight = weight;
    this.operation = operation;
    this.k = k;
    this.weightBounds = weightBounds;
  }

  toDict(): ProfileInputData {
    const d: ProfileInputData = {
      signal_id: this.signalId,
      weight: this.weight,
      operation: this.operation,
    };
    if (this.operation === "diminishing_returns") {
      d.k = this.k;
    }
    if (this.weightBounds !== undefined) {
      d.weight_bounds = this.weightBounds;
    }
    return d;
  }

  static fromDict(d: ProfileInputData): ProfileInput {
    return new ProfileInput(
      d.signal_id,
      d.weight,
      d.operation ?? "linear",
      d.k ?? 100.0,
      d.weight_bounds
    );
  }
}

export class Gate {
  readonly signalId: string;
  readonly threshold: number;
  readonly gateType: string;

  constructor(
    signalId: string,
    threshold: number,
    gateType: string = "minimum"
  ) {
    this.signalId = signalId;
    this.threshold = threshold;
    this.gateType = gateType;
  }

  evaluate(value: number): boolean {
    if (this.gateType === "minimum") return value >= this.threshold;
    if (this.gateType === "maximum") return value <= this.threshold;
    return true;
  }

  toDict(): GateData {
    return {
      signal_id: this.signalId,
      threshold: this.threshold,
      gate_type: this.gateType,
    };
  }

  static fromDict(d: GateData): Gate {
    return new Gate(d.signal_id, d.threshold, d.gate_type ?? "minimum");
  }
}

export class PenaltyFloor {
  readonly signalId: string;
  readonly floor: number;
  readonly maxPenalty: number;

  constructor(signalId: string, floor: number, maxPenalty: number) {
    this.signalId = signalId;
    this.floor = floor;
    this.maxPenalty = maxPenalty;
  }

  computePenalty(rawValue: number): number {
    if (rawValue >= this.floor) return 0.0;
    return this.maxPenalty * (this.floor - rawValue) / this.floor;
  }

  toDict(): PenaltyFloorData {
    return {
      signal_id: this.signalId,
      floor: this.floor,
      max_penalty: this.maxPenalty,
    };
  }

  static fromDict(d: PenaltyFloorData): PenaltyFloor {
    return new PenaltyFloor(d.signal_id, d.floor, d.max_penalty);
  }
}

export interface WeightProfileOptions {
  profileId: string;
  version?: string;
  description?: string;
  inputs?: ProfileInput[];
  gates?: Gate[];
  penaltyFloors?: PenaltyFloor[];
  outputRange?: [number, number];
  rotationSchedule?: string;
  governanceApproved?: string;
  effectiveUntil?: string;
}

export class WeightProfile {
  readonly profileId: string;
  readonly version: string;
  readonly description: string;
  readonly inputs: ProfileInput[];
  readonly gates: Gate[];
  readonly penaltyFloors: PenaltyFloor[];
  readonly outputRange: [number, number];
  readonly rotationSchedule: string;
  readonly governanceApproved: string;
  readonly effectiveUntil: string;

  constructor(opts: WeightProfileOptions) {
    this.profileId = opts.profileId;
    this.version = opts.version ?? "";
    this.description = opts.description ?? "";
    this.inputs = opts.inputs ?? [];
    this.gates = opts.gates ?? [];
    this.penaltyFloors = opts.penaltyFloors ?? [];
    this.outputRange = opts.outputRange ?? [0, 100];
    this.rotationSchedule = opts.rotationSchedule ?? "quarterly";
    this.governanceApproved = opts.governanceApproved ?? "";
    this.effectiveUntil = opts.effectiveUntil ?? "";
  }

  toDict(): WeightProfileData {
    return {
      profile_id: this.profileId,
      version: this.version,
      description: this.description,
      inputs: this.inputs.map((i) => i.toDict()),
      gates: this.gates.map((g) => g.toDict()),
      penalty_floors: this.penaltyFloors.map((pf) => pf.toDict()),
      output_range: [...this.outputRange],
      rotation_schedule: this.rotationSchedule,
      governance_approved: this.governanceApproved,
      effective_until: this.effectiveUntil,
    };
  }

  toJson(): string {
    return JSON.stringify(this.toDict());
  }

  static fromDict(d: WeightProfileData): WeightProfile {
    const outRange = d.output_range ?? [0, 100];
    return new WeightProfile({
      profileId: d.profile_id,
      version: d.version ?? "",
      description: d.description ?? "",
      inputs: (d.inputs ?? []).map((i) => ProfileInput.fromDict(i)),
      gates: (d.gates ?? []).map((g) => Gate.fromDict(g)),
      penaltyFloors: (d.penalty_floors ?? []).map((pf) =>
        PenaltyFloor.fromDict(pf)
      ),
      outputRange: [outRange[0], outRange[1]],
      rotationSchedule: d.rotation_schedule ?? "quarterly",
      governanceApproved: d.governance_approved ?? "",
      effectiveUntil: d.effective_until ?? "",
    });
  }

  static fromJson(s: string): WeightProfile {
    return WeightProfile.fromDict(JSON.parse(s));
  }
}

export class CompositeSignal {
  readonly profileId: string;
  readonly value: number;
  readonly confidence: number;
  readonly inputCount: number;
  readonly weakestInput: { signal_id: string; confidence: number } | undefined;
  readonly gateStatus: string;
  readonly computedAt: string;
  readonly validUntil: string;
  readonly computedBy: string;

  constructor(opts: {
    profileId: string;
    value: number;
    confidence: number;
    inputCount: number;
    weakestInput?: { signal_id: string; confidence: number };
    gateStatus?: string;
    computedAt?: string;
    validUntil?: string;
    computedBy?: string;
  }) {
    this.profileId = opts.profileId;
    this.value = opts.value;
    this.confidence = opts.confidence;
    this.inputCount = opts.inputCount;
    this.weakestInput = opts.weakestInput;
    this.gateStatus = opts.gateStatus ?? "all_passed";
    this.computedAt = opts.computedAt ?? new Date().toISOString();
    this.computedBy = opts.computedBy ?? "";

    if (opts.validUntil) {
      this.validUntil = opts.validUntil;
    } else {
      const d = new Date();
      d.setDate(d.getDate() + 7);
      this.validUntil = d.toISOString();
    }
  }

  isValid(): boolean {
    try {
      const until = new Date(this.validUntil.replace("Z", "+00:00"));
      return new Date() <= until;
    } catch {
      return false;
    }
  }

  toDict(): CompositeSignalData {
    const d: CompositeSignalData = {
      profile_id: this.profileId,
      value: Math.round(this.value * 100) / 100,
      confidence: Math.round(this.confidence * 10000) / 10000,
      input_count: this.inputCount,
      gate_status: this.gateStatus,
      computed_at: this.computedAt,
      valid_until: this.validUntil,
    };
    if (this.weakestInput) {
      d.weakest_input = this.weakestInput;
    }
    if (this.computedBy) {
      d.computed_by = this.computedBy;
    }
    return d;
  }
}

export function diminishingReturnsTransform(
  value: number,
  k: number
): number {
  if (k <= 0) throw new Error("k must be positive");
  return 100.0 * (1.0 - Math.exp(-value / k));
}

export function compose(
  signals: Signal[],
  profile: WeightProfile,
  computedBy: string = "",
  validityDays: number = 7
): CompositeSignal {
  const sigMap = new Map<string, Signal>();
  for (const s of signals) sigMap.set(s.signalId, s);

  // Step 1: Gates
  const failedGates: string[] = [];
  for (const gate of profile.gates) {
    const sig = sigMap.get(gate.signalId);
    if (!sig) {
      failedGates.push(`${gate.signalId}: missing signal`);
      continue;
    }
    if (!gate.evaluate(sig.value)) {
      failedGates.push(
        `${gate.signalId}: ${sig.value} fails ${gate.gateType} threshold ${gate.threshold}`
      );
    }
  }

  if (failedGates.length > 0) {
    const now = new Date();
    const validUntil = new Date(now);
    validUntil.setDate(validUntil.getDate() + validityDays);
    return new CompositeSignal({
      profileId: profile.profileId,
      value: -1.0,
      confidence: 0.0,
      inputCount: signals.length,
      gateStatus: `failed: ${failedGates.join("; ")}`,
      computedAt: now.toISOString(),
      validUntil: validUntil.toISOString(),
      computedBy: computedBy,
    });
  }

  // Step 2: Diminishing returns transform
  const transformed = new Map<string, number>();
  for (const inp of profile.inputs) {
    const sig = sigMap.get(inp.signalId);
    if (!sig) continue;
    if (inp.operation === "diminishing_returns") {
      transformed.set(
        inp.signalId,
        diminishingReturnsTransform(sig.value, inp.k)
      );
    } else {
      transformed.set(inp.signalId, sig.value);
    }
  }

  // Steps 3 & 4: Confidence-adjusted weighted combination
  let weightedSum = 0;
  let weightSum = 0;
  let weakestInput: { signal_id: string; confidence: number } | undefined;
  let weakestConfidence = Infinity;
  let inputCount = 0;

  for (const inp of profile.inputs) {
    const sig = sigMap.get(inp.signalId);
    if (!sig) continue;
    inputCount++;

    const val = transformed.get(inp.signalId) ?? sig.value;
    let w: number;
    if (inp.operation === "confidence_adjusted") {
      w = inp.weight * sig.confidence;
    } else {
      w = inp.weight;
    }
    weightedSum += w * val;
    weightSum += w;

    if (sig.confidence < weakestConfidence) {
      weakestConfidence = sig.confidence;
      weakestInput = {
        signal_id: inp.signalId,
        confidence: sig.confidence,
      };
    }
  }

  let rawComposite = weightSum === 0 ? 0 : weightedSum / weightSum;

  // Step 5: Penalty floors
  let totalPenalty = 0;
  for (const pf of profile.penaltyFloors) {
    const sig = sigMap.get(pf.signalId);
    if (!sig) continue;
    totalPenalty += pf.computePenalty(sig.value);
  }

  let final = Math.max(profile.outputRange[0], rawComposite - totalPenalty);
  final = Math.min(profile.outputRange[1], final);

  // Composite confidence
  let confSum = 0;
  let confWeight = 0;
  for (const inp of profile.inputs) {
    const sig = sigMap.get(inp.signalId);
    if (!sig) continue;
    confSum += inp.weight * sig.confidence;
    confWeight += inp.weight;
  }
  const compositeConfidence = confWeight > 0 ? confSum / confWeight : 0;

  const now = new Date();
  const validUntil = new Date(now);
  validUntil.setDate(validUntil.getDate() + validityDays);

  return new CompositeSignal({
    profileId: profile.profileId,
    value: final,
    confidence: compositeConfidence,
    inputCount,
    weakestInput,
    gateStatus: "all_passed",
    computedAt: now.toISOString(),
    validUntil: validUntil.toISOString(),
    computedBy: computedBy,
  });
}

// Standard weight profiles
function standardGates(): Gate[] {
  return [
    new Gate("arp:total_ratings_received", 5, "minimum"),
    new Gate("coc:operational_age_days", 7, "minimum"),
  ];
}

function standardPenaltyFloors(): PenaltyFloor[] {
  return [
    new PenaltyFloor("arp:reliability:weighted_mean", 30, 25),
  ];
}

export const GENERAL_PURPOSE = new WeightProfile({
  profileId: "urn:absupport:arp:v2:profile:general-purpose",
  version: "2026-Q1",
  description: "General-purpose agent trust composite",
  inputs: [
    new ProfileInput("arp:reliability:weighted_mean", 0.25, "confidence_adjusted"),
    new ProfileInput("arp:accuracy:weighted_mean", 0.25, "confidence_adjusted"),
    new ProfileInput("arp:latency:weighted_mean", 0.10, "confidence_adjusted"),
    new ProfileInput("arp:protocol_compliance:weighted_mean", 0.15, "confidence_adjusted"),
    new ProfileInput("arp:cost_efficiency:weighted_mean", 0.10, "confidence_adjusted"),
    new ProfileInput("coc:operational_age_days", 0.10, "diminishing_returns", 365),
    new ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
  ],
  gates: standardGates(),
  penaltyFloors: standardPenaltyFloors(),
  rotationSchedule: "quarterly",
});

export const HIGH_RELIABILITY = new WeightProfile({
  profileId: "urn:absupport:arp:v2:profile:high-reliability",
  version: "2026-Q1",
  description: "High-reliability for infrastructure and payments",
  inputs: [
    new ProfileInput("arp:reliability:weighted_mean", 0.40, "confidence_adjusted"),
    new ProfileInput("arp:accuracy:weighted_mean", 0.25, "confidence_adjusted"),
    new ProfileInput("arp:latency:weighted_mean", 0.05, "confidence_adjusted"),
    new ProfileInput("arp:protocol_compliance:weighted_mean", 0.10, "confidence_adjusted"),
    new ProfileInput("arp:cost_efficiency:weighted_mean", 0.05, "confidence_adjusted"),
    new ProfileInput("coc:operational_age_days", 0.10, "diminishing_returns", 365),
    new ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
  ],
  gates: standardGates(),
  penaltyFloors: [
    new PenaltyFloor("arp:reliability:weighted_mean", 50, 30),
  ],
  rotationSchedule: "quarterly",
});

export const FAST_TURNAROUND = new WeightProfile({
  profileId: "urn:absupport:arp:v2:profile:fast-turnaround",
  version: "2026-Q1",
  description: "Fast turnaround for content and translation",
  inputs: [
    new ProfileInput("arp:reliability:weighted_mean", 0.15, "confidence_adjusted"),
    new ProfileInput("arp:accuracy:weighted_mean", 0.25, "confidence_adjusted"),
    new ProfileInput("arp:latency:weighted_mean", 0.30, "confidence_adjusted"),
    new ProfileInput("arp:protocol_compliance:weighted_mean", 0.10, "confidence_adjusted"),
    new ProfileInput("arp:cost_efficiency:weighted_mean", 0.05, "confidence_adjusted"),
    new ProfileInput("coc:operational_age_days", 0.10, "diminishing_returns", 365),
    new ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
  ],
  gates: standardGates(),
  penaltyFloors: standardPenaltyFloors(),
  rotationSchedule: "quarterly",
});

export const COMPLIANCE_FIRST = new WeightProfile({
  profileId: "urn:absupport:arp:v2:profile:compliance-first",
  version: "2026-Q1",
  description: "Compliance-first for regulated industries",
  inputs: [
    new ProfileInput("arp:reliability:weighted_mean", 0.15, "confidence_adjusted"),
    new ProfileInput("arp:accuracy:weighted_mean", 0.25, "confidence_adjusted"),
    new ProfileInput("arp:latency:weighted_mean", 0.05, "confidence_adjusted"),
    new ProfileInput("arp:protocol_compliance:weighted_mean", 0.35, "confidence_adjusted"),
    new ProfileInput("arp:cost_efficiency:weighted_mean", 0.05, "confidence_adjusted"),
    new ProfileInput("coc:operational_age_days", 0.10, "diminishing_returns", 365),
    new ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
  ],
  gates: standardGates(),
  penaltyFloors: [
    new PenaltyFloor("arp:protocol_compliance:weighted_mean", 50, 30),
  ],
  rotationSchedule: "quarterly",
});

export const COST_OPTIMIZED = new WeightProfile({
  profileId: "urn:absupport:arp:v2:profile:cost-optimized",
  version: "2026-Q1",
  description: "Cost-optimized for bulk processing",
  inputs: [
    new ProfileInput("arp:reliability:weighted_mean", 0.25, "confidence_adjusted"),
    new ProfileInput("arp:accuracy:weighted_mean", 0.15, "confidence_adjusted"),
    new ProfileInput("arp:latency:weighted_mean", 0.10, "confidence_adjusted"),
    new ProfileInput("arp:protocol_compliance:weighted_mean", 0.10, "confidence_adjusted"),
    new ProfileInput("arp:cost_efficiency:weighted_mean", 0.30, "confidence_adjusted"),
    new ProfileInput("coc:operational_age_days", 0.05, "diminishing_returns", 365),
    new ProfileInput("behavioral:rating_participation_rate", 0.05, "linear"),
  ],
  gates: standardGates(),
  penaltyFloors: standardPenaltyFloors(),
  rotationSchedule: "quarterly",
});

export const STANDARD_PROFILES: Record<string, WeightProfile> = {
  "general-purpose": GENERAL_PURPOSE,
  "high-reliability": HIGH_RELIABILITY,
  "fast-turnaround": FAST_TURNAROUND,
  "compliance-first": COMPLIANCE_FIRST,
  "cost-optimized": COST_OPTIMIZED,
};

export function getProfile(name: string): WeightProfile {
  const profile = STANDARD_PROFILES[name];
  if (!profile) {
    throw new Error(
      `Unknown profile '${name}'. Available: ${Object.keys(STANDARD_PROFILES).join(", ")}`
    );
  }
  return profile;
}
