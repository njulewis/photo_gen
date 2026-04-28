import base64
import os
import httpx
from dotenv import load_dotenv
from volcenginesdkarkruntime import Ark

load_dotenv()

_client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv("ARK_API_KEY", ""),
    timeout=300,
)
_MODEL = "doubao-seedream-5-0-260128"


def _to_data_uri(image_bytes: bytes) -> str:
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        mime = "image/png"
    elif image_bytes[:3] == b'\xff\xd8\xff':
        mime = "image/jpeg"
    elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"


def generate_scene(
    scene_config: dict,
    scene_image_bytes: bytes,
    user_photo_bytes: bytes,
    retry_seed: int = 0,
) -> bytes:
    response = _client.images.generate(
        model=_MODEL,
        prompt=scene_config["fusion_prompt"],
        image=[
            _to_data_uri(scene_image_bytes),
            _to_data_uri(user_photo_bytes),
        ],
        size="2K",
        sequential_image_generation="disabled",
        output_format="png",
        response_format="url",
        watermark=False,
    )

    image_url: str = response.data[0].url

    dl_timeout = httpx.Timeout(connect=15.0, read=120.0, write=10.0, pool=5.0)
    with httpx.Client(timeout=dl_timeout) as client:
        img_resp = client.get(image_url)
        img_resp.raise_for_status()

    return img_resp.content
