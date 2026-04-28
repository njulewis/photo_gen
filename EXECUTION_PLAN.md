# 执行计划 — 场景融合照片生成

## Phase 1：环境与基础搭建

### Step 1 — 初始化项目结构
- 创建目录：`graph/`、`services/`、`scenes/1-3/`、`static/`、`outputs/`
- 创建 `requirements.txt`（按 FEATURE_SPEC.md 五节依赖项填写）
- 安装依赖：`pip install -r requirements.txt`
- 验证：`python -c "import fastapi, langgraph, insightface"` 无报错

### Step 2 — 准备场景素材
- 为 3 个场景各准备：`background.jpg`（背景图）、`thumbnail.jpg`（缩略图）、`pose_reference.jpg`（姿势参考图）
- 生成 `scenes/config.json`（参照 FEATURE_SPEC.md 2.3 节结构）
- 验证：`json.load(open("scenes/config.json"))` 无报错

### Step 3 — 配置 Replicate API
- 注册 Replicate 账号，获取 API Token
- 设置环境变量 `REPLICATE_API_TOKEN`
- 测试调用 `replicate.run("zsxkib/instant-id:...")` 返回图片 URL

---

## Phase 2：后端核心服务

### Step 4 — 人脸服务（`services/face_service.py`）
- 实现 `detect_and_extract(image_bytes) -> (face_crop_bytes, embedding)`
- 使用 InsightFace `buffalo_l` 模型
- 处理边界条件：无人脸 → 抛出 `FaceNotFoundError`；多人脸 → 取最大人脸
- 单元测试：用本地人脸照片验证 embedding shape 正确

### Step 5 — 图像生成服务（`services/generation_service.py`）
- 实现 `generate_character(face_crop_bytes, scene_config) -> image_bytes`
- 调用 Replicate IP-Adapter FaceID + ControlNet（传入 `pose_image` 路径）
- 传入 `style_prompt` 和 `negative_prompt`
- 单元测试：对场景 1 生成一张图，肉眼验证人脸相似度

### Step 6 — 图像融合服务（`services/composite_service.py`）
- 实现 `composite(char_bytes, scene_config) -> final_bytes`
- 步骤：rembg 去背 → OpenCV 泊松融合 → Pillow 色调匹配
- 单元测试：生成融合图，检查边缘无明显割裂感

---

## Phase 3：LangGraph 编排

### Step 7 — State 定义（`graph/state.py`）
- 按 FEATURE_SPEC.md 2.4 节实现 `ImageGenState` TypedDict

### Step 8 — 节点实现（`graph/nodes.py`）
- 实现 6 个节点函数：`load_scene`、`extract_face`、`generate_char`、`composite_image`、`quality_check`、`output_result`
- 每个节点：读取 state → 调用对应 service → 返回更新后的 state 字段
- `quality_check` 节点：使用 InsightFace 计算原图与生成图人脸 embedding cosine 相似度，阈值 0.7

### Step 9 — 工作流构建（`graph/workflow.py`）
- 用 `StateGraph` 连接所有节点
- 添加条件边：`quality_check` 后判断 score 和 retry_count，决定重试或输出
- `compile()` 生成可执行 graph
- 测试：用模拟 state 跑通完整流程无异常

---

## Phase 4：FastAPI 后端

### Step 10 — API 路由（`main.py`）
- 实现 `GET /api/scenes` — 读取 config.json 返回场景列表
- 实现 `POST /api/generate` — 接收 multipart（scene_id + photo），创建 task_id，后台启动 graph，返回 task_id
- 实现 `GET /api/result/{task_id}` — 返回生成图片文件
- 实现 `WebSocket /ws/progress/{task_id}` — 从队列读取节点进度推送给前端

### Step 11 — 进度推送集成
- 在每个 LangGraph 节点末尾调用 `state["progress_callback"](step_name, percent)`
- callback 将消息写入 task 对应的 asyncio.Queue
- WebSocket handler 从 Queue 中读取并推送

### Step 12 — 集成测试
- 用 `curl` / Postman 测试完整链路：上传照片 → 获取 task_id → WebSocket 收到进度 → 下载结果图

---

## Phase 5：前端页面

### Step 13 — 场景选择器（`static/index.html` + `static/app.js`）
- 渲染 3 个场景卡片（缩略图 + 名称 + 描述）
- 点击选中高亮，记录 `selectedSceneId`

### Step 14 — 上传与预览组件
- 拖拽 / 点击上传，FileReader 预览
- 前端校验文件格式和大小

### Step 15 — 生成流程 UI
- 点击"开始生成"：POST `/api/generate` 获取 task_id
- 建立 WebSocket 连接，监听进度更新进度条
- 完成后请求 `/api/result/{task_id}` 显示结果图
- 提供下载、重新生成、换场景按钮

### Step 16 — 样式（`static/style.css`）
- 响应式布局，移动端友好
- 场景卡片选中效果，进度条动画

---

## Phase 6：收尾

### Step 17 — 错误处理完善
- 前端：网络错误、超时、人脸未检测到，给出对应提示
- 后端：每个节点 try/except，错误通过 WebSocket 推送 `{"type": "error", "message": "..."}`

### Step 18 — outputs/ 清理机制
- 启动时注册 APScheduler 定时任务，每小时清理 24 小时前的文件

### Step 19 — 本地完整验证
- 3 个场景各生成一张图，检查质量
- 测试重试逻辑（构造低质量 prompt 触发重试）
- 测试并发两个请求不互相干扰

---

## 里程碑

| 阶段 | 预计完成 | 交付物 |
|------|---------|--------|
| Phase 1 | 第 1 天 | 环境就绪、场景素材、Replicate 可调用 |
| Phase 2 | 第 2-3 天 | 3 个 service 单元测试通过 |
| Phase 3 | 第 4 天 | LangGraph 流程跑通 |
| Phase 4 | 第 5-6 天 | API + WebSocket 集成测试通过 |
| Phase 5 | 第 7-8 天 | 前端页面完整可用 |
| Phase 6 | 第 9 天 | 错误处理、清理机制、全流程验证 |
