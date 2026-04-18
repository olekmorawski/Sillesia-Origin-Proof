"""Multi-layer watermarking — pixel, neural, and semantic frequency-domain.

Three-layer defence-in-depth:
  Layer 0 (semantic):   DWT-DCT-SVD frequency-domain fingerprint — survives AI
                        regeneration (img2img), aggressive JPEG, and screenshots.
                        Encodes short_id into wavelet sub-band singular values.
  Layer 1 (neural):     TrustMark (Adobe/CAI) 100-bit BCH-protected neural watermark.
                        Survives JPEG, resize, format conversion.
  Layer 2 (metadata):   PNG iTXt text chunk — human-readable, easily verified.

ZK proof integration:
  dual_watermark() optionally captures the encoder input tensors during the
  forward pass so generate_proof() can prove honest watermark application.

Payload: 16-char hex short_id derived from watermark_id UUID.
Models are downloaded automatically on first use.
"""

import hashlib
import io
import json
import logging
from typing import Optional

import numpy as np
from PIL import Image, PngImagePlugin

from pipeline.latent_encoder import get_encoder as _get_semantic_encoder

logger = logging.getLogger(__name__)

PNG_METADATA_KEY = "ProofOfOrigin"

_tm = None


def _get_model():
    global _tm
    if _tm is None:
        from trustmark import TrustMark
        _tm = TrustMark(verbose=False, model_type='Q')
    return _tm


def _short_id(uuid_str: str, length: int = 16) -> str:
    return hashlib.sha256(uuid_str.encode()).hexdigest()[:length]


def dual_watermark(
    image_bytes: bytes,
    provenance: dict,
    capture_tensors: bool = False,
) -> tuple[bytes, Optional[tuple[np.ndarray, np.ndarray]]]:
    """Embed provenance into image via two independent watermark layers.

    Layer 1 — TrustMark neural watermark:
        Encodes a 16-char short_id into pixel data. Robust against JPEG
        compression, resizing, and basic image transforms.

    Layer 2 — PNG iTXt metadata chunk:
        Embeds full provenance JSON as a human-readable text chunk under
        the key "ProofOfOrigin". Survives lossless copies; stripped by
        re-encoding to JPEG (hence Layer 1 as primary).

    Args:
        image_bytes:     Input image bytes (any PIL-readable format).
        provenance:      Dict with {"watermark_id": str, "short_id": str, "timestamp": str}.
        capture_tensors: If True, register a forward hook and return the
                         (image_tensor, secret_tensor) arrays passed to the
                         encoder — used by generate_proof().

    Returns:
        (watermarked_png_bytes, tensors_or_None)
        tensors_or_None is (image_np, secret_np) when capture_tensors=True
        and the hook fired, else None.
    """
    watermark_id = provenance.get("watermark_id", "")
    sid = _short_id(watermark_id)

    # Layer 0: Semantic frequency-domain fingerprint (DWT-DCT-SVD)
    try:
        semantic_enc = _get_semantic_encoder()
        image_bytes = semantic_enc.embed(image_bytes, sid)
        logger.debug("Semantic layer (Layer 0) encoded | short_id=%s", sid)
    except Exception as exc:
        logger.warning("Semantic layer skipped: %s", exc)

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    model = _get_model()

    # Optionally capture encoder input tensors for ZK proof
    captured: dict = {}
    handle = None
    if capture_tensors:
        def _hook(module, inputs, output):
            # inputs = (image_tensor, secret_bits_tensor)
            if len(inputs) >= 2:
                captured["image"] = inputs[0].detach().cpu().numpy()
                captured["secret"] = inputs[1].detach().cpu().numpy()

        handle = model.encoder.register_forward_hook(_hook)

    # Layer 1: TrustMark neural watermark
    watermarked = model.encode(img, sid)
    if handle is not None:
        handle.remove()
    logger.debug("TrustMark layer encoded | short_id=%s", sid)

    # Layer 2: PNG iTXt metadata chunk
    pnginfo = PngImagePlugin.PngInfo()
    metadata_payload = json.dumps({
        "short_id": sid,
        "watermark_id": watermark_id,
        "timestamp": provenance.get("timestamp", ""),
    })
    pnginfo.add_itxt(PNG_METADATA_KEY, metadata_payload)

    out = io.BytesIO()
    watermarked.save(out, format="PNG", pnginfo=pnginfo)

    tensors = None
    if capture_tensors and "image" in captured and "secret" in captured:
        tensors = (captured["image"], captured["secret"])
        logger.debug("Encoder tensors captured | image=%s secret=%s",
                     captured["image"].shape, captured["secret"].shape)

    return out.getvalue(), tensors


def verify_lsb(image_bytes: bytes) -> Optional[dict]:
    """Extract watermark via TrustMark decoder (Layer 1).

    Accepts PNG or JPEG — TrustMark is robust to JPEG compression.

    Returns:
        {"short_id": str} if watermark detected, else None.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        model = _get_model()
        wm_secret, wm_present, wm_schema = model.decode(img)

        decoded = wm_secret.strip() if wm_secret else ""
        if wm_present and len(decoded) == 16 and all(c in "0123456789abcdef" for c in decoded):
            return {"short_id": decoded}
    except Exception as exc:
        logger.debug("TrustMark decode failed: %s", exc)
    return None


def verify_exif(image_bytes: bytes) -> Optional[dict]:
    """Extract provenance from PNG iTXt metadata chunk (Layer 2).

    Reads the "ProofOfOrigin" iTXt chunk embedded by dual_watermark().
    This layer is present on lossless PNG copies but stripped by JPEG
    re-encoding — use verify_lsb() as primary and this as fallback.

    Returns:
        {"short_id": str, ...} if metadata chunk found, else None.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        text_data = img.info.get(PNG_METADATA_KEY)
        if text_data:
            payload = json.loads(text_data)
            if "short_id" in payload:
                logger.debug("PNG metadata layer found | short_id=%s", payload["short_id"])
                return payload
    except Exception as exc:
        logger.debug("PNG metadata decode failed: %s", exc)
    return None


def sha256_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


# ---------------------------------------------------------------------------
# Perceptual hash — binarized DINOv2 ViT-S/14, robust to JPEG/resize/screenshot
# ---------------------------------------------------------------------------

PHASH_SIMILAR_THRESHOLD = 15  # Hamming bits; < 15 → perceptually same image

_dino_model = None


def _get_dino():
    global _dino_model
    if _dino_model is None:
        import torch
        _dino_model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')
        _dino_model.eval()
    return _dino_model


def compute_phash(image_bytes: bytes) -> int:
    """Compute 63-bit binarized DINOv2 fingerprint packed into an int64-safe uint64.

    Run DINOv2 ViT-S/14, extract CLS token (384-dim), select 64 evenly-spaced
    dimensions (DINO_DIM_MASK), threshold each at the mean, pack into a 63-bit
    integer. The top bit is forced to 0 so the value always fits in SQLite's
    signed INTEGER (int64) column and in Solidity's uint64 without sign issues.

    DINO_DIM_MASK is a protocol constant — changing it invalidates all registered
    pHashes. It lives in settings.py as DINO_DIM_MASK.
    """
    import torch
    from torchvision import transforms
    from settings import DINO_DIM_MASK

    transform = transforms.Compose([
        transforms.Resize(224),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = transform(img).unsqueeze(0)  # (1, 3, 224, 224)

    with torch.no_grad():
        output = _get_dino()(tensor)

    emb = output[0].numpy()                       # CLS token, shape (384,)
    selected = emb[DINO_DIM_MASK]                 # shape (64,)
    bits = (selected > selected.mean()).astype(int)

    result = 0
    for b in bits:
        result = (result << 1) | int(b)
    return result & ((1 << 63) - 1)               # top bit forced to 0


def phash_hamming_distance(a: int, b: int) -> int:
    """Count differing bits between two 64-bit pHashes."""
    return bin(a ^ b).count("1")


def verify_semantic(image_bytes: bytes, short_id: str) -> tuple[bool, float]:
    """Verify semantic (DWT-DCT-SVD) watermark layer.

    Returns (is_authentic, bit_correlation) where correlation is 0.0–1.0.
    Falls back to (False, 0.0) if the semantic backend is unavailable.
    """
    try:
        encoder = _get_semantic_encoder()
        return encoder.verify(image_bytes, short_id)
    except Exception as exc:
        logger.debug("Semantic verify unavailable: %s", exc)
        return False, 0.0
