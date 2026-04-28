# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

VR 体验馆游客 3D 沉浸式纪念照生成系统。用户选择预设场景，上传个人照片，AI 将用户融入场景并生成可跟随鼠标交互的 3D 视差图。

主入口：`main.py`（FastAPI 服务器），运行命令：`uv run uvicorn main:app --reload --port 8000`

---

## Key Documents

- **`FEATURE_SPEC.md`** — 完整产品与技术规格文档
- **`EXECUTION_PLAN.md`** — 6 Phase / 19 Step 执行计划与里程碑

---

## 最终架构

**Tech stack:** FastAPI + LangGraph + InsightFace + SiliconFlow Qwen-Image-Edit（图像编辑）+ Depth Anything V2（本地深度估计）+ Three.js WebGL 视差渲染 + WebSocket

**LangGraph 节点流程（当前最终版）：**
```
load_scene → extract_face → generate_scene → quality_check → depth_estimation → output_result
                                  ↑               │ score < 0.6 且 retry < 3
                           increment_retry ◄───────┘
```

**目录结构：**
```
photo_gen/
├── main.py                        # FastAPI 入口，4个API + WebSocket + 静态文件
├── graph/
│   ├── state.py                   # ImageGenState TypedDict
│   ├── nodes.py                   # 6个节点函数
│   └── workflow.py                # StateGraph 编译
├── services/
│   ├── face_service.py            # InsightFace 人脸检测 + embedding
│   ├── generation_service.py      # SiliconFlow Qwen-Image-Edit API
│   ├── depth_service.py           # Depth Anything V2 本地推理
│   └── composite_service.py       # 已废弃（占位）
├── scenes/
│   └── config.json                # 3个场景纯提示词配置
├── static/                        # 前端 HTML/CSS/JS
├── outputs/                       # 生成结果（24h 自动清理）
├── models/                        # 本地模型文件（inswapper 等，已不使用）
├── pyproject.toml                 # uv 依赖管理
└── .env                           # API Key 和运行参数
```

---

## 环境配置

**`.env` 关键变量：**
```
SILICONFLOW_API_KEY=sk-...         # 硅基流动 API Key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
OUTPUT_DIR=outputs
SCENE_CONFIG_PATH=scenes/config.json
OUTPUT_RETENTION_HOURS=24
QUALITY_SCORE_THRESHOLD=0.6
MAX_RETRY_COUNT=3
```

**安装依赖：** `uv sync`（含 torch / torchvision / transformers，首次较慢）

---

## 三个场景

| ID | 名称 | 风格 |
|----|------|------|
| 1 | 魔法城堡探险 | Harry Potter / 霍格沃茨大礼堂，浮空蜡烛、巫师袍 |
| 2 | 宇宙探险 | 复古科幻 Alien 风，HR Giger 生化走廊、迷雾蒸汽 |
| 3 | 赛博都市 | Cyberpunk / Blade Runner，霓虹夜雨、中文全息广告 |

场景无需预置图片，全部由提示词驱动 Qwen-Image-Edit 生成。

---

## API 接口

| 接口 | 说明 |
|------|------|
| `GET /api/scenes` | 获取场景列表 |
| `POST /api/generate` | 上传照片 + scene_id，返回 task_id |
| `WS /ws/progress/{task_id}` | 实时推送进度（progress/done/error） |
| `GET /api/result/{task_id}` | 获取生成图 JPEG |
| `GET /api/depth/{task_id}` | 获取深度图 PNG（可能不存在） |

---

## 执行记录

### Phase 1 — 完成 (2026-04-27)
目录结构、`pyproject.toml`、`scenes/config.json`、`.env` 全部创建；`uv sync` 安装完成。

### Phase 2 — 完成 (2026-04-27)
`face_service.py`（InsightFace 检测/embedding）、`generation_service.py`、`composite_service.py` 三个 service 实现，导入验证通过。

### Phase 3 — 完成 (2026-04-27)
`graph/state.py` + `nodes.py` + `workflow.py` 实现，LangGraph 编译通过，条件重试逻辑完整。

### Phase 4 — 完成 (2026-04-27)
`main.py` 实现全部路由，WebSocket 进度推送，outputs/ 24h 自动清理。

### Phase 5 — 完成 (2026-04-27)
前端三文件完成：场景选择器、拖拽上传、WebSocket 进度条、Three.js 3D 视差渲染器（GLSL shader + 鼠标/触摸/陀螺仪）、下载按钮。

### 架构改造 v2 — 完成 (2026-04-27)
- 去掉背景图素材依赖，改为全提示词驱动文生图
- 新增 `depth_service.py`（Depth Anything V2 Small）
- 前端结果区改为 Three.js WebGL 视差 3D 渲染

### 问题修复记录

| 时间 | 问题 | 根因 | 修复 |
|------|------|------|------|
| 2026-04-27 | 图像生成 403 Forbidden | FLUX.1-schnell 账号被禁用 | 改用 `Kwai-Kolors/Kolors` |
| 2026-04-27 | Face swap 401 Unauthorized | HuggingFace inswapper 下载需鉴权 | 移除 swap_face 节点，改用 Qwen-Image-Edit 直接输入人脸 |
| 2026-04-27 | 生成模型改为 Qwen-Image-Edit | 账号仅此模型可用 | `generation_service.py` 传入 face_crop base64 作为输入图 |
| 2026-04-27 | 保存结果报 NoneType 错误 | depth_estimation 失败但流程未中断 | depth 失败改为非致命，output_result 加 None 检查，前端降级为平面展示 |
| 2026-04-27 | 深度图持续失败 | `torchvision` 未安装 | `pyproject.toml` 加入 `torchvision>=0.17.0`，`uv sync` 安装 |

---

## 开发注意事项

- Depth Anything V2 首次运行自动下载模型（~100MB），之后缓存在 HuggingFace 本地目录
- `quality_score` 阈值 0.6（cosine 相似度），低于此值且 retry < 3 时重新生成
- 生成图片由 Qwen 返回 S3 URL，下载后以原格式存储（实际为 PNG，扩展名写 .jpg 浏览器可正常读取）
- `swap_face` / `composite_service` 已废弃，不应再引用
- WebSocket 超时设为 180 秒（Qwen 生成 + 深度估计合计耗时）
