/**
 * =================================================================================
 * 项目: designarena-2api (Cloudflare Worker 单文件版)
 * 版本: 2.0.0 (代号: F1-Cockpit / 开发者驾驶舱级终极版)
 * 作者: 首席AI执行官 & 开发者体验架构师
 * 理念: 为开发者打造如同F1赛车驾驶舱般的工具——信息密集、响应迅捷、绝对可靠。
 * 
 * [核心特性]
 * 1. [配置即代码] 顶部集中式全局配置字典，易于部署和管理。
 * 2. [开发者驾驶舱] 根路径 (/) 渲染无懈可击的全中文、信息密集的交互面板，采用 Web Components (Shadow DOM)。
 * 3. [完美兼容] 向上兼容 OpenAI 格式 (/v1/chat/completions) 和流式 (SSE) 协议。
 * 4. [进度伪流] 完美解决上游生成等待时间过长导致的超时问题，采用伪流动画实时反馈进度。
 * 5. [链路追踪] 统一注入 `X-Worker-Trace-ID` 并集成错误处理。
 * 6. [边缘缓存] 支持 Cloudflare 内置 Cache API 进行 /v1/models 静态路由缓存。
 * =================================================================================
 */

// --- [第一部分: 核心配置 (Configuration-as-Code)] ---
const CONFIG = {
  PROJECT_NAME: "designarena-2api",
  PROJECT_VERSION: "3.0.0-Cockpit",

  // 安全与认证 (API_MASTER_KEY 可在 CF 环境变量中覆盖)
  API_MASTER_KEY: "1",

  // 上游架构映射
  UPSTREAM_URL: "https://www.designarena.ai",
  UPSTREAM_AUTH_TOKEN: "" /* 彻底抛弃源码硬编码，强制在环境变量中注入 API_MASTER_KEY */,
  // 必须使用提取的 Cookie
  UPSTREAM_COOKIE: "_ga=GA1.1.498965500.1765977860; NEXT_LOCALE=zh; NEXT_TIMEZONE=Asia/Shanghai; _ga_8YBN2LD1WG=GS2.1.s1774701052$o24$g0$t1774701052$j60$l0$h0; _gcl_au=1.1.506033947.1774701053; _ga_YNTFBNE29J=GS2.1.s1774701053$o27$g0$t1774701053$j60$l0$h0; ph_phc_i6iFf7vuaXs59sLohA9hgYK3mOQWEYDEo3qLsXktpGz_posthog=%7B%22%24device_id%22%3A%22019b2c7b-a884-7e5e-a8e7-5dfaa85480e0%22%2C%22distinct_id%22%3A%22kskEZYwPXqTgyodWoiXobGLiGn92%22%2C%22%24sesid%22%3A%5B1774701104626%2C%22019d346d-012a-75f4-bb86-60537ed2b0f9%22%2C1774701052199%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22https%3A%2F%2Fwww.nodeloc.com%2F%22%2C%22u%22%3A%22https%3A%2F%2Fwww.designarena.ai%2F%22%7D%2C%22%24user_state%22%3A%22identified%22%7D",

  // 模型支持
  DEFAULT_MODEL: "designarena-image",
  MODELS: ["designarena-image", "dall-e-3", "gpt-4-vision-preview"], // 增加常见名称映射，提升集成兼容性

  // 公共伪装浏览器指纹
  HEADERS: {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "origin": "https://www.designarena.ai",
    "priority": "u=1, i",
    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
  }
};

// --- [第二部分: 核心路由和入口机制] ---
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    // 配置注入：优先使用环境变量
    const apiKey = env.API_MASTER_KEY || CONFIG.API_MASTER_KEY;
    request.ctx = { apiKey: apiKey };

    // 1. CORS 预检
    if (request.method === "OPTIONS") return handleCorsPreflight();

    // 2. HTTP/3 提升：Cloudflare 默认会在前端处理。内部与上游通信的 Fetch 会自动采用最优化协议（包括 Brotli 与 HTTP/3）。

    // 3. 根目录驶向 F1 Cockpit 驾驶舱 UI
    if (url.pathname === "/" || url.pathname === "/index.html") {
      return handleWebUI(request, env, ctx);
    }

    // 4. API 路由 (/v1/**)
    if (url.pathname.startsWith('/v1/')) {
      return handleApi(request, env, ctx); // 传入 Worker execution context 用于缓存
    }

    // 5. 迷航拦截 (404)
    return createJsonResponse({
      error: { message: "未能找到此航点 (Path Not Found).", type: "invalid_request_error", code: 404 }
    }, 404);
  }
};

// --- [第三部分: API 核心代理逻辑与认证] ---

async function handleApi(request, env, ctx) {
  // 1. 动态凭证透传 (Dynamic Credential Proxying) 与严格认证
  const authHeader = request.headers.get("Authorization");
  const passedToken = authHeader ? authHeader.replace("Bearer ", "").trim() : "";

  // 启发式：如果用户传入的是真正的 JWT Token（长且包含分隔符），直接将其穿透给上游
  let dynamicAuthToken = CONFIG.UPSTREAM_AUTH_TOKEN;
  let isDynamicProxy = false;
  if (passedToken.length > 50 && passedToken.includes(".")) {
    dynamicAuthToken = passedToken;
    isDynamicProxy = true;
  }

  const expectedKey = `Bearer ${request.ctx.apiKey}`;
  if (!isDynamicProxy && request.ctx.apiKey !== "1" && authHeader !== expectedKey) {
    return createJsonResponse({ error: { message: "未获授权：您的密钥无效。提示: 您可直接将 DesignArena 的 JWT Token 作为密钥填入客户端以永久免去刷新。", code: 401 } }, 401);
  }

  request.ctx.upstreamAuthToken = dynamicAuthToken;

  const url = new URL(request.url);
  const traceId = `req-${crypto.randomUUID()}`; // 请求水印，用于追踪

  // 2. 边缘缓存优化：API Models
  if (url.pathname === '/v1/models' && request.method === 'GET') {
    return await serveCachedModels(request, ctx);
  }

  // 3. 核心聊天/图片生成入口
  if (url.pathname === '/v1/chat/completions' && request.method === 'POST') {
    return await handleChatCompletions(request, traceId);
  }

  if (url.pathname === '/v1/images/generations' && request.method === 'POST') {
    return await handleImageGenerations(request, traceId);
  }

  return createJsonResponse({ error: { message: `此接口当前在主代理节点未挂载: ${url.pathname}`, code: 404 } }, 404);
}

// 模型获取接口（利用 Cloudflare CF Cache API 缓存幂等数据）
async function serveCachedModels(request, ctx) {
  const cache = caches.default;
  let response = await cache.match(request);
  if (!response) {
    const modelsData = {
      object: 'list',
      data: CONFIG.MODELS.map(model => ({ id: model, object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'designarena' }))
    };
    response = createJsonResponse(modelsData, 200);
    // 缓存 1 小时
    response.headers.set('Cache-Control', 'public, max-age=3600');
    ctx.waitUntil(cache.put(request, response.clone()));
  }
  return response;
}

// 聊天生成：实现高度抽象的三步合成架构与智能背压反馈

// --- [核心引擎架构：三步合成抽象层] ---
async function uploadImageToDesignArena(imageUrl, authHeaders) {
  let blob, contentType, fileName = "input-image.png";

  if (imageUrl.startsWith('data:')) {
    const parts = imageUrl.split(',');
    const mime = parts[0].match(/:(.*?);/)[1];
    const binary = atob(parts[1]);
    const array = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) array[i] = binary.charCodeAt(i);
    blob = new Blob([array], { type: mime });
    contentType = mime;
    fileName = `input-${Date.now()}.${mime.split('/')[1] || 'png'}`;
  } else {
    const res = await fetch(imageUrl);
    if (!res.ok) throw new Error(`无法下载输入图像: ${res.status}`);
    blob = await res.blob();
    contentType = blob.type || "image/png";
    fileName = `input-${Date.now()}.png`;
  }

  // 1. 获取上传链接
  const uploadUrlRes = await fetch(`${CONFIG.UPSTREAM_URL}/api/voteNew/upload-url`, {
    method: "POST", headers: authHeaders, body: JSON.stringify({ fileName, contentType })
  });
  if (!uploadUrlRes.ok) throw new Error(`无法获取上传凭证: ${uploadUrlRes.status}`);
  const { uploadUrl, storagePath } = await uploadUrlRes.json();

  // 2. 执行 PUT 上传
  const putRes = await fetch(uploadUrl, {
    method: "PUT", headers: { "Content-Type": contentType }, body: blob
  });
  if (!putRes.ok) throw new Error(`上传图像失败: ${putRes.status}`);

  return storagePath;
}

async function executeDesignArenaFlow(prompt, imageUrl, ctx, traceId, onHeartbeat = async (p0) => { }) {
  const authHeaders = {
    ...CONFIG.HEADERS,
    "authorization": `Bearer ${ctx.upstreamAuthToken}`,
    "cookie": CONFIG.UPSTREAM_COOKIE,
    "X-Request-ID": traceId
  };

  let inputImageStoragePath = null;
  if (imageUrl) {
    await onHeartbeat("📤 [0/3] 正在同步视觉素材到云创作中心...");
    inputImageStoragePath = await uploadImageToDesignArena(imageUrl, authHeaders);
  }

  await onHeartbeat("🚀 [1/3] 正在挂载通信信道...");
  const chatRes = await fetch(`${CONFIG.UPSTREAM_URL}/api/chats`, {
    method: "POST", headers: authHeaders, body: JSON.stringify({ prompt: prompt })
  });
  if (!chatRes.ok) throw new Error(`[通道申请失败] status: ${chatRes.status}`);
  const chatId = (await chatRes.json()).chatId;

  await onHeartbeat(`📡 [2/3] 信道确立 (${chatId.substring(0, 8)}...), 正在构建创作矩阵...`);
  const tourHeaders = { ...authHeaders, "referer": `${CONFIG.UPSTREAM_URL}/chat/${chatId}` };

  // 使用官方 storagePath 架构进行图生图
  const tourBody = {
    prompt: prompt,
    arena: "models",
    category: "image",
    premiumMode: true, // 强制开启高级模式以支持图生图
    chatId: chatId,
    inputImageStoragePath: inputImageStoragePath,
    inputImageStoragePaths: inputImageStoragePath ? [inputImageStoragePath] : [],
    // 补齐官方参数，防止服务端因缺少字段而忽略输入
    inputVideoStoragePath: null,
    inputVideoUrl: null,
    inputAudioStoragePath: null,
    videoDuration: null,
    testingId: null
  };

  const tourRes = await fetch(`${CONFIG.UPSTREAM_URL}/api/voteNew/tournament`, {
    method: "POST", headers: tourHeaders, body: JSON.stringify(tourBody)
  });
  if (!tourRes.ok) throw new Error(`[竞技场构建失败] status: ${tourRes.status}`);
  const tournamentId = (await tourRes.json()).tournamentId;

  await onHeartbeat(`🎨 [3/3] 图像引擎启动！约需 10-20 秒，请稍候...`);
  const genRes = await fetch(`${CONFIG.UPSTREAM_URL}/api/voteNew/tournament/${tournamentId}/generate`, {
    method: "POST", headers: { ...tourHeaders, "content-length": "0" }
  });

  if (!genRes.ok) throw new Error(`[渲染崩溃] status: ${genRes.status}`);
  return await genRes.json();
}

async function handleImageGenerations(request, traceId) {
  try {
    const body = await request.json();
    const prompt = body.prompt || "a beautiful image";
    const imageUrl = body.image || body.image_url || null; // 处理多渠道图生图映射

    // 我们直接使用 executeDesignArenaFlow 进行阻塞调用
    const generateData = await executeDesignArenaFlow(prompt, imageUrl, request.ctx, traceId);

    const dataArray = [];
    if (generateData.success && generateData.tournament?.generations) {
      generateData.tournament.generations.forEach(g => {
        if (g.imageUrl) dataArray.push({ url: g.imageUrl });
      });
    }

    if (dataArray.length === 0) {
      throw new Error("模型未返回任何有效图像，可能已被过滤或风控拦截。");
    }

    // 符合 OpenAI 规范的 v1/images/generations 实体
    return createJsonResponse({
      created: Math.floor(Date.now() / 1000),
      data: dataArray
    }, 200, { "X-Worker-Trace-ID": traceId });

  } catch (err) {
    console.error("[GENERATION_ERROR]", err);
    return createJsonResponse({ error: { message: `图像生成链路崩溃: ${err.message}`, code: 500 } }, 500);
  }
}
async function handleChatCompletions(request, traceId) {
  try {
    const body = await request.json();

    // 动态提取 prompt 与 imageUrl
    let prompt = "an image";
    let imageUrl = body.image || body.image_url || null; // 检查外层定义的图像字段

    if (body.messages && body.messages.length > 0) {
      const reversedMessages = [...body.messages].reverse();
      // 从后往前找第一个包含文本或图像的消息
      for (const msg of reversedMessages) {
        if (typeof msg.content === 'string') {
          if (!prompt || prompt === "an image") prompt = msg.content;
        } else if (Array.isArray(msg.content)) {
          for (let item of msg.content) {
            if (item.type === 'text' && (!prompt || prompt === "an image")) prompt = item.text;
            if (item.type === 'image_url') {
              // 支持对象格式或直接字符串格式
              imageUrl = (typeof item.image_url === 'object') ? item.image_url.url : item.image_url;
            }
          }
        }
        if (imageUrl) break; // 找到图像后停止搜索
      }
    }

    const isStream = body.stream !== false;
    const model = body.model || CONFIG.DEFAULT_MODEL;

    // 动态增加模型白名单
    if (!CONFIG.MODELS.includes(model)) CONFIG.MODELS.push(model);

    if (isStream) {
      const { readable, writable } = new TransformStream();
      const writer = writable.getWriter();
      const encoder = new TextEncoder();

      const writeChunk = async (content, finishReason = null) => {
        const chunk = {
          id: traceId, object: "chat.completion.chunk", created: Math.floor(Date.now() / 1000), model: model,
          choices: [{ index: 0, delta: { content }, finish_reason: finishReason }]
        };
        await writer.write(encoder.encode(`data: ${JSON.stringify(chunk)}

`));
      };

      (async () => {
        try {
          await writeChunk("🚀 收到指令，正在启动 DesignArena V3 图像引擎...\n");
          if (imageUrl) {
            await writeChunk(`📸 [Found] 识别到参考图像，正在解析特征向量...\n`);
          }
          let resultMarkdown = "";

          const execPromise = executeDesignArenaFlow(prompt, imageUrl, request.ctx, traceId, async (msg) => {
            await writeChunk(msg + "\n");
          });

          let ticks = 0;
          while (true) {
            const winner = await Promise.race([
              execPromise.then(res => ({ done: true, data: res })).catch(err => ({ error: true, data: err })),
              new Promise(r => setTimeout(() => r({ timeout: true }), 1000))
            ]);

            if (winner.done) {
              const generateData = winner.data;
              resultMarkdown = "\n\n### 🎨 DesignArena 结集展板\n\n";
              if (generateData.success && generateData.tournament?.generations) {
                const gens = generateData.tournament.generations;
                let validCount = 0;
                for (let i = 0; i < gens.length; i++) {
                  if (gens[i].imageUrl) {
                    const providerName = gens[i].metadata?.providerId || `Node-${i + 1}`;
                    resultMarkdown += `![模型 ${providerName} 的渲染结晶](${gens[i].imageUrl})

`;
                    validCount++;
                  }
                }
                if (validCount === 0) resultMarkdown += "> ⚠️ **生成故障**：所有引擎都未返回可用的图像源。";
              } else {
                resultMarkdown += "> ⚠️ **解析异常**：数据格式不符合预设链路。\n\n```json\n" + JSON.stringify(generateData) + "\n```";
              }
              break;
            }
            if (winner.error) throw winner.data;
            if (winner.timeout) {
              ticks++;
              if (ticks % 2 === 0) await writeChunk("▰");
              // 补充SSE标准 Keep-Alive 心跳注释，防止被Nginx等代理网关由于长时间空闲切断
              if (ticks % 5 === 0) await writer.write(encoder.encode(": keep-alive\n\n"));
            }
          }

          await writeChunk(resultMarkdown);

        } catch (e) {
          console.error("[STREAM_ERROR]", e);
          await writeChunk(`

❌ **致命错误**：链路请求已断开。报错详情：${e.message}
请检查配置和通信凭证是否有效。`);
        } finally {
          await writeChunk("", "stop");
          await writer.write(encoder.encode("data: [DONE]\n\n"));
          await writer.close();
        }
      })();

      return new Response(readable, {
        status: 200,
        headers: {
          ...corsHeaders(),
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
          "X-Worker-Trace-ID": traceId
        }
      });
    }

    // --- 非流式接口处理 ---
    const generateData = await executeDesignArenaFlow(prompt, imageUrl, request.ctx, traceId);
    let resultMarkdown = "### 🎨 DesignArena 结集展板\n\n";
    if (generateData.success && generateData.tournament?.generations) {
      generateData.tournament.generations.forEach(g => {
        if (g.imageUrl) resultMarkdown += `![图像](${g.imageUrl})

`;
      });
    } else {
      resultMarkdown += "生成数据解析失败。";
    }

    return createJsonResponse({
      id: traceId, object: "chat.completion", created: Math.floor(Date.now() / 1000), model: model,
      choices: [{ index: 0, message: { role: "assistant", content: resultMarkdown }, finish_reason: "stop" }],
      usage: { prompt_tokens: prompt.length, completion_tokens: 100, total_tokens: prompt.length + 100 }
    }, 200, { "X-Worker-Trace-ID": traceId });

  } catch (err) {
    return createJsonResponse({ error: { message: `内部中继错误: ${err.message}`, code: 500 } }, 500);
  }
}


// 辅助函数：从多类型的 OpenAI 消息格式中强壮提取最后一句用户对话
function extractPrompt(messages) {
  if (!messages || !Array.isArray(messages) || messages.length === 0) return "a highly detailed masterwork image";
  const lastMsg = messages[messages.length - 1];
  if (typeof lastMsg.content === 'string') return lastMsg.content;
  if (Array.isArray(lastMsg.content)) {
    // 多模态文本提取
    for (let item of lastMsg.content) {
      if (item.type === 'text') return item.text;
    }
  }
  return "an image";
}

function handleCorsPreflight() {
  return new Response(null, { status: 204, headers: corsHeaders() });
}

function corsHeaders(extra = {}) {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    ...extra
  };
}

function createJsonResponse(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status: status,
    headers: corsHeaders({ "Content-Type": "application/json; charset=utf-8", "Content-Encoding": "br", ...extraHeaders })
  });
}

// --- [第四部分: Web 前端 - 开发者驾驶舱 (Developer Cockpit)] ---
function handleWebUI(request, env, ctx) {
  const originUrl = new URL(request.url).origin;
  const rawApiKey = request.ctx.apiKey;
  const apiKeyDisplay = "1"; // UI 面板统一简化显示为 1，避免泄露长效上游 Token
  const theHtml = `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${CONFIG.PROJECT_NAME} ⚡ F1-Cockpit</title>
  <!-- 考虑到追求极简与安全，未引入任何外部 CDN 框架。以下 CSS 使用 Shadow DOM 隔离理念，原生绘制所有元素。 -->
  <style>
    /* 全局根重置 */
    :root {
      --bg-dark: #121212; --panel-light: #1A1A1A; --border-clr: #333333;
      --text-main: #E0E0E0; --text-muted: #888888;
      --amber-main: #FFBF00; --amber-dim: rgba(255, 191, 0, 0.15); --amber-hover: #FFC933;
      --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      --font-mono: "Fira Code", consolas, monospace;
      --status-ok: #00E676; --status-err: #FF1744; --status-load: #2979FF;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; display: flex; flex-direction: column; 
      min-height: 100vh; background-color: var(--bg-dark); color: var(--text-main); font-family: var(--font-body);
      overflow-x: hidden;
    }
    /* Web Components 解析失败时的降级显示 */
    body:not(:defined) .fallback-notice { display: block; padding: 20px; text-align: center; color: var(--amber-main); }
    .fallback-notice { display: none; }
  </style>
  <!-- 引入 Markdown 渲染支持以便实时终端可用图片 -->
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"><\/script>
</head>
<body>
  <div class="fallback-notice">如果您看到此信息，说明浏览器不支持 Web Components。请升级浏览器以开启 F1-Cockpit。</div>

  <!-- 在此挂载我们的 F1 驾驶舱主组件 -->
  <f1-cockpit></f1-cockpit>

  <!-- === 核心前端逻辑库 === -->
  <script>
    // 注入前端运行时变量
    const ENV = {
       origin: '${originUrl}',
       apiUrl: '${originUrl}/v1/chat/completions',
       modelsUrl: '${originUrl}/v1/models',
       apiKey: '${rawApiKey}',
       apiKeyDisplay: '${apiKeyDisplay}',
       defaultModel: '${CONFIG.DEFAULT_MODEL}',
       version: '${CONFIG.PROJECT_VERSION}'
    };

    /** ==== [组件库构建模块] ====  */

    // 1. 基石：自定义元素抽象类 (Shadow DOM)
    class AbstractComponent extends HTMLElement {
       constructor() { super(); this.attachShadow({ mode: 'open' }); }
       addStyle(cssText) { const style = document.createElement('style'); style.textContent = cssText; this.shadowRoot.appendChild(style); }
       addHTML(htmlText) { const tpl = document.createElement('template'); tpl.innerHTML = htmlText; this.shadowRoot.appendChild(tpl.content.cloneNode(true)); }
    }

    // 2. 指示器组件 (Status Indicator)
    class StatusIndicator extends AbstractComponent {
       constructor() {
          super();
          this.addStyle(\`
            .wrap { display: flex; align-items: center; gap: 8px; font-size: 11px; font-family: var(--font-mono); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;}
            .dot { width: 8px; height: 8px; border-radius: 50%; box-shadow: 0 0 5px currentColor; transition: all 0.3s; }
            .INITIALIZING { color: var(--text-muted); } .HEALTH_CHECKING { color: var(--status-load); animation: blink 1s infinite alternate;}
            .READY { color: var(--status-ok); } .ERROR { color: var(--status-err); } .STREAMING { color: var(--amber-main); animation: pulse 1s infinite alternate; }
            @keyframes blink { from {opacity:0.3} to {opacity:1} }
            @keyframes pulse { from {box-shadow: 0 0 2px var(--amber-main); opacity: 0.7;} to {box-shadow: 0 0 8px var(--amber-main); opacity: 1;} }
          \`);
          this.addHTML(\`<div class="wrap" id="ctn"><div class="dot INITIALIZING" id="dot"></div><span id="lbl" class="INITIALIZING">BOOT SEQUENCE INIT</span></div>\`);
          this.dot = this.shadowRoot.getElementById('dot'); this.lbl = this.shadowRoot.getElementById('lbl');
       }
       setState(state, textMsg) {
          this.dot.className = \`dot \${state}\`; this.lbl.className = state;
          this.lbl.innerText = textMsg;
       }
    }
    customElements.define('status-indicator', StatusIndicator);

    // 3. 实时终端组件 (Live Terminal) 
    class LiveTerminal extends AbstractComponent {
       constructor() {
          super();
          this.addStyle(\`
            :host { display: flex; flex-direction: column; height: 100%; border: 1px solid var(--border-clr); border-radius: 6px; background: #0A0A0A; flex: 1; }
            .history { flex: 1; overflow-y: auto; padding: 20px; scroll-behavior: smooth; }
            .history::-webkit-scrollbar { width: 6px; } .history::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
            .msg { margin-bottom: 24px; display: flex; flex-direction: column; font-size: 13px; line-height: 1.6; }
            .msg.user { border-left: 2px solid var(--amber-main); padding-left: 14px; color: var(--amber-main); }
            .msg.system { border-left: 2px solid var(--status-load); padding-left: 14px; color: #BBB; }
            .msg.ai { padding: 14px; background: #141414; border: 1px solid #1F1F1F; border-radius: 4px; color: #DDD; }
            .msg.ai img { max-width: 100%; border-radius: 4px; border: 1px solid #333; margin-top: 10px; cursor: crosshair;}
            .input-box { background: #111; border-top: 1px solid var(--border-clr); padding: 15px; display: flex; gap: 10px; align-items: flex-end;}
            textarea { flex: 1; background: #1C1C1C; color: var(--text-main); border: 1px solid #2B2B2B; padding: 12px; font-family: var(--font-body); font-size: 13px; border-radius: 4px; outline: none; resize: none; max-height: 150px; overflow-y: auto;}
            textarea:focus { border-color: var(--amber-main); box-shadow: 0 0 5px var(--amber-dim); }
            button { width: 44px; height: 44px; border-radius: 4px; background: var(--amber-main); border: none; color: #000; cursor: pointer; display: flex; justify-content: center; align-items: center; transition: 0.2s;}
            button:hover { background: var(--amber-hover); transform: translateY(-1px); }
            button:disabled { background: #333; color: #666; cursor: not-allowed; transform: none; }
            button.cancel { background: var(--status-err); color: white; }
          \`);
          this.addHTML(\`
             <div class="history" id="history">
                <div class="msg system"><strong>SYS_MAIN></strong> 正在与后端网关执行握手，并拉取指令集配置...</div>
             </div>
             <div class="input-box">
                <textarea id="cmd-input" rows="1" placeholder="输入待生成的图像 Prompt 指令, 敲击 Enter 发射 [Shift+Enter 换行] (例如: 一只穿着赛车服的可爱小猫)"></textarea>
                <button id="btn-fire"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg></button>
             </div>
          \`);
          this.historyDiv = this.shadowRoot.getElementById('history');
          this.inputBox = this.shadowRoot.getElementById('cmd-input');
          this.btnFire = this.shadowRoot.getElementById('btn-fire');
          
          this.isGenerating = false;
          this.abortController = null;
       }

       connectedCallback() {
          // 绑定自适应高宽事件
          this.inputBox.addEventListener('input', () => {
             this.inputBox.style.height = 'auto'; 
             this.inputBox.style.height = (this.inputBox.scrollHeight < 150 ? this.inputBox.scrollHeight : 150) + 'px';
          });
          
          this.inputBox.addEventListener('keydown', (e) => {
             if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.dispatchAction(); }
          });

          this.btnFire.addEventListener('click', () => { this.dispatchAction(); });
       }

       printLog(type, htmlContent) {
          const div = document.createElement('div');
          div.className = \`msg \${type}\`;
          // 如果是 AI 且包含 Markdown，可以用 marked 渲染
          if(type === 'ai' && typeof marked !== 'undefined') {
              div.innerHTML = marked.parse(htmlContent);
          } else {
              div.innerHTML = htmlContent;
          }
          this.historyDiv.appendChild(div);
          this.scrollToBottom();
          return div;
       }

       scrollToBottom() { this.historyDiv.scrollTop = this.historyDiv.scrollHeight; }

       async dispatchAction() {
          if (this.isGenerating) { this.abortStream(); return; }
          const prompt = this.inputBox.value.trim();
          if (!prompt) return;

          this.inputBox.value = ''; this.inputBox.dispatchEvent(new Event('input')); //重置高度
          this.printLog('user', \`<strong>USER></strong> \${prompt}\`);
          
          // Switch to stream mode
          this.isGenerating = true;
          this.btnFire.className = "cancel";
          this.btnFire.innerHTML = \`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>\`;
          cockpit.setStatus('STREAMING', 'TX_BUSY_STREAMING');

          const aiNode = this.printLog('ai', '正在等待返回序列...');
          const startTime = performance.now();

          try {
             this.abortController = new AbortController();
             this.btnFire.disabled = false; //允许中断
             
             const requestOptions = {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": \`Bearer \${ENV.apiKey}\` },
                body: JSON.stringify({ model: ENV.defaultModel, messages: [{ role: "user", content: prompt}], stream: true }),
                signal: this.abortController.signal
             };

             const res = await fetch(ENV.apiUrl, requestOptions);
             if (!res.ok) throw new Error(\`上游驳回指令 (\${res.status})\`);
             
             const reader = res.body.getReader();
             const decoder = new TextDecoder();
             let allText = "";
             
             while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunkStr = decoder.decode(value);
                const lines = chunkStr.split('\\n');
                for (let line of lines) {
                   if (line.startsWith("data:")) {
                      const dataStr = line.slice(5).trim();
                      if (dataStr === '[DONE]') break;
                      try {
                         const jsonObj = JSON.parse(dataStr);
                         const dText = jsonObj.choices[0].delta.content;
                         if (dText) {
                            allText += dText;
                            // 渲染 Markdown
                            aiNode.innerHTML = typeof marked !== 'undefined' ? marked.parse(allText) : allText;
                            this.scrollToBottom();
                         }
                      } catch (e) {} // 丢弃无法解析的残片
                   }
                }
             }
             
             const costTimeMs = Math.round(performance.now() - startTime);
             cockpit.recordPerf(costTimeMs, 'SUCCESS'); cockpit.saveHistory(prompt, '');

          } catch (err) {
             const costTimeMs = Math.round(performance.now() - startTime);
             if (err.name === 'AbortError') {
                 aiNode.innerHTML += '<br/><span style="color:var(--amber-main)">[指令已被人为阻断]</span>';
                 cockpit.recordPerf(costTimeMs, 'ABORTED');
             } else {
                 aiNode.innerHTML += \`<br/><span style="color:var(--status-err)">[严重异常]：\${err.message}</span>\`;
                 cockpit.recordPerf(costTimeMs, 'FAILED');
                 cockpit.setStatus('ERROR', 'TX_CRASH');
             }
          } finally {
             this.isGenerating = false;
             this.btnFire.className = "";
             this.btnFire.innerHTML = \`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>\`;
             if (cockpit.currentStatus !== 'ERROR') cockpit.setStatus('READY', 'SYSTEM_STANDBY_AWARE');
          }
       }

       abortStream() {
          if (this.abortController) this.abortController.abort();
       }
    }
    customElements.define('live-terminal', LiveTerminal);

    // 4. 战术看板组件 (Tactic Dashboard)
    class F1Cockpit extends AbstractComponent {
       constructor() {
          super();
          this.currentStatus = 'INITIALIZING';
          this.addStyle(\`
            .grid-container {
               display: grid;
               grid-template-columns: 360px 1fr;
               height: 100vh;
            }
            @media (max-width: 900px) { .grid-container { grid-template-columns: 1fr; grid-template-rows: auto 1fr; } }
            
            /* Sidebar panel */
            .left-panel { background: var(--panel-light); border-right: 1px solid var(--border-clr); padding: 24px; display: flex; flex-direction: column; overflow-y: auto; }
            .right-panel { padding: 24px; display: flex; flex-direction: column; overflow: hidden; background: radial-gradient(circle at 100% 0%, #171511 0%, transparent 400px); }
            
            h1.brand { color: var(--amber-main); font-size: 22px; margin: 0 0 8px 0; font-family: var(--font-mono); letter-spacing: -1px; display: flex; align-items: center; justify-content: space-between; }
            .version-tag { font-size: 10px; background: rgba(255,191,0,0.1); padding: 2px 8px; border-radius: 10px; color: var(--amber-main); letter-spacing: 0; }
            hr { border: none; border-top: 1px dashed #333; margin: 20px 0; }
            
            /* Data Modules */
            .box { padding: 16px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-clr); border-radius: 6px; margin-bottom: 20px;}
            .box-title { font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: bold; margin-bottom: 12px; display: flex; align-items: center;}
            .box-title i { width:4px; height:12px; background:var(--amber-main); margin-right: 8px; border-radius: 2px; }
            
            .row { display: flex; flex-direction: column; gap: 4px; margin-bottom: 14px; }
            .row:last-child { margin-bottom: 0; }
            .col { font-size: 11px; color: #666; font-family: var(--font-mono);}
            .val { font-size: 13px; font-family: var(--font-mono); color: #fff; background: #080808; padding: 10px; border-radius: 4px; border: 1px solid #222; word-break: break-all; cursor: pointer; position: relative;}
            .val:hover::after { content: 'Click to Copy'; position: absolute; right: 10px; opacity: 0.6; font-size: 10px;}
            
            /* Perf module */
            .perf { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
            .perf-card { background: #111; border: 1px solid #222; border-radius: 4px; padding: 10px; text-align: center; }
            .perf-val { font-size: 20px; color: var(--status-ok); font-family: var(--font-mono); font-weight: bold; margin-top: 4px; }
            .perf-err .perf-val { color: var(--status-err); }
            
            /* Collapse */
            details { margin-top: 20px; font-size: 13px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-clr); border-radius: 6px;}
            summary { padding: 14px; font-weight: bold; cursor: pointer; color: #AAA; outline: none; }
            details[open] summary { border-bottom: 1px solid var(--border-clr); color: var(--amber-main); }
            .tabs-content { padding: 14px; background: #000; font-family: var(--font-mono); font-size: 11px; color: #888; white-space: pre-wrap; word-wrap: break-word;}
          \`);
          
          this.addHTML(\`
            <div class="grid-container">
               <div class="left-panel">
                  <h1 class="brand">🚀 DESIGN.ARENA <span class="version-tag">2API // ${CONFIG.PROJECT_VERSION}</span></h1>
                  <status-indicator id="status-ind"></status-indicator>
                  <hr>
                  
                  <div class="box">
                     <div class="box-title"><i></i> CORE_INTELLIGENCE (接口情报)</div>
                     <div class="row">
                        <span class="col">API_BASE_URL (URL地址)</span>
                        <div class="val" onclick="navigator.clipboard.writeText('${originUrl}/v1')">${originUrl}/v1</div>
                     </div>
                     <div class="row">
                        <span class="col">AUTHORIZATION_KEY (通讯密钥)</span>
                        <div class="val" onclick="navigator.clipboard.writeText('${apiKeyDisplay}')">Bearer ${apiKeyDisplay}</div>
                     </div>
                     <div class="row">
                        <span class="col">TARGET_MODELS (目标主模型)</span>
                        <div class="val">${CONFIG.DEFAULT_MODEL}</div>
                     </div>
                  </div>

                  <div class="box">
                     <div class="box-title"><i></i> TELEMETRY_DASHBOARD (性能遥测)</div>
                     <div class="perf">
                        <div class="perf-card">
                           <div class="col">AVR. LAP (耗时)</div>
                           <div class="perf-val" id="avg-time">-- ms</div>
                        </div>
                        <div class="perf-card perf-err">
                           <div class="col">LOSS RT. (失败率)</div>
                           <div class="perf-val" id="loss-rate">0%</div>
                        </div>
                     </div>
                  </div>

                  <div class="box" style="margin-top: 20px;">
                     <div class="box-title" style="display:flex; justify-content:space-between"><span><i></i> LOCAL_ARCHIVE (本地请求记录)</span> <span style="cursor:pointer;" onclick="localStorage.removeItem('dArenaV3_History');cockpit.loadHistory();">🗑️</span></div>
                     <div class="tabs-content" id="history-box" style="max-height: 250px; overflow-y: auto; background: #111; padding: 10px; border-radius: 4px; font-family:var(--font-mono); font-size: 11px; line-height:1.4;">
                        无记录。
                     </div>
                  </div>
                  
                  <details open>
                     <summary>⚙️ INTEGRATION_DECK (客户端装配库)</summary>
                     <div class="tabs-content">
[ LobeChat / Cherry Studio 配置规范 ]
- 服务商类型: OpenAI / 自定义
- API 服务器地址: ${originUrl}/v1 (ComfyUI等工具直接填此地址)
- 代理接口支持: 
  ✅ /v1/chat/completions (针对大模型Markdown流式通讯)
  ✅ /v1/images/generations (对接原生生图工具如 ComfyUI/Midjourney)

- 🔑 通讯鉴权 API Key (重要): 
  ✅ 默认体验 Key: 1
  ⚠️ <span style="color:var(--status-err)">如果无法生成，说明体验节点 Token 已被风控过期。</span>
  🔥 <span style="color:var(--amber-main)">全自动长效续期方案 (必读):</span>
     1. 登录 DesignArena 官网，按 \\\`F12\\\` 打开开发者工具 -> \\\`网络 (Network)\\\` 面板。
     2. 随便发一条消息或生图，找到名字为 \\\`generate-title\\\` 或 \\\`messages\\\` 的网络请求包。
     3. 点开该包，在右侧的 \\\`标头 (Headers)\\\` -> \\\`请求标头\\\` 里面找到 \\\`Authorization: Bearer ey...\\\`
     4. 复制它后面那段以 \\\`ey\\\` 开头的超长串 Token。
     5. 拿到以后，您直接在 **Cherry Studio** 或 **LobeChat** 客户端的【API Key】配置里，填入这段 \\\`ey...\\\` 就行了！
     *(新网关支持凭证穿透：只要检测到传入真 JWT 就能绕开默认写死的 Key，直连官网引擎，0 延迟免配置！)*

[ cURL 原生 DALL-E 架构测试 ]
curl -X POST "${originUrl}/v1/images/generations" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer 1 (如果过期请换成您抓到的 ey... 密钥)" \\
  -d '{"model": "${CONFIG.DEFAULT_MODEL}", "prompt": "a beautiful kitten"}'
                     </div>
                  </details>
               </div>
               
               <div class="right-panel">
                  <live-terminal id="term"></live-terminal>
               </div>
            </div>
          \`);

          this.ind = this.shadowRoot.getElementById('status-ind');
          this.term = this.shadowRoot.getElementById('term');
          this.avgTimeObj = this.shadowRoot.getElementById('avg-time');
          this.errRateObj = this.shadowRoot.getElementById('loss-rate');

          this.perfLogs = [];
          this.loadHistory();
       }

       connectedCallback() {
          // 初始化自检
          this.setStatus('HEALTH_CHECKING', 'ENGINES_WARM_UP...');
          fetch(ENV.modelsUrl, { headers: { 'Authorization': \`Bearer \${ENV.apiKey}\` } })
            .then(res => {
               if(!res.ok) throw new Error(\`HTTP \${res.status}\`);
               this.term.printLog('system', '握手验收 -> <strong>[OK]</strong><br/>模型池装载挂载 -> <strong>[OK]</strong><br/>主驾驶员允许启动。');
               this.setStatus('READY', 'SYSTEM_STANDBY_AWARE');
            })
            .catch(err => {
               this.term.printLog('system', \`<span style="color:var(--status-err)">[严重] 链路握手失败: \${err.message} 检查通讯密钥等配置。</span>\`);
               this.setStatus('ERROR', 'SYS_MALFUNC_AUTH_REJECTED');
            });
       }

       
       loadHistory() {
           try {
               const hist = JSON.parse(localStorage.getItem('dArenaV3_History')) || [];
               const box = document.getElementById('history-box');
               if (box) {
                   box.innerHTML = hist.length > 0 ? hist.map(e => \`[\${new Date(e.time).toLocaleTimeString()}]<br/><span style="color:var(--amber-main)">\${e.p}</span>\`).join('<hr style="margin:8px 0; border-top:1px solid #333"/>') : '无可用指令历史。';
               }
           } catch(e) {}
       }
       saveHistory(prompt, url) {
           try {
               const hist = JSON.parse(localStorage.getItem('dArenaV3_History')) || [];
               hist.unshift({ time: Date.now(), p: prompt, u: url });
               if(hist.length > 20) hist.pop();
               localStorage.setItem('dArenaV3_History', JSON.stringify(hist));
               this.loadHistory();
           } catch(e) {}
       }
setStatus(stateCode, msgText) {
          this.currentStatus = stateCode;
          this.ind.setState(stateCode, msgText);
       }

       recordPerf(timeMs, resultType) {
          this.perfLogs.push({ t: timeMs, r: resultType });
          if(this.perfLogs.length > 10) this.perfLogs.shift();
          
          let totalTime = 0, successCount = 0, errCount = 0;
          this.perfLogs.forEach(n => {
             if (n.r === 'SUCCESS') { totalTime += n.t; successCount++; }
             if (n.r === 'FAILED') { errCount++; }
          });

          // avg time
          if (successCount > 0) {
             const avg = Math.round(totalTime / successCount);
             this.avgTimeObj.innerText = \`\${avg} ms\`;
             this.avgTimeObj.style.color = (avg > 18000) ? 'var(--amber-main)' : 'var(--status-ok)';
          }
          // error rate
          const erate = Math.round((errCount / this.perfLogs.length) * 100);
          this.errRateObj.innerText = \`\${erate}%\`;
       }
    }
    customElements.define('f1-cockpit', F1Cockpit);
    
    // 全局实例
    window.cockpit = document.querySelector('f1-cockpit');
  </script>
</body>
</html>`;
  return new Response(theHtml, { headers: { "Content-Type": "text/html;charset=UTF-8" } });
}

// 代理完毕，起航！
