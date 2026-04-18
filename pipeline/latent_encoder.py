
import hashlib
import io
import logging
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


_WATERMARK_LEN = 16


def _short_id_to_bytes(short_id: str) -> bytes:
    return bytes.fromhex(short_id[:_WATERMARK_LEN])


def _bytes_to_hex(data: bytes) -> str:
    return data.hex()



def _try_imwatermark():
    try:
        from imwatermark import WatermarkEncoder, WatermarkDecoder
        return WatermarkEncoder, WatermarkDecoder
    except ImportError:
        return None



def _embed_pywt(img_array: np.ndarray, bits: np.ndarray, strength: float = 5.0) -> np.ndarray:
    import pywt

    result = img_array.copy().astype(np.float64)
    for c in range(min(3, result.shape[2])):
        channel = result[:, :, c]
        coeffs = pywt.wavedec2(channel, "haar", level=2)

        cA, (cH1, cV1, cD1) = coeffs[0], coeffs[1]
        U, S, Vt = np.linalg.svd(cV1, full_matrices=False)

        n = min(len(bits), len(S))
        q = strength
        for i in range(n):
            if np.isfinite(S[i]):
                S[i] = q * round(S[i] / q) + q * (bits[i] - 0.5) * 0.5

        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            cV1_mod = np.nan_to_num(U @ np.diag(S) @ Vt)
        coeffs[1] = (cH1, cV1_mod, cD1)

        rec = pywt.waverec2(coeffs, "haar")
        result[:, :, c] = rec[: channel.shape[0], : channel.shape[1]]

    return np.clip(result, 0, 255).astype(np.uint8)


def _extract_pywt(img_array: np.ndarray, n_bits: int = 64, strength: float = 5.0) -> np.ndarray:
    import pywt

    votes = np.zeros(n_bits, dtype=np.float64)
    arr = img_array.astype(np.float64)

    for c in range(min(3, arr.shape[2])):
        channel = arr[:, :, c]
        coeffs = pywt.wavedec2(channel, "haar", level=2)
        _, (_, cV1, _) = coeffs[0], coeffs[1]
        _, S, _ = np.linalg.svd(cV1, full_matrices=False)

        n = min(n_bits, len(S))
        q = strength
        for i in range(n):
            remainder = (S[i] % q) / q
            votes[i] += 1.0 if remainder > 0.25 else -1.0

    return (votes > 0).astype(np.uint8)



class LatentEncoder:

    def __init__(self, strength: float = 5.0, method: str = "auto"):
        self.strength = strength

        if method == "auto":
            self._use_imw = _try_imwatermark() is not None
        else:
            self._use_imw = method == "dwtDctSvd"

        backend = "invisible-watermark (DWT-DCT-SVD)" if self._use_imw else "pywt+SVD fallback"
        logger.info("LatentEncoder initialised | backend=%s strength=%.1f", backend, strength)


    def embed(self, image_bytes: bytes, short_id: str) -> bytes:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        if self._use_imw:
            img_array = self._embed_imw(img_array, short_id)
        else:
            bits = np.unpackbits(np.frombuffer(_short_id_to_bytes(short_id), dtype=np.uint8))
            img_array = _embed_pywt(img_array, bits.astype(np.float64), self.strength)

        result = Image.fromarray(img_array, "RGB")
        buf = io.BytesIO()
        result.save(buf, format="PNG")
        logger.debug("semantic embed OK | short_id=%s method=%s", short_id, "imw" if self._use_imw else "pywt")
        return buf.getvalue()

    def _embed_imw(self, img_array: np.ndarray, short_id: str) -> np.ndarray:
        from imwatermark import WatermarkEncoder
        import cv2

        h, w = img_array.shape[:2]
        if h * w < 256 * 256:
            bits = np.unpackbits(np.frombuffer(_short_id_to_bytes(short_id), dtype=np.uint8))
            return _embed_pywt(img_array, bits.astype(np.float64), self.strength)

        bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        encoder = WatermarkEncoder()
        encoder.set_watermark("bytes", _short_id_to_bytes(short_id))
        encoded = encoder.encode(bgr, "dwtDctSvd")
        return cv2.cvtColor(encoded, cv2.COLOR_BGR2RGB)


    def extract(self, image_bytes: bytes) -> Optional[str]:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        try:
            if self._use_imw:
                raw = self._extract_imw(img_array)
            else:
                bits = _extract_pywt(img_array, n_bits=64, strength=self.strength)
                raw = np.packbits(bits).tobytes()

            hex_str = _bytes_to_hex(raw[:8])
            int(hex_str, 16)
            return hex_str
        except Exception as exc:
            logger.debug("semantic extract failed: %s", exc)
            return None

    def _extract_imw(self, img_array: np.ndarray) -> bytes:
        from imwatermark import WatermarkDecoder
        import cv2

        h, w = img_array.shape[:2]
        if h * w < 256 * 256:
            bits = _extract_pywt(img_array, n_bits=64, strength=self.strength)
            return np.packbits(bits).tobytes()

        bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        decoder = WatermarkDecoder("bytes", 8 * 8)
        return decoder.decode(bgr, "dwtDctSvd")


    def verify(self, image_bytes: bytes, short_id: str, threshold: float = 0.70) -> tuple[bool, float]:
        expected_bytes = _short_id_to_bytes(short_id)
        expected_bits = np.unpackbits(np.frombuffer(expected_bytes, dtype=np.uint8))

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        try:
            if self._use_imw:
                raw = self._extract_imw(img_array)
            else:
                extracted_bits = _extract_pywt(img_array, n_bits=64, strength=self.strength)
                raw = np.packbits(extracted_bits).tobytes()

            extracted_bits = np.unpackbits(np.frombuffer(raw[:8], dtype=np.uint8))
            n = min(len(expected_bits), len(extracted_bits))
            correlation = float(np.mean(expected_bits[:n] == extracted_bits[:n]))
        except Exception as exc:
            logger.debug("semantic verify failed: %s", exc)
            correlation = 0.0

        return correlation >= threshold, correlation


_encoder: Optional[LatentEncoder] = None


def get_encoder() -> LatentEncoder:
    global _encoder
    if _encoder is None:
        _encoder = LatentEncoder()
    return _encoder
