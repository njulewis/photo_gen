import json
import os
from dotenv import load_dotenv

from graph.state import ImageGenState
from services.face_service import detect_and_extract, compute_similarity, FaceNotFoundError
from services.generation_service import generate_scene

load_dotenv()

_SCENE_CONFIG_PATH = os.getenv("SCENE_CONFIG_PATH", "scenes/config.json")
_OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
_QUALITY_THRESHOLD = float(os.getenv("QUALITY_SCORE_THRESHOLD", "0.6"))
_MAX_RETRY = int(os.getenv("MAX_RETRY_COUNT", "3"))


def _report(state: ImageGenState, step: str, pct: int) -> None:
    cb = state.get("progress_callback")
    if cb:
        cb(step, pct)


def load_scene(state: ImageGenState) -> dict:
    _report(state, "加载场景配置", 5)
    with open(_SCENE_CONFIG_PATH, encoding="utf-8") as f:
        configs = json.load(f)
    scene_id = str(state["scene_id"])
    if scene_id not in configs:
        return {"error": f"Scene {scene_id} not found"}
    scene_config = configs[scene_id]

    scene_image_path = scene_config.get("scene_image", "")
    if not os.path.exists(scene_image_path):
        return {"error": f"Scene image not found: {scene_image_path}"}
    with open(scene_image_path, "rb") as f:
        scene_image_bytes = f.read()

    return {"scene_config": scene_config, "scene_image_bytes": scene_image_bytes, "error": None}


def extract_face(state: ImageGenState) -> dict:
    _report(state, "检测并提取人脸", 15)
    try:
        face_crop_bytes, embedding = detect_and_extract(state["user_photo_bytes"])
        return {"face_crop_bytes": face_crop_bytes, "face_embedding": embedding, "error": None}
    except FaceNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Face extraction failed: {e}"}


def generate_scene_node(state: ImageGenState) -> dict:
    _report(state, "AI 生成场景图", 40)
    try:
        scene_bytes = generate_scene(
            scene_config=state["scene_config"],
            scene_image_bytes=state["scene_image_bytes"],
            user_photo_bytes=state["user_photo_bytes"],
            retry_seed=state.get("retry_count", 0),
        )
        return {"generated_scene_bytes": scene_bytes, "error": None}
    except Exception as e:
        return {"error": f"Scene generation failed: {e}"}


def quality_check(state: ImageGenState) -> dict:
    _report(state, "质量检测", 80)
    try:
        _, gen_embedding = detect_and_extract(state["generated_scene_bytes"])
        score = compute_similarity(state["face_embedding"], gen_embedding)
    except FaceNotFoundError:
        score = 0.0
    except Exception:
        score = 0.55

    return {"quality_score": score}


def output_result(state: ImageGenState) -> dict:
    _report(state, "保存结果", 95)
    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    img_bytes = state.get("generated_scene_bytes")
    if not img_bytes:
        return {"error": "Generated image is empty, cannot save result"}

    img_path = os.path.join(_OUTPUT_DIR, f"{state['task_id']}.jpg")
    with open(img_path, "wb") as f:
        f.write(img_bytes)

    _report(state, "完成", 100)
    return {"output_path": img_path}
