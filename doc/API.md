# XHS Agent API 文档

## 基础信息

- Base URL: `http://localhost:8000`
- Content-Type: `application/json`
- 所有接口路径前缀：`/api`

---

## 内容生成

### POST /api/generate

生成小红书图文内容及配图。

调用链：text_service → prompt_agent（选模板+填充细节）→ image_service（并发生成图片）

**请求参数**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| topic | string | ✅ | - | 内容主题，例如"秋日咖啡馆探店" |
| style | string | ❌ | 生活方式 | 内容风格 |
| aspect_ratio | string | ❌ | 3:4 | 图片比例：1:1 / 4:5 / 3:4 / 9:16 / 16:9 / 4:3 / 2:3 / 3:2 / 21:9 |
| image_count | int | ❌ | 1 | 生成图片数量，范围 1-4 |

**响应示例**

```json
{
  "content": {
    "title": "☕ 秋日最治愈的咖啡馆，藏在这条小巷里",
    "body": "最近发现了一家超级治愈的咖啡馆...",
    "hashtags": ["咖啡探店", "秋日氛围", "城市漫游"],
    "image_prompts": ["手机随手误拍风格，极度真实的生活快照..."],
    "image_styles": ["photo"]
  },
  "images": [
    { "url": "https://...", "b64_json": null }
  ]
}
```

---

### POST /api/upload

将已生成的图文内容发布到小红书。

**请求参数**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| account_id | string | ✅ | 账号 ID（从账号管理获取） |
| title | string | ✅ | 笔记标题 |
| desc | string | ✅ | 笔记正文（含话题标签） |
| image_urls | list[string] | ✅ | 图片 URL 列表 |
| hashtags | list[string] | ❌ | 话题标签列表 |

**响应示例**

```json
{ "success": true, "note_id": "64fa75a9000000001f0076bf", "detail": "" }
```

---

## 账号管理

### GET /api/accounts

获取已保存账号列表（Cookie 脱敏显示）。

**响应示例**

```json
[
  {
    "id": "acc_001",
    "name": "我的账号",
    "nickname": "小红书用户",
    "avatar_url": "https://...",
    "fans": "1234",
    "created_at": "2026-02-20 10:00"
  }
]
```

---

### POST /api/accounts

新增账号。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 账号备注名 |
| cookie | string | ✅ | 小红书网页版 Cookie |

---

### PATCH /api/accounts/{account_id}

更新账号名称或 Cookie（字段均可选）。

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 新备注名 |
| cookie | string | 新 Cookie |

---

### DELETE /api/accounts/{account_id}

删除账号。

---

### GET /api/accounts/{account_id}/check

检查账号 Cookie 有效性，同步账号昵称、头像、粉丝数。

**响应示例**

```json
{ "valid": true, "nickname": "你我都有美好的未来", "fans": "1234" }
```

---

### POST /api/accounts/preview

预览账号信息（不保存），用于添加账号前验证 Cookie。

| 字段 | 类型 | 必填 |
|------|------|------|
| cookie | string | ✅ |

---

## 账号参考图片

### POST /api/accounts/{account_id}/images

上传参考图片，异步调用 GLM-4.6V 视觉模型识别内容。识别 prompt 根据分类不同而不同。

**请求格式**：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | ✅ | 图片文件（JPG/PNG/WebP），不超过 10MB |
| category | string | ❌ | 图片分类，默认 `style`。可选值：`style`(风格参考)、`person`(人物形象)、`product`(产品素材)、`scene`(场景环境)、`brand`(品牌元素) |

**响应示例**

```json
{
  "id": 1,
  "account_id": "acc_001",
  "file_path": "https://mybucket-1250000000.cos.ap-guangzhou.myqcloud.com/ref_images/acc_001/style/abc123.jpg",
  "original_name": "咖啡店.jpg",
  "category": "style",
  "annotation": "",
  "status": "pending",
  "created_at": "2026-02-21 22:00"
}
```

---

### GET /api/accounts/{account_id}/images

获取账号的参考图片列表，支持按分类过滤。

**查询参数**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| category | string | ❌ | 按分类过滤，可选值同上传接口。不传则返回全部 |

**响应示例**

```json
[
  {
    "id": 1,
    "account_id": "acc_001",
    "file_path": "https://mybucket-1250000000.cos.ap-guangzhou.myqcloud.com/ref_images/acc_001/style/abc123.jpg",
    "original_name": "咖啡店.jpg",
    "category": "style",
    "annotation": "图片展示了一家温馨的咖啡店内景...",
    "status": "done",
    "created_at": "2026-02-21 22:00"
  }
]
```

---

### DELETE /api/accounts/images/{image_id}

删除参考图片（同时删除文件和数据库记录）。

---

### POST /api/accounts/images/{image_id}/retry

重新触发视觉模型识别（用于识别失败时重试）。

---

## 运营目标

### GET /api/goals

获取所有运营目标列表。

---

### POST /api/goals

创建运营目标。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| account_id | string | ✅ | 绑定账号 ID |
| title | string | ✅ | 目标标题 |
| description | string | ✅ | 目标详细描述 |
| style | string | ✅ | 内容风格 |
| post_freq | int | ✅ | 每日发布频率 |

---

### PATCH /api/goals/{goal_id}

更新运营目标信息。

---

### DELETE /api/goals/{goal_id}

删除运营目标及其所有排期。

---

### PATCH /api/goals/{goal_id}/toggle

启用/停用运营目标。

| 字段 | 类型 | 说明 |
|------|------|------|
| active | bool | true=启用，false=停用 |

---

### POST /api/goals/{goal_id}/plan

触发总管 AI 分析账号历史数据，生成并保存 7 天发布计划。同一目标同时只允许一个规划请求（429 防重复）。

AI 会根据账号的参考图片素材库（按分类：风格参考/人物形象/产品素材/场景环境/品牌元素），为每条排期选择合适的参考图片，存入 `ref_image_ids` 字段。执行时 PromptAgent 会将参考图片标注融入提示词。

**响应示例**

```json
{
  "analysis": "根据账号近期数据分析，建议...",
  "posts": [
    {
      "id": 1,
      "topic": "秋日咖啡馆探店",
      "scheduled_at": "2026-02-21 20:00",
      "status": "pending"
    }
  ]
}
```

---

### GET /api/goals/{goal_id}/posts

获取指定目标的所有排期列表。

---

## 排期管理

### GET /api/posts

获取所有排期列表。

---

### POST /api/posts/{post_id}/run

手动立即执行指定排期任务（跳过定时等待）。

---

## 系统配置

### GET /api/config

获取所有系统配置项（API Key 等敏感字段脱敏显示）。

**响应示例**

```json
{
  "siliconflow_api_key": "sk-****",
  "siliconflow_base_url": "https://api.siliconflow.cn/v1",
  "text_model": "Qwen/Qwen2.5-72B-Instruct",
  "vision_model": "zai-org/GLM-4.6V",
  "image_api_key": "****",
  "image_api_base_url": "https://...",
  "image_model": "doubao-seedream-4-5-251128",
  "wxpusher_app_token": "",
  "wxpusher_uid": "",
  "cos_secret_id": "AKID****",
  "cos_secret_key": "****",
  "cos_region": "ap-guangzhou",
  "cos_bucket": "mybucket-1250000000"
}
```

---

### PUT /api/config

更新系统配置，传入需要修改的字段即可（其余字段不变）。

**请求示例**

```json
{
  "siliconflow_api_key": "sk-xxxx",
  "text_model": "Qwen/Qwen2.5-72B-Instruct"
}
```

---

## 其他

### GET /api/proxy/image?url={url}

图片代理接口，用于前端展示小红书图片（绕过防盗链）。
