import test from "node:test";
import assert from "node:assert/strict";

import { buildTelegramText, handleRequest, normalizeIntent } from "../src/worker.js";

class FakeDB {
  constructor() {
    this.rows = [];
  }

  prepare(sql) {
    return new FakeStmt(this, sql);
  }
}

class FakeStmt {
  constructor(db, sql) {
    this.db = db;
    this.sql = sql;
    this.args = [];
  }

  bind(...args) {
    this.args = args;
    return this;
  }

  async first() {
    if (this.sql.includes("COUNT(*)")) {
      const [clientKey, since] = this.args;
      return {
        count: this.db.rows.filter((row) => row.client_key === clientKey && row.created_at >= since).length,
      };
    }
    return null;
  }

  async run() {
    if (this.sql.includes("INSERT INTO intents")) {
      const [
        id,
        created_at,
        updated_at,
        source_id,
        source_name,
        source_version,
        intent_type,
        intent_type_label,
        name,
        contact,
        message,
        status,
        client_key,
        user_agent,
      ] = this.args;
      this.db.rows.push({
        id,
        created_at,
        updated_at,
        source_id,
        source_name,
        source_version,
        intent_type,
        intent_type_label,
        name,
        contact,
        message,
        status,
        client_key,
        user_agent,
      });
    }
    return { success: true };
  }

  async all() {
    return { results: this.db.rows };
  }
}

test("normalizeIntent uses source terminology", () => {
  const intent = normalizeIntent({
    source_name: "Codex Session Patcher",
    source_version: "1.4.4",
    intent_type: "token_supply",
    name: "张三",
    contact: "tg:@demo",
    message: "想咨询 AI 中转站 Token 批发供应",
  }, "codex-session-patcher");

  assert.equal(intent.source_id, "codex-session-patcher");
  assert.equal(intent.intent_type_label, "AI 中转站 Token 批发供应");
});

test("buildTelegramText includes source fields", () => {
  const text = buildTelegramText({
    source_id: "codex-session-patcher",
    source_name: "Codex Session Patcher",
    source_version: "1.4.4",
    intent_type_label: "广告位出租",
    name: "张三",
    contact: "微信 demo",
    created_at: "2026-06-01T00:00:00.000Z",
    message: "想咨询广告位",
  });

  assert.match(text, /来源: Codex Session Patcher/);
  assert.match(text, /版本: 1.4.4/);
  assert.match(text, /广告位出租/);
});

test("submit intent saves to D1 and returns success", async () => {
  const db = new FakeDB();
  const env = { DB: db, ADMIN_TOKEN: "admin", IP_HASH_SALT: "salt" };
  const request = new Request("https://leads.example/api/sources/codex-session-patcher/intents", {
    method: "POST",
    headers: { "content-type": "application/json", "cf-connecting-ip": "127.0.0.1" },
    body: JSON.stringify({
      source_name: "Codex Session Patcher",
      source_version: "1.4.4",
      intent_type: "ads",
      name: "张三",
      contact: "微信 demo",
      message: "想咨询广告位",
    }),
  });

  const response = await handleRequest(request, env);
  const data = await response.json();

  assert.equal(response.status, 200);
  assert.equal(data.success, true);
  assert.equal(db.rows.length, 1);
  assert.equal(db.rows[0].source_id, "codex-session-patcher");
});

test("submit intent is rate limited", async () => {
  const db = new FakeDB();
  const env = { DB: db, ADMIN_TOKEN: "admin", IP_HASH_SALT: "salt" };

  for (let index = 0; index < 4; index += 1) {
    const response = await handleRequest(new Request("https://leads.example/api/sources/demo/intents", {
      method: "POST",
      headers: { "content-type": "application/json", "cf-connecting-ip": "127.0.0.1" },
      body: JSON.stringify({
        source_name: "Demo",
        intent_type: "development",
        name: "张三",
        contact: "qq:89045349",
        message: "需要项目开发合作",
      }),
    }), env);

    if (index < 3) {
      assert.equal(response.status, 200);
    } else {
      assert.equal(response.status, 429);
    }
  }
});
