from typing import TypedDict, Optional, Callable
import numpy as np


class ImageGenState(TypedDict):
    # inputs
    scene_id: int
    user_photo_bytes: bytes

    # loaded config
    scene_config: Optional[dict]
    scene_image_bytes: Optional[bytes]

    # face extraction
    face_embedding: Optional[np.ndarray]   # shape (512,), L2-normalised
    face_crop_bytes: Optional[bytes]

    # Qwen-Image-Edit output
    generated_scene_bytes: Optional[bytes]

    # quality check
    quality_score: float
    retry_count: int

    # output
    output_path: Optional[str]
    task_id: str

    # injected at runtime, not serialised
    progress_callback: Optional[Callable[[str, int], None]]

    # error
    error: Optional[str]
