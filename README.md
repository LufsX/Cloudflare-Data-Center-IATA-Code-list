# [Cloudflare-Data-Center-IATA-Code-list](https://github.com/LufsX/Cloudflare-Data-Center-IATA-Code-list)

Cloudflare 最全数据中心及其 IATA 代码列表

---

Cloudflare's Comprehensive Data Center and IATA Code List

## 数据文件 Data Files

### 基础数据 Basic Data

仅包含 IATA 代码和对应的位置名称。格式为 JSON 字典：`{ "IATA 代码": "位置名称" }`

Only includes IATA codes and their corresponding location names. The format is JSON dict: `{ "IATA Code": "Location Name" }`

- 中文 Chinese
  - GitHub Raw: [`https://github.com/LufsX/Cloudflare-Data-Center-IATA-Code-list/raw/main/cloudflare-iata-zh.json`](https://github.com/LufsX/Cloudflare-Data-Center-IATA-Code-list/raw/main/cloudflare-iata-zh.json)
  - Jsdelivr CDN: [`https://cdn.jsdelivr.net/gh/LufsX/Cloudflare-Data-Center-IATA-Code-list/cloudflare-iata-zh.json`](https://cdn.jsdelivr.net/gh/LufsX/Cloudflare-Data-Center-IATA-Code-list/cloudflare-iata-zh.json)
  - Cloudflare Pages CDN: [`https://iata.isteed.cc/cloudflare-iata-zh.json`](https://iata.isteed.cc/cloudflare-iata-zh.json)
- 英文 English
  - GitHub Raw: [`https://github.com/LufsX/Cloudflare-Data-Center-IATA-Code-list/raw/main/cloudflare-iata.json`](https://github.com/LufsX/Cloudflare-Data-Center-IATA-Code-list/raw/main/cloudflare-iata.json)
  - Jsdelivr CDN: [`https://cdn.jsdelivr.net/gh/LufsX/Cloudflare-Data-Center-IATA-Code-list/cloudflare-iata.json`](https://cdn.jsdelivr.net/gh/LufsX/Cloudflare-Data-Center-IATA-Code-list/cloudflare-iata.json)
  - Cloudflare Pages: [`https://iata.isteed.cc/cloudflare-iata.json`](https://iata.isteed.cc/cloudflare-iata.json)

### 完整数据 Full Data

包含每个数据中心的中英文位置名称、经纬度信息。格式为 JSON 字典：`{ "IATA 代码": { "place": "英文位置", "place_zh": "中文位置", "lat": 纬度, "lng": 经度 } }`

Contains the location in both English and Chinese, along with latitude and longitude for each data center. The format is JSON dict: `{ "IATA Code": { "place": "English Location", "place_zh": "Chinese Location", "lat": Latitude, "lng": Longitude } }`

- GitHub Raw: [`https://github.com/LufsX/Cloudflare-Data-Center-IATA-Code-list/raw/main/cloudflare-iata-full.json`](https://github.com/LufsX/Cloudflare-Data-Center-IATA-Code-list/raw/main/cloudflare-iata-full.json)
- Jsdelivr CDN: [`https://cdn.jsdelivr.net/gh/LufsX/Cloudflare-Data-Center-IATA-Code-list/cloudflare-iata-full.json`](https://cdn.jsdelivr.net/gh/LufsX/Cloudflare-Data-Center-IATA-Code-list/cloudflare-iata-full.json)
- Cloudflare Pages: [`https://iata.isteed.cc/cloudflare-iata-full.json`](https://iata.isteed.cc/cloudflare-iata-full.json)

### 中英文对照表

英文地名翻译成对应格式的中文地名的对照表；已有译文可人工维护，更新数据时缺失的机器译文会自动追加到文件末尾

- GitHub Raw: [`https://github.com/LufsX/Cloudflare-Data-Center-IATA-Code-list/raw/main/en2zh.json`](https://github.com/LufsX/Cloudflare-Data-Center-IATA-Code-list/raw/main/en2zh.json)
- Jsdelivr CDN: [`https://cdn.jsdelivr.net/gh/LufsX/Cloudflare-Data-Center-IATA-Code-list/en2zh.json`](https://cdn.jsdelivr.net/gh/LufsX/Cloudflare-Data-Center-IATA-Code-list/en2zh.json)
- Cloudflare Pages: [`https://iata.isteed.cc/en2zh.json`](https://iata.isteed.cc/en2zh.json)

## /cdn-cgi/trace

可以通过在使用了 Cloudflare 的网站访问 `/cdn-cgi/trace`（例如 [`https://iata.isteed.cc/cdn-cgi/trace`](https://iata.isteed.cc/cdn-cgi/trace)） 来查看当前请求被路由到的 Cloudflare 数据中心的 IATA 代码，返回内容中的 `colo` 字段即为 IATA 代码。

---

You can check which Cloudflare data center your request is routed to by visiting `/cdn-cgi/trace` (e.g. [`https://iata.isteed.cc/cdn-cgi/trace`](https://iata.isteed.cc/cdn-cgi/trace)) on a website using Cloudflare. The `colo` field in the returned content represents the IATA code.

---

例如 Example:

```
fl=618f32
h=iata.isteed.cc
ip=114.51.41.191
ts=1763212940.000
visit_scheme=https
uag=xh/0.25.0
colo=LAX
sliver=none
http=http/2
loc=CN
tls=TLSv1.3
sni=plaintext
warp=off
gateway=off
rbi=off
kex=X25514
```

## API

用法 Example Usage:

- `https://iata.isteed.cc/<zh|en|full>/<IATA Code>`
  - `<zh|en|full>`: 查询类型 Query Type，`zh` 中文地名 Chinese，`en` 英文地名 English，`full` 完整信息 Full Information
  - `<IATA Code>`: IATA 代码

示例 Example:

- [`https://iata.isteed.cc/zh/LAX`](https://iata.isteed.cc/zh/LAX)
  - 返回值 Return Value: `美国洛杉矶`
- [`https://iata.isteed.cc/en/LAX`](https://iata.isteed.cc/en/LAX)
  - 返回值 Return Value: `Los Angeles, United States`
- [`https://iata.isteed.cc/full/LAX`](https://iata.isteed.cc/full/LAX)
  - 返回值 Return Value: `{"place":"Los Angeles, United States","place_zh":"美国洛杉矶","lat":33.94250107,"lng":-118.4079971,"cca2":"US","region":"North America"}`

## 其它 Others

数据抓取自 [Cloudflare System Status](https://www.cloudflarestatus.com/api/v2/components.json)

位置数据来源于 [speed.cloudflare.com](https://speed.cloudflare.com/locations) 和 [ourairports-data](https://davidmegginson.github.io/ourairports-data/airports.csv)

其中添加了一个特例: `LOCAL` 用于标识本地网络，以便在本地网络中使用

地名对照表: `en2zh.json`

欢迎纠错补充～

---

Data retrieved from [Cloudflare System Status](https://www.cloudflarestatus.com/api/v2/components.json)

Location data sourced from [speed.cloudflare.com](https://speed.cloudflare.com/locations) and [ourairports-data](https://davidmegginson.github.io/ourairports-data/airports.csv)

A special case has been added: `LOCAL` is used to identify the local network for use in the local network

Pull requests and issues are welcome ~
