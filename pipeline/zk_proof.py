"""Per-image ZK proof generation and verification.

Proves: Poseidon(short_id_bits ++ image_hash_bits ++ phash_bits) = commitment
  → the prover knows the short_id AND the exact image that was watermarked
  → a proof is bound to one specific (short_id, image) pair — it cannot be
    transplanted to a different image even with the same short_id
  → commitment is a single field element (ezkl hashed-input visibility)

Setup required before first use:
    python scripts/setup_zk_circuit.py   (writes artefacts to zk/)

Usage:
    from pipeline.zk_proof import generate_proof, verify_proof_local, get_proof_hash

    proof_path = await generate_proof(short_id, image_hash_hex)   # seconds on CPU
    valid      = await verify_proof_local(short_id)
    proof_hash = get_proof_hash(short_id)                          # register this on-chain
"""

import asyncio
import hashlib
import json
import logging
import pathlib
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths — all ZK artefacts live under zk/
# ---------------------------------------------------------------------------
ZK_DIR                  = pathlib.Path(__file__).parent.parent / "zk"
ONNX_PATH               = ZK_DIR / "circuit.onnx"
COMPILED_PATH           = ZK_DIR / "model.compiled"
SETTINGS_PATH           = ZK_DIR / "settings.json"
VK_PATH                 = ZK_DIR / "vk.key"
PK_PATH                 = ZK_DIR / "pk.key"
SRS_PATH                = ZK_DIR / "kzg.srs"
CALIBRATION_INPUT_PATH  = ZK_DIR / "calibration_input.json"
EVM_VERIFIER_SOL_PATH   = ZK_DIR / "Verifier.sol"
EVM_VERIFIER_ABI_PATH   = ZK_DIR / "verifier_abi.json"

# Circuit input: short_id[64] + sha256[256] + phash[64] = 384 bits
INPUT_DIM = 384

_ezkl = None


def _get_ezkl():
    global _ezkl
    if _ezkl is None:
        import ezkl
        _ezkl = ezkl
    return _ezkl


def is_setup_complete() -> bool:
    """True if all circuit artefacts exist and proving is possible."""
    return all(p.exists() for p in [COMPILED_PATH, SETTINGS_PATH, VK_PATH, PK_PATH, SRS_PATH])


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

def encode_inputs(short_id: str, image_hash_hex: str, phash_int: int) -> np.ndarray:
    """short_id[64] + image_hash[256] + phash[64] → (1, 384) float32 bits.

    Layout: [short_id_bits | sha256_bits | phash_bits]
    Hex nibbles expand MSB-first to 4 bits; phash_int expands bit 63 first.
    """
    bits: list[float] = []
    for ch in short_id[:16]:
        val = int(ch, 16)
        for bit_pos in range(3, -1, -1):
            bits.append(float((val >> bit_pos) & 1))
    for ch in image_hash_hex[:64]:
        val = int(ch, 16)
        for bit_pos in range(3, -1, -1):
            bits.append(float((val >> bit_pos) & 1))
    for bit_pos in range(63, -1, -1):
        bits.append(float((phash_int >> bit_pos) & 1))
    return np.array(bits, dtype=np.float32).reshape(1, INPUT_DIM)


def compute_commitment(short_id: str, image_hash_hex: str, phash_int: int) -> list[str]:
    """Compute Poseidon commitment matching the ezkl circuit.

    Quantizes the encoded input bits using the scale from settings.json, then
    calls ezkl.poseidon_hash to produce the same field element the circuit
    exposes as its public instance.

    Requires circuit to be set up (settings.json must exist).
    """
    ezkl = _get_ezkl()
    bits = encode_inputs(short_id, image_hash_hex, phash_int)
    settings_data = json.loads(SETTINGS_PATH.read_text())
    scale = settings_data["model_input_scales"][0]
    field_elements = [format(round(float(b) * (2 ** scale)), '064x') for b in bits.flatten().tolist()]
    return ezkl.poseidon_hash(field_elements)


# ---------------------------------------------------------------------------
# Per-image prove / verify
# ---------------------------------------------------------------------------

async def generate_proof(short_id: str, image_hash_hex: str, phash_int: int) -> Optional[str]:
    """Generate ZK proof binding short_id, image hash, and perceptual hash together.

    Returns path to proof.json, or None if circuit not set up or on error.
    Proof files are stored at zk/proofs/<short_id>/.
    """
    if not is_setup_complete():
        logger.warning("ZK circuit not set up — run scripts/setup_zk_circuit.py")
        return None

    ezkl = _get_ezkl()
    proof_dir = ZK_DIR / "proofs" / short_id
    proof_dir.mkdir(parents=True, exist_ok=True)

    input_path   = proof_dir / "input.json"
    witness_path = proof_dir / "witness.json"
    proof_path   = proof_dir / "proof.json"

    bits = encode_inputs(short_id, image_hash_hex, phash_int)
    input_path.write_text(json.dumps({"input_data": [bits.flatten().tolist()]}))

    try:
        logger.info("witness | short_id=%s", short_id)
        await asyncio.to_thread(
            ezkl.gen_witness,
            str(input_path),    # data
            str(COMPILED_PATH), # model
            str(witness_path),  # output
        )

        logger.info("prove | short_id=%s", short_id)
        await asyncio.to_thread(
            ezkl.prove,
            str(witness_path),  # witness
            str(COMPILED_PATH), # model
            str(PK_PATH),       # pk_path
            str(proof_path),    # proof_path
            str(SRS_PATH),      # srs_path
        )

        logger.info("proof OK | short_id=%s size=%d B", short_id, proof_path.stat().st_size)
        return str(proof_path)

    except Exception as exc:
        logger.error("prove failed | short_id=%s error=%s", short_id, exc)
        return None


async def verify_proof_local(short_id: str) -> bool:
    """Verify a stored proof locally (no gas cost, no network)."""
    if not is_setup_complete():
        return False

    ezkl = _get_ezkl()
    proof_path = ZK_DIR / "proofs" / short_id / "proof.json"
    if not proof_path.exists():
        return False

    try:
        result = await asyncio.to_thread(
            ezkl.verify,
            str(proof_path),    # proof_path
            str(SETTINGS_PATH), # settings_path
            str(VK_PATH),       # vk_path
            str(SRS_PATH),      # srs_path
            False,              # reduced_srs
        )
        return bool(result)
    except Exception as exc:
        logger.error("verify failed | short_id=%s error=%s", short_id, exc)
        return False


def read_proof_calldata(short_id: str) -> Optional[tuple[bytes, list[int]]]:
    """Read proof.json and return (proof_bytes, instances) for on-chain verification.

    proof_bytes  — raw proof bytes to pass as `bytes calldata zkProof`
    instances    — flattened list of field elements (uint256) for `uint256[] calldata zkInstances`

    Returns None if the proof file does not exist.
    """
    proof_path = ZK_DIR / "proofs" / short_id / "proof.json"
    if not proof_path.exists():
        return None

    data = json.loads(proof_path.read_text())

    proof_raw = data["proof"]
    if isinstance(proof_raw, list):
        proof_bytes = bytes(proof_raw)
    else:
        proof_bytes = bytes.fromhex(proof_raw[2:] if proof_raw.startswith("0x") else proof_raw)

    # instances is a list of columns; each column is a list of hex field-element strings
    raw: list[list[str]] = data.get("instances", [[]])
    instances: list[int] = [
        int(val, 16) if isinstance(val, str) else int(val)
        for col in raw
        for val in col
    ]

    return proof_bytes, instances
