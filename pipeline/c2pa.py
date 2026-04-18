import io
import json
import logging
from typing import Optional

from settings import settings

logger = logging.getLogger(__name__)


def sign_with_c2pa(image_bytes: bytes, provenance: dict) -> bytes:
    if not settings.c2pa_cert_pem or not settings.c2pa_private_key_pem:
        logger.debug("C2PA signing skipped: certs not configured")
        return image_bytes

    try:
        import c2pa

        manifest_def = {
            "claim_generator": "ProofOfOrigin/1.0",
            "format": "image/png",
            "assertions": [
                {
                    "label": "com.proof-of-origin.watermark",
                    "data": {
                        "watermark_id": provenance.get("watermark_id", ""),
                        "short_id":     provenance.get("short_id", ""),
                        "timestamp":    provenance.get("timestamp", ""),
                    },
                }
            ],
        }

        def _sign(data: bytes) -> bytes:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import hashes, serialization
            key = serialization.load_pem_private_key(
                settings.c2pa_private_key_pem.encode(), password=None
            )
            return key.sign(data, ec.ECDSA(hashes.SHA256()))

        signer = c2pa.create_signer(
            _sign,
            c2pa.SigningAlg.ES256,
            settings.c2pa_cert_pem.encode(),
            None,
        )

        builder = c2pa.Builder(json.dumps(manifest_def))
        output = io.BytesIO()
        builder.sign(signer, "image/png", io.BytesIO(image_bytes), output)
        signed = output.getvalue()

        if not signed:
            logger.warning("C2PA builder.sign produced empty output; returning original")
            return image_bytes

        logger.debug("C2PA manifest signed | watermark_id=%s", provenance.get("watermark_id"))
        return signed

    except Exception as exc:
        logger.warning("C2PA signing failed: %s; returning original bytes", exc)
        return image_bytes
