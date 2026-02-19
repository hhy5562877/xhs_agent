# MediaCrawlerPro API 接口文档

## 目录

- [小红书 (XiaoHongShu)](#小红书-xiaohongshu)

---

## 小红书 (XiaoHongShu)

### 基础信息

| 项目 | 值 |
|------|-----|
| API 基础 URL | `https://edith.xiaohongshu.com` |
| 网页首页 URL | `https://www.xiaohongshu.com` |
| 客户端类 | `XiaoHongShuClient` |
| 文件路径 | `media_platform/xhs/client.py` |

### 通用请求头

每个请求都会自动添加以下请求头：

| 请求头 | 值 | 说明 |
|--------|-----|------|
| accept | `application/json, text/plain, */*` | 接受类型 |
| accept-language | `zh-CN,zh;q=0.9` | 语言偏好 |
| cache-control | `no-cache` | 缓存控制 |
| content-type | `application/json;charset=UTF-8` | 内容类型 |
| origin | `https://www.xiaohongshu.com` | 来源 |
| pragma | `no-cache` | Pragma |
| priority | `u=1, i` | 优先级 |
| referer | `https://www.xiaohongshu.com/` | 引用页 |
| sec-ch-ua | `"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"` | UA信息 |
| sec-ch-ua-mobile | `?0` | 移动设备标识 |
| sec-ch-ua-platform | `"Windows"` | 平台信息 |
| sec-fetch-dest | `empty` | 目标 |
| sec-fetch-mode | `cors` | 模式 |
| sec-fetch-site | `same-site` | 站点 |
| user-agent | `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36` | 用户代理 |
| cookie | `<动态Cookie>` | 登录Cookie |

---

### 签名服务 (Sign Service)

所有请求在发送前都需要通过**独立的签名服务**生成签名参数。

#### 签名服务配置

| 配置项 | 默认值 | 环境变量 | 说明 |
|--------|--------|----------|------|
| 签名服务地址 | `localhost` | `SIGN_SRV_HOST` | 签名服务主机地址 |
| 签名服务端口 | `8989` | `SIGN_SRV_PORT` | 签名服务端口 |
| 签名接口路径 | `/signsrv/v1/xhs/sign` | - | 小红书签名接口路径 |

#### 签名请求参数 (XhsSignRequest)

向签名服务发送 POST 请求时的参数：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| uri | str | 是 | 请求的URI路径（如：`/api/sns/web/v1/feed`） |
| data | dict | 否 | 请求体数据（POST请求时使用） |
| cookies | str | 是 | 请求使用的Cookie字符串 |

**签名请求示例：**

```json
POST http://localhost:8989/signsrv/v1/xhs/sign
Content-Type: application/json

{
  "uri": "/api/sns/web/v1/feed",
  "data": {
    "source_note_id": "65a1b2c3d4e5f6g7h8i9j0k",
    "image_formats": ["jpg", "webp", "avif"]
  },
  "cookies": "sessionid=xxx; ..."
}
```

#### 签名响应

签名服务会在请求头中添加以下签名参数：

| 请求头 | 类型 | 说明 |
|--------|------|------|
| X-s | str | **核心签名参数** |
| X-t | str | 时间戳 |
| x-s-common | str | 通用签名 |
| X-B3-Traceid | str | 追踪ID |

---

### 核心签名参数：X-s

#### 重要性等级：⭐⭐⭐⭐⭐ (最高)

`X-s` 是小红书 API 最核心的反爬虫签名参数，**没有正确的 X-s 签名，请求将被直接拒绝或返回错误**。

#### 作用机制

| 项目 | 说明 |
|------|------|
| 签名对象 | URI + 请求体 + Cookie |
| 签名算法 | **专有加密算法**（需独立签名服务实现） |
| 签名位置 | HTTP 请求头 |
| 有效期 | 单次请求有效（不可重复使用） |
| 验证位置 | 服务器端实时验证 |
| 错误后果 | 返回 `300015` 签名错误或空响应 |

#### 签名生成过程

**步骤 1: 准备签名输入**
```python
# 准备请求数据
sign_request = {
    "uri": "/api/sns/web/v1/feed",
    "data": {
        "source_note_id": "65a1b2c3d4e5f6g7h8i9j0k",
        "image_formats": ["jpg", "webp", "avif"]
    },
    "cookies": "sessionid=xxx; ..."
}

# POST 到签名服务
response = await sign_client.xiaohongshu_sign(sign_request)
```

**步骤 2: 获取签名参数**
```python
# 从签名响应中提取签名参数
x_s = response.data.x_s
x_t = response.data.x_t
x_s_common = response.data.x_s_common
x_b3_traceid = response.data.x_b3_traceid
```

**步骤 3: 添加签名到请求头**
```python
headers = {
    "X-s": x_s,
    "X-t": x_t,
    "x-s-common": x_s_common,
    "X-B3-Traceid": x_b3_traceid,
    # ... 其他通用请求头
}
```

#### 签名算法说明

**注意**: 小红书的 X-s 签名算法是**闭源专有算法**，本项目通过独立的签名服务 (MediaCrawlerPro-SignSrv) 实现。

**算法特点**:
- 🔒 **高度混淆**: 使用字节码混淆、反调试、动态代码生成
- 🔄 **动态更新**: 小红书定期更新算法，需要签名服务同步更新
- 🧩 **多因子**: 综合考虑 URI、请求体、时间戳、Cookie
- 🎯 **精确匹配**: 参数顺序、大小写、编码方式必须完全一致

**签名服务部署**:
```bash
# 克隆签名服务仓库（需要独立部署）
git clone https://github.com/MediaCrawlerPro/MediaCrawlerPro-SignSrv

# 启动签名服务（默认端口 8989）
cd MediaCrawlerPro-SignSrv
npm install
npm start
```

---

### search_id 生成算法

#### get_search_id() 函数

**算法**: 时间戳左移64位 + 随机数，然后进行 Base36 编码

```python
def get_search_id():
    e = int(time.time() * 1000) << 64  # 毫秒时间戳左移64位
    t = int(random.uniform(0, 2147483646))  # 随机数 (0 ~ 2147483646)
    return base36encode((e + t))  # Base36 编码
```

**生成规则**:
- 时间戳：当前毫秒时间戳
- 左移：将时间戳左移64位，为随机数预留空间
- 随机数：0 到 2147483646 之间的随机整数
- 编码：将相加结果进行 Base36 编码

**格式示例**: `lkm8abc0123456789xyz`

**使用场景**: 搜索接口的 `search_id` 参数，用于标识一次搜索会话

---

## API 接口详情

### 1. 登录状态检查

| 属性 | 值 |
|------|-----|
| 方法名 | `query_self()` / `pong()` |
| 请求方式 | GET |
| URL | `https://edith.xiaohongshu.com/api/sns/web/v1/user/selfinfo` |
| 需要签名 | 是 |

**接口特定参数**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| 无 | - | - | - | 无特定参数，仅使用签名参数 |

**返回值**: `Optional[Dict]`

**响应示例**:
```json
{
  "success": true,
  "data": {
    "result": {
      "success": true,
      "user": {
        "user_id": "5a1b2c3d4e5f6g7h8i9j0k",
        "nickname": "用户昵称",
        "avatar": "https://..."
      }
    }
  }
}
```

**返回值**: `bool` - True 表示已登录，False 表示未登录

---

### 2. 关键词搜索笔记

| 属性 | 值 |
|------|-----|
| 方法名 | `get_note_by_keyword()` |
| 请求方式 | POST |
| URL | `https://edith.xiaohongshu.com/api/sns/web/v1/search/notes` |
| 需要签名 | 是 |

**接口特定参数 (Body)**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| keyword | str | 是 | - | 搜索关键字 |
| page | int | 否 | 1 | 分页页码 |
| page_size | int | 否 | 20 | 每页数量 |
| search_id | str | 是 | - | 搜索会话ID（由 `get_search_id()` 生成） |
| sort | str | 否 | `general` | 排序类型 |
| note_type | int | 否 | 0 | 笔记类型 |

**排序类型枚举 (SearchSortType)**

| 枚举值 | 值 | 说明 |
|--------|-----|------|
| GENERAL | `general` | 综合排序（默认） |
| MOST_POPULAR | `popularity_descending` | 最热 |
| LATEST | `time_descending` | 最新 |

**笔记类型枚举 (SearchNoteType)**

| 枚举值 | 值 | 说明 |
|--------|-----|------|
| ALL | 0 | 全部（默认） |
| VIDEO | 1 | 仅视频 |
| IMAGE | 2 | 仅图片 |

**返回值**: `Dict` - API 原始响应，包含搜索结果列表

---

### 3. 获取笔记详情

| 属性 | 值 |
|------|-----|
| 方法名 | `get_note_by_id()` |
| 请求方式 | POST |
| URL | `https://edith.xiaohongshu.com/api/sns/web/v1/feed` |
| 需要签名 | 是 |

**接口特定参数 (Body)**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| source_note_id | str | 是 | - | 笔记ID |
| image_formats | list | 否 | `["jpg", "webp", "avif"]` | 图片格式 |
| extra | dict | 否 | `{"need_body_topic": 1}` | 额外参数 |
| xsec_token | str | 否 | - | 验证token（搜索结果返回） |
| xsec_source | str | 否 | - | 渠道来源 |

**返回值**: `Optional[XhsNote]`

**XhsNote 数据结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| note_id | str | 笔记ID |
| title | str | 标题 |
| desc | str | 描述 |
| type | str | 类型（normal/video） |
| user | dict | 用户信息 |
| img_urls | list | 图片URL列表 |
| video_url | str | 视频URL |
| tag_list | list | 标签列表 |
| at_user_list | list | @用户列表 |
| collected_count | str | 收藏数 |
| comment_count | str | 评论数 |
| liked_count | str | 点赞数 |
| share_count | str | 分享数 |
| time | int | 发布时间戳 |
| last_update_time | int | 最后更新时间戳 |

---

### 4. 获取笔记评论列表

| 属性 | 值 |
|------|-----|
| 方法名 | `get_note_comments()` |
| 请求方式 | GET |
| URL | `https://edith.xiaohongshu.com/api/sns/web/v2/comment/page` |
| 需要签名 | 是 |

**接口特定参数 (Query)**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| note_id | str | 是 | - | 笔记ID |
| cursor | str | 否 | `""` | 分页游标 |
| top_comment_id | str | 否 | `""` | 置顶评论ID |
| image_formats | str | 否 | `jpg,webp,avif` | 图片格式 |
| xsec_token | str | 否 | - | 验证token |

**返回值**: `Tuple[List[XhsComment], Dict]`
- 第一个元素: 评论列表
- 第二个元素: 元数据 (包含 cursor, has_more 等)

**XhsComment 数据结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| comment_id | str | 评论ID |
| note_id | str | 笔记ID |
| content | str | 评论内容 |
| create_time | str | 评论时间 |
| like_count | str | 点赞数 |
| sub_comment_count | str | 子评论数 |
| parent_comment_id | str | 父评论ID |
| root_comment_id | str | 根评论ID |
| ip_location | str | IP地址 |
| user_id | str | 用户ID |
| nickname | str | 昵称 |
| avatar | str | 头像URL |

---

### 5. 获取子评论（回复）

| 属性 | 值 |
|------|-----|
| 方法名 | `get_note_sub_comments()` |
| 请求方式 | GET |
| URL | `https://edith.xiaohongshu.com/api/sns/web/v2/comment/sub/page` |
| 需要签名 | 是 |

**接口特定参数 (Query)**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| note_id | str | 是 | - | 笔记ID |
| root_comment_id | str | 是 | - | 根评论ID |
| num | int | 否 | 10 | 每页数量 |
| cursor | str | 否 | `""` | 分页游标 |
| xsec_token | str | 否 | - | 验证token |

**返回值**: `Tuple[List[XhsComment], Dict]`
- 数据结构同 `get_note_comments()`

---

### 6. 获取创作者信息

| 属性 | 值 |
|------|-----|
| 方法名 | `get_creator_info()` |
| 请求方式 | GET |
| URL | `https://www.xiaohongshu.com/user/profile/{user_id}` |
| 需要签名 | 否（网页解析） |
| 特殊说明 | 通过解析HTML页面获取信息 |

**接口特定参数 (Query)**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| user_id | str | 是 | - | 用户ID（在URL路径中） |
| xsec_token | str | 否 | - | 验证token |
| xsec_source | str | 否 | - | 渠道来源 |

**返回值**: `Optional[XhsCreator]`

**XhsCreator 数据结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | str | 用户ID |
| nickname | str | 昵称 |
| avatar | str | 头像URL |
| desc | str | 签名/描述 |
| gender | str | 性别 |
| follows | str | 关注数 |
| fans | str | 粉丝数 |
| interaction | str | 获赞总数 |
| notes_count | str | 笔记数 |

---

### 7. 获取创作者笔记列表

| 属性 | 值 |
|------|-----|
| 方法名 | `get_notes_by_creator()` |
| 请求方式 | GET |
| URL | `https://edith.xiaohongshu.com/api/sns/web/v1/user_posted` |
| 需要签名 | 是 |

**接口特定参数 (Query)**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| user_id | str | 是 | - | 用户ID |
| cursor | str | 是 | - | 分页游标 |
| num | int | 否 | 30 | 每页数量 |
| image_formats | str | 否 | `jpg,webp,avif` | 图片格式 |
| xsec_token | str | 否 | - | 验证token |
| xsec_source | str | 否 | `pc_feed` | 渠道来源 |

**返回值**: `Dict` - API 原始响应，包含用户笔记列表及分页信息

---

### 8. 通过HTML获取笔记详情

| 属性 | 值 |
|------|-----|
| 方法名 | `get_note_by_id_from_html()` |
| 请求方式 | GET |
| URL | `https://www.xiaohongshu.com/explore/{note_id}` |
| 需要签名 | 否（网页解析） |
| 特殊说明 | 通过解析HTML页面获取信息，最多重试5次 |

**接口特定参数 (Query)**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| note_id | str | 是 | - | 笔记ID（在URL路径中） |
| xsec_token | str | 否 | - | 验证token |
| xsec_source | str | 否 | - | 渠道来源 |

**返回值**: `Optional[XhsNote]`

**特殊处理**:
- 检测验证码页面（`www.xiaohongshu.com/website-login/captcha`）
- 前3次尝试不带Cookie请求（需高权重账号的xsec_token）
- 后2次使用代理重试

---

### 9. 获取笔记短链接

| 属性 | 值 |
|------|-----|
| 方法名 | `get_note_short_url()` |
| 请求方式 | POST |
| URL | `https://edith.xiaohongshu.com/api/sns/web/short_url` |
| 需要签名 | 是 |

**接口特定参数 (Body)**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| original_url | str | 是 | - | 原始URL |

**返回值**: `Dict` - API 原始响应，包含短链接

---

### 10. 获取首页推荐笔记

| 属性 | 值 |
|------|-----|
| 方法名 | `get_homefeed_notes()` |
| 请求方式 | POST |
| URL | `https://edith.xiaohongshu.com/api/sns/web/v1/homefeed` |
| 需要签名 | 是 |

**接口特定参数 (Body)**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| category | str | 否 | `homefeed_recommend` | 分类 |
| cursor_score | str | 否 | `""` | 分页游标 |
| image_formats | list | 否 | `["jpg", "webp", "avif"]` | 图片格式 |
| need_filter_image | bool | 否 | `false` | 是否过滤图片 |
| need_num | int | 否 | 18 | 需要数量 |
| note_index | int | 否 | 0 | 笔记索引 |
| num | int | 否 | 18 | 数量 |
| refresh_type | int | 否 | 3 | 刷新类型 |
| search_key | str | 否 | `""` | 搜索关键字 |
| unread_begin_note_id | str | 否 | `""` | 未读开始笔记ID |
| unread_end_note_id | str | 否 | `""` | 未读结束笔记ID |
| unread_note_count | int | 否 | 0 | 未读笔记数 |

**推荐分类枚举 (FeedType)**

| 枚举值 | 值 | 说明 |
|--------|-----|------|
| RECOMMEND | `homefeed_recommend` | 推荐（默认） |
| FASION | `homefeed.fashion_v3` | 穿搭 |
| FOOD | `homefeed.food_v3` | 美食 |
| COSMETICS | `homefeed.cosmetics_v3` | 彩妆 |
| MOVIE | `homefeed.movie_and_tv_v3` | 影视 |
| CAREER | `homefeed.career_v3` | 职场 |
| EMOTION | `homefeed.love_v3` | 情感 |
| HOURSE | `homefeed.household_product_v3` | 家居 |
| GAME | `homefeed.gaming_v3` | 游戏 |
| TRAVEL | `homefeed.travel_v3` | 旅行 |
| FITNESS | `homefeed.fitness_v3` | 健身 |

**返回值**: `Dict` - API 原始响应，包含推荐笔记列表

---

### 接口总览表

| 接口 | 方法名 | 请求方式 | URL | 返回类型 |
|------|--------|---------|-----|----------|
| 登录检查 | `query_self()` / `pong()` | GET | `/api/sns/web/v1/user/selfinfo` | `Optional[Dict]` / `bool` |
| 关键词搜索 | `get_note_by_keyword()` | POST | `/api/sns/web/v1/search/notes` | `Dict` |
| 笔记详情 | `get_note_by_id()` | POST | `/api/sns/web/v1/feed` | `Optional[XhsNote]` |
| 评论列表 | `get_note_comments()` | GET | `/api/sns/web/v2/comment/page` | `Tuple[List, Dict]` |
| 子评论 | `get_note_sub_comments()` | GET | `/api/sns/web/v2/comment/sub/page` | `Tuple[List, Dict]` |
| 创作者信息 | `get_creator_info()` | GET | `/user/profile/{user_id}` | `Optional[XhsCreator]` |
| 创作者笔记 | `get_notes_by_creator()` | GET | `/api/sns/web/v1/user_posted` | `Dict` |
| HTML笔记详情 | `get_note_by_id_from_html()` | GET | `/explore/{note_id}` | `Optional[XhsNote]` |
| 短链接 | `get_note_short_url()` | POST | `/api/sns/web/short_url` | `Dict` |
| 推荐流 | `get_homefeed_notes()` | POST | `/api/sns/web/v1/homefeed` | `Dict` |

---

### 异常类型

| 异常类 | 说明 | 触发场景 |
|--------|------|----------|
| `DataFetchError` | 数据获取失败 | 返回空响应、blocked响应、JSON解析异常 |
| `IPBlockError` | IP被阻止 | 请求过于频繁导致IP被临时封禁（错误码 300012） |
| `SignError` | 签名错误 | X-s 签名验证失败（错误码 300015） |
| `AccessFrequencyError` | 访问频次异常 | 访问过于频繁（错误码 300013） |
| `NeedVerifyError` | 需要验证 | 出现滑块验证码（状态码 461/471） |

**错误码枚举 (ErrorEnum)**

| 错误码 | 枚举值 | 说明 |
|--------|--------|------|
| 300012 | `IP_BLOCK` | 网络连接异常，请检查网络设置或重启试试 |
| -510001 | `NOTE_ABNORMAL` | 笔记状态异常，请稍后查看 |
| -510001 | `NOTE_SECRETE_FAULT` | 当前内容无法展示 |
| 300015 | `SIGN_FAULT` | 浏览器异常，请尝试关闭/卸载风险插件或重启试试 |
| -100 | `SESSION_EXPIRED` | 登录已过期 |
| 300013 | `ACCEESS_FREQUENCY_ERROR` | 访问频次异常，请勿频繁操作或重启试试 |

---

### 使用示例

#### 搜索并获取笔记详情

```python
from media_platform.xhs.client import XiaoHongShuClient
from media_platform.xhs.field import SearchSortType, SearchNoteType

async def example():
    client = XiaoHongShuClient()
    await client.async_initialize()

    # 搜索关键字
    search_result = await client.get_note_by_keyword(
        keyword="美食",
        page=1,
        page_size=20,
        sort=SearchSortType.GENERAL,
        note_type=SearchNoteType.ALL
    )

    # 获取笔记详情
    note_id = search_result["items"][0]["id"]
    note = await client.get_note_by_id(note_id)

    # 获取评论
    comments, meta = await client.get_note_comments(note_id, cursor="")
```

#### 获取创作者信息和笔记

```python
async def get_creator_content():
    client = XiaoHongShuClient()
    await client.async_initialize()

    # 获取创作者信息
    creator = await client.get_creator_info(
        user_id="5a1b2c3d4e5f6g7h8i9j0k",
        xsec_token="xxx",
        xsec_source="pc_feed"
    )

    # 获取创作者笔记列表
    posts = await client.get_notes_by_creator(
        creator="5a1b2c3d4e5f6g7h8i9j0k",
        cursor="",
        page_size=30,
        xsec_token="xxx",
        xsec_source="pc_feed"
    )
```

#### 获取首页推荐

```python
from media_platform.xhs.field import FeedType

async def get_homefeed():
    client = XiaoHongShuClient()
    await client.async_initialize()

    # 获取推荐流
    notes = await client.get_homefeed_notes(
        category=FeedType.RECOMMEND,
        cursor="",
        note_index=0,
        note_num=18
    )

    # 获取美食分类
    food_notes = await client.get_homefeed_notes(
        category=FeedType.FOOD,
        cursor="",
        note_index=0,
        note_num=18
    )
```

---

### 图片CDN说明

小红书使用多个CDN域名分发图片，可通过 `trace_id` 获取不同CDN的图片URL。

**CDN域名列表**:

| 域名 | 说明 |
|------|------|
| `https://sns-img-qc.xhscdn.com` | 青岛 CDN |
| `https://sns-img-hw.xhscdn.com` | 华为 CDN |
| `https://sns-img-bd.xhscdn.com` | 北京 CDN |
| `https://sns-img-qn.xhscdn.com` | 七牛 CDN |

**工具函数**:

```python
from media_platform.xhs.help import get_img_url_by_trace_id, get_img_urls_by_trace_id

# 获取单个CDN的图片URL
img_url = get_img_url_by_trace_id("7a3abfaf-90c1-a828-5de7-022c80b92aa3", format_type="png")
# 返回: https://sns-img-bd.xhscdn.com/7a3abfaf-90c1-a828-5de7-022c80b92aa3?imageView2/format/png

# 获取所有CDN的图片URL
img_urls = get_img_urls_by_trace_id("7a3abfaf-90c1-a828-5de7-022c80b92aa3", format_type="png")
# 返回: [
#   "https://sns-img-qc.xhscdn.com/7a3abfaf-90c1-a828-5de7-022c80b92aa3?imageView2/format/png",
#   "https://sns-img-hw.xhscdn.com/7a3abfaf-90c1-a828-5de7-022c80b92aa3?imageView2/format/png",
#   "https://sns-img-bd.xhscdn.com/7a3abfaf-90c1-a828-5de7-022c80b92aa3?imageView2/format/png",
#   "https://sns-img-qn.xhscdn.com/7a3abfaf-90c1-a828-5de7-022c80b92aa3?imageView2/format/png"
# ]
```
