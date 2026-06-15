const INTENT_TYPES = {
  ads: "广告位出租",
  development: "项目开发合作",
  token_supply: "AI 中转站 Token 批发供应",
  other: "其他",
};

const STATUSES = new Set(["new", "contacted", "closed"]);
const RATE_WINDOW_SECONDS = 60;
const RATE_MAX = 3;

export default {
  fetch(request, env) {
    return handleRequest(request, env);
  },
};

export async function handleRequest(request, env) {
  const url = new URL(request.url);

  if (request.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders(request, env) });
  }

  const sourceMatch = url.pathname.match(/^\/api\/sources\/([^/]+)\/intents$/);
  if (sourceMatch && request.method === "POST") {
    return submitIntent(request, env, decodeURIComponent(sourceMatch[1]));
  }

  if (url.pathname === "/admin" && request.method === "GET") {
    return html(adminPage());
  }

  if (url.pathname === "/api/admin/login" && request.method === "POST") {
    return adminLogin(request, env);
  }

  if (url.pathname === "/api/admin/intents" && request.method === "GET") {
    const auth = requireAdmin(request, env);
    if (auth) return auth;
    return listIntents(request, env);
  }

  const intentStatusMatch = url.pathname.match(/^\/api\/admin\/intents\/([^/]+)$/);
  if (intentStatusMatch && request.method === "PATCH") {
    const auth = requireAdmin(request, env);
    if (auth) return auth;
    return updateIntentStatus(request, env, decodeURIComponent(intentStatusMatch[1]));
  }

  return json({ success: false, message: "Not found" }, 404, request, env);
}

async function submitIntent(request, env, sourceId) {
  let raw;
  try {
    raw = await request.json();
  } catch {
    return json({ success: false, message: "请求格式无效" }, 400, request, env);
  }

  let intent;
  try {
    intent = normalizeIntent(raw, sourceId);
  } catch (error) {
    return json({ success: false, message: error.message }, 400, request, env);
  }

  const clientKey = await clientFingerprint(request, env, intent.source_id);
  const since = new Date(Date.now() - RATE_WINDOW_SECONDS * 1000).toISOString();
  const recent = await env.DB.prepare(
    "SELECT COUNT(*) AS count FROM intents WHERE client_key = ? AND created_at >= ?"
  ).bind(clientKey, since).first();
  if ((recent?.count || 0) >= RATE_MAX) {
    return json({ success: false, message: "提交太频繁，请稍后再试" }, 429, request, env);
  }

  const now = new Date().toISOString();
  const id = crypto.randomUUID();
  await env.DB.prepare(
    `INSERT INTO intents (
      id, created_at, updated_at, source_id, source_name, source_version,
      intent_type, intent_type_label, name, contact, message, status, client_key, user_agent
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  ).bind(
    id,
    now,
    now,
    intent.source_id,
    intent.source_name,
    intent.source_version,
    intent.intent_type,
    intent.intent_type_label,
    intent.name,
    intent.contact,
    intent.message,
    "new",
    clientKey,
    request.headers.get("user-agent") || ""
  ).run();

  let notified = false;
  try {
    notified = await notifyTelegram(env, buildTelegramText({ id, created_at: now, ...intent }));
  } catch (error) {
    console.warn("Telegram notification failed", error);
  }

  return json({ success: true, message: "已提交，我会尽快联系你。", id, notified }, 200, request, env);
}

export function normalizeIntent(raw, sourceId) {
  const source_id = clean(sourceId, 80);
  const source_name = clean(raw.source_name || source_id, 120);
  const source_version = clean(raw.source_version || "", 40);
  const intent_type = clean(raw.intent_type, 40);
  const intent_type_label = clean(raw.intent_type_label || INTENT_TYPES[intent_type] || intent_type, 80);
  const name = clean(raw.name, 80);
  const contact = clean(raw.contact, 120);
  const message = clean(raw.message, 1000);

  if (!source_id) throw new Error("来源不能为空");
  if (!INTENT_TYPES[intent_type]) throw new Error("合作类型无效");
  if (!name) throw new Error("称呼不能为空");
  if (!contact) throw new Error("联系方式不能为空");
  if (message.length < 5) throw new Error("合作需求不能少于 5 个字符");

  return {
    source_id,
    source_name,
    source_version,
    intent_type,
    intent_type_label,
    name,
    contact,
    message,
  };
}

function clean(value, limit) {
  return String(value || "").trim().slice(0, limit);
}

async function clientFingerprint(request, env, sourceId) {
  const ip = request.headers.get("cf-connecting-ip") || request.headers.get("x-forwarded-for") || "unknown";
  const salt = env.IP_HASH_SALT || env.ADMIN_TOKEN || "muggle-leads";
  return sha256(`${salt}:${sourceId}:${ip}`);
}

async function sha256(input) {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function buildTelegramText(intent) {
  return [
    "新的合作意向",
    `来源: ${intent.source_name} (${intent.source_id})`,
    intent.source_version ? `版本: ${intent.source_version}` : "",
    `类型: ${intent.intent_type_label}`,
    `称呼: ${intent.name}`,
    `联系方式: ${intent.contact}`,
    `时间: ${intent.created_at}`,
    "",
    "合作需求:",
    intent.message,
  ].filter(Boolean).join("\n");
}

async function notifyTelegram(env, text) {
  if (!env.TG_BOT_TOKEN || !env.TG_CHAT_ID) {
    return false;
  }

  const response = await fetch(`https://api.telegram.org/bot${env.TG_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: env.TG_CHAT_ID,
      text,
      disable_web_page_preview: true,
    }),
  });
  if (!response.ok) return false;
  const data = await response.json().catch(() => ({}));
  return data.ok === true;
}

async function listIntents(request, env) {
  const url = new URL(request.url);
  const where = [];
  const params = [];
  const source = clean(url.searchParams.get("source") || "", 80);
  const status = clean(url.searchParams.get("status") || "", 30);
  const q = clean(url.searchParams.get("q") || "", 120);
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit") || 50), 1), 100);

  if (source) {
    where.push("source_id = ?");
    params.push(source);
  }
  if (status && STATUSES.has(status)) {
    where.push("status = ?");
    params.push(status);
  }
  if (q) {
    where.push("(name LIKE ? OR contact LIKE ? OR message LIKE ? OR source_name LIKE ?)");
    params.push(...Array(4).fill(`%${q}%`));
  }

  const sql = `
    SELECT id, created_at, updated_at, source_id, source_name, source_version,
      intent_type, intent_type_label, name, contact, message, status
    FROM intents
    ${where.length ? `WHERE ${where.join(" AND ")}` : ""}
    ORDER BY created_at DESC
    LIMIT ?
  `;
  params.push(limit);
  const result = await env.DB.prepare(sql).bind(...params).all();
  return json({ success: true, items: result.results || [] });
}

async function updateIntentStatus(request, env, id) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ success: false, message: "请求格式无效" }, 400);
  }

  const status = clean(body.status, 30);
  if (!STATUSES.has(status)) {
    return json({ success: false, message: "状态无效" }, 400);
  }

  await env.DB.prepare("UPDATE intents SET status = ?, updated_at = ? WHERE id = ?")
    .bind(status, new Date().toISOString(), id)
    .run();
  return json({ success: true });
}

async function adminLogin(request, env) {
  if (!env.ADMIN_TOKEN) {
    return json({ success: false, message: "ADMIN_TOKEN 未配置" }, 503);
  }

  const body = await request.json().catch(() => ({}));
  if (body.token !== env.ADMIN_TOKEN) {
    return json({ success: false, message: "登录失败" }, 401);
  }

  return json({ success: true }, 200, request, env, {
    "set-cookie": `ml_admin=${encodeURIComponent(env.ADMIN_TOKEN)}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=604800`,
  });
}

function requireAdmin(request, env) {
  if (!env.ADMIN_TOKEN) {
    return json({ success: false, message: "ADMIN_TOKEN 未配置" }, 503);
  }

  const auth = request.headers.get("authorization") || "";
  if (auth === `Bearer ${env.ADMIN_TOKEN}`) {
    return null;
  }

  const cookie = request.headers.get("cookie") || "";
  if (cookie.split(";").some((item) => item.trim() === `ml_admin=${encodeURIComponent(env.ADMIN_TOKEN)}`)) {
    return null;
  }

  return json({ success: false, message: "未登录" }, 401);
}

function json(data, status = 200, request, env, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...corsHeaders(request, env),
      ...extraHeaders,
    },
  });
}

function html(body) {
  return new Response(body, {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "content-security-policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'",
    },
  });
}

function corsHeaders(request, env) {
  if (!request) return {};
  const origin = request.headers.get("origin") || "*";
  const configured = (env?.ALLOWED_ORIGINS || "*").split(",").map((item) => item.trim()).filter(Boolean);
  const allowOrigin = configured.includes("*") || configured.includes(origin) ? origin : configured[0] || "*";
  return {
    "access-control-allow-origin": allowOrigin,
    "access-control-allow-methods": "GET,POST,PATCH,OPTIONS",
    "access-control-allow-headers": "content-type,authorization",
  };
}

function adminPage() {
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>麻瓜合作台</title>
  <style>
    body{margin:0;background:#111;color:#f4f4f4;font:14px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    main{max-width:1120px;margin:0 auto;padding:28px}
    h1{font-size:24px;margin:0 0 18px}
    .bar,.login{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}
    input,select,button{background:#1f1f1f;color:#fff;border:1px solid #333;border-radius:8px;padding:9px 10px}
    button{cursor:pointer}
    button:hover{border-color:#777}
    table{width:100%;border-collapse:collapse;background:#181818;border:1px solid #2a2a2a;border-radius:12px;overflow:hidden}
    th,td{text-align:left;vertical-align:top;border-bottom:1px solid #2a2a2a;padding:10px}
    th{color:#aaa;font-weight:500;background:#151515}
    .muted{color:#888}.msg{white-space:pre-wrap;max-width:360px}.hidden{display:none}
  </style>
</head>
<body>
  <main>
    <h1>麻瓜合作台</h1>
    <section id="login" class="login">
      <input id="token" type="password" placeholder="管理 Token" />
      <button id="loginBtn">登录</button>
      <span id="loginMsg" class="muted"></span>
    </section>
    <section id="app" class="hidden">
      <div class="bar">
        <input id="source" placeholder="来源" />
        <select id="status">
          <option value="">全部状态</option>
          <option value="new">未处理</option>
          <option value="contacted">已联系</option>
          <option value="closed">已关闭</option>
        </select>
        <input id="q" placeholder="关键词搜索" />
        <button id="refresh">刷新</button>
      </div>
      <table>
        <thead><tr><th>时间</th><th>来源</th><th>类型</th><th>联系人</th><th>需求</th><th>状态</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </section>
  </main>
  <script>
    const login = document.querySelector("#login");
    const app = document.querySelector("#app");
    const rows = document.querySelector("#rows");
    document.querySelector("#loginBtn").onclick = async () => {
      const token = document.querySelector("#token").value;
      const res = await fetch("/api/admin/login", { method:"POST", headers:{ "content-type":"application/json" }, body: JSON.stringify({ token }) });
      if (!res.ok) { document.querySelector("#loginMsg").textContent = "登录失败"; return; }
      login.classList.add("hidden"); app.classList.remove("hidden"); load();
    };
    document.querySelector("#refresh").onclick = load;
    async function load() {
      const params = new URLSearchParams();
      for (const id of ["source","status","q"]) {
        const value = document.querySelector("#" + id).value.trim();
        if (value) params.set(id, value);
      }
      const res = await fetch("/api/admin/intents?" + params.toString());
      if (res.status === 401) { login.classList.remove("hidden"); app.classList.add("hidden"); return; }
      const data = await res.json();
      rows.replaceChildren(...(data.items || []).map(renderRow));
    }
    function renderRow(item) {
      const tr = document.createElement("tr");
      const cells = [
        item.created_at,
        item.source_name + "\\n" + item.source_id + (item.source_version ? " @" + item.source_version : ""),
        item.intent_type_label,
        item.name + "\\n" + item.contact,
        item.message,
      ];
      for (const text of cells) {
        const td = document.createElement("td");
        td.className = text === item.message ? "msg" : "";
        td.textContent = text;
        tr.appendChild(td);
      }
      const status = document.createElement("select");
      for (const [value,label] of [["new","未处理"],["contacted","已联系"],["closed","已关闭"]]) {
        const option = document.createElement("option");
        option.value = value; option.textContent = label; option.selected = item.status === value;
        status.appendChild(option);
      }
      status.onchange = () => fetch("/api/admin/intents/" + encodeURIComponent(item.id), {
        method:"PATCH", headers:{ "content-type":"application/json" }, body: JSON.stringify({ status: status.value })
      });
      const td = document.createElement("td");
      td.appendChild(status);
      tr.appendChild(td);
      return tr;
    }
  </script>
</body>
</html>`;
}
