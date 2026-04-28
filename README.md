# 沉浸式纪念照生成系统

上传一张自拍，选择预设场景，AI 自动将你的脸融合进场景图，生成一张专属纪念照。

## 功能

- 三个预设场景：魔法城堡探险、宇宙探险、赛博都市
- 上传自拍后自动检测人脸，融合进场景图
- 实时进度推送（WebSocket）
- 生成完成后可直接下载

## 技术栈

FastAPI · LangGraph · InsightFace · 火山引擎 Seedream 5.0

## 快速开始

**1. 安装依赖**

```bash
pip install uv
uv sync
```

**2. 配置 API Key**

复制 `.env.example` 为 `.env`，填入火山引擎 API Key：

```bash
cp .env.example .env
```

```
ARK_API_KEY=your_key_here
```

> 获取 API Key：https://console.volcengine.com/ark/region:ark+cn-beijing/apikey

**3. 准备场景图**

在以下路径各放一张场景图片（PNG 格式）：

```
scenes/1/scene.png   # 魔法城堡
scenes/2/scene.png   # 宇宙探险
scenes/3/scene.png   # 赛博都市
```

**4. 启动服务**

```bash
uv run uvicorn main:app --reload --port 8000
```

浏览器打开 http://localhost:8000 即可使用。

**5. 效果预览**
<img width="809" height="1871" alt="PixPin_2026-04-28_15-18-24" src="https://github.com/user-attachments/assets/6459159e-a09b-48be-bfc2-a98810b79c11" />

