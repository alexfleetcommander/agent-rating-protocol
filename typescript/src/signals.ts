import { createHash } from "node:crypto";
import { SignalTier, VerificationLevel } from "./types";

export { SignalTier, VerificationLevel };

export const DEFAULT_TIER_MAP: Record<string, SignalTier> = {
  operational_age: SignalTier.PUBLIC,
  total_interactions: SignalTier.PUBLIC,
  tier_level: SignalTier.PUBLIC,
  composite_score: SignalTier.QUERYABLE,
  dimension_averages: SignalTier.QUERYABLE,
  rating_confidence: SignalTier.QUERYABLE,
  calibration_scores: SignalTier.PRIVATE,
  collusion_flags: SignalTier.PRIVATE,
  shadow_metrics: SignalTier.PRIVATE,
  rotation_parameters: SignalTier.PRIVATE,
};

export interface HashChainVerificationData {
  rating_id: string;
  exists: boolean;
  hash_valid: boolean;
  timestamp_verified: boolean;
  level: string;
  error?: string;
}

export class HashChainVerification {
  readonly ratingId: string;
  readonly exists: boolean;
  readonly hashValid: boolean;
  readonly timestampVerified: boolean;
  readonly error: string;

  constructor(opts: {
    ratingId: string;
    exists: boolean;
    hashValid: boolean;
    timestampVerified?: boolean;
    error?: string;
  }) {
    this.ratingId = opts.ratingId;
    this.exists = opts.exists;
    this.hashValid = opts.hashValid;
    this.timestampVerified = opts.timestampVerified ?? false;
    this.error = opts.error ?? "";
  }

  toDict(): HashChainVerificationData {
    const d: HashChainVerificationData = {
      rating_id: this.ratingId,
      exists: this.exists,
      hash_valid: this.hashValid,
      timestamp_verified: this.timestampVerified,
      level: VerificationLevel.BASIC,
    };
    if (this.error) d.error = this.error;
    return d;
  }
}

export function verifyHashChain(
  recordHash: string,
  computedHash: string,
  ratingId: string = ""
): HashChainVerification {
  if (!recordHash || !computedHash) {
    return new HashChainVerification({
      ratingId,
      exists: false,
      hashValid: false,
      error: "Missing hash data",
    });
  }
  return new HashChainVerification({
    ratingId,
    exists: true,
    hashValid: recordHash === computedHash,
  });
}

export interface MerkleProofData {
  leaf_hash: string;
  proof_hashes: Array<{ hash: string; side: string }>;
  root_hash: string;
}

export class MerkleProof {
  readonly leafHash: string;
  readonly proofHashes: Array<[string, string]>;
  readonly rootHash: string;

  constructor(
    leafHash: string,
    proofHashes: Array<[string, string]>,
    rootHash: string
  ) {
    this.leafHash = leafHash;
    this.proofHashes = proofHashes;
    this.rootHash = rootHash;
  }

  toDict(): MerkleProofData {
    return {
      leaf_hash: this.leafHash,
      proof_hashes: this.proofHashes.map(([h, s]) => ({ hash: h, side: s })),
      root_hash: this.rootHash,
    };
  }
}

export class MerkleTree {
  private _root: string;
  private _layers: string[][];

  constructor(leaves: string[]) {
    if (leaves.length === 0) {
      this._root = createHash("sha256").update("empty").digest("hex");
      this._layers = [[this._root]];
      return;
    }
    this._layers = [[...leaves]];
    this._root = "";
    this._build([...leaves]);
  }

  private _build(leaves: string[]): void {
    let current = [...leaves];
    while (current.length > 1) {
      const nextLayer: string[] = [];
      for (let i = 0; i < current.length; i += 2) {
        const left = Buffer.from(current[i], "hex");
        const rightIdx = i + 1 < current.length ? i + 1 : i;
        const right = Buffer.from(current[rightIdx], "hex");
        const parent = createHash("sha256")
          .update(Buffer.concat([left, right]))
          .digest("hex");
        nextLayer.push(parent);
      }
      this._layers.push(nextLayer);
      current = nextLayer;
    }
    this._root = current[0];
  }

  get root(): string {
    return this._root;
  }

  get leafCount(): number {
    return this._layers[0].length;
  }

  getProof(leafIndex: number): MerkleProof {
    if (leafIndex < 0 || leafIndex >= this._layers[0].length) {
      throw new RangeError(
        `Leaf index ${leafIndex} out of range [0, ${this._layers[0].length})`
      );
    }

    const proofHashes: Array<[string, string]> = [];
    let idx = leafIndex;

    for (let li = 0; li < this._layers.length - 1; li++) {
      const layer = this._layers[li];
      if (idx % 2 === 0) {
        const sibIdx = idx + 1 < layer.length ? idx + 1 : idx;
        proofHashes.push([layer[sibIdx], "right"]);
      } else {
        proofHashes.push([layer[idx - 1], "left"]);
      }
      idx = Math.floor(idx / 2);
    }

    return new MerkleProof(
      this._layers[0][leafIndex],
      proofHashes,
      this._root
    );
  }
}

export function verifyMerkleProof(proof: MerkleProof): boolean {
  let current = Buffer.from(proof.leafHash, "hex");

  for (const [siblingHex, side] of proof.proofHashes) {
    const sibling = Buffer.from(siblingHex, "hex");
    if (side === "left") {
      current = createHash("sha256")
        .update(Buffer.concat([sibling, current]))
        .digest();
    } else {
      current = createHash("sha256")
        .update(Buffer.concat([current, sibling]))
        .digest();
    }
  }

  return current.toString("hex") === proof.rootHash;
}

export interface MerkleVerificationResultData {
  root_hash_matches: boolean;
  proofs_verified: number;
  proofs_failed: number;
  sample_size: number;
  total_ratings: number;
  level: string;
}

export class MerkleVerificationResult {
  readonly rootHashMatches: boolean;
  readonly proofsVerified: number;
  readonly proofsFailed: number;
  readonly sampleSize: number;
  readonly totalRatings: number;
  readonly level: string;

  constructor(opts: {
    rootHashMatches: boolean;
    proofsVerified: number;
    proofsFailed: number;
    sampleSize: number;
    totalRatings: number;
  }) {
    this.rootHashMatches = opts.rootHashMatches;
    this.proofsVerified = opts.proofsVerified;
    this.proofsFailed = opts.proofsFailed;
    this.sampleSize = opts.sampleSize;
    this.totalRatings = opts.totalRatings;
    this.level = VerificationLevel.STANDARD;
  }

  toDict(): MerkleVerificationResultData {
    return {
      root_hash_matches: this.rootHashMatches,
      proofs_verified: this.proofsVerified,
      proofs_failed: this.proofsFailed,
      sample_size: this.sampleSize,
      total_ratings: this.totalRatings,
      level: this.level,
    };
  }
}

export function verifyPrbMerkle(
  claimedRoot: string,
  ratingHashes: string[],
  sampleSize: number = 50
): MerkleVerificationResult {
  if (ratingHashes.length === 0) {
    return new MerkleVerificationResult({
      rootHashMatches: false,
      proofsVerified: 0,
      proofsFailed: 0,
      sampleSize: 0,
      totalRatings: 0,
    });
  }

  const tree = new MerkleTree(ratingHashes);
  const rootMatches = tree.root === claimedRoot;
  const total = ratingHashes.length;

  let indices: number[];
  if (sampleSize <= 0 || sampleSize >= total) {
    indices = Array.from({ length: total }, (_, i) => i);
  } else {
    const all = Array.from({ length: total }, (_, i) => i);
    indices = [];
    for (let i = all.length - 1; i > 0 && indices.length < sampleSize; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [all[i], all[j]] = [all[j], all[i]];
      indices.push(all[i]);
    }
    if (indices.length < sampleSize) indices.push(all[0]);
  }

  let verified = 0;
  let failed = 0;
  for (const idx of indices) {
    const proof = tree.getProof(idx);
    if (verifyMerkleProof(proof)) {
      verified++;
    } else {
      failed++;
    }
  }

  return new MerkleVerificationResult({
    rootHashMatches: rootMatches,
    proofsVerified: verified,
    proofsFailed: failed,
    sampleSize: indices.length,
    totalRatings: total,
  });
}

export interface ZKPThresholdProofData {
  public_inputs: Record<string, unknown>;
  valid_until: string;
  proof_system: string;
  proof_value: string;
  level: string;
}

export class ZKPThresholdProof {
  readonly thresholdComposite: number;
  readonly thresholdDimension: number | undefined;
  readonly thresholdDimensionName: string | undefined;
  readonly ratingsRootHash: string;
  readonly validUntil: string;
  readonly proofSystem: string;
  readonly proofValue: string;

  constructor(opts: {
    thresholdComposite: number;
    thresholdDimension?: number;
    thresholdDimensionName?: string;
    ratingsRootHash?: string;
    validUntil?: string;
    proofSystem?: string;
    proofValue?: string;
  }) {
    this.thresholdComposite = opts.thresholdComposite;
    this.thresholdDimension = opts.thresholdDimension;
    this.thresholdDimensionName = opts.thresholdDimensionName;
    this.ratingsRootHash = opts.ratingsRootHash ?? "";
    this.validUntil = opts.validUntil ?? "";
    this.proofSystem = opts.proofSystem ?? "placeholder";
    this.proofValue = opts.proofValue ?? "";
  }

  toDict(): ZKPThresholdProofData {
    const publicInputs: Record<string, unknown> = {
      threshold_composite: this.thresholdComposite,
      ratingsRootHash: this.ratingsRootHash,
    };
    if (this.thresholdDimension !== undefined) {
      publicInputs.threshold_dimension = this.thresholdDimension;
      publicInputs.dimension_name = this.thresholdDimensionName;
    }
    return {
      public_inputs: publicInputs,
      valid_until: this.validUntil,
      proof_system: this.proofSystem,
      proof_value: this.proofValue,
      level: VerificationLevel.PRIVACY_PRESERVING,
    };
  }
}

export function createZkpThresholdProof(opts: {
  actualComposite: number;
  thresholdComposite: number;
  ratingsRootHash?: string;
  actualDimension?: number;
  thresholdDimension?: number;
  dimensionName?: string;
}): ZKPThresholdProof {
  if (opts.actualComposite < opts.thresholdComposite) {
    throw new Error(
      `Composite ${opts.actualComposite} does not meet threshold ${opts.thresholdComposite}`
    );
  }
  if (
    opts.actualDimension !== undefined &&
    opts.thresholdDimension !== undefined &&
    opts.actualDimension < opts.thresholdDimension
  ) {
    throw new Error(
      `Dimension ${opts.dimensionName} score ${opts.actualDimension} does not meet threshold ${opts.thresholdDimension}`
    );
  }

  return new ZKPThresholdProof({
    thresholdComposite: opts.thresholdComposite,
    thresholdDimension: opts.thresholdDimension,
    thresholdDimensionName: opts.dimensionName,
    ratingsRootHash: opts.ratingsRootHash,
    proofSystem: "placeholder",
    proofValue: "PLACEHOLDER_NOT_CRYPTOGRAPHIC",
  });
}

export function verifyZkpThresholdProof(
  proof: ZKPThresholdProof
): Record<string, unknown> {
  if (proof.proofSystem === "placeholder") {
    return {
      verified: false,
      level: VerificationLevel.PRIVACY_PRESERVING,
      warning:
        "ZKP verification not available — proof_system is 'placeholder'. " +
        "Real ZKP verification requires Groth16, PLONK, or STARKs " +
        "integration (see ARP v2 Section 5.4).",
      thresholds: proof.toDict().public_inputs,
    };
  }
  return {
    verified: false,
    level: VerificationLevel.PRIVACY_PRESERVING,
    error: `Unsupported proof system: ${proof.proofSystem}`,
  };
}
