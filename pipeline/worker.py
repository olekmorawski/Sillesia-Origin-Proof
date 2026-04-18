import asyncio
import logging

from arq import Retry
from arq.connections import RedisSettings

from pipeline.arweave import upload_provenance
from pipeline.blockchain import create_placeholder, complete_registration
from pipeline.outbox import DB_PATH, get_image, get_job, update_job
from pipeline.zk_proof import generate_proof, is_setup_complete as zk_ready, read_proof_calldata
from settings import settings

logger = logging.getLogger(__name__)


async def _maybe_generate_proof(short_id: str, image):
    if not zk_ready():
        return None, None
    proof_path = await generate_proof(short_id, image.sha256, image.phash)
    if proof_path is None:
        return None, None
    calldata = read_proof_calldata(short_id)
    if calldata is None:
        return None, None
    return calldata


async def process_registration(ctx, watermark_id: str) -> None:
    job = get_job(DB_PATH, watermark_id)
    if job is None:
        logger.error("process_registration: no job found for watermark_id=%s", watermark_id)
        return

    image = get_image(DB_PATH, watermark_id)
    if image is None:
        logger.error("process_registration: no image found for watermark_id=%s", watermark_id)
        return

    if job.status == "pending":
        receipt = await asyncio.to_thread(create_placeholder, image.short_id)
        update_job(DB_PATH, watermark_id, status="placeholder_done",
                   tx_hash=receipt["transactionHash"].hex())
        job = get_job(DB_PATH, watermark_id)

    if job.status == "placeholder_done":
        proof_bytes, proof_instances = await _maybe_generate_proof(image.short_id, image)
        receipt = await asyncio.to_thread(
            complete_registration,
            image.short_id, image.sha256, image.phash,
            proof_bytes, proof_instances,
        )
        update_job(DB_PATH, watermark_id, status="registered",
                   tx_hash=receipt["transactionHash"].hex())
        job = get_job(DB_PATH, watermark_id)

    if job.status == "registered":
        image = get_image(DB_PATH, watermark_id)
        provenance = {
            "watermark_id": watermark_id,
            "short_id": image.short_id,
            "sha256": image.sha256,
            "phash": image.phash,
            "prompt": image.prompt,
            "model": image.model,
            "created_at": image.created_at,
            "tx_hash": job.tx_hash,
        }
        arweave_id = await upload_provenance(provenance)
        update_job(DB_PATH, watermark_id, status="done", arweave_id=arweave_id)
        logger.info("process_registration done | watermark_id=%s arweave_id=%s",
                    watermark_id, arweave_id)


class WorkerSettings:
    functions = [process_registration]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 5
    retry_delay = 30
    job_timeout = 300
    keep_result = 3600
