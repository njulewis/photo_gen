import io
import numpy as np
from PIL import Image

_MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
_processor = None
_model = None


def _load_model():
    global _processor, _model
    if _model is None:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        print(f"Loading depth model {_MODEL_ID} (first run: auto-download ~100MB)...")
        _processor = AutoImageProcessor.from_pretrained(_MODEL_ID)
        _model = AutoModelForDepthEstimation.from_pretrained(_MODEL_ID)
        _model.eval()

        if torch.backends.mps.is_available():
            _model = _model.to("mps")
        print("Depth model loaded.")
    return _processor, _model


def estimate_depth(image_bytes: bytes) -> bytes:
    """
    Run Depth Anything V2 on the input image.
    Returns a grayscale PNG depth map where brighter pixels = closer to camera.
    Output size matches input image size.
    """
    import torch

    processor, model = _load_model()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_w, orig_h = image.size

    inputs = processor(images=image, return_tensors="pt")

    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        depth = model(**inputs).predicted_depth.squeeze()

    depth_np = depth.cpu().float().numpy()

    # Normalise to [0, 1] then invert so that closer = brighter (higher value)
    d_min, d_max = depth_np.min(), depth_np.max()
    depth_norm = (depth_np - d_min) / (d_max - d_min + 1e-6)
    depth_inv = 1.0 - depth_norm          # invert: near → 1.0, far → 0.0
    depth_uint8 = (depth_inv * 255).astype(np.uint8)

    depth_img = Image.fromarray(depth_uint8, mode="L")
    depth_img = depth_img.resize((orig_w, orig_h), Image.BILINEAR)

    buf = io.BytesIO()
    depth_img.save(buf, format="PNG")
    return buf.getvalue()
