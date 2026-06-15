# Muggle Leads / 麻瓜合作台

统一收集多个本地工具的合作意向，保存到 Cloudflare D1，并通知到 Telegram。

## 功能

- `POST /api/sources/:source_id/intents`：接收合作意向。
- `GET /admin`：查看后台。
- `GET /api/admin/intents`：按来源、状态、关键词筛选。
- `PATCH /api/admin/intents/:id`：更新状态。

后台文案统一使用“来源”，不使用“项目”。

## 官方线上地址

- 管理后台：`https://leads.3jiezhiwai.com/admin`
- Codex Session Patcher 提交接口：`https://leads.3jiezhiwai.com/api/sources/codex-session-patcher/intents`

## 数据字段

```json
{
  "source_id": "codex-session-patcher",
  "source_name": "Codex Session Patcher",
  "source_version": "1.4.5",
  "intent_type": "ads",
  "intent_type_label": "广告位出租",
  "name": "张三",
  "contact": "微信 xxx",
  "message": "想咨询广告位"
}
```

## 部署

1. 创建 D1 数据库。

```bash
npx wrangler d1 create muggle-leads-db
```

2. 把返回的 `database_id` 写入 `wrangler.toml`。

3. 执行数据库迁移。

```bash
npm run d1:migrate
```

4. 设置密钥。

```bash
npx wrangler secret put TG_BOT_TOKEN
npx wrangler secret put TG_CHAT_ID
npx wrangler secret put ADMIN_TOKEN
npx wrangler secret put IP_HASH_SALT
```

5. 部署。

```bash
npm run deploy
```

6. 在 fork 项目或开发环境中覆盖远程提交地址。

```bash
export MUGGLE_LEADS_ENDPOINT="https://你的 Worker 域名/api/sources/codex-session-patcher/intents"
```

官方版 Codex Session Patcher 已内置作者自己的线上提交地址，普通用户不需要配置这个环境变量。

## 管理后台

打开：

```text
https://你的 Worker 域名/admin
```

使用 `ADMIN_TOKEN` 登录。后台支持按来源、状态和关键词筛选，并可把意向标记为：

- `new`：未处理
- `contacted`：已联系
- `closed`：已关闭

## 安全说明

- Telegram Bot token 只保存在 Cloudflare Worker secrets，不进入本地工具和前端构建产物。
- 提交接口按来源和 IP 哈希做 60 秒 3 次的简单限频。
- `IP_HASH_SALT` 用于生成不可逆的客户端标识，建议设置。
