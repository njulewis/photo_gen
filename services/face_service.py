import os
import io
import urllib.request
import numpy as np
import cv2
import insightface
from insightface.app import FaceAnalysis
from insightface.model_zoo import model_zoo

_INSWAPPER_URL = "https://huggingface.co/deepinsight/inswapper/resolve/main/inswapper_128.onnx"
_INSWAPPER_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "inswapper_128.onnx")


class FaceNotFoundError(Exception):
    pass


_app: FaceAnalysis | None = None
_swapper = None


def _get_app() -> FaceAnalysis:
    global _app
    if _app is None:
        _app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(640, 640))
    return _app


def _get_swapper():
    global _swapper
    if _swapper is None:
        model_path = os.path.abspath(_INSWAPPER_PATH)
        if not os.path.exists(model_path):
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            print(f"Downloading inswapper model to {model_path} ...")
            urllib.request.urlretrieve(_INSWAPPER_URL, model_path)
            print("Download complete.")
        _swapper = insightface.model_zoo.get_model(
            model_path, providers=["CPUExecutionProvider"]
        )
    return _swapper


def detect_and_extract(image_bytes: bytes) -> tuple[bytes, np.ndarray]:
    """Detect the largest face, return (cropped face JPEG bytes, 512-d embedding)."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Cannot decode image")

    app = _get_app()
    faces = app.get(img)

    if not faces:
        raise FaceNotFoundError("No face detected in the uploaded image")

    # pick the largest face by bounding-box area
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    x1, y1, x2, y2 = [int(v) for v in face.bbox]
    # add 20% padding
    pad_x = int((x2 - x1) * 0.2)
    pad_y = int((y2 - y1) * 0.2)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(img.shape[1], x2 + pad_x)
    y2 = min(img.shape[0], y2 + pad_y)

    face_crop = img[y1:y2, x1:x2]
    _, buf = cv2.imencode(".jpg", face_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
    face_bytes = buf.tobytes()

    embedding: np.ndarray = face.normed_embedding  # shape (512,), already L2-normalised

    return face_bytes, embedding


def compute_similarity(emb_a: np.ndarray, emb_b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalised embeddings."""
    return float(np.dot(emb_a, emb_b))


def swap_face(source_bytes: bytes, target_bytes: bytes) -> bytes:
    """
    Swap the face from source image into the largest face found in target image.
    source_bytes: user's original photo
    target_bytes: generated character image from SiliconFlow
    Returns JPEG bytes of the target image with the user's face swapped in.
    """
    src_arr = np.frombuffer(source_bytes, dtype=np.uint8)
    src_img = cv2.imdecode(src_arr, cv2.IMREAD_COLOR)

    tgt_arr = np.frombuffer(target_bytes, dtype=np.uint8)
    tgt_img = cv2.imdecode(tgt_arr, cv2.IMREAD_COLOR)

    app = _get_app()
    swapper = _get_swapper()

    src_faces = app.get(src_img)
    if not src_faces:
        raise FaceNotFoundError("No face found in source (user) image for swapping")

    tgt_faces = app.get(tgt_img)
    if not tgt_faces:
        raise FaceNotFoundError("No face found in generated target image for swapping")

    src_face = max(src_faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    tgt_face = max(tgt_faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    result = swapper.get(tgt_img, tgt_face, src_face, paste_back=True)

    _, buf = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buf.tobytes()

