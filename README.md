# XHS Agent

小红书内容自动生成与发布 Agent，支持 AI 生成图文内容、自动配图、定时发布。

## 功能特性

- **AI 内容生成**：根据主题和风格，自动生成小红书标题、正文、话题标签
- **图片提示词 Agent**：预设 8 种高质量图片模板（4 种真实照片风格 + 4 种海报设计风格），由 LLM 根据内容自动选择最合适的模板并填充细节
- **AI 图片生成**：调用即梦4（doubao-seedream）API 并发生成配图，支持 photo/poster 双风格路由
- **运营计划**：总管 AI 分析账号历史数据，自动制定 7 天内容发布计划
- **定时发布**：APScheduler 驱动，自动在最佳时间发布笔记到小红书
- **多账号管理**：支持多个小红书账号 Cookie 管理，含有效性检查
- **WxPusher 通知**：发布成功/失败实时推送微信通知
- **Web 管理界面**：React 前端，支持内容生成、账号管理、运营目标、系统配置

## 技术架构

```
前端 (React + Vite)
    ↓
FastAPI 后端
    ├── xhs_agent.run()          # 主编排流程
    │   ├── text_service         # 文本生成（SiliconFlow）
    │   ├── prompt_agent         # 图片提示词 Agent（模板选择 + 细节填充）
    │   └── image_service        # 图片生成（即梦4 API）
    ├── manager_service          # 运营总管 AI（7天计划）
    ├── goal_service             # 定时任务执行
    ├── upload_service           # 小红书发布
    └── scheduler_service        # APScheduler 定时调度
```

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
| siliconflow_api_key | SiliconFlow API Key（文本生成） |
| siliconflow_base_url | SiliconFlow API 地址，默认 `https://api.siliconflow.cn/v1` |
| text_model | 文本生成模型，例如 `Qwen/Qwen2.5-72B-Instruct` |
| image_api_key | 即梦4 API Key（图片生成） |
| image_api_base_url | 即梦4 API 地址 |
| image_model | 图片生成模型，例如 `doubao-seedream-4-5-251128` |
| wxpusher_app_token | WxPusher AppToken（可选，用于发布通知） |
| wxpusher_uid | WxPusher 用户 UID（可选） |

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

## 日志

- 终端：INFO 级别，显示关键流程节点
- 文件：DEBUG 级别，记录完整提示词、LLM 原始响应、API 参数
- 日志文件路径：`log/xhs_agent.log`，按天轮转，保留 30 天

## 数据存储

所有数据存储在 `data/xhs_agent.db`（SQLite），包含：

- `accounts`：账号信息和 Cookie
- `operation_goals`：运营目标
- `scheduled_posts`：定时发布排期
- `system_config`：系统配置（API Key 等）

## API 文档

详见 [doc/API.md](doc/API.md)