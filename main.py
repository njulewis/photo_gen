import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from graph.workflow import graph

load_dotenv()

_SCENE_CONFIG_PATH = os.getenv("SCENE_CONFIG_PATH", "scenes/config.json")
_OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
_RETENTION_HOURS = float(os.getenv("OUTPUT_RETENTION_HOURS", "24"))

_progress_queues: Dict[str, asyncio.Queue] = {}
_task_results: Dict[str, dict] = {}


async def _cleanup_old_outputs():
    while True:
        await asyncio.sleep(3600)
        cutoff = time.time() - _RETENTION_HOURS * 3600
        for fname in os.listdir(_OUTPUT_DIR):
            fpath = os.path.join(_OUTPUT_DIR, fname)
            try:
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
            except OSError:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    if not os.getenv("ARK_API_KEY"):
        print("\n⚠️  未检测到 ARK_API_KEY，请在 .env 文件中填入你的火山引擎 API Key：")
        print("   ARK_API_KEY=your_key_here")
        print("   获取地址：https://console.volcengine.com/ark/region:ark+cn-beijing/apikey\n")
    asyncio.create_task(_cleanup_old_outputs())
    yield


app = FastAPI(title="Scene Photo Fusion", lifespan=lifespan)


@app.get("/api/scenes")
async def get_scenes():
    with open(_SCENE_CONFIG_PATH, encoding="utf-8") as f:
        configs = json.load(f)
    return {"scenes": [
        {"id": int(sid), "name": cfg["name"], "description": cfg["description"],
         "thumbnail": f"/scenes/{sid}/thumbnail.jpg"}
        for sid, cfg in configs.items()
    ]}


@app.post("/api/generate")
async def generate(scene_id: int = Form(...), photo: UploadFile = File(...)):
    if photo.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Only JPEG/PNG/WebP images are accepted")
    photo_bytes = await photo.read()
    if len(photo_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "Image size must be ≤ 10 MB")

    task_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _progress_queues[task_id] = queue
    asyncio.create_task(_run_graph(task_id, scene_id, photo_bytes, queue))
    return {"task_id": task_id}


async def _run_graph(task_id: str, scene_id: int, photo_bytes: bytes, queue: asyncio.Queue):
    loop = asyncio.get_event_loop()

    def progress_callback(step: str, pct: int):
        loop.call_soon_threadsafe(
            queue.put_nowait, {"type": "progress", "step": step, "percent": pct}
        )

    initial_state = {
        "scene_id": scene_id,
        "user_photo_bytes": photo_bytes,
        "scene_config": None,
        "scene_image_bytes": None,
        "face_embedding": None,
        "face_crop_bytes": None,
        "generated_scene_bytes": None,
        "quality_score": 0.0,
        "retry_count": 0,
        "output_path": None,
        "task_id": task_id,
        "progress_callback": progress_callback,
        "error": None,
    }

    try:
        final_state = await loop.run_in_executor(None, graph.invoke, initial_state)
        _task_results[task_id] = final_state
        if final_state.get("error"):
            await queue.put({"type": "error", "message": final_state["error"]})
        else:
            await queue.put({"type": "done", "task_id": task_id})
    except Exception as e:
        _task_results[task_id] = {"error": str(e)}
        await queue.put({"type": "error", "message": str(e)})


@app.websocket("/ws/progress/{task_id}")
async def ws_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    if task_id not in _progress_queues:
        await websocket.send_json({"type": "error", "message": "Unknown task_id"})
        await websocket.close()
        return

    queue = _progress_queues[task_id]
    try:
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=360)
            await websocket.send_json(msg)
            if msg["type"] in ("done", "error"):
                break
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "Task timed out"})
    except WebSocketDisconnect:
        pass
    finally:
        _progress_queues.pop(task_id, None)
        await websocket.close()


@app.get("/api/result/{task_id}")
async def get_result(task_id: str):
    result = _task_results.get(task_id)
    if result is None:
        raise HTTPException(404, "Task not found or still running")
    if result.get("error"):
        raise HTTPException(500, result["error"])
    out_path: str = result.get("output_path", "")
    if not out_path or not os.path.exists(out_path):
        raise HTTPException(404, "Output file not found")
    return FileResponse(out_path, media_type="image/jpeg", filename=f"{task_id}.jpg")


app.mount("/scenes", StaticFiles(directory="scenes"), name="scenes")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
