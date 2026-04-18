import asyncio
import base64
import logging
import uuid
from datetime import datetime, timezone

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from settings import settings  # noqa: F401 — validates env vars at startup
from pipeline.watermark import (
    _short_id,
    compute_phash,
    dual_watermark,
    phash_hamming_distance,
    PHASH_SIMILAR_THRESHOLD,
    sha256_hash,
    verify_exif,
    verify_lsb,
    verify_semantic,
)
from pipeline.blockchain import encode_hash, verify_on_chain
from pipeline.image_gen import generate_image
from pipeline.c2pa import sign_with_c2pa
from pipeline.outbox import (
    DB_PATH, init_db,
    insert_image_and_job,
    get_image, get_image_by_short_id,
    get_job_by_short_id,
    get_images_by_phash_proximity,
)
from pipeline.zk_proof import (
    is_setup_complete as zk_ready,
    verify_proof_local,
)

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Proof of Origin")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

_arq_pool = None


@app.on_event("startup")
async def startup():
    global _arq_pool
    init_db(DB_PATH)
    _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    logger.info("Startup: DB initialized, ARQ pool connected")


@app.on_event("shutdown")
async def shutdown():
    if _arq_pool:
        await _arq_pool.aclose()


class GenerateRequest(BaseModel):
    prompt: str
    model: str | None = None


@app.get("/")
async def root():
    return FileResponse("dist/index.html")


@app.post("/generate")
@limiter.limit("5/minute")
async def generate(request: Request, body: GenerateRequest):
    """Generate a watermarked image and enqueue provenance registration.

    Pipeline:
      1. generate_image   — OpenRouter
      2. dual_watermark   — TrustMark + DWT-DCT-SVD
      3. sign_with_c2pa   — C2PA manifest (soft-binding, skipped if unconfigured)
      4. compute_phash    — DINOv2 binarized uint64
      5. SQLite write     — images + outbox_jobs (atomic)
      6. ARQ enqueue      — worker handles placeholder → register → Arweave

    Returns immediately; blockchain + Arweave happen in the background.
    """
    model = body.model or settings.default_model

    try:
        raw_png = await asyncio.to_thread(generate_image, body.prompt, model)
    except Exception as exc:
        import requests
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response.status_code == 402:
            raise HTTPException(
                status_code=402,
                detail="OpenRouter: Payment Required. Please check your account balance."
            )
        logger.error(f"Generate failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    watermark_id = str(uuid.uuid4())
    short_id = _short_id(watermark_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    provenance = {
        "watermark_id": watermark_id,
        "short_id": short_id,
        "timestamp": timestamp,
    }

    watermarked_png, _ = await asyncio.to_thread(dual_watermark, raw_png, provenance)
    signed_png = await asyncio.to_thread(sign_with_c2pa, watermarked_png, provenance)
    image_hash = await asyncio.to_thread(sha256_hash, signed_png)
    phash_int = await asyncio.to_thread(compute_phash, signed_png)

    job_id = str(uuid.uuid4())

    # Atomic write: both rows committed or neither
    insert_image_and_job(
        DB_PATH, watermark_id, short_id, signed_png, image_hash, phash_int,
        body.prompt, model, job_id,
    )

    await _arq_pool.enqueue_job("process_registration", watermark_id)

    return {
        "watermark_id": watermark_id,
        "image_hash": image_hash,
        "image_b64": base64.b64encode(signed_png).decode(),
        "model": model,
        "zk_proof": zk_ready(),
        "status": "anchoring",
    }


@app.post("/verify")
async def verify(file: UploadFile = File(...)):
    """Verify provenance of an uploaded PNG or JPEG."""
    png_bytes = await file.read()
    uploaded_sha256 = sha256_hash(png_bytes)
    uploaded_phash = await asyncio.to_thread(compute_phash, png_bytes)

    provenance = verify_lsb(png_bytes)
    if provenance is None:
        provenance = verify_exif(png_bytes)

    if provenance is None:
        candidates = get_images_by_phash_proximity(DB_PATH, uploaded_phash, threshold=15)
        if candidates:
            provenance = {"short_id": candidates[0].short_id}

    if provenance is None:
        return {
            "verified": False,
            "consistent": False,
            "tamper_risk": True,
            "zk_proof_valid": None,
            "on_chain": None,
        }

    short_id = provenance.get("short_id")
    if not short_id:
        return {
            "verified": False,
            "consistent": False,
            "tamper_risk": True,
            "zk_proof_valid": None,
            "on_chain": None,
        }

    # Check registration status from SQLite outbox
    job = get_job_by_short_id(DB_PATH, short_id)
    if job and job.status in ("pending", "placeholder_done", "registered"):
        return {
            "verified": False,
            "consistent": True,
            "tamper_risk": False,
            "status": "pending",
            "message": "Blockchain registration in progress. Try again in a few seconds.",
            "zk_proof_valid": None,
            "on_chain": None,
            "short_id": short_id,
        }

    tasks = [
        asyncio.to_thread(verify_on_chain, short_id),
        asyncio.to_thread(verify_semantic, png_bytes, short_id),
    ]
    if zk_ready():
        tasks.append(verify_proof_local(short_id))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    on_chain = results[0] if not isinstance(results[0], BaseException) else None
    semantic_result = results[1] if not isinstance(results[1], BaseException) else (False, 0.0)
    semantic_match, semantic_correlation = (
        semantic_result if isinstance(semantic_result, tuple) else (False, 0.0)
    )
    zk_proof_valid = (
        results[2]
        if len(results) > 2 and not isinstance(results[2], BaseException)
        else None
    )

    if on_chain is None or on_chain.get("timestamp", 0) == 0:
        return {
            "verified": False,
            "consistent": False,
            "tamper_risk": True,
            "zk_proof_valid": zk_proof_valid,
            "on_chain": None,
            "short_id": short_id,
        }

    uploaded_hash_encoded = await asyncio.to_thread(encode_hash, uploaded_sha256)
    exact_match = uploaded_hash_encoded == on_chain["image_hash"]

    registered_phash = on_chain.get("perceptual_hash", 0)
    phash_distance = phash_hamming_distance(uploaded_phash, registered_phash)
    perceptual_match = phash_distance < PHASH_SIMILAR_THRESHOLD

    origin_verified = perceptual_match
    integrity = "original" if exact_match else ("transformed" if perceptual_match else "none")
    proof_verified_on_chain = on_chain.get("proof_verified_on_chain", False)

    # Fetch generation metadata + tx_hash from SQLite
    image_row = get_image_by_short_id(DB_PATH, short_id)
    job_row = get_job_by_short_id(DB_PATH, short_id)
    tx_hash = job_row.tx_hash if job_row else None
    arweave_id = job_row.arweave_id if job_row else None

    return {
        "verified": origin_verified,
        "integrity": integrity,
        "phash_distance": phash_distance,
        "short_id": short_id,
        "uploaded_phash": uploaded_phash,
        "contract_address": settings.contract_address,
        "semantic_fingerprint": {
            "match": semantic_match,
            "correlation": round(semantic_correlation, 4),
        },
        "tamper_risk": not perceptual_match,
        "zk_proof_valid": zk_proof_valid,
        "zk_proof_on_chain": proof_verified_on_chain,
        "on_chain": {
            "image_hash": on_chain["image_hash"],
            "perceptual_hash": registered_phash,
            "proof_verified_on_chain": proof_verified_on_chain,
            "registrant": on_chain["creator"],
            "timestamp": on_chain["timestamp"],
            "arweave_url": f"https://gateway.irys.xyz/{arweave_id}" if arweave_id else None,
            "explorer_url": (
                f"https://sepolia.basescan.org/tx/{tx_hash}"
                if tx_hash
                else f"https://sepolia.basescan.org/address/{settings.contract_address}"
            ),
        },
        "generation": {
            "model": image_row.model if image_row else "unknown",
            "prompt": image_row.prompt if image_row else None,
            "generated_at": datetime.fromtimestamp(image_row.created_at, tz=timezone.utc).isoformat()
            if image_row else None,
        },
    }


@app.get("/download/{watermark_id}")
async def download(watermark_id: str):
    image_row = get_image(DB_PATH, watermark_id)
    if image_row is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(
        content=image_row.image_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="proof-of-origin-{watermark_id}.png"'
        },
    )
