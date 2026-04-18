export type Mode = 'generate' | 'verify';

export interface VerificationResult {
  verified: boolean;
  consistent?: boolean;
  tamper_risk: boolean;
  integrity?: 'original' | 'transformed' | 'none';
  phash_distance?: number;
  semantic_fingerprint?: {
    match: boolean;
    correlation: number;
  };
  zk_proof_valid?: boolean | null;
  zk_proof_on_chain?: boolean;
  status?: string;
  message?: string;
  short_id?: string;
  uploaded_phash?: number;
  contract_address?: string;
  on_chain: {
    image_hash: string;
    perceptual_hash: number;
    proof_verified_on_chain: boolean;
    registrant: string;
    timestamp: number;
    explorer_url: string;
  } | null;
  generation: {
    model: string;
    prompt: string | null;
    generated_at: string | null;
  } | null;
}

export interface AIModel {
  id: string;
  name: string;
  provider: string;
}
