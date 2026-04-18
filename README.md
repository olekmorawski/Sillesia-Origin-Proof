# Proof of Origin

Cryptographic provenance for AI-generated images. Every image gets watermarked, ZK-proven, registered on-chain, and permanently anchored to Arweave — so anyone can verify **where it came from** and **whether it's been changed**, even after screenshots, crops, or AI regeneration.

---

## The Problem

AI-generated images are indistinguishable from real photos. Metadata is trivially stripped. There is no built-in way to tell if an image you see on the internet is:

1. **Authentic** — did it come from the system that claims it?
2. **Unmodified** — is it the exact original, or a screenshot / crop / edit?
3. **Verifiable** — can someone check this without trusting a central backend?

Existing solutions fail because they rely on a single layer (EXIF metadata, a database lookup, a reversible watermark) that breaks the moment the image is re-encoded.

---

## The Solution

Proof of Origin answers all three questions with **five independent verification layers**, each surviving different attack vectors:

| Layer | What it proves | Survives | Fails when |
|-------|---------------|----------|------------|
| **0 — Semantic fingerprint** | Structural identity (DWT-DCT-SVD) | AI regeneration (img2img), aggressive JPEG, screenshots | Complete repaint / unrelated image |
| **1 — Neural watermark** | Pixel-level steganography (TrustMark) | JPEG, resize, format conversion | Pixel-level destruction, aggressive crop |
| **2 — C2PA manifest** | Signed Content Credential (soft-binding) | Lossless copies | Stripped by JPEG re-encode |
| **3 — ZK proof on-chain** | Cryptographic binding of watermark + pixels + pHash | Anything — proof is immutable on-chain | Invalid proof (tampering) |
| **4 — Arweave anchor** | Permanent storage of full provenance | Server disappearance | — |

No single layer is sufficient. Together they form a **defence-in-depth** system where breaking provenance requires defeating watermarks, cryptographic proofs, and permanent storage simultaneously.

### Short-ID recovery chain

The verification pipeline needs to recover a `short_id` before it can look the image up on-chain. The endpoint tries three recovery paths in order and stops at the first hit:

| # | Path | Mechanism | Survives | Trust assumption |
|---|------|-----------|----------|------------------|
| 1 | `verify_lsb`  | TrustMark neural watermark decode | JPEG, resize, format conversion | None — purely client-verifiable with the TrustMark library |
| 2 | `verify_exif` | PNG iTXt metadata chunk | Lossless PNG copies | None — embedded in the file |
| 3 | `phash_proximity` | Scan SQLite `images` table for rows within Hamming distance ≤ 15 of the uploaded DINOv2 pHash | Aggressive crop, heavy re-encoding, screenshot that wiped the neural watermark | **Requires this backend.** The trustless on-chain path below needs a `short_id` already in hand. |

If all three paths fail, the response returns `verified: false, tamper_risk: true` — either the image was never registered, or every recovery signal was destroyed.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FASTAPI  (/generate)                         │
│                                                                     │
│  prompt ──► generate_image() ──► raw PNG                            │
│                │                                                      │
│                ▼                                                      │
│           dual_watermark() ──► watermarked PNG                        │
│           ├─ Layer 0: DWT-DCT-SVD semantic fingerprint                │
│           ├─ Layer 1: TrustMark neural watermark (16-char short_id)   │
│           └─ Layer 2: PNG iTXt metadata chunk                         │
│                │                                                      │
│                ▼                                                      │
│           sign_with_c2pa() ──► C2PA-signed PNG                        │
│                │                                                      │
│                ▼                                                      │
│       compute_phash() + sha256_hash() ──► hashes                      │
│                │                                                      │
│                ▼                                                      │
│     insert_image_and_job() ──► SQLite  (images + outbox_jobs)         │
│                │                                                      │
│                ▼                                                      │
│     _arq_pool.enqueue_job() ──► Redis queue                           │
│                                                                     │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ARQ  WORKER  (process_registration)              │
│                                                                     │
│  Step 1: createPlaceholder(watermark_id)                             │
│           ──► reserves on-chain slot (~45k gas, fast)                │
│                                                                     │
│  Step 2: completeRegistration(short_id, sha256, phash, zk_proof)     │
│           ──► fills in hash + optional ZK proof                      │
│           ──► calls Verifier.verify() on-chain, reverts if invalid    │
│                                                                     │
│  Step 3: upload_provenance() ──► Arweave via Irys                    │
│           ──► permanent anchor at gateway.irys.xyz/<tx_id>            │
│                                                                     │
│  Each step is idempotent — crash-resume via SQLite job status.       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        FASTAPI  (/verify)                           │
│                                                                     │
│  uploaded image ──► sha256_hash() + compute_phash()                 │
│         │                                                           │
│         ▼  short_id recovery — try in order, stop at first hit      │
│    1. verify_lsb()            TrustMark neural watermark            │
│    2. verify_exif()           PNG iTXt metadata chunk               │
│    3. get_images_by_phash_    SQLite scan for rows within           │
│       proximity(≤15)          Hamming distance ≤ 15 (backend-only)  │
│         │                                                           │
│         ▼  (short_id recovered)                                     │
│    verify_on_chain(short_id)      ──► on-chain record               │
│    verify_semantic(short_id)      ──► DWT-DCT-SVD correlation       │
│    verify_proof_local(short_id)   ──► ZK verify (optional)          │
│         │                                                           │
│         ▼  integrity classification                                 │
│    sha256(upload) == on_chain.imageHash         → "original"        │
│    pHash distance < 15 but sha256 differs       → "transformed"     │
│    pHash distance ≥ 15                          → "none"            │
│                                                                     │
│  Returns: verified, integrity, phash_distance,                      │
│           semantic_fingerprint, zk_proof_valid, on_chain{},         │
│           generation{}                                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Design Decisions

### Why SQLite outbox instead of in-memory dicts?

The original implementation stored images, metadata, and registration status in Python dicts that vanished on server restart. The **outbox pattern** replaces them with a SQLite database (WAL mode for concurrent reads/writes) that provides:

- **Crash recovery** — if the server dies after watermarking but before blockchain registration, the job row guarantees the ARQ worker picks it up on restart
- **Atomic writes** — `insert_image_and_job()` inserts both rows in a single transaction; either both succeed or neither does
- **Persistent verification** — `/verify` can look up any image ever generated, not just ones from the current server session
- **Two-ID lookups** — `/verify` receives only `short_id` (from watermark decode), so `get_image_by_short_id()` and `get_job_by_short_id()` join across the images and outbox_jobs tables

### Why ARQ worker instead of FastAPI BackgroundTasks?

`BackgroundTasks` runs in the same process as FastAPI and offers no retry, no crash recovery, and no concurrency control. **ARQ** (async Redis queue) gives:

- **Retry with backoff** — blockchain transactions fail (nonce gaps, gas spikes); ARQ retries up to 5 times with exponential backoff
- **Crash-resume idempotence** — each of the 3 steps checks the current job status in SQLite and resumes from the last incomplete step
- **Separation of concerns** — the `/generate` endpoint returns in <2 seconds; the worker handles the slow blockchain + ZK + Arweave steps independently
- **Observability** — Redis stores job results, attempt counts, and errors

### Why two-phase blockchain registration?

If the server died between image generation and transaction submission, the image was watermarked but never registered. The two-phase flow eliminates this:

1. **`createPlaceholder(watermark_id)`** — fast (~45k gas), reserves the slot immediately. Called as the **first** worker step, before any expensive computation.
2. **`completeRegistration(...)`** — fills in the SHA-256, perceptual hash, and optional ZK proof. Safe to retry: a second call reverts with "Already registered", which the worker catches and marks the job done.

This means the crash window is **before step 1** (nothing lost — image is in SQLite) and **between steps 1–2** (slot reserved, registration completes on retry).

### Why ZK proofs at all?

A blockchain record alone only proves that *someone* registered *something*. A ZK proof adds cryptographic certainty:

- The prover knew the `short_id`, the exact SHA-256 of the image, and the perceptual hash **at the same time**
- The proof is bound to a specific `(short_id, image)` pair — it cannot be transplanted to a different image
- The Solidity verifier contract calls `Verifier.verify(zkProof, zkInstances)` **on-chain**; the transaction reverts if the proof is invalid
- If registration succeeded with `proofVerifiedOnChain = true`, the blockchain itself verified the proof — not just stored a hash

The circuit uses **Poseidon** (ZK-native sponge hash) via ezkl's `input_visibility = hashed` setting, which is cryptographically sound and far more efficient than the previous CommitmentNet MLP approach.

### Why Irys for permanent storage?

Blockchain records are permanent but expensive to store and limited in size. Irys provides **permanent, cheap storage** for the full provenance JSON (prompt, model, timestamp, tx_hash, hashes). The Irys JS SDK handles the upload via a Node.js subprocess bridge, keeping the Python codebase clean.

Combined with the on-chain record, this means:
- **On-chain**: cryptographic verification (ZK proof, hashes, timestamp)
- **Irys**: human-readable provenance (what was generated, when, with which model)
- **Both are permanent** — neither depends on this server existing

### Why C2PA manifest signing?

C2PA (Content Authenticity Initiative) is the industry standard for "Content Credentials" — a signed manifest attached to media files. It's a **soft-binding** layer:

- Strippable by JPEG re-encode (same limitation as PNG iTXt metadata)
- But combined with the Irys anchor, it provides a **recovery path**: if the C2PA signature is present, any C2PA-aware tool (Adobe, browsers) can verify it without running our backend
- Uses ES256 elliptic-curve signing with a self-generated certificate
- Graceful fallback: if `c2pa_cert_pem` / `c2pa_private_key_pem` are not configured, signing is skipped and the pipeline continues

### Why DINOv2 for perceptual hashing?

DINOv2 (Vision Transformer) provides:

- **Semantic similarity** — two images that "look the same" to a human also produce similar DINOv2 embeddings, even after AI regeneration
- **Binarized output** — 384-dimensional CLS token → select 64 dimensions → threshold at mean → 64-bit integer
- **`DINO_DIM_MASK`** — a protocol constant (64 evenly-spaced indices from 0..383) that must never change, or all registered hashes become invalid

DINOv2 ViT-S/14 is the active implementation. The model is loaded once from `torch.hub` on first use and runs on CPU; no gated access is required (DINOv2 weights are public).

### Why Semantic Watermarking (DWT-DCT-SVD)?

Traditional watermarks embed data in pixel values and break under AI regeneration. The **semantic frequency-domain** approach is different:

```
image ──► DWT (2-level Haar wavelet decomposition)
      ──► extract HL sub-band (horizontal edge/texture coefficients)
      ──► SVD decomposition ──► singular values S[i]
      ──► quantize S[i] to embed watermark bits
      ──► inverse SVD + inverse DWT ──► imperceptible fingerprint
```

The watermark lives in the **statistical correlations between textures and light**, not in individual pixels. When a diffusion model regenerates a watermarked image, it preserves the structural layout — edges, textures, lighting — so the watermark survives.

Verification returns a **bit correlation score** (0.0–1.0). A correlation ≥ 0.70 indicates the semantic fingerprint survived transformation.

### Why three security layers?

No single watermark survives all attacks. Three layers provide **defence-in-depth**:

- **Layer 0 (Semantic)** survives AI regeneration — the strongest attack
- **Layer 1 (TrustMark)** survives JPEG compression and resize — the most common transforms
- **Layer 2 (PNG iTXt)** provides human-readable provenance and C2PA integration — the easiest to verify

An attacker must defeat all three to remove provenance completely.

---

## Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Image generation | OpenRouter (Flux.2 Pro, DALL-E 3, Gemini) | Model-agnostic, single API for all providers |
| Semantic watermark | DWT-DCT-SVD (invisible-watermark / PyWavelets) | Survives AI regeneration |
| Neural watermark | TrustMark (Adobe/CAI) | Survives JPEG, resize, format conversion |
| Perceptual hash | DINOv2 ViT-S/14 (binarized CLS token, 63-bit) | Survives JPEG/resize/crop; semantically robust. Top bit held at 0 for int64/uint64 safety. |
| C2PA signing | c2pa-python + cryptography | Industry-standard Content Credentials |
| ZK proving | ezkl (ONNX → Halo2 → Solidity verifier) | On-chain verification, not just storage |
| Blockchain | web3.py + Base Sepolia (EIP-1559) | Cheap testnet, Ethereum-compatible |
| Queue | ARQ (async Redis queue) | Retry, crash-resume, concurrency control |
| Storage | SQLite (WAL mode) | Crash-proof outbox, concurrent reads/writes |
| Permanent storage | Arweave via Irys (@irys/upload) | Permanent, cheap, decentralized |
| Backend | FastAPI + slowapi | Async, rate-limited, type-safe |
| Frontend | React + Tailwind | SPA served by FastAPI static files |

---

## Setup

### Prerequisites

- **Python 3.13+** with pip
- **Node.js 18+** (for Irys upload script)
- **Redis** (for ARQ worker)
- **OpenRouter API key** (for image generation)
- **Base Sepolia wallet** with testnet ETH (for blockchain registration)

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Node dependencies

```bash
npm install @irys/upload @irys/upload-ethereum
```

### 3. Start Redis

```bash
redis-server
```

### 4. Configure environment

Create `.env`:

```env
# Image generation
OPENROUTER_API_KEY=...              # https://openrouter.ai/keys

# Blockchain
WALLET_PRIVATE_KEY=...              # Base Sepolia wallet private key (hex)
CONTRACT_ADDRESS=...                # Output of deploy step below
RPC_URL=https://sepolia.base.org

# Queue (ARQ worker)
REDIS_URL=redis://localhost:6379    # Default, change if needed

# C2PA signing (optional — generate with scripts/generate_c2pa_cert.py)
C2PA_CERT_PEM=...                   # Self-signed X.509 certificate
C2PA_PRIVATE_KEY_PEM=...            # ECDSA P-256 private key
```

### 5. Generate C2PA certificates (one time, optional)

```bash
python scripts/generate_c2pa_cert.py
# Copy the output into .env as C2PA_CERT_PEM and C2PA_PRIVATE_KEY_PEM
```

This generates a self-signed ECDSA P-256 certificate for C2PA manifest signing. In production, use a CA-issued certificate.

### 6. Set up the ZK circuit (one time, optional)

```bash
python scripts/setup_zk_circuit.py
```

Exports a trivial Relu circuit (384 inputs) to ONNX with `input_visibility=hashed`, calibrates ezkl settings, downloads the SRS (~4 MB), compiles the circuit, generates proving/verification keys, and outputs `zk/Verifier.sol` + `zk/verifier_abi.json`.

Use `--force` to regenerate from scratch (required after any INPUT_DIM change).

**The server runs without this step** — ZK proof generation is skipped and `proofVerifiedOnChain` is stored as `false`.

### 7. Deploy contracts (one time, in order)

```bash
# 1. Deploy ezkl-generated verifier (Verifier.sol + VK.sol from zk/)
# 2. Deploy ProofOfOriginRegistry with verifier address:
#    constructor(address _verifier)
#    Pass address(0) to deploy without ZK verification initially
```

To point the registry at a new verifier after re-setup:
```solidity
registry.setVerifier(newVerifierAddress)  // owner only
```

### 8. Start the system

Three processes must run:

**Terminal 1 — FastAPI backend:**
```bash
uvicorn main:app --reload
```

**Terminal 2 — ARQ worker:**
```bash
arq pipeline.worker.WorkerSettings
```

Open http://localhost:8000

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve the React UI |
| `POST` | `/generate` | Generate + watermark + C2PA-sign image; enqueue blockchain registration |
| `POST` | `/verify` | Verify provenance of an uploaded PNG or JPEG |
| `GET` | `/download/{watermark_id}` | Download watermarked PNG by ID |

### `POST /generate`

```json
{ "prompt": "a red cube on a white background", "model": "black-forest-labs/flux.2-pro" }
```

Returns immediately with `status: "anchoring"`. The ARQ worker handles blockchain + ZK + Arweave in the background.

```json
{
  "watermark_id": "uuid-here",
  "image_hash": "sha256-hex",
  "image_b64": "base64-encoded PNG",
  "model": "black-forest-labs/flux.2-pro",
  "zk_proof": true,
  "status": "anchoring"
}
```

Rate limited: **5 requests/minute per IP**.

### `POST /verify`

Upload PNG or JPEG as `multipart/form-data` with field name `file`.

```json
{
  "verified": true,
  "integrity": "transformed",
  "phash_distance": 6,
  "semantic_fingerprint": {
    "match": true,
    "correlation": 0.8906
  },
  "tamper_risk": false,
  "zk_proof_valid": true,
  "zk_proof_on_chain": true,
  "on_chain": {
    "image_hash": "0x...",
    "perceptual_hash": 12345678901234,
    "proof_verified_on_chain": true,
    "registrant": "0x...",
    "timestamp": 1712345678,
    "arweave_url": "https://gateway.irys.xyz/...",
    "explorer_url": "https://sepolia.basescan.org/tx/0x..."
  },
  "generation": {
    "model": "black-forest-labs/flux.2-pro",
    "prompt": "a cat on the moon",
    "generated_at": "2026-04-08T12:00:00+00:00"
  }
}
```

#### Response field meanings

| Field | Meaning |
|-------|---------|
| `verified` | `true` if the image is perceptually the same as the registered original (watermark found + pHash match) |
| `integrity` | `"original"` (exact bytes match), `"transformed"` (screenshot/crop/JPEG), or `"none"` (unrecognised) |
| `phash_distance` | Hamming distance between uploaded and registered perceptual hashes; < 15 = same image |
| `semantic_fingerprint.match` | `true` if DWT-DCT-SVD bit correlation ≥ 0.70 (survived AI regeneration) |
| `tamper_risk` | `true` if the perceptual hash doesn't match — the image has been meaningfully altered |
| `zk_proof_valid` | Local ZK verification result (no gas cost); `null` if circuit not set up or no proof exists |
| `zk_proof_on_chain` | Whether the on-chain record shows the ZK proof was verified during registration |

#### Verification tiers

| Scenario | short_id recovered by | `verified` | `integrity` | `phash_distance` | `semantic_fingerprint` |
|----------|----------------------|-----------|-------------|-----------------|----------------------|
| Original file (exact bytes)      | TrustMark / PNG metadata | `true`  | `"original"`    | `0`    | `{match: true, correlation: 0.98}` |
| Lossless PNG copy                | PNG metadata             | `true`  | `"transformed"` | `0–3`  | `{match: true, correlation: 0.95}` |
| Screenshot / JPEG re-encode      | TrustMark                | `true`  | `"transformed"` | `1–15` | `{match: true, correlation: 0.85}` |
| Aggressive crop (watermark gone) | pHash DB proximity       | `true`  | `"transformed"` | `5–15` | `{match: true/false, correlation: variable}` |
| AI regeneration (img2img)        | TrustMark / pHash        | `true`  | `"transformed"` | `5–15` | `{match: true, correlation: 0.72}` |
| Heavily modified / unrelated     | none                     | `false` | —               | —      | — |
| Blockchain registration pending  | any                      | `false` | —               | —      | — |

Note: when short_id is recovered by pHash proximity, the `integrity` check still uses the registered on-chain SHA-256 and perceptual hash. It cannot be `"original"` because any transformation that wipes the watermark also changes the SHA-256.

---

## Running Without Redis / ARQ

For development or single-server deployments, you can skip the ARQ worker and run registration inline:

1. Don't start Redis
2. Don't run `arq pipeline.worker.WorkerSettings`
3. The `/generate` endpoint will still return immediately, but the blockchain registration **will not happen** (the ARQ enqueue call will fail silently or throw)

For a fully synchronous flow, modify `/generate` to call `process_registration` directly instead of enqueuing.

---

## Trustless Verification

Once a verifier holds a `short_id`, everything downstream is fully trustless — no backend required, just a Base Sepolia RPC.

### What's trustless

| Step | Path | Requires |
|------|------|----------|
| Recover `short_id` from a watermarked copy | TrustMark decode (open-source library) or PNG iTXt chunk read | The image file only |
| On-chain lookup of registration record     | `ProofOfOriginRegistry.lookup(keccak256(short_id))`            | Base Sepolia RPC |
| Derivative check (pHash similarity)        | `ProofOfOriginRegistry.verifyDerivative(...)`                  | Base Sepolia RPC |
| ZK proof verification                      | `Verifier.verify(zkProof, zkInstances)` (ezkl-generated)        | Base Sepolia RPC |

### What is **not** trustless

Recovering a `short_id` from a cropped or heavily transformed image where **both** the TrustMark watermark and the PNG metadata have been destroyed requires scanning the `images` table in this server's SQLite database by DINOv2 pHash Hamming distance. That scan is a property of this backend and is not published on-chain.

A fully decentralised lookup would require either publishing `(short_id, pHash)` pairs on-chain (doable — each record already stores `perceptualHash`, so an off-chain indexer can mirror it) or using a pHash-indexed content-addressed storage layer. The current implementation keeps the lookup index off-chain for cost reasons; migrating to an on-chain index is an open extension.

### On-chain derivative check

```solidity
// Call via BaseScan Read Contract tab or any web3 library
verifyDerivative(
    keccak256(short_id),    // watermarkId — from TrustMark decode or PNG metadata
    uploadedPHash,          // 64-bit DINOv2 pHash of the image being checked
    15                      // threshold — Hamming bits
) → (isDerivative: true, distance: 6)
```

This is a free `view` function — no gas, no backend, no network beyond Base Sepolia.

The frontend exposes this as a **"Verify on-chain (no backend)"** button in the verification result panel. It hits `verifyDerivative()` directly from the browser via `viem` on Base Sepolia — no wallet prompt, no gas, pure `view` call. The panel shows the live block number, contract address, watermarkId (keccak256 of the short_id), uploaded pHash, and the contract's raw `(isDerivative, distance)` return — so you can see the chain confirming the backend's claim in real time.

### ZK proof verification

The ezkl-generated `Verifier.sol` contract can verify proofs independently:

```solidity
verifier.verify(zkProof, zkInstances) → bool
```

Pass the proof bytes and public instances from the stored proof — the contract returns `true` if the proof is valid, `false` otherwise (and reverts if invalid in the registration context).

---

## Project Structure

```
main.py                          # FastAPI app — /generate, /verify, /download
settings.py                      # Pydantic settings (reads .env), DINO_DIM_MASK constant
pipeline/
  outbox.py                      # SQLite outbox: images + outbox_jobs tables
                                 # insert_image_and_job(), get_image_by_short_id(), etc.
  worker.py                      # ARQ worker: process_registration (3-step idempotent)
  image_gen.py                   # Image generation via OpenRouter
  watermark.py                   # Three-layer orchestration
                                 # + DCT perceptual hash (compute_phash)
  latent_encoder.py              # Semantic Latent Watermark — DWT-DCT-SVD
  blockchain.py                  # web3.py: create_placeholder + completeRegistration
  c2pa.py                        # C2PA manifest signing (ES256, graceful fallback)
  arweave.py                     # Arweave upload via Irys Node.js subprocess
  zk_proof.py                    # ezkl proof generation and local verification
  zk_setup.py                    # One-time circuit setup (ONNX export, key generation)
contracts/
  ProofOfOriginRegistry.sol      # Two-phase: createPlaceholder + completeRegistration
scripts/
  deploy_registry.py             # Contract deployment script
  setup_zk_circuit.py            # CLI wrapper for zk_setup.py
  generate_c2pa_cert.py          # Generate self-signed C2PA certificate
  irys_upload.mjs                # Irys upload helper (Node.js, called by arweave.py)
zk/                              # Generated ZK artefacts (gitignored)
  circuit.onnx
  Verifier.sol                   # ezkl-generated Solidity verifier
  verifier_abi.json
  vk.key / pk.key / kzg.srs
  proofs/<short_id>/proof.json
src/                             # React frontend
dist/                            # Built frontend assets (served by FastAPI)
tests/
  test_outbox.py                 # SQLite outbox CRUD + atomic insert tests
  test_pipeline.py               # FastAPI endpoint tests (mocked)
  test_watermark.py              # Watermark + pHash tests
  test_blockchain.py             # Blockchain function tests (mocked)
provenance.db                    # SQLite database (created at runtime)
```

---

## Running the Full Stack

After all setup is complete:

**Terminal 1 — Redis:**
```bash
redis-server
```

**Terminal 2 — FastAPI backend:**
```bash
uvicorn main:app --reload
```

**Terminal 3 — ARQ worker:**
```bash
arq pipeline.worker.WorkerSettings
```

Expected: JSON response with `watermark_id`, `image_b64`, `status: "anchoring"`. The ARQ worker terminal should show `createPlaceholder OK → completeRegistration OK → Arweave upload OK`.

---

## Security Notes

- **Never commit `.env`** — it contains your wallet private key
- This is a **testnet demo**; the private key controls a Base Sepolia wallet only
- The C2PA certificate generated by `scripts/generate_c2pa_cert.py` is **self-signed** — suitable for development, not for production trust
- Rate limit: **5 req/min per IP** on `/generate` (configurable via slowapi)
- The SQLite database (`provenance.db`) contains full image bytes — back it up or it's lost
- The `DINO_DIM_MASK` constant in `settings.py` is a **protocol-level invariant** — changing it invalidates all registered perceptual hashes
- Two-phase blockchain registration means the `createPlaceholder` slot is reserved before any expensive computation — the crash window is eliminated

Progect created durring hackathon Eth Silesia 2026