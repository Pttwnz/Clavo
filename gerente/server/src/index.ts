import fastify from "fastify";
import fastifyStatic from "@fastify/static";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  addDaysIso,
  getDb,
  isoDateInTimeZone,
  type OrderRow,
  type SupplierRow,
  type TaskRow,
} from "./db.js";
import { buildWhatsappDraft, parseTemplateJson } from "./templates.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT || "37893");
const DATABASE_PATH = process.env.DATABASE_PATH || path.join(__dirname, "..", "data", "gerente.db");
const API_KEY = process.env.GERENTE_API_KEY || "";
const CRON_SECRET = process.env.GERENTE_CRON_SECRET || "";
const TZ = process.env.GERENTE_TZ || "Europe/Madrid";
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID || "";

const app = fastify({ logger: true });

function todayIso(): string {
  return isoDateInTimeZone(new Date(), TZ);
}

function weekdayNumberInTimeZone(timeZone: string, when = new Date()): number {
  const short = new Intl.DateTimeFormat("en-US", { timeZone, weekday: "short" }).format(when);
  const map: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  return map[short] ?? 0;
}

function supplierDueToday(s: SupplierRow, today: string): boolean {
  const lines = parseTemplateJson(s.template_json);
  if (lines.length === 0) return false;
  if (s.order_weekday !== null && s.order_weekday !== undefined) {
    return weekdayNumberInTimeZone(TZ, new Date()) === s.order_weekday;
  }
  if (s.order_interval_days && s.order_interval_days > 0) {
    if (!s.last_sent_on) return true;
    const due = addDaysIso(s.last_sent_on, s.order_interval_days);
    return due <= today;
  }
  return false;
}

async function sendTelegram(text: string): Promise<void> {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return;
  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: TELEGRAM_CHAT_ID,
      text,
      parse_mode: "HTML",
      disable_web_page_preview: true,
    }),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`telegram: ${res.status} ${t}`);
  }
}

function getDbOrThrow() {
  return getDb(DATABASE_PATH);
}

if (!API_KEY) {
  app.log.warn("GERENTE_API_KEY vacío: la API quedará abierta (solo para desarrollo local).");
}

app.register(async (api) => {
  api.addHook("preHandler", async (request, reply) => {
    if (!API_KEY) return;
    const path = request.url.split("?")[0];
    if (request.method === "GET" && path === "/api/health") return;
    const h = request.headers.authorization;
    const key =
      (typeof h === "string" && h.startsWith("Bearer ") ? h.slice(7) : null) ||
      (typeof request.headers["x-api-key"] === "string" ? request.headers["x-api-key"] : null);
    if (!key || key !== API_KEY) {
      return reply.code(401).send({ error: "unauthorized" });
    }
  });

  api.get("/health", async () => ({ ok: true }));

  api.get("/today", async () => {
    const db = getDbOrThrow();
    const today = todayIso();
    const suppliers = db.prepare("SELECT * FROM suppliers ORDER BY name ASC").all() as SupplierRow[];
    const dueSuppliers = suppliers.filter((s) => supplierDueToday(s, today));

    const openOrders = db
      .prepare(
        `SELECT o.*, s.name AS supplier_name FROM orders o
         JOIN suppliers s ON s.id = o.supplier_id
         WHERE o.status IN ('draft','sent')
         ORDER BY o.created_at DESC`
      )
      .all() as (OrderRow & { supplier_name: string })[];

    const tasksDue = db
      .prepare(
        `SELECT * FROM tasks
         WHERE next_due_on IS NOT NULL AND next_due_on <= ?
         ORDER BY next_due_on ASC`
      )
      .all(today) as TaskRow[];

    return {
      today,
      timeZone: TZ,
      dueSuppliers,
      openOrders,
      tasksDue,
    };
  });

  api.get("/suppliers", async () => {
    const db = getDbOrThrow();
    return db.prepare("SELECT * FROM suppliers ORDER BY name ASC").all() as SupplierRow[];
  });

  api.post<{ Body: Record<string, unknown> }>("/suppliers", async (request, reply) => {
    const db = getDbOrThrow();
    const b = request.body || {};
    const name = String(b.name || "").trim();
    if (!name) return reply.code(400).send({ error: "name required" });
    const template_json = JSON.stringify(parseTemplateJson(typeof b.template_json === "string" ? b.template_json : "[]"));
    const stmt = db.prepare(
      `INSERT INTO suppliers (name, whatsapp_phone, notes, order_weekday, order_interval_days, last_sent_on, template_json)
       VALUES (@name, @whatsapp_phone, @notes, @order_weekday, @order_interval_days, @last_sent_on, @template_json)`
    );
    const info = stmt.run({
      name,
      whatsapp_phone: b.whatsapp_phone != null ? String(b.whatsapp_phone) : null,
      notes: b.notes != null ? String(b.notes) : null,
      order_weekday: b.order_weekday != null ? Number(b.order_weekday) : null,
      order_interval_days: b.order_interval_days != null ? Number(b.order_interval_days) : null,
      last_sent_on: b.last_sent_on != null ? String(b.last_sent_on) : null,
      template_json,
    });
    return db.prepare("SELECT * FROM suppliers WHERE id = ?").get(info.lastInsertRowid) as SupplierRow;
  });

  api.patch<{ Params: { id: string }; Body: Record<string, unknown> }>("/suppliers/:id", async (request, reply) => {
    const db = getDbOrThrow();
    const id = Number(request.params.id);
    const cur = db.prepare("SELECT * FROM suppliers WHERE id = ?").get(id) as SupplierRow | undefined;
    if (!cur) return reply.code(404).send({ error: "not_found" });
    const b = request.body || {};
    const name = b.name != null ? String(b.name).trim() : cur.name;
    const template_json =
      typeof b.template_json === "string" ? JSON.stringify(parseTemplateJson(b.template_json)) : cur.template_json;
    db.prepare(
      `UPDATE suppliers SET
        name = @name,
        whatsapp_phone = @whatsapp_phone,
        notes = @notes,
        order_weekday = @order_weekday,
        order_interval_days = @order_interval_days,
        last_sent_on = @last_sent_on,
        template_json = @template_json,
        updated_at = datetime('now')
       WHERE id = @id`
    ).run({
      id,
      name,
      whatsapp_phone: b.whatsapp_phone !== undefined ? (b.whatsapp_phone ? String(b.whatsapp_phone) : null) : cur.whatsapp_phone,
      notes: b.notes !== undefined ? (b.notes ? String(b.notes) : null) : cur.notes,
      order_weekday:
        b.order_weekday !== undefined ? (b.order_weekday === null ? null : Number(b.order_weekday)) : cur.order_weekday,
      order_interval_days:
        b.order_interval_days !== undefined
          ? b.order_interval_days === null
            ? null
            : Number(b.order_interval_days)
          : cur.order_interval_days,
      last_sent_on:
        b.last_sent_on !== undefined ? (b.last_sent_on === null ? null : String(b.last_sent_on)) : cur.last_sent_on,
      template_json,
    });
    return db.prepare("SELECT * FROM suppliers WHERE id = ?").get(id) as SupplierRow;
  });

  api.delete<{ Params: { id: string } }>("/suppliers/:id", async (request, reply) => {
    const db = getDbOrThrow();
    const id = Number(request.params.id);
    db.prepare("DELETE FROM suppliers WHERE id = ?").run(id);
    await reply.code(204).send();
  });

  api.post<{ Params: { id: string }; Body: Record<string, unknown> }>("/suppliers/:id/orders", async (request, reply) => {
    const db = getDbOrThrow();
    const supplierId = Number(request.params.id);
    const s = db.prepare("SELECT * FROM suppliers WHERE id = ?").get(supplierId) as SupplierRow | undefined;
    if (!s) return reply.code(404).send({ error: "not_found" });
    const lines = parseTemplateJson(s.template_json);
    const b = request.body || {};
    const overrideLines =
      typeof b.lines_json === "string" ? parseTemplateJson(b.lines_json) : lines;
    const notes = b.notes != null ? String(b.notes) : null;
    const draft = buildWhatsappDraft(s.name, overrideLines, notes || undefined);
    const stmt = db.prepare(
      `INSERT INTO orders (supplier_id, status, notes, lines_json, whatsapp_draft)
       VALUES (?, 'draft', ?, ?, ?)`
    );
    const info = stmt.run(supplierId, notes, JSON.stringify(overrideLines), draft);
    return db.prepare("SELECT * FROM orders WHERE id = ?").get(info.lastInsertRowid) as OrderRow;
  });

  api.get("/orders", async () => {
    const db = getDbOrThrow();
    return db
      .prepare(
        `SELECT o.*, s.name AS supplier_name FROM orders o
         JOIN suppliers s ON s.id = o.supplier_id
         ORDER BY o.created_at DESC LIMIT 200`
      )
      .all() as (OrderRow & { supplier_name: string })[];
  });

  api.patch<{ Params: { id: string }; Body: Record<string, unknown> }>("/orders/:id", async (request, reply) => {
    const db = getDbOrThrow();
    const id = Number(request.params.id);
    const cur = db.prepare("SELECT * FROM orders WHERE id = ?").get(id) as OrderRow | undefined;
    if (!cur) return reply.code(404).send({ error: "not_found" });
    const b = request.body || {};
    let status = cur.status;
    if (typeof b.status === "string" && ["draft", "sent", "received"].includes(b.status)) {
      status = b.status as OrderRow["status"];
    }
    let sent_at = cur.sent_at;
    let received_at = cur.received_at;
    if (status === "sent" && !sent_at) sent_at = new Date().toISOString();
    if (status === "received" && !received_at) received_at = new Date().toISOString();

    const lines_json =
      typeof b.lines_json === "string" ? JSON.stringify(parseTemplateJson(b.lines_json)) : cur.lines_json;
    const notes = b.notes !== undefined ? (b.notes === null ? null : String(b.notes)) : cur.notes;
    const s = db.prepare("SELECT * FROM suppliers WHERE id = ?").get(cur.supplier_id) as SupplierRow;
    const whatsapp_draft = buildWhatsappDraft(
      s.name,
      parseTemplateJson(lines_json),
      notes || undefined
    );

    db.prepare(
      `UPDATE orders SET status = ?, notes = ?, lines_json = ?, whatsapp_draft = ?, sent_at = ?, received_at = ?
       WHERE id = ?`
    ).run(status, notes, lines_json, whatsapp_draft, sent_at, received_at, id);

    if (status === "sent") {
      db.prepare("UPDATE suppliers SET last_sent_on = ?, updated_at = datetime('now') WHERE id = ?").run(
        todayIso(),
        cur.supplier_id
      );
    }

    return db.prepare("SELECT * FROM orders WHERE id = ?").get(id) as OrderRow;
  });

  api.get("/tasks", async () => {
    const db = getDbOrThrow();
    return db.prepare("SELECT * FROM tasks ORDER BY COALESCE(next_due_on, '9999-12-31'), title").all() as TaskRow[];
  });

  api.post<{ Body: Record<string, unknown> }>("/tasks", async (request, reply) => {
    const db = getDbOrThrow();
    const b = request.body || {};
    const title = String(b.title || "").trim();
    if (!title) return reply.code(400).send({ error: "title required" });
    const cadence = String(b.cadence || "weekly");
    if (!["once", "daily", "weekly", "monthly"].includes(cadence))
      return reply.code(400).send({ error: "invalid cadence" });
    const next_due_on = b.next_due_on != null ? String(b.next_due_on) : null;
    const stmt = db.prepare(
      `INSERT INTO tasks (title, cadence, next_due_on) VALUES (?, ?, ?)`
    );
    const info = stmt.run(title, cadence, next_due_on);
    return db.prepare("SELECT * FROM tasks WHERE id = ?").get(info.lastInsertRowid) as TaskRow;
  });

  api.patch<{ Params: { id: string }; Body: Record<string, unknown> }>("/tasks/:id", async (request, reply) => {
    const db = getDbOrThrow();
    const id = Number(request.params.id);
    const cur = db.prepare("SELECT * FROM tasks WHERE id = ?").get(id) as TaskRow | undefined;
    if (!cur) return reply.code(404).send({ error: "not_found" });
    const b = request.body || {};
    const title = b.title != null ? String(b.title).trim() : cur.title;
    const cadence = b.cadence != null ? String(b.cadence) : cur.cadence;
    if (!["once", "daily", "weekly", "monthly"].includes(cadence))
      return reply.code(400).send({ error: "invalid cadence" });
    let next_due_on = b.next_due_on !== undefined ? (b.next_due_on === null ? null : String(b.next_due_on)) : cur.next_due_on;
    let last_done_on = cur.last_done_on;
    if (b.mark_done) {
      const t = todayIso();
      last_done_on = t;
      if (cadence === "daily") next_due_on = addDaysIso(t, 1);
      else if (cadence === "weekly") next_due_on = addDaysIso(t, 7);
      else if (cadence === "monthly") next_due_on = addDaysIso(t, 30);
      else if (cadence === "once") next_due_on = null;
    }
    db.prepare(
      `UPDATE tasks SET title = ?, cadence = ?, next_due_on = ?, last_done_on = ?, updated_at = datetime('now') WHERE id = ?`
    ).run(title, cadence, next_due_on, last_done_on, id);
    return db.prepare("SELECT * FROM tasks WHERE id = ?").get(id) as TaskRow;
  });

  api.delete<{ Params: { id: string } }>("/tasks/:id", async (request, reply) => {
    const db = getDbOrThrow();
    db.prepare("DELETE FROM tasks WHERE id = ?").run(Number(request.params.id));
    await reply.code(204).send();
  });
}, { prefix: "/api" });

// Cron: sin API key de usuario; usa secreto dedicado
app.post("/api/internal/digest", async (request, reply) => {
  const secret = request.headers["x-cron-secret"];
  if (!CRON_SECRET || secret !== CRON_SECRET) {
    return reply.code(403).send({ error: "forbidden" });
  }
  const db = getDbOrThrow();
  const today = todayIso();
  const suppliers = db.prepare("SELECT * FROM suppliers").all() as SupplierRow[];
  const due = suppliers.filter((s) => supplierDueToday(s, today));
  const openOrders = db
    .prepare(`SELECT COUNT(1) AS c FROM orders WHERE status IN ('draft','sent')`)
    .get() as { c: number };
  const tasksDue = db
    .prepare(`SELECT COUNT(1) AS c FROM tasks WHERE next_due_on IS NOT NULL AND next_due_on <= ?`)
    .get(today) as { c: number };

  const lines: string[] = [];
  lines.push(`<b>Gerente — ${today}</b>`);
  if (due.length) {
    lines.push(`\n📦 <b>Pedidos (proveedor tocado hoy)</b>: ${due.map((d) => d.name).join(", ")}`);
  } else {
    lines.push(`\n📦 Pedidos: ningún proveedor con día fijo / intervalo vence hoy.`);
  }
  lines.push(`\n📋 Pedidos abiertos (borrador/enviado): <b>${openOrders.c}</b>`);
  lines.push(`\n✅ Tareas con fecha límite hoy o antes: <b>${tasksDue.c}</b>`);

  const text = lines.join("");
  try {
    await sendTelegram(text);
  } catch (e) {
    app.log.error(e);
    return reply.code(500).send({ error: "telegram_failed" });
  }
  return { ok: true, sent: Boolean(TELEGRAM_BOT_TOKEN && TELEGRAM_CHAT_ID) };
});

const publicDir = path.join(__dirname, "..", "public");
if (fs.existsSync(publicDir)) {
  await app.register(fastifyStatic, {
    root: publicDir,
    prefix: "/",
  });
  app.setNotFoundHandler((request, reply) => {
    if (request.url.startsWith("/api")) {
      return reply.code(404).send({ error: "not_found" });
    }
    return reply.sendFile("index.html");
  });
}

await app.listen({ port: PORT, host: "0.0.0.0" });
