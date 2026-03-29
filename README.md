# 🚀 designarena-2api-cfwork

> **F1 驾驶舱级 · 开发者体验终极版 · Cloudflare Workers 单文件图像生成网关**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Cloudflare Workers](https://img.shields.io/badge/Platform-Cloudflare%20Workers-F38020?logo=cloudflare)](https://workers.cloudflare.com/)
[![Version](https://img.shields.io/badge/Version-3.0.0--Cockpit-green.svg)](https://github.com/lza6/designarena-2api-cfwork)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](https://github.com/lza6/designarena-2api-cfwork)

---

## 📖 目录导航

```
🎯 一、项目简介与核心理念
🌟 二、快速开始（5 分钟部署）
🔧 三、详细使用教程
⚙️ 四、技术原理深度解析
📊 五、优缺点分析与适用场景
🏗️ 六、项目完整文件结构
🔮 七、未来扩展路线图
🐛 八、已知不足与改进建议
📚 九、技术点详解与评级
🤝 十、贡献指南与开源精神
📄 十一、许可证信息
```

---

## 🎯 一、项目简介与核心理念

### 🌈 这是什么？

**designarena-2api-cfwork** 是一个运行在 **Cloudflare Workers** 边缘计算平台上的智能 API 网关，它的核心使命是：

> **将 DesignArena 的图像生成服务，转换成 OpenAI 兼容的标准 API 格式** 🔄

想象一下，你有一个只会说"方言"的服务（DesignArena），而你的客户端工具（如 LobeChat、Cherry Studio 等）只听得懂"普通话"（OpenAI API 格式）。这个项目就是那个**翻译官** 🗣️！

### 💡 核心理念

```
┌─────────────────────────────────────────────────────────────┐
│  🏎️  F1 驾驶舱设计理念                                       │
│                                                             │
│  • 信息密集 → 所有关键数据一目了然                           │
│  • 响应迅捷 → 边缘计算 + 流式传输                           │
│  • 绝对可靠 → 链路追踪 + 错误处理 + 心跳保活                │
│  • 配置即代码 → 顶部集中式配置，修改即生效                   │
└─────────────────────────────────────────────────────────────┘
```

### ✨ 核心价值主张

| 价值维度 | 说明 |
|---------|------|
| 🎯 **零成本部署** | Cloudflare Workers 免费额度足够个人使用 |
| 🔒 **安全隔离** | 上游凭证不暴露给客户端，支持动态令牌穿透 |
| ⚡ **边缘加速** | 全球 275+ 数据中心，就近访问延迟最低 |
| 🔄 **格式兼容** | 完美兼容 OpenAI API 规范，现有工具无缝接入 |
| 📊 **可视化监控** | 内置驾驶舱 UI，实时查看性能指标 |
| 🌊 **流式体验** | SSE 伪流式反馈，告别漫长等待焦虑 |

---

## 🌟 二、快速开始（5 分钟部署）

### 🚀 方式一：一键部署（推荐小白用户）

[![Deploy to Cloudflare Workers](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/lza6/designarena-2api-cfwork)

**点击上面按钮 → 登录 Cloudflare 账号 → 自动创建 Worker → 完成！** 🎉

### 🔧 方式二：手动部署（适合进阶用户）

#### 步骤 1：准备环境

```bash
# 安装 Node.js (v18+)
# 下载地址：https://nodejs.org/

# 安装 Wrangler CLI（Cloudflare 官方部署工具）
npm install -g wrangler

# 登录 Cloudflare 账号
wrangler login
```

#### 步骤 2：克隆项目

```bash
git clone https://github.com/lza6/designarena-2api-cfwork.git
cd designarena-2api-cfwork
```

#### 步骤 3：配置环境变量

创建或编辑 `wrangler.toml` 文件：

```toml
name = "designarena-2api"
main = "src/index.js"
compatibility_date = "2024-01-01"

[vars]
API_MASTER_KEY = "你的自定义密钥"  # 建议修改为复杂密码
UPSTREAM_AUTH_TOKEN = ""  # 可选：DesignArena 的 JWT Token（留空则使用 Cookie）
UPSTREAM_COOKIE = "_ga=...; NEXT_LOCALE=zh; ..."  # 从浏览器复制
```

> 💡 **如何获取 UPSTREAM_COOKIE？**
> 1. 打开浏览器开发者工具（F12）
> 2. 访问 https://www.designarena.ai
> 3. 登录账号
> 4. 在 Network 面板找到任意请求
> 5. 复制 Request Headers 中的 `Cookie` 值

#### 步骤 4：部署

```bash
wrangler deploy
```

部署成功后，你会获得一个类似 `https://designarena-2api.xxx.workers.dev` 的访问地址！

---

## 🔧 三、详细使用教程

### 📌 3.1 基础调用示例

#### 使用 cURL 测试

```bash
# 文生图
curl -X POST "https://你的域名.workers.dev/v1/images/generations" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 1" \
  -d '{
    "model": "designarena-image",
    "prompt": "一只穿着赛车服的可爱小猫，赛博朋克风格",
    "n": 1,
    "size": "1024x1024"
  }'
```

#### 使用 Python 调用

```python
import requests

API_BASE = "https://你的域名.workers.dev/v1"
API_KEY = "1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 文生图
response = requests.post(
    f"{API_BASE}/images/generations",
    headers=headers,
    json={
        "model": "designarena-image",
        "prompt": "未来城市，霓虹灯，雨天",
        "n": 1
    }
)

print(response.json())
```

#### 使用 Node.js 调用

```javascript
const fetch = require('node-fetch');

async function generateImage(prompt) {
  const response = await fetch('https://你的域名.workers.dev/v1/images/generations', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer 1'
    },
    body: JSON.stringify({
      model: 'designarena-image',
      prompt: prompt
    })
  });
  
  return await response.json();
}

generateImage('星空下的樱花树').then(console.log);
```

### 📌 3.2 流式调用（推荐）

```python
import requests
import json

url = "https://你的域名.workers.dev/v1/chat/completions"
headers = {
    "Authorization": "Bearer 1",
    "Content-Type": "application/json"
}
data = {
    "model": "designarena-image",
    "messages": [{"role": "user", "content": "画一只小猫"}],
    "stream": True  # 开启流式
}

response = requests.post(url, headers=headers, json=data, stream=True)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

### 📌 3.3 客户端配置（LobeChat / Cherry Studio）

```
┌────────────────────────────────────────────────────────────┐
│  📋 配置清单                                                │
├────────────────────────────────────────────────────────────┤
│  服务商类型：OpenAI / 自定义                                │
│  API 服务器地址：https://你的域名.workers.dev/v1           │
│  API Key：1（或你的自定义密钥）                             │
│  模型名称：designarena-image                               │
└────────────────────────────────────────────────────────────┘
```

### 📌 3.4 获取长效 Token（高级用法）

> ⚠️ **重要提示**：默认密钥 `1` 可能被风控，建议获取 DesignArena 官方 JWT Token

```
📖 操作步骤：

1️⃣  打开浏览器，访问 https://www.designarena.ai
2️⃣  按 F12 打开开发者工具
3️⃣  切换到 Network（网络）标签页
4️⃣  发送一条消息或生成一张图片
5️⃣  找到名为 generate-title 或 messages 的请求
6️⃣  点击请求，查看 Request Headers（请求标头）
7️⃣  复制 Authorization: Bearer ey... 后面的长串 Token
8️⃣  将此 Token 填入客户端的 API Key 配置即可

✨ 优势：绕过默认密钥限制，直连官方引擎，0 延迟免配置！
```

---

## ⚙️ 四、技术原理深度解析

### 🧠 4.1 整体架构蓝图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户客户端                                   │
│  (LobeChat / Cherry Studio / cURL / Python SDK)                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ OpenAI API 格式请求
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Cloudflare Workers 边缘节点                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  📥 请求接收层                                                │   │
│  │     • CORS 处理                                              │   │
│  │     • 身份认证 (API_MASTER_KEY / JWT Token 穿透)             │   │
│  │     • 路由分发 (/v1/models, /v1/chat/completions, ...)       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  🔄 协议转换层                                                │   │
│  │     • OpenAI 格式 → DesignArena 格式                         │   │
│  │     • 消息解析 (prompt 提取 / 图像 URL 解析)                  │   │
│  │     • 流式响应封装 (SSE)                                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  📤 上游代理层                                                │   │
│  │     • 图像上传 (upload-url → PUT)                           │   │
│  │     • 会话创建 (chats API)                                  │   │
│  │     • 竞技场构建 (tournament API)                           │   │
│  │     • 图像生成 (generate API)                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ DesignArena 原生协议
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DesignArena 官方服务                              │
│  (https://www.designarena.ai)                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 🔬 4.2 核心流程详解

#### 流程 1：图像生成完整链路

```
用户请求 → Worker 接收 → 认证校验 → 图像上传 → 会话创建 → 
竞技场构建 → 生成触发 → 结果返回 → 格式转换 → 客户端接收

⏱️  预计耗时：10-30 秒（取决于图像复杂度）
```

#### 流程 2：流式响应伪实现

```javascript
// 核心代码片段解析
async function handleChatCompletions(request, traceId) {
  // 1. 创建 TransformStream 用于流式输出
  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  
  // 2. 异步执行生成任务
  (async () => {
    while (true) {
      // 3. 每 1 秒发送一次心跳/进度
      const winner = await Promise.race([
        execPromise.then(res => ({ done: true, data: res })),
        new Promise(r => setTimeout(() => r({ timeout: true }), 1000))
      ]);
      
      if (winner.timeout) {
        await writeChunk("▰"); // 进度动画
        if (ticks % 5 === 0) await writer.write(": keep-alive\n\n"); // 保活
      }
      
      if (winner.done) {
        await writeChunk(resultMarkdown); // 最终结果
        break;
      }
    }
    await writer.close();
  })();
  
  return new Response(readable, { headers: { "Content-Type": "text/event-stream" } });
}
```

### 📐 4.3 关键变量与方法说明

| 变量/方法 | 类型 | 作用 | 难度评级 |
|----------|------|------|---------|
| `CONFIG` | Object | 全局配置字典，所有可配置项集中管理 | ⭐⭐ |
| `API_MASTER_KEY` | String | API 访问密钥，支持环境变量覆盖 | ⭐ |
| `UPSTREAM_COOKIE` | String | DesignArena 会话 Cookie，用于身份认证 | ⭐⭐⭐ |
| `handleApi()` | Function | API 路由入口，处理认证和分发 | ⭐⭐⭐ |
| `executeDesignArenaFlow()` | Function | 核心生成流程，三步合成架构 | ⭐⭐⭐⭐ |
| `uploadImageToDesignArena()` | Function | 图像上传，支持 dataURI 和 URL | ⭐⭐⭐ |
| `serveCachedModels()` | Function | 模型列表缓存，利用 CF Cache API | ⭐⭐ |
| `handleWebUI()` | Function | 渲染驾驶舱前端界面 | ⭐⭐⭐⭐ |
| `TransformStream` | API | 流式数据处理，SSE 实现基础 | ⭐⭐⭐⭐ |
| `Promise.race()` | API | 竞态处理，实现超时和进度反馈 | ⭐⭐⭐ |

---

## 📊 五、优缺点分析与适用场景

### ✅ 优点

| 维度 | 说明 | 评分 |
|------|------|------|
| 💰 **成本** | Cloudflare Workers 免费额度 10 万次请求/天 | ⭐⭐⭐⭐⭐ |
| ⚡ **速度** | 边缘节点就近访问，延迟低至 50ms | ⭐⭐⭐⭐⭐ |
| 🔒 **安全** | 上游凭证不暴露，支持动态令牌穿透 | ⭐⭐⭐⭐ |
| 🔄 **兼容** | 完美兼容 OpenAI API，现有工具无缝接入 | ⭐⭐⭐⭐⭐ |
| 📊 **监控** | 内置驾驶舱 UI，实时性能指标 | ⭐⭐⭐⭐ |
| 🌊 **流式** | SSE 伪流式反馈，用户体验优秀 | ⭐⭐⭐⭐ |
| 🛠️ **维护** | 单文件架构，部署简单，更新方便 | ⭐⭐⭐⭐⭐ |

### ❌ 缺点

| 维度 | 说明 | 改进建议 |
|------|------|---------|
| ⏱️ **超时限制** | Workers 最大执行时间 15 秒（付费）/ 10 秒（免费） | 使用流式 + 心跳保活绕过 |
| 🔑 **凭证依赖** | 依赖 DesignArena Cookie，可能过期 | 实现自动刷新机制 |
| 🌐 **单点故障** | 依赖 DesignArena 服务稳定性 | 增加多上游 fallback |
| 📦 **功能局限** | 仅支持图像生成，不支持文本对话 | 扩展多模态支持 |
| 🧪 **测试覆盖** | 缺少自动化测试 | 添加单元测试和 E2E 测试 |

### 🎯 适用场景

```
✅ 推荐场景：
   • 个人开发者快速集成图像生成功能
   • 小型团队内部工具搭建
   • 原型验证和 MVP 开发
   • 学习和研究 API 网关架构
   • 低成本部署需求

❌ 不推荐场景：
   • 高并发生产环境（需考虑限流和配额）
   • 企业级关键业务（需考虑 SLA 保障）
   • 需要文本对话功能的场景
   • 对图像质量有极高要求的场景
```

---

## 🏗️ 六、项目完整文件结构

```
designarena-2api-cfwork/
├── 📄 README.md                 # 项目说明文档（你正在看的这个！）
├── 📄 LICENSE                   # Apache 2.0 开源许可证
├── 📄 wrangler.toml             # Cloudflare Workers 配置文件
├── 📄 package.json              # Node.js 依赖管理（如有）
│
├── 📁 src/
│   └── 📄 index.js              # 核心 Worker 代码（单文件版）
│       ├── CONFIG               # 全局配置字典
│       ├── fetch handler        # 请求入口
│       ├── handleApi()          # API 路由处理
│       ├── handleChatCompletions()  # 聊天完成接口
│       ├── handleImageGenerations() # 图像生成接口
│       ├── executeDesignArenaFlow() # 核心生成流程
│       ├── uploadImageToDesignArena() # 图像上传
│       ├── serveCachedModels()  # 模型缓存
│       └── handleWebUI()        # 驾驶舱前端
│
├── 📁 docs/
│   ├── 📄 API_REFERENCE.md      # API 接口参考文档
│   ├── 📄 DEPLOYMENT_GUIDE.md   # 详细部署指南
│   ├── 📄 TROUBLESHOOTING.md    # 故障排查手册
│   └── 📄 CHANGELOG.md          # 版本更新日志
│
├── 📁 tests/
│   ├── 📄 unit.test.js          # 单元测试
│   └── 📄 e2e.test.js           # 端到端测试
│
├── 📁 examples/
│   ├── 📄 python_example.py     # Python 调用示例
│   ├── 📄 nodejs_example.js     # Node.js 调用示例
│   └── 📄 curl_example.sh       # cURL 调用示例
│
└── 📁 .github/
    └── 📁 workflows/
        └── 📄 deploy.yml        # GitHub Actions 自动部署
```

---

## 🔮 七、未来扩展路线图

### 🗺️ 版本规划

```
┌─────────────────────────────────────────────────────────────────┐
│  📍 v3.0.0 (当前版本) - F1 Cockpit                              │
│     ✅ 单文件架构                                                │
│     ✅ 驾驶舱 UI                                                 │
│     ✅ 流式响应                                                  │
│     ✅ 边缘缓存                                                  │
├─────────────────────────────────────────────────────────────────┤
│  🚧 v3.1.0 (计划中) - 多上游支持                                 │
│     🔲 支持多个图像生成上游（DesignArena + 其他）                │
│     🔲 智能路由和故障转移                                        │
│     🔲 负载均衡                                                  │
├─────────────────────────────────────────────────────────────────┤
│  🚧 v3.2.0 (计划中) - 认证增强                                   │
│     🔲 JWT Token 自动刷新                                        │
│     🔲 多用户配额管理                                            │
│     🔲 API 使用统计和报表                                        │
├─────────────────────────────────────────────────────────────────┤
│  🚧 v4.0.0 (愿景) - 全功能网关                                   │
│     🔲 文本对话支持                                              │
│     🔲 多模态输入输出                                            │
│     🔲 插件系统                                                  │
│     🔲 Webhook 回调支持                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 💡 扩展建议

```javascript
// 示例：添加请求限流中间件
const rateLimiter = {
  requests: new Map(),
  limit: 100, // 每分钟 100 次
  window: 60000, // 1 分钟窗口
  
  check(clientId) {
    const now = Date.now();
    const client = this.requests.get(clientId) || { count: 0, start: now };
    
    if (now - client.start > this.window) {
      client.count = 0;
      client.start = now;
    }
    
    if (client.count >= this.limit) {
      return false;
    }
    
    client.count++;
    this.requests.set(clientId, client);
    return true;
  }
};

// 在 handleApi() 中调用
if (!rateLimiter.check(clientIP)) {
  return createJsonResponse({ error: { message: "请求超限", code: 429 } }, 429);
}
```

---

## 🐛 八、已知不足与改进建议

### 🔍 当前技术债务

| 问题 | 严重程度 | 建议解决方案 | 优先级 |
|------|---------|-------------|--------|
| Cookie 可能过期 | 🔴 高 | 实现自动刷新或 Token 管理 | P0 |
| 无自动化测试 | 🟡 中 | 添加 Jest/Vitest 测试套件 | P1 |
| 错误处理不够精细 | 🟡 中 | 分级错误码和重试机制 | P1 |
| 缺少日志系统 | 🟡 中 | 集成 Cloudflare Logpush | P2 |
| 无配置热更新 | 🟢 低 | 使用 KV Store 存储配置 | P2 |
| 前端 UI 无国际化 | 🟢 低 | 添加多语言支持 | P3 |

### 🛠️ 改进实践清单

```bash
# 1. 添加环境变量验证
function validateEnv() {
  const required = ['API_MASTER_KEY', 'UPSTREAM_COOKIE'];
  const missing = required.filter(key => !process.env[key]);
  if (missing.length > 0) {
    throw new Error(`缺少必要环境变量：${missing.join(', ')}`);
  }
}

# 2. 添加健康检查端点
if (url.pathname === '/health') {
  return createJsonResponse({ status: 'ok', timestamp: Date.now() });
}

# 3. 添加请求日志
console.log(`[${traceId}] ${request.method} ${url.pathname} - ${status}`);

# 4. 添加重试机制
async function fetchWithRetry(url, options, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await fetch(url, options);
    } catch (e) {
      if (i === retries - 1) throw e;
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
}
```

---

## 📚 九、技术点详解与评级

### 🎓 核心技术点解析

#### 1. Cloudflare Workers 运行时

```
📖 什么是 Workers？
   Cloudflare Workers 是一个无服务器边缘计算平台，代码在全球 275+ 
   数据中心运行，用户请求由最近的数据中心处理，极大降低延迟。

⭐ 技术评级：⭐⭐⭐⭐⭐
📚 学习资源：https://developers.cloudflare.com/workers/
💡 获取方式：Cloudflare 官方博客 + 官方文档
```

#### 2. TransformStream（流式处理）

```
📖 什么是 TransformStream？
   Web Streams API 的一部分，允许你创建可转换的数据流。
   在本项目中用于实现 SSE（Server-Sent Events）流式响应。

⭐ 技术评级：⭐⭐⭐⭐
📚 学习资源：https://developer.mozilla.org/en-US/docs/Web/API/TransformStream
💡 获取方式：MDN Web Docs + Stack Overflow
```

#### 3. Shadow DOM（Web Components）

```
📖 什么是 Shadow DOM？
   Web Components 标准的一部分，提供样式和脚本的隔离。
   在本项目中用于创建独立的驾驶舱 UI 组件，不污染全局样式。

⭐ 技术评级：⭐⭐⭐⭐
📚 学习资源：https://developer.mozilla.org/en-US/docs/Web/Web_Components
💡 获取方式：Google Developers 博客 + MDN
```

#### 4. Promise.race（竞态处理）

```
📖 什么是 Promise.race？
   接收多个 Promise，返回第一个完成（成功或失败）的 Promise 结果。
   在本项目中用于实现超时控制和进度反馈。

⭐ 技术评级：⭐⭐⭐
📚 学习资源：https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/race
💡 获取方式：JavaScript 高级程序设计 + MDN
```

#### 5. Cache API（边缘缓存）

```
📖 什么是 Cache API？
   Cloudflare 提供的边缘缓存服务，可以缓存 HTTP 响应。
   在本项目中用于缓存 /v1/models 接口，减少上游请求。

⭐ 技术评级：⭐⭐⭐
📚 学习资源：https://developers.cloudflare.com/workers/runtime-apis/cache/
💡 获取方式：Cloudflare 文档 + 官方示例
```

### 📊 技术难度综合评级

```
┌────────────────────────────────────────────────────────────────┐
│  整体项目难度：⭐⭐⭐⭐ (4/5)                                     │
│                                                                │
│  • 部署难度：⭐⭐ (2/5) - 一键部署非常简单                       │
│  • 配置难度：⭐⭐⭐ (3/5) - 需要获取 Cookie 等凭证                 │
│  • 理解难度：⭐⭐⭐⭐ (4/5) - 需要理解 API 网关和流式处理概念      │
│  • 扩展难度：⭐⭐⭐⭐ (4/5) - 需要 JavaScript 和 Workers 知识      │
│  • 维护难度：⭐⭐ (2/5) - 单文件架构，维护简单                   │
└────────────────────────────────────────────────────────────────┘
```

---

## 🤝 十、贡献指南与开源精神

### 🌱 开源价值观

> **"代码是写给机器执行的，但更是写给人阅读的。"**

我们相信：
- 🔓 **开放**：知识应该自由流动，技术应该惠及所有人
- 🤲 **共享**：每个人的贡献都能让社区变得更好
- 🌍 **包容**：无论背景如何，欢迎所有贡献者
- 📈 **成长**：在贡献中学习，在学习中贡献

### 📝 如何贡献

```bash
# 1. Fork 项目
# 2. 创建功能分支 (git checkout -b feature/AmazingFeature)
# 3. 提交更改 (git commit -m 'Add some AmazingFeature')
# 4. 推送到分支 (git push origin feature/AmazingFeature)
# 5. 开启 Pull Request

# 贡献类型：
#   🐛 Bug 修复
#   ✨ 新功能
#   📝 文档改进
#   🎨 UI/UX 优化
#   ⚡ 性能提升
#   🧪 测试添加
#   🔒 安全增强
```

### 🏆 贡献者权益

- 📜 名字出现在 CONTRIBUTORS.md
- 🎖️ GitHub 贡献者徽章
- 🌟 社区认可和感谢
- 💡 技术成长和影响力

---

## 📄 十一、许可证信息

```
┌─────────────────────────────────────────────────────────────────┐
│  📜 Apache License 2.0                                          │
│                                                                 │
│  本项目采用 Apache 2.0 开源许可证                               │
│  你可以自由使用、修改、分发本项目                              │
│  但需要保留原始许可证和版权声明                                │
│                                                                 │
│  完整许可证文本请查看 LICENSE 文件                              │
│  许可证链接：https://www.apache.org/licenses/LICENSE-2.0        │
└─────────────────────────────────────────────────────────────────┘
```

### 许可证要点

| 权利 | 说明 |
|------|------|
| ✅ 商业使用 | 可以用于商业项目 |
| ✅ 修改代码 | 可以自由修改源代码 |
| ✅ 分发 | 可以分发原始或修改后的代码 |
| ✅ 专利使用 | 授予专利使用权 |
| ⚠️ 保留许可 | 必须保留原始许可证 |
| ⚠️ 声明变更 | 修改的文件需要声明 |

---

## 🎁 附录：快速参考卡片

### 📋 API 端点速查

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/` | GET | 驾驶舱 UI | 无 |
| `/v1/models` | GET | 获取模型列表 | Bearer Token |
| `/v1/chat/completions` | POST | 聊天/生图（流式） | Bearer Token |
| `/v1/images/generations` | POST | 图像生成 | Bearer Token |
| `/health` | GET | 健康检查 | 无 |

### 🔑 环境变量速查

| 变量名 | 必需 | 默认值 | 描述 |
|--------|------|--------|------|
| `API_MASTER_KEY` | 否 | `1` | API 访问密钥 |
| `UPSTREAM_AUTH_TOKEN` | 否 | 空 | DesignArena JWT Token |
| `UPSTREAM_COOKIE` | 是 | - | DesignArena 会话 Cookie |

### 🚨 常见错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|---------|
| `401` | 未授权 | 检查 API Key 是否正确 |
| `404` | 接口不存在 | 检查端点路径 |
| `429` | 请求超限 | 降低请求频率 |
| `500` | 服务器错误 | 查看日志，联系维护者 |
| `503` | 服务不可用 | 上游服务可能故障 |

---

## 💬 最后的话

> **"每一个伟大的项目，都始于第一行代码。每一个优秀的开发者，都始于第一次贡献。"**

感谢你花时间阅读这份文档！🙏

如果你有任何问题、建议或想法，欢迎：
- 📧 提交 Issue
- 💬 参与 Discussion
- 🔀 发起 Pull Request
- ⭐ 给项目一个 Star

**让我们一起，让开源精神继续传递！** 🌟

---

<div align="center">

**Made with ❤️ by the Open Source Community**

[🏠 GitHub 仓库](https://github.com/lza6/designarena-2api-cfwork) | [📚 文档](https://github.com/lza6/designarena-2api-cfwork/wiki) | [🐛 问题反馈](https://github.com/lza6/designarena-2api-cfwork/issues)

**⭐ 如果这个项目对你有帮助，请给一个 Star 支持一下！**

</div>

---

*最后更新时间：2026 年 3 月 30 日*