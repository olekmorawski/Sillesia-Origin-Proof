
import asyncio
import hashlib
import json
import logging
import pathlib
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

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

INPUT_DIM = 384

_ezkl = None


def _get_ezkl():
    global _ezkl
    if _ezkl is None:
        import ezkl
        _ezkl = ezkl
    return _ezkl


def is_setup_complete() -> bool:
    return all(p.exists() for p in [COMPILED_PATH, SETTINGS_PATH, VK_PATH, PK_PATH, SRS_PATH])



def encode_inputs(short_id: str, image_hash_hex: str, phash_int: int) -> np.ndarray:
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
    ezkl = _get_ezkl()
    bits = encode_inputs(short_id, image_hash_hex, phash_int)
    settings_data = json.loads(SETTINGS_PATH.read_text())
    scale = settings_data["model_input_scales"][0]
    field_elements = [format(round(float(b) * (2 ** scale)), '064x') for b in bits.flatten().tolist()]
    return ezkl.poseidon_hash(field_elements)



async def generate_proof(short_id: str, image_hash_hex: str, phash_int: int) -> Optional[str]:
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
            str(input_path),
            str(COMPILED_PATH),
            str(witness_path),
        )

        logger.info("prove | short_id=%s", short_id)
        await asyncio.to_thread(
            ezkl.prove,
            str(witness_path),
            str(COMPILED_PATH),
            str(PK_PATH),
            str(proof_path),
            str(SRS_PATH),
        )

        logger.info("proof OK | short_id=%s size=%d B", short_id, proof_path.stat().st_size)
        return str(proof_path)

    except Exception as exc:
        logger.error("prove failed | short_id=%s error=%s", short_id, exc)
        return None


async def verify_proof_local(short_id: str) -> bool:
    if not is_setup_complete():
        return False

    ezkl = _get_ezkl()
    proof_path = ZK_DIR / "proofs" / short_id / "proof.json"
    if not proof_path.exists():
        return False

    try:
        result = await asyncio.to_thread(
            ezkl.verify,
            str(proof_path),
            str(SETTINGS_PATH),
            str(VK_PATH),
            str(SRS_PATH),
            False,
        )
        return bool(result)
    except Exception as exc:
        logger.error("verify failed | short_id=%s error=%s", short_id, exc)
        return False


def read_proof_calldata(short_id: str) -> Optional[tuple[bytes, list[int]]]:
    proof_path = ZK_DIR / "proofs" / short_id / "proof.json"
    if not proof_path.exists():
        return None

    data = json.loads(proof_path.read_text())

    proof_raw = data["proof"]
    if isinstance(proof_raw, list):
        proof_bytes = bytes(proof_raw)
    else:
        proof_bytes = bytes.fromhex(proof_raw[2:] if proof_raw.startswith("0x") else proof_raw)

    raw: list[list[str]] = data.get("instances", [[]])
    instances: list[int] = [
        int(val, 16) if isinstance(val, str) else int(val)
        for col in raw
        for val in col
    ]

    return proof_bytes, instances
