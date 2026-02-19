# XHS Agent API 文档

## 基础信息

- Base URL: `http://localhost:8000`
- Content-Type: `application/json`

---

## POST /api/generate

生成小红书图文内容及配图。

### 请求参数 (Body)

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| topic | string | ✅ | - | 内容主题，例如"秋日咖啡馆探店" |
| style | string | ❌ | 生活方式 | 内容风格 |
| aspect_ratio | string | ❌ | 3:4 | 图片比例，可选：1:1 / 4:5 / 3:4 / 9:16 / 16:9 / 4:3 / 2:3 / 3:2 / 21:9 |
| image_count | int | ❌ | 1 | 生成图片数量，范围 1-4 |

### 响应示例

```json
{
  "content": {
    "title": "☕ 秋日最治愈的咖啡馆，藏在这条小巷里",
    "body": "最近发现了一家超级治愈的咖啡馆...",
    "hashtags": ["咖啡探店", "秋日氛围", "城市漫游"],
    "image_prompts": ["cozy autumn cafe interior, warm lighting, wooden tables..."]
  },
  "images": [
    { "url": "https://...", "b64_json": null }
  ]
}
```

### 错误响应

```json
{ "detail": "错误信息" }
```

---

## POST /api/upload

将已生成的图文内容发布到小红书。

### 请求参数 (Body)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cookie | string | ✅ | 小红书网页版 Cookie |
| title | string | ✅ | 笔记标题 |
| desc | string | ✅ | 笔记正文（含话题标签） |
| image_urls | list[string] | ✅ | 图片 URL 列表 |
| hashtags | list[string] | ❌ | 话题标签列表，用于匹配小红书话题 |

### 响应示例

```json
{ "success": true, "note_id": "64fa75a9000000001f0076bf", "detail": "" }
```

### 说明

- `account_id` 和 `cookie` 二选一，优先使用 `account_id`
- 上传依赖 Playwright + stealth.min.js，首次运行需安装 Chromium：`uv run playwright install chromium`

---

## GET /api/accounts

获取已保存账号列表（Cookie 脱敏显示）。

## POST /api/accounts

新增账号。

| 字段 | 类型 | 必填 |
|------|------|------|
| name | string | ✅ |
| cookie | string | ✅ |

## PATCH /api/accounts/{account_id}

更新账号名称或 Cookie（字段可选）。

## DELETE /api/accounts/{account_id}

删除账号。
