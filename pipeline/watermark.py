
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
    watermark_id = provenance.get("watermark_id", "")
    sid = _short_id(watermark_id)

    try:
        semantic_enc = _get_semantic_encoder()
        image_bytes = semantic_enc.embed(image_bytes, sid)
        logger.debug("Semantic layer (Layer 0) encoded | short_id=%s", sid)
    except Exception as exc:
        logger.warning("Semantic layer skipped: %s", exc)

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    model = _get_model()

    captured: dict = {}
    handle = None
    if capture_tensors:
        def _hook(module, inputs, output):
            if len(inputs) >= 2:
                captured["image"] = inputs[0].detach().cpu().numpy()
                captured["secret"] = inputs[1].detach().cpu().numpy()

        handle = model.encoder.register_forward_hook(_hook)

    watermarked = model.encode(img, sid)
    if handle is not None:
        handle.remove()
    logger.debug("TrustMark layer encoded | short_id=%s", sid)

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



PHASH_SIMILAR_THRESHOLD = 15

_dino_model = None


def _get_dino():
    global _dino_model
    if _dino_model is None:
        import torch
        _dino_model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')
        _dino_model.eval()
    return _dino_model


def compute_phash(image_bytes: bytes) -> int:
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
    tensor = transform(img).unsqueeze(0)

    with torch.no_grad():
        output = _get_dino()(tensor)

    emb = output[0].numpy()
    selected = emb[DINO_DIM_MASK]
    bits = (selected > selected.mean()).astype(int)

    result = 0
    for b in bits:
        result = (result << 1) | int(b)
    return result & ((1 << 63) - 1)


def phash_hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def verify_semantic(image_bytes: bytes, short_id: str) -> tuple[bool, float]:
    try:
        encoder = _get_semantic_encoder()
        return encoder.verify(image_bytes, short_id)
    except Exception as exc:
        logger.debug("Semantic verify unavailable: %s", exc)
        return False, 0.0
