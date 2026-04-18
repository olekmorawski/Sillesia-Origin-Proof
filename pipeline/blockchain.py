"""On-chain registration via web3.py + Base Sepolia.

Two-phase flow:
  1. create_placeholder(watermark_id)   — reserves the slot (~45k gas)
  2. complete_registration(...)         — fills in hash + optional ZK proof

All functions are synchronous. Call via asyncio.to_thread() from async context.
_submit_with_retry() handles nonce refresh + exponential backoff on failure.
"""
import json
import logging
import pathlib
import threading
import time
from typing import Optional

from web3 import Web3

from settings import settings

logger = logging.getLogger(__name__)

CHAIN_ID = 84532  # Base Sepolia
DEPLOYMENT_FILE = pathlib.Path(__file__).parent.parent / "deployment.json"

_nonce_lock = threading.Lock()
_w3: Web3 | None = None
_contract = None


def _get_contract():
    global _w3, _contract
    if _w3 is None or _contract is None:
        deployment = json.loads(DEPLOYMENT_FILE.read_text())
        _w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
        _contract = _w3.eth.contract(
            address=deployment["address"],
            abi=deployment["abi"],
        )
    return _w3, _contract


def _submit_with_retry(build_tx_fn, max_attempts: int = 5) -> dict:
    """Send a tx with nonce refresh + exponential backoff on failure.

    Nonce is fetched fresh inside the lock on every attempt, so a nonce gap
    from a previous dropped tx is self-healing.
    """
    w3, _ = _get_contract()
    account = w3.eth.account.from_key(settings.wallet_private_key)
    last_exc = None

    for attempt in range(max_attempts):
        try:
            with _nonce_lock:
                nonce = w3.eth.get_transaction_count(account.address, "pending")
                tx = build_tx_fn(nonce)
                signed = account.sign_transaction(tx)
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return dict(receipt)
        except Exception as exc:
            last_exc = exc
            logger.warning("tx attempt %d failed: %s", attempt + 1, exc)
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s, 16s

    raise RuntimeError(f"tx failed after {max_attempts} attempts: {last_exc}") from last_exc


def create_placeholder(watermark_id: str) -> dict:
    """Reserve a slot on-chain before the crash window opens (~45k gas).

    Args:
        watermark_id: 16-char short_id string.

    Returns:
        Full web3 tx receipt dict.

    Raises:
        RuntimeError: if all retry attempts fail.
    """
    w3, contract = _get_contract()
    account = w3.eth.account.from_key(settings.wallet_private_key)
    wid_bytes32 = w3.keccak(text=watermark_id)

    def build(nonce):
        return contract.functions.createPlaceholder(wid_bytes32).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "chainId": CHAIN_ID,
            "maxFeePerGas": int(w3.eth.gas_price * 1.2),
            "maxPriorityFeePerGas": w3.eth.max_priority_fee,
        })

    receipt = _submit_with_retry(build)
    logger.info("createPlaceholder OK | watermark_id=%s tx=%s",
                watermark_id, receipt["transactionHash"].hex())
    return receipt


def complete_registration(
    watermark_id: str,
    image_hash: str,
    perceptual_hash: int,
    proof_bytes: Optional[bytes] = None,
    proof_instances: Optional[list[int]] = None,
) -> dict:
    """Complete a previously reserved registration.

    Safe to retry: second call reverts with 'Already registered'; caller should
    catch that revert, call verify_on_chain() to confirm, and mark job done.

    Args:
        watermark_id:    16-char short_id string.
        image_hash:      64-char hex SHA-256 of the watermarked PNG.
        perceptual_hash: 64-bit DINOv2 binarized pHash as Python int.
        proof_bytes:     Raw ezkl proof bytes (optional).
        proof_instances: ezkl public instances as uint256 list (optional).

    Returns:
        Full web3 tx receipt dict.

    Raises:
        RuntimeError: if all retry attempts fail.
    """
    w3, contract = _get_contract()
    account = w3.eth.account.from_key(settings.wallet_private_key)
    wid_bytes32  = w3.keccak(text=watermark_id)
    hash_bytes32 = w3.keccak(text=image_hash)
    zk_proof     = proof_bytes or b""
    zk_instances = proof_instances or []

    def build(nonce):
        return contract.functions.completeRegistration(
            wid_bytes32, hash_bytes32, perceptual_hash, zk_proof, zk_instances
        ).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "chainId": CHAIN_ID,
            "maxFeePerGas": int(w3.eth.gas_price * 1.2),
            "maxPriorityFeePerGas": w3.eth.max_priority_fee,
        })

    receipt = _submit_with_retry(build)
    logger.info("completeRegistration OK | watermark_id=%s proof=%s tx=%s",
                watermark_id, "verified" if proof_bytes else "none",
                receipt["transactionHash"].hex())
    return receipt


def encode_hash(value: str) -> str:
    """Encode a string to bytes32 hex via keccak256."""
    w3, _ = _get_contract()
    return w3.keccak(text=value).hex()


def verify_on_chain(watermark_id: str) -> dict | None:
    """Look up a registered watermark_id on-chain (free view call).

    Returns:
        Dict with keys {image_hash, perceptual_hash, proof_verified_on_chain,
        timestamp, creator} if registered, or None on any error.
    """
    try:
        w3, contract = _get_contract()
        wid_bytes32 = w3.keccak(text=watermark_id)
        image_hash_bytes, perceptual_hash, proof_verified, timestamp, creator = (
            contract.functions.lookup(wid_bytes32).call()
        )
        return {
            "image_hash": image_hash_bytes.hex(),
            "perceptual_hash": perceptual_hash,
            "proof_verified_on_chain": proof_verified,
            "timestamp": timestamp,
            "creator": creator,
        }
    except Exception as exc:
        logger.error("verify_on_chain failed | watermark_id=%s error=%s", watermark_id, exc)
        return None
