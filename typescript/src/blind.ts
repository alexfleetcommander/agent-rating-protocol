import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

export function generateNonce(nbytes: number = 32): string {
  return randomBytes(nbytes).toString("hex");
}

export function commit(
  ratingDict: Record<string, unknown>,
  nonce: string
): string {
  const payload = JSON.stringify(ratingDict, Object.keys(ratingDict).sort());
  const combined = payload + nonce;
  return createHash("sha256").update(combined, "utf-8").digest("hex");
}

export function reveal(
  ratingDict: Record<string, unknown>,
  nonce: string,
  commitment: string
): boolean {
  const computed = commit(ratingDict, nonce);
  if (computed.length !== commitment.length) return false;
  return timingSafeEqual(Buffer.from(computed), Buffer.from(commitment));
}

export interface BlindCommitmentData {
  agent_id: string;
  interaction_id: string;
  commitment_hash: string;
  committed_at: number;
  revealed: boolean;
  rating_dict?: Record<string, unknown>;
}

export class BlindCommitment {
  agentId: string;
  interactionId: string;
  commitmentHash: string;
  committedAt: number;
  revealed: boolean;
  ratingDict: Record<string, unknown> | undefined;
  nonce: string | undefined;

  constructor(
    agentId: string,
    interactionId: string,
    commitmentHash: string,
    committedAt?: number
  ) {
    this.agentId = agentId;
    this.interactionId = interactionId;
    this.commitmentHash = commitmentHash;
    this.committedAt = committedAt ?? Date.now() / 1000;
    this.revealed = false;
  }

  toDict(): BlindCommitmentData {
    const d: BlindCommitmentData = {
      agent_id: this.agentId,
      interaction_id: this.interactionId,
      commitment_hash: this.commitmentHash,
      committed_at: this.committedAt,
      revealed: this.revealed,
    };
    if (this.revealed && this.ratingDict !== undefined) {
      d.rating_dict = this.ratingDict;
    }
    return d;
  }

  static fromDict(d: BlindCommitmentData): BlindCommitment {
    const bc = new BlindCommitment(
      d.agent_id,
      d.interaction_id,
      d.commitment_hash,
      d.committed_at ?? 0
    );
    bc.revealed = d.revealed ?? false;
    bc.ratingDict = d.rating_dict;
    return bc;
  }
}

export interface BlindExchangeData {
  interaction_id: string;
  window_seconds: number;
  created_at: number;
  commitment_a: BlindCommitmentData | null;
  commitment_b: BlindCommitmentData | null;
}

export class BlindExchange {
  readonly interactionId: string;
  readonly windowSeconds: number;
  readonly createdAt: number;
  commitmentA: BlindCommitment | null;
  commitmentB: BlindCommitment | null;

  constructor(interactionId: string, windowSeconds: number = 86400) {
    this.interactionId = interactionId;
    this.windowSeconds = windowSeconds;
    this.createdAt = Date.now() / 1000;
    this.commitmentA = null;
    this.commitmentB = null;
  }

  get bothCommitted(): boolean {
    return this.commitmentA !== null && this.commitmentB !== null;
  }

  get bothRevealed(): boolean {
    return (
      this.commitmentA !== null &&
      this.commitmentA.revealed &&
      this.commitmentB !== null &&
      this.commitmentB.revealed
    );
  }

  get windowExpired(): boolean {
    return Date.now() / 1000 - this.createdAt > this.windowSeconds;
  }

  get revealTriggered(): boolean {
    return this.bothCommitted || this.windowExpired;
  }

  submitCommitment(
    agentId: string,
    ratingDict: Record<string, unknown>,
    nonce: string
  ): BlindCommitment {
    if (this.windowExpired) {
      throw new Error("Commitment window has expired");
    }

    const commitmentHash = commit(ratingDict, nonce);
    const bc = new BlindCommitment(
      agentId,
      this.interactionId,
      commitmentHash
    );

    if (this.commitmentA === null) {
      this.commitmentA = bc;
    } else if (this.commitmentB === null) {
      if (this.commitmentA.agentId === agentId) {
        throw new Error(
          `Agent ${agentId} has already committed to this exchange`
        );
      }
      this.commitmentB = bc;
    } else {
      throw new Error("Both sides have already committed");
    }

    return bc;
  }

  revealRating(
    agentId: string,
    ratingDict: Record<string, unknown>,
    nonce: string
  ): boolean {
    if (!this.revealTriggered) {
      throw new Error(
        "Reveal phase not yet triggered — waiting for both commitments or window expiry"
      );
    }

    const target = this._findCommitment(agentId);
    if (target === null) {
      throw new Error(`No commitment found for agent ${agentId}`);
    }
    if (target.revealed) {
      throw new Error(`Agent ${agentId} has already revealed`);
    }
    if (!reveal(ratingDict, nonce, target.commitmentHash)) {
      throw new Error(
        "Reveal verification failed — rating or nonce does not match commitment"
      );
    }

    target.revealed = true;
    target.ratingDict = ratingDict;
    target.nonce = nonce;
    return true;
  }

  getResults():
    | [Record<string, unknown> | null, Record<string, unknown> | null]
    | null {
    if (!this.revealTriggered) return null;

    const ratingA =
      this.commitmentA?.revealed ? (this.commitmentA.ratingDict ?? null) : null;
    const ratingB =
      this.commitmentB?.revealed ? (this.commitmentB.ratingDict ?? null) : null;

    return [ratingA, ratingB];
  }

  private _findCommitment(agentId: string): BlindCommitment | null {
    if (this.commitmentA && this.commitmentA.agentId === agentId)
      return this.commitmentA;
    if (this.commitmentB && this.commitmentB.agentId === agentId)
      return this.commitmentB;
    return null;
  }

  toDict(): BlindExchangeData {
    return {
      interaction_id: this.interactionId,
      window_seconds: this.windowSeconds,
      created_at: this.createdAt,
      commitment_a: this.commitmentA?.toDict() ?? null,
      commitment_b: this.commitmentB?.toDict() ?? null,
    };
  }

  static fromDict(d: BlindExchangeData): BlindExchange {
    const ex = new BlindExchange(
      d.interaction_id,
      d.window_seconds ?? 86400
    );
    (ex as { createdAt: number }).createdAt = d.created_at ?? Date.now() / 1000;
    if (d.commitment_a) {
      ex.commitmentA = BlindCommitment.fromDict(d.commitment_a);
    }
    if (d.commitment_b) {
      ex.commitmentB = BlindCommitment.fromDict(d.commitment_b);
    }
    return ex;
  }
}
