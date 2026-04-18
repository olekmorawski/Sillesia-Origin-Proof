
import base64
import logging
import requests
from io import BytesIO
from PIL import Image
from settings import settings

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = [
    "black-forest-labs/flux.2-pro",
    "black-forest-labs/flux.2-schnell",
    "black-forest-labs/flux.2-klein-4b",
    "openai/dall-e-3",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-2.0-flash-exp",
]


def generate_image(
    refined_prompt: str, model: str | None = None, dev_mode: bool = False
) -> bytes:
    if dev_mode:
        model = "black-forest-labs/flux.2-klein-4b"
    elif model is None:
        model = settings.default_model

    if model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model: {model}. Supported: {SUPPORTED_MODELS}")
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://proof-of-origin.demo",
            "X-Title": "Proof of Origin",
        },
        json={
            "model": model,
            "messages": [
                {"role": "user", "content": refined_prompt},
            ],
            "modalities": ["image"],
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise RuntimeError(f"OpenRouter error: {data['error']['message']}")

    try:
        image_url = data["choices"][0]["message"]["images"][0]["image_url"]["url"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected image response shape: {data}") from exc

    if image_url.startswith("data:"):
        _header, b64_data = image_url.split(",", 1)
        raw_bytes = base64.b64decode(b64_data)
    else:
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        raw_bytes = img_resp.content

    img = Image.open(BytesIO(raw_bytes))
    img.load()
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    logger.info("generated %d bytes PNG (%dx%d)", len(png_bytes), img.size[0], img.size[1])
    return png_bytes
