# 小红书签名生成逻辑

## 概述

小红书签名生成主要用于API请求的鉴权，包含多个参数的组合计算。本项目支持两种签名生成方式：

1. **Playwright 方式**：通过浏览器环境调用 `window._webmsxyw(url, data)` 获取签名
2. **JavaScript 方式**：通过 execjs 执行 JS 代码生成签名

---

## 签名参数

### 请求参数 (XhsSignRequest)

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `uri` | string | 是 | 请求的 URI |
| `data` | Any | 否 | 请求 body 的数据 |
| `cookies` | string | 是 | 请求的 cookies |

### 响应参数 (XhsSignResponse)

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `x-s` | string | 请求签名 |
| `x-t` | string | 时间戳 |
| `x-s-common` | string | 通用签名参数 |
| `x-b3-traceid` | string | 链路追踪 ID |

---

## 签名生成流程


### JavaScript 签名

```python
# logic/xhs/xhs_logic.py - XhsJavascriptSign

async def sign(self, req: XhsSignRequest, force_init: bool = False) -> XhsSignResponse:
    # 直接调用 JS 签名函数
    sign_result = self.xhs_xs_sign_obj.call('sign', req.uri, req.data, req.cookies)

    return XhsSignResponse(
        x_s=sign_result.get("x-s"),
        x_t=str(sign_result.get("x-t")),
        x_s_common=sign_result.get("x-s-common"),
        x_b3_traceid=sign_result.get("x-b3-traceid"),
    )
```

---

## 核心签名参数详解

### 1. x-s-common 参数

`x-s-common` 是一个 Base64 编码的 JSON 字符串，包含以下字段：

| 字段 | 值 | 说明 |
|------|-----|------|
| `s0` | 3 | 平台代码 (getPlatformCode) |
| `s1` | "" | 空字符串 |
| `x0` | "1" | localStorage.getItem("b1b1") |
| `x1` | "3.6.8" 或 "4.3.1" | 版本号 |
| `x2` | "Mac OS" | 操作系统 |
| `x3` | "xhs-pc-web" | 平台标识 |
| `x4` | "4.20.1" 或 "4.74.0" | 版本号 |
| `x5` | a1 | Cookie 中的 a1 值 |
| `x6` | x_t | 时间戳 |
| `x7` | x_s | 签名值 |
| `x8` | b1 | localStorage.getItem("b1") |
| `x9` | mrc(x_t + x_s + b1) | CRC32 计算值 |
| `x10` | 1 | 签名计数 (getSigCount) |

#### x-s-common 生成代码

```python
# logic/xhs/help.py

def sign(a1="", b1="", x_s="", x_t=""):
    common = {
        "s0": 3,                    # getPlatformCode
        "s1": "",
        "x0": "1",                  # localStorage.getItem("b1b1")
        "x1": "3.6.8",              # version
        "x2": "Mac OS",             # 操作系统
        "x3": "xhs-pc-web",         # 平台标识
        "x4": "4.20.1",             # 版本号
        "x5": a1,                   # cookie of a1
        "x6": x_t,                  # 时间戳
        "x7": x_s,                  # 签名值
        "x8": b1,                   # localStorage.getItem("b1")
        "x9": mrc(x_t + x_s + b1),  # CRC32计算
        "x10": 1,                   # getSigCount
    }
    encode_str = encodeUtf8(json.dumps(common, separators=(',', ':')))
    x_s_common = b64Encode(encode_str)
    return x_s_common
```

### 2. x-s 参数

`x-s` 是通过 `seccore_signv2` 函数生成的，格式为 `XYS_` + Base64 编码字符串。

#### seccore_signv2 生成逻辑

```javascript
// pkg/js/xhs/xhs_xs_new.js

function seccore_signv2(e, a) {
    // e: URI, a: data
    var r = window.toString, c = e;
    "[object Object]" === r.call(a) || "[object Array]" === r.call(a) ||
    (void 0 === a ? "undefined" : (0, _type_of)(a)) === "object" && null !== a ?
        c += JSON.stringify(a) : "string" == typeof a && (c += a);

    // 1. MD5 计算
    var d = md5hexmd5hex(c)

    // 2. 调用 mnsv2 生成 mns 标识
    var f = window.mnsv2(c, d)

    // 3. 构建签名对象
    var s = {
        "x0": "4.3.1",           // 版本号
        "x1": "xhs-pc-web",      // 平台标识
        "x2": "Mac OS",          // 操作系统
        "x3": f,                 // mns 标识
        "x4": "object"
    };

    // 4. 返回 XYS_ + Base64 编码
    return "XYS_" + b64Encode(encodeUtf8(JSON.stringify(s)))
}
```

### 3. x-t 参数

`x-t` 是当前时间戳（毫秒）。

```javascript
// pkg/js/xhs/xhs_xs_new.js

function sign(api, params, cookies) {
    return {
        "x-t": Date.now(),  // 当前时间戳
        // ...
    }
}
```

### 4. x-b3-traceid 参数

`x-b3-traceid` 是一个 16 位随机十六进制字符串，用于链路追踪。

```javascript
// pkg/js/xhs/xhs_xs_new.js

function get_trace_id() {
    for (var t = "", e = 0; e < 16; e++)
      t += "abcdef0123456789".charAt(Math.floor(16 * Math.random()));
    return t
}
```

```python
# logic/xhs/help.py

def get_b3_trace_id():
    re = "abcdef0123456789"
    je = 16
    e = ""
    for t in range(16):
        e += re[random.randint(0, je - 1)]
    return e
```

---

## 辅助函数

### CRC32 计算 (mrc 函数)

```python
# logic/xhs/help.py

def mrc(e):
    ie = [
        0, 1996959894, 3993919788, 2567524794, 124634137, 1886057615, 3915621685,
        # ... (完整 CRC32 查找表)
        1555261956, 3268935591, 3050360625, 752459403, 1541320221, 2607071920,
        3965973030, 1969922972, 40735498, 2617837225, 3943577151, 1913087877,
        83908371, 2512341634, 3803740692, 2075208622, 213261112, 2463272603,
        3855990285, 2094854071, 198958881, 2262029012, 4057260610, 1759359992,
        534414190, 2176718541, 4139329115, 1873836001, 414664567, 2282248934,
        4279200368, 1711684554, 285281116, 2405801727, 4167216745, 1634467795,
        376229701, 2685067896, 3608007406, 1308918612, 956543938, 2808555105,
        3495958263, 1231636301, 1047427035, 2932959818, 3654703836, 1088359270,
        936918000, 2847714899, 3736837829, 1202900863, 817233897, 3183342108,
        3401237130, 1404277552, 615818150, 3134207493, 3453421203, 1423857449,
        601450431, 3009837614, 3294710456, 1567103746, 711928724, 3020668471,
        3272380065, 1510334235, 755167117,
    ]
    o = -1

    def right_without_sign(num: int, bit: int = 0) -> int:
        val = ctypes.c_uint32(num).value >> bit
        MAX32INT = 4294967295
        return (val + (MAX32INT + 1)) % (2 * (MAX32INT + 1)) - MAX32INT - 1

    for n in range(57):
        o = ie[(o & 255) ^ ord(e[n])] ^ right_without_sign(o, 8)
    return o ^ -1 ^ 3988292384
```

### Base64 编码

```python
# logic/xhs/help.py

lookup = [
    "Z", "m", "s", "e", "r", "b", "B", "o", "H", "Q", "t", "N", "P", "+", "w", "O",
    "c", "z", "a", "/", "L", "p", "n", "g", "G", "8", "y", "J", "q", "4", "2", "K",
    "W", "Y", "j", "0", "D", "S", "f", "d", "i", "k", "x", "3", "V", "T", "1", "6",
    "I", "l", "U", "A", "F", "M", "9", "7", "h", "E", "C", "v", "u", "R", "X", "5",
]

def tripletToBase64(e):
    return (
        lookup[63 & (e >> 18)] +
        lookup[63 & (e >> 12)] +
        lookup[(e >> 6) & 63] +
        lookup[e & 63]
    )

def encodeChunk(e, t, r):
    m = []
    for b in range(t, r, 3):
        n = (16711680 & (e[b] << 16)) + \
            ((e[b + 1] << 8) & 65280) + (e[b + 2] & 255)
        m.append(tripletToBase64(n))
    return ''.join(m)

def b64Encode(e):
    P = len(e)
    W = P % 3
    U = []
    z = 16383
    H = 0
    Z = P - W
    while H < Z:
        U.append(encodeChunk(e, H, Z if H + z > Z else H + z))
        H += z
    if 1 == W:
        F = e[P - 1]
        U.append(lookup[F >> 2] + lookup[(F << 4) & 63] + "==")
    elif 2 == W:
        F = (e[P - 2] << 8) + e[P - 1]
        U.append(lookup[F >> 10] + lookup[63 & (F >> 4)] +
                 lookup[(F << 2) & 63] + "=")
    return "".join(U)
```

### UTF-8 编码

```python
# logic/xhs/help.py

def encodeUtf8(e):
    b = []
    m = urllib.parse.quote(e, safe='~()*!.\'')
    w = 0
    while w < len(m):
        T = m[w]
        if T == "%":
            E = m[w + 1] + m[w + 2]
            S = int(E, 16)
            b.append(S)
            w += 2
        else:
            b.append(ord(T[0]))
        w += 1
    return b
```

---

## 完整签名生成示例

### Python 版本 (help.py)

```python
def sign(a1="", b1="", x_s="", x_t=""):
    """
    生成小红书签名

    Args:
        a1: Cookie 中的 a1 值
        b1: localStorage.getItem("b1")
        x_s: 签名值
        x_t: 时间戳

    Returns:
        dict: 包含 x-s, x-t, x-s-common, x-b3-traceid
    """
    common = {
        "s0": 3,
        "s1": "",
        "x0": "1",
        "x1": "3.6.8",
        "x2": "Mac OS",
        "x3": "xhs-pc-web",
        "x4": "4.20.1",
        "x5": a1,
        "x6": x_t,
        "x7": x_s,
        "x8": b1,
        "x9": mrc(x_t + x_s + b1),
        "x10": 1,
    }
    encode_str = encodeUtf8(json.dumps(common, separators=(',', ':')))
    x_s_common = b64Encode(encode_str)
    x_b3_traceid = get_b3_trace_id()
    return {
        "x-s": x_s,
        "x-t": x_t,
        "x-s-common": x_s_common,
        "x-b3-traceid": x_b3_traceid
    }
```

### JavaScript 版本 (xhs_xs_new.js)

```javascript
function sign(api, params, cookies) {
    const a1 = get_a1_params(cookies)
    return {
        "x-s": seccore_signv2(api, params),
        "x-t": Date.now(),
        "x-s-common": get_xs_common(a1),
        'x-b3-traceid': get_trace_id(),
    }
}
```

## 注意事项

1. **Cookie 中的 a1 值**：必须从请求的 cookies 中提取，用于签名计算
2. **localStorage 中的 b1 值**：在 Playwright 模式下从浏览器获取，在 JS 模式下使用固定值
3. **时间戳**：x-t 需要与签名计算时的时间戳保持一致
4. **重试机制**：签名失败时会自动重试 3 次，每次间隔 500ms
5. **环境模拟**：JS 签名需要模拟浏览器环境（window, document, navigator, localStorage 等）
