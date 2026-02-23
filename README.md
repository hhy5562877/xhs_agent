# XHS Agent

小红书内容自动生成与发布 Agent，支持 AI 生成图文内容、自动配图、定时发布。

## 功能特性

- **AI 内容生成**：根据主题和风格，自动生成小红书标题、正文、话题标签
- **智能风格判断**：默认倾向海报设计风格，仅明确真实场景（探店/穿搭/旅行等）才选真实照片风格；参考图片标注信息辅助风格决策
- **图片提示词 Agent**：预设 8 种图片模板（4 种真实照片 + 4 种海报设计），LLM 自动选择模板并填充场景细节
- **AI 图片生成**：支持 nano-banana（硅基流动）和 doubao-seedream（即梦4）双模型，poster 风格串行生成保持风格一致，photo 风格并发生成
- **参考图片系统**：为每个账号上传参考图片组（最多 9 张/组），GLM-4.6V 视觉模型自动识别标注，5 种分类（风格参考/人物形象/产品素材/场景环境/品牌元素），生图时作为图生图参考传入 API
- **运营计划**：总管 AI 分析账号历史数据和参考图片素材库，自动制定 7 天内容发布计划，为每条排期选择合适的参考图片组
- **定时发布**：APScheduler 驱动，自动在最佳时间发布笔记到小红书
- **多账号管理**：支持多个小红书账号 Cookie 管理，含有效性检查
- **WxPusher 通知**：发布成功/失败实时推送微信通知，失败通知包含失败阶段、错误类型和详情
- **腾讯云 COS 存储**：参考图片上传至腾讯云对象存储，路径前缀可配置
- **Web 管理界面**：React 前端，支持内容生成、账号管理、参考图片管理、运营目标、系统配置

## 技术架构

```
前端 (React + Vite + Ant Design)
    ↓
FastAPI 后端
    ├── xhs_agent.run()              # 手动生成流程
    │   ├── text_service             # 文本生成（SiliconFlow LLM）
    │   ├── prompt_agent             # 图片提示词 Agent（模板选择 + 细节填充）
    │   └── image_service            # 图片生成（nano-banana / doubao-seedream）
    ├── manager_service              # 运营总管 AI（7天计划 + 参考图选择）
    ├── goal_service                 # 定时任务执行（完整编排链路）
    ├── account_image_service        # 参考图片组管理（CRUD + 视觉识别）
    ├── vision_service               # GLM-4.6V 视觉模型识别
    ├── cos_service                  # 腾讯云 COS 对象存储
    ├── upload_service               # 小红书发布（含图片下载重试）
    ├── notification_service         # WxPusher 微信通知
    └── scheduler_service            # APScheduler 定时调度
```

## 核心流程

### 定时任务执行链路（goal_service.execute_scheduled_post）

```
1. 加载参考图片组
   └── 从 scheduled_posts.ref_image_ids 读取总管AI选择的组ID
   └── 查询 image_groups + account_images 获取标注和 COS URL

2. 生成文本内容（text_service）
   └── 传入参考图标注 → 影响 image_style 决策（poster/photo）
   └── 生成标题、正文、话题标签、图片提示词

3. 提示词优化（prompt_agent）
   └── 根据统一风格筛选模板（poster 4种 / photo 4种）
   └── LLM 选模板 + 填充场景细节
   └── 参考图标注融入提示词

4. 图片生成（image_service）
   ├── poster 模式（串行）：
   │   ├── 第1张：总管AI参考图 → 生成
   │   └── 第2~N张：总管AI参考图 + 第1张结果 → 生成（风格锚定）
   └── photo 模式（并发）：
       └── 所有图片同时生成，各自携带总管AI参考图

5. 下载图片到临时文件（含重试机制，最多3次）

6. 上传笔记到小红书

7. 发送通知（成功/失败，失败含详细错误信息）
```

### 参考图片系统

```
上传流程：
  前端选择图片（1-9张/组）→ 选择分类 + 可选识别提示
    → COS 上传 → 创建 image_groups + account_images 记录
    → 异步调用 GLM-4.6V 视觉模型识别 → 组级标注存储

分类体系：
  - style（风格参考）：整体视觉调性参考，决定生图的感觉
  - person（人物形象）：真人/IP/宠物，保持跨帖一致性
  - product（产品素材）：要推广的产品/物品
  - scene（场景环境）：拍摄场景/背景环境
  - brand（品牌元素）：Logo、色卡、视觉规范

使用流程：
  总管AI规划 → 按分类浏览素材库 → 为每条排期选择参考图片组
    → 执行时标注传 text_service（影响风格）+ COS URL 传 image_service（图生图）
```

### 风格判断逻辑

默认倾向 poster（海报设计），仅以下场景选 photo（真实照片）：
- 真实探店体验（餐厅、咖啡馆）
- 穿搭展示（真人穿搭、OOTD）
- 旅行实拍（景点打卡）
- 美食实拍（菜品实拍）
- 日常生活记录（居家、宠物）

参考图片标注中的关键词也影响判断：
- "插画""手绘""卡通""设计""海报" → 必须 poster
- "实拍""真实照片""手机拍摄" → photo

## 快速开始

### Docker 部署（推荐）

```bash
# 拉取镜像并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

服务启动后访问 `http://localhost:8000`，在「系统配置」页面填写 API Key。

### 本地开发

**环境要求**：Python 3.12+，Node.js 18+

```bash
# 安装依赖
uv sync

# 构建前端
cd frontend && npm install && npm run build
cp -r dist/* ../static/

# 启动服务
uv run python main.py
```

## 系统配置

首次启动后，访问 Web 界面的「系统配置」Tab 填写以下配置：

| 配置项 | 说明 |
|--------|------|
| siliconflow_api_key | SiliconFlow API Key（文本生成 + 视觉识别） |
| siliconflow_base_url | SiliconFlow API 地址，默认 `https://api.siliconflow.cn/v1` |
| text_model | 文本生成模型，例如 `Qwen/Qwen3-VL-32B-Instruct` |
| vision_model | 视觉识别模型，默认 `zai-org/GLM-4.6V` |
| image_api_key | 图片生成 API Key |
| image_api_base_url | 图片生成 API 地址 |
| image_model | 图片生成模型，例如 `nano-banana-2-2k` 或 `doubao-seedream-4-5-251128` |
| cos_secret_id | 腾讯云 COS SecretId |
| cos_secret_key | 腾讯云 COS SecretKey |
| cos_region | COS 地域，例如 `ap-guangzhou` |
| cos_bucket | COS 存储桶名称 |
| cos_path_prefix | COS 存储路径前缀，默认 `ref_images` |
| wxpusher_app_token | WxPusher AppToken（可选，用于发布通知） |
| wxpusher_uids | WxPusher 用户 UID（可选） |

## 图片风格模板

prompt_agent 预设 8 种模板，LLM 根据笔记内容自动选择：

| 模板 | 风格 | 适用场景 |
|------|------|----------|
| photo_lifestyle | 真实照片 | 日常生活、桌面物品、居家场景 |
| photo_food | 真实照片 | 餐厅探店、菜品特写、咖啡甜品 |
| photo_outdoor | 真实照片 | 旅行打卡、街头场景、户外活动 |
| photo_study | 真实照片 | 学习打卡、备考记录、书桌笔记 |
| poster_product | 海报设计 | 产品推荐、好物分享、美妆护肤 |
| poster_knowledge | 海报设计 | 知识分享、技能教程、干货总结 |
| poster_motivation | 海报设计 | 励志内容、正能量、目标打卡 |
| poster_event | 海报设计 | 节日活动、品牌推广、打卡挑战 |

poster 模板提示词已精简，重点描述主题内容，允许输出中文文字，无水印，引导贴近参考图视觉形式。

## 日志

- 终端：INFO 级别，显示关键流程节点
- 文件：DEBUG 级别，记录完整提示词、LLM 原始响应、API 参数、完整图片 URL
- 日志文件路径：`log/xhs_agent.log`，按天轮转，保留 30 天

## 数据存储

所有数据存储在 `data/xhs_agent.db`（SQLite），启动时自动对比 schema 定义与实际表结构，缺失字段自动补充。

| 表名 | 说明 |
|------|------|
| accounts | 账号信息和 Cookie |
| operation_goals | 运营目标 |
| scheduled_posts | 定时发布排期（含 ref_image_ids 参考图组ID） |
| system_config | 系统配置（API Key 等） |
| image_groups | 参考图片组（分类、标注、状态） |
| account_images | 参考图片（COS URL、所属组） |

## API 文档

详见 [doc/API.md](doc/API.md)