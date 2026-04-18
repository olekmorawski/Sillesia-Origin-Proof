"""Arweave permanent storage via Irys new JS SDK.

Calls scripts/irys_upload.mjs as a subprocess, passing provenance JSON on
stdin and reading the Arweave transaction ID from stdout.

Permanent record URL: https://gateway.irys.xyz/<id>
"""
import asyncio
import json
import logging
import os

from settings import settings

logger = logging.getLogger(__name__)

_SCRIPT = str((
    __import__("pathlib").Path(__file__).parent.parent / "scripts" / "irys_upload.mjs"
))


async def upload_provenance(provenance: dict) -> str:
    """Upload provenance JSON to Arweave via Irys. Returns transaction ID.

    Args:
        provenance: Dict containing at minimum watermark_id, short_id,
                    timestamp, image_hash.

    Returns:
        Irys transaction ID (permanent at https://gateway.irys.xyz/<id>).

    Raises:
        RuntimeError: if the Node.js subprocess exits non-zero.
    """
    env = {**os.environ, "WALLET_PRIVATE_KEY": settings.wallet_private_key}

    proc = await asyncio.create_subprocess_exec(
        "node", _SCRIPT,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    stdout, stderr = await proc.communicate(input=json.dumps(provenance).encode())

    if proc.returncode != 0:
        raise RuntimeError(f"Irys upload failed: {stderr.decode().strip()}")

    result = json.loads(stdout.decode().strip())
    tx_id = result["id"]
    logger.info("Arweave upload OK | watermark_id=%s tx_id=%s",
                provenance.get("watermark_id"), tx_id)
    return tx_id
