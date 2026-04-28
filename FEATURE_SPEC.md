# 场景融合照片生成功能文档

## 一、产品概述

用户选择预设场景，上传个人照片，系统通过 AI 图像生成与融合技术，将用户面部特征与场景预设人物动作相结合，生成一张用户身处该场景的沉浸式照片。

---

## 二、功能模块

### 2.1 前端页面

**场景选择器**
- 展示 3 个预设场景缩略图，编号 1-3
- 点击切换当前选中场景，高亮显示
- 每个场景展示名称和简短描述

**照片上传组件**
- 支持点击上传或拖拽上传
- 格式限制：JPG / PNG，大小 ≤ 10MB
- 上传后显示预览缩略图
- 人脸检测失败时给出明确提示（"未检测到人脸，请重新上传"）

**生成按钮与进度反馈**
- 点击"开始生成"触发后端流程
- 通过 WebSocket 实时推送进度（加载场景 → 提取人脸 → 生成人物 → 融合场景 → 质量检测 → 完成）
- 进度条 + 当前步骤文字说明

**结果展示**
- 生成完成后展示最终图片
- 提供下载按钮
- 提供"重新生成"和"换一个场景"按钮

---

### 2.2 后端 API（FastAPI）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/scenes` | GET | 获取所有场景配置（名称、缩略图、描述） |
| `/api/generate` | POST | 接收 scene_id + 用户照片，返回 task_id |
| `/ws/progress/{task_id}` | WebSocket | 推送生成进度 |
| `/api/result/{task_id}` | GET | 获取最终生成图片 |

---

### 2.3 场景配置系统

每个场景预先配置以下信息，存储在 `scenes/config.json`：

```json
{
  "1": {
    "name": "山顶英雄",
    "description": "站在雪山之巅，感受天地辽阔",
    "background_image": "scenes/1/background.jpg",
    "thumbnail": "scenes/1/thumbnail.jpg",
    "pose_image": "scenes/1/pose_reference.jpg",
    "pose_keypoints": "scenes/1/pose.json",
    "style_prompt": "epic cinematic lighting, golden hour, mountain peak, dramatic sky",
    "negative_prompt": "blurry, low quality, distorted face"
  },
  "2": {
    "name": "海边漫步",
    "description": "沐浴夕阳余晖，漫步金色沙滩",
    "background_image": "scenes/2/background.jpg",
    "thumbnail": "scenes/2/thumbnail.jpg",
    "pose_image": "scenes/2/pose_reference.jpg",
    "pose_keypoints": "scenes/2/pose.json",
    "style_prompt": "golden sunset, beach, warm tones, soft lighting, ocean waves",
    "negative_prompt": "blurry, low quality, distorted face"
  },
  "3": {
    "name": "都市精英",
    "description": "繁华都市中心，尽显职场风采",
    "background_image": "scenes/3/background.jpg",
    "thumbnail": "scenes/3/thumbnail.jpg",
    "pose_image": "scenes/3/pose_reference.jpg",
    "pose_keypoints": "scenes/3/pose.json",
    "style_prompt": "modern city, professional, sharp suit, city lights, confident pose",
    "negative_prompt": "blurry, low quality, distorted face"
  }
}
```

---

### 2.4 LangGraph AI 编排流程

#### State 定义

```python
class ImageGenState(TypedDict):
    scene_id: int
    scene_config: dict
    user_photo_bytes: bytes
    face_embedding: Optional[any]
    face_crop: Optional[bytes]
    generated_char: Optional[bytes]
    final_image: Optional[bytes]
    quality_score: float
    retry_count: int
    error: Optional[str]
    progress_callback: Callable
```

#### 节点列表

| 节点名 | 功能 | 输入 | 输出 |
|--------|------|------|------|
| `load_scene` | 根据 scene_id 读取场景配置 | scene_id | scene_config |
| `extract_face` | 人脸检测、提取、embedding | user_photo_bytes | face_embedding, face_crop |
| `generate_char` | IP-Adapter + ControlNet 生成带预设姿势的用户人物图 | face_embedding, scene_config | generated_char |
| `composite_image` | 人物与背景融合（色调/光影匹配） | generated_char, scene_config | final_image |
| `quality_check` | 评估人脸相似度与图像自然度 | final_image, face_embedding | quality_score |
| `output` | 保存结果，通知前端完成 | final_image | 最终图片路径 |

#### 流程图

```
load_scene
    │
extract_face ──► [人脸未检测到] ──► 返回错误
    │
generate_char
    │
composite_image
    │
quality_check
    │
  ┌─┴─────────────────────────┐
score ≥ 0.7                score < 0.7 且 retry < 3
  │                              │
output                    retry_count += 1
                               │
                          generate_char (重试)
                               │
                    retry >= 3 ──► output（取最佳结果）
```

---

### 2.5 图像处理技术栈

| 功能 | 技术方案 |
|------|---------|
| 人脸检测与提取 | InsightFace（`buffalo_l` 模型） |
| 人脸特征保留 | IP-Adapter FaceID（via Replicate API 或本地 ComfyUI） |
| 姿势控制 | ControlNet OpenPose |
| 图像融合后处理 | OpenCV（泊松融合）+ Pillow（色调匹配） |
| 背景分割 | rembg（去除人物背景便于融合） |

---

## 三、目录结构

```
photo_gen/
├── CLAUDE.md
├── FEATURE_SPEC.md
├── EXECUTION_PLAN.md
├── main.py                  # FastAPI 入口
├── graph/
│   ├── __init__.py
│   ├── state.py             # State TypedDict
│   ├── nodes.py             # 各节点函数
│   └── workflow.py          # LangGraph 图构建
├── services/
│   ├── face_service.py      # 人脸处理
│   ├── generation_service.py # 图像生成
│   └── composite_service.py  # 图像融合
├── scenes/
│   ├── config.json
│   ├── 1/
│   ├── 2/
│   └── 3/
├── static/                  # 前端静态文件
│   ├── index.html
│   ├── app.js
│   └── style.css
├── outputs/                 # 生成结果存储
└── requirements.txt
```

---

## 四、非功能需求

- **响应时间**：生成全流程 ≤ 60 秒（使用 Replicate API）
- **并发**：初期支持单任务队列，后期可接入 Celery
- **错误处理**：每个节点捕获异常，通过 WebSocket 返回友好错误信息
- **图片存储**：本地 `outputs/` 目录，文件名使用 task_id，保留 24 小时后清理

---

## 五、依赖项

```
fastapi
uvicorn
langgraph
langchain-core
insightface
onnxruntime
opencv-python
Pillow
rembg
replicate
websockets
python-multipart
aiofiles
```
